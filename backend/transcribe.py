# backend/transcribe.py
import os
import shutil
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError
import logging
import tempfile
from openai import OpenAI
from datetime import datetime, timedelta # For SRT timestamp formatting

# Configure logging (ensure it's not duplicated)
if not logging.getLogger().hasHandlers() and not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Constants ---
MAX_CHUNK_DURATION_MS_CONFIG = 28 * 60 * 1000 # Default, can be overridden for testing
MAX_CHUNK_SIZE_BYTES = 24 * 1024 * 1024
# Directory to store final transcription files
RESULTS_DIR = "transcription_results"
os.makedirs(RESULTS_DIR, exist_ok=True) # Ensure it exists

# --- OpenAI Client Initialization ---
try:
    client = OpenAI()
    if not os.getenv("OPENAI_API_KEY"):
        logger.warning("OPENAI_API_KEY environment variable not set. OpenAI API calls will likely fail.")
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {e}")
    client = None

# --- Existing audio processing and OpenAI functions ---
def split_audio_into_chunks(audio_file_path: str, max_chunk_duration_ms: int = MAX_CHUNK_DURATION_MS_CONFIG) -> tuple[list[str], float | None]:
    """
    Splits an audio file into chunks.
    Returns a list of chunk paths and the total audio duration in seconds.
    Accepts max_chunk_duration_ms to allow override for testing.
    """
    try:
        logger.info(f"Loading audio file: {audio_file_path}")
        audio = AudioSegment.from_file(audio_file_path)
        total_duration_seconds = len(audio) / 1000.0
        logger.info(f"Audio file loaded. Duration: {total_duration_seconds:.2f}s")
    except CouldntDecodeError as e:
        logger.error(f"Could not decode audio file: {audio_file_path}. Error: {e}")
        if "ffmpeg" in str(e).lower(): logger.error("This might be due to ffmpeg not being installed/found.")
        return [], None
    except FileNotFoundError:
        logger.error(f"Audio file not found: {audio_file_path}")
        return [], None

    chunk_paths = []
    if total_duration_seconds == 0:
        logger.warning(f"Audio file {audio_file_path} is empty.")
        return [], 0.0

    temp_dir = tempfile.mkdtemp(prefix="audio_chunks_")
    logger.info(f"Created temporary directory for chunks: {temp_dir}")

    current_position_ms = 0
    chunk_count = 0
    while current_position_ms < len(audio):
        chunk_count += 1
        end_position_ms_duration = current_position_ms + max_chunk_duration_ms # Use parameter
        actual_end_position_ms = min(end_position_ms_duration, len(audio))
        chunk_segment = audio[current_position_ms:actual_end_position_ms]

        if len(chunk_segment) == 0:
            logger.warning("Empty chunk segment detected during splitting, skipping.")
            break

        current_frame_rate = chunk_segment.frame_rate
        if current_frame_rate is None or current_frame_rate == 0:
            logger.info(f"Chunk {chunk_count} has invalid frame_rate ({current_frame_rate}). Setting to 44100Hz.")
            chunk_segment = chunk_segment.set_frame_rate(44100)

        chunk_file_name = f"chunk_{chunk_count}.mp3"
        chunk_file_path = os.path.join(temp_dir, chunk_file_name)
        try:
            logger.info(f"Exporting chunk {chunk_count}: {current_position_ms / 1000:.2f}s to {actual_end_position_ms / 1000:.2f}s")
            chunk_segment.export(chunk_file_path, format="mp3")

            file_size_bytes = os.path.getsize(chunk_file_path)
            logger.info(f"Chunk {chunk_count} exported: {chunk_file_path}, Size: {file_size_bytes / (1024*1024):.2f}MB")
            if file_size_bytes == 0:
                logger.warning(f"Chunk {chunk_count} is 0 bytes. This may cause API issues.")
            if file_size_bytes > MAX_CHUNK_SIZE_BYTES:
                 logger.warning(f"Chunk {chunk_count} ({file_size_bytes / (1024*1024):.2f}MB) exceeds limit.")
            chunk_paths.append(chunk_file_path)
        except Exception as e:
            logger.error(f"Error exporting chunk {chunk_count} ({chunk_file_path}): {type(e).__name__} - {e}")
            if os.path.exists(chunk_file_path):
                try: os.remove(chunk_file_path)
                except Exception as rm_e: logger.error(f"Failed to remove temp chunk {chunk_file_path}: {rm_e}")
            continue
        current_position_ms = actual_end_position_ms

    if not chunk_paths and os.path.exists(temp_dir) and os.path.isdir(temp_dir):
        try:
            shutil.rmtree(temp_dir)
            logger.info(f"Cleaned up empty or residual temp directory: {temp_dir}")
        except Exception as rmdir_e:
             logger.error(f"Error cleaning up temp dir {temp_dir}: {rmdir_e}")

    if chunk_paths:
        logger.info(f"Successfully split audio into {len(chunk_paths)} chunks in {temp_dir}")
    return chunk_paths, total_duration_seconds


def transcribe_chunk_openai(chunk_file_path: str, language: str = None) -> dict | None:
    if not client:
        logger.error("OpenAI client not initialized for transcribe_chunk_openai.")
        return None
    if not os.path.exists(chunk_file_path):
        logger.error(f"Chunk file not found for transcription: {chunk_file_path}")
        return None
    if os.path.getsize(chunk_file_path) == 0:
        logger.error(f"Chunk file is 0 bytes, cannot be transcribed: {chunk_file_path}")
        return None

    logger.info(f"Transcribing chunk: {chunk_file_path}...")
    try:
        with open(chunk_file_path, "rb") as audio_file:
            params = {"model": "whisper-1", "file": audio_file, "response_format": "verbose_json", "timestamp_granularities": ["segment"]}
            if language: params["language"] = language
            transcription = client.audio.transcriptions.create(**params)
        logger.info(f"Successfully transcribed chunk: {chunk_file_path}")
        return transcription.model_dump() if hasattr(transcription, 'model_dump') else vars(transcription)
    except Exception as e:
        logger.error(f"Error during OpenAI API call for chunk {chunk_file_path}: {type(e).__name__} - {e}")
        return None

def cleanup_chunks(chunk_paths: list[str]):
    if not chunk_paths:
        logger.info("No chunk paths provided for cleanup.")
        return
    temp_dir = os.path.dirname(chunk_paths[0])
    if os.path.exists(temp_dir) and os.path.isdir(temp_dir):
        try:
            shutil.rmtree(temp_dir)
            logger.info(f"Successfully removed temporary chunk directory: {temp_dir}")
        except OSError as e:
            logger.error(f"Error deleting temporary chunk directory {temp_dir}: {e}")
    else:
        logger.warning(f"Temporary directory {temp_dir} not found or is not a dir. Skipping cleanup.")


# --- New Formatting and Re-assembly Functions ---

def format_timestamp_srt(seconds: float) -> str:
    """Converts seconds to SRT timestamp format HH:MM:SS,mmm."""
    delta = timedelta(seconds=seconds)
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds_val = divmod(remainder, 60)
    milliseconds = delta.microseconds // 1000
    return f"{hours:02}:{minutes:02}:{seconds_val:02},{milliseconds:03}"

def format_timestamp_txt(seconds: float) -> str:
    """Converts seconds to [HH:MM:SS] format for TXT file."""
    delta = timedelta(seconds=seconds)
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds_val = divmod(remainder, 60)
    return f"[{hours:02}:{minutes:02}:{seconds_val:02}]"

def generate_srt_content(all_segments: list[dict]) -> str:
    """Generates SRT content from a list of segments with absolute timestamps."""
    srt_content = []
    for i, segment in enumerate(all_segments):
        start_time_str = format_timestamp_srt(segment['start'])
        end_time_str = format_timestamp_srt(segment['end'])
        text = segment.get('text', '').strip()
        if text:
            srt_content.append(f"{i + 1}")
            srt_content.append(f"{start_time_str} --> {end_time_str}")
            srt_content.append(text)
            srt_content.append("")
    return "\n".join(srt_content)

def generate_txt_content(all_segments: list[dict]) -> str:
    """Generates TXT content from a list of segments with absolute timestamps."""
    txt_content = []
    for segment in all_segments:
        start_time_str = format_timestamp_txt(segment['start'])
        text = segment.get('text', '').strip()
        if text:
            txt_content.append(f"{start_time_str} {text}")
    return "\n".join(txt_content)

def save_transcription_file(content: str, base_filename: str, extension: str) -> str | None:
    filepath = ""
    try:
        os.makedirs(RESULTS_DIR, exist_ok=True)
        filepath = os.path.join(RESULTS_DIR, f"{base_filename}.{extension}")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Transcription saved to {filepath}")
        return filepath
    except IOError as e:
        logger.error(f"Error saving transcription to {filepath}: {e}")
        return None

def process_audio_file(
    original_audio_path: str,
    base_output_filename: str,
    language: str = None,
    max_chunk_duration_ms_override: int = MAX_CHUNK_DURATION_MS_CONFIG
) -> tuple[str | None, str | None, float | None, str | None]:
    logger.info(f"Starting full processing for: {original_audio_path} with base filename: {base_output_filename}")

    chunk_file_paths, original_duration_s = split_audio_into_chunks(original_audio_path, max_chunk_duration_ms=max_chunk_duration_ms_override)
    if original_duration_s is None:
        err_msg = f"Failed to load or split audio {original_audio_path}. Cannot determine duration."
        logger.error(err_msg)
        cleanup_chunks(chunk_file_paths)
        return None, None, None, err_msg
    if not chunk_file_paths:
        err_msg = f"Failed to split audio into chunks for {original_audio_path}. Duration was {original_duration_s:.2f}s."
        logger.error(err_msg)
        return None, None, original_duration_s, err_msg

    all_segments_absolute = []
    current_time_offset_s = 0.0

    for i, chunk_path in enumerate(chunk_file_paths):
        logger.info(f"Processing chunk {i+1}/{len(chunk_file_paths)}: {chunk_path}")

        chunk_duration_s = 0.0
        try:
            chunk_audio = AudioSegment.from_file(chunk_path)
            chunk_duration_s = len(chunk_audio) / 1000.0
            if chunk_duration_s == 0:
                 logger.warning(f"Chunk {chunk_path} has zero duration after loading. Skipping transcription.")
                 continue
        except Exception as e:
            logger.error(f"Could not load chunk {chunk_path} to get its duration: {e}. Skipping this chunk.")
            continue

        transcription_result = transcribe_chunk_openai(chunk_path, language=language)
        if not transcription_result or 'segments' not in transcription_result:
            logger.warning(f"Transcription failed or no segments for chunk {chunk_path}. Skipping.")
            current_time_offset_s += chunk_duration_s
            continue

        segments_from_chunk = transcription_result['segments']
        for segment in segments_from_chunk:
            segment_start_abs = segment['start'] + current_time_offset_s
            segment_end_abs = segment['end'] + current_time_offset_s
            if segment_start_abs >= original_duration_s + 0.1: # Allow small tolerance for end segment
                logger.warning(f"Segment start {segment_start_abs:.2f}s exceeds total duration {original_duration_s:.2f}s. Skipping.")
                continue
            segment['start'] = segment_start_abs
            segment['end'] = min(segment_end_abs, original_duration_s)
            all_segments_absolute.append(segment)

        current_time_offset_s += chunk_duration_s

    cleanup_chunks(chunk_file_paths)

    if not all_segments_absolute:
        err_msg = f"No segments transcribed for {original_audio_path} after processing all chunks."
        logger.error(err_msg)
        return None, None, original_duration_s, err_msg

    txt_content = generate_txt_content(all_segments_absolute)
    srt_content = generate_srt_content(all_segments_absolute)

    txt_filepath = save_transcription_file(txt_content, base_output_filename, "txt")
    srt_filepath = save_transcription_file(srt_content, base_output_filename, "srt")

    final_error_message = None
    if not txt_filepath or not srt_filepath:
        final_error_message = f"Failed to save one or both transcription files for {base_output_filename}."

    logger.info(f"Finished processing for {base_output_filename} (TXT: {txt_filepath}, SRT: {srt_filepath})")
    return txt_filepath, srt_filepath, original_duration_s, final_error_message


if __name__ == '__main__':
    if not logging.getLogger().hasHandlers() and not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    logger.info("Starting test script for transcribe.py - reassembly and export...")

    # This test requires OpenAI API key for actual transcription.
    # If key is not present, it will use mocked transcription data.

    project_root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if not project_root_dir or project_root_dir == "/": project_root_dir = "."

    test_audio_duration_ms = 30 * 1000
    dummy_file_name = "dummy_audio_reassembly_test.mp3"
    dummy_file_path_reassembly_test = os.path.join(project_root_dir, dummy_file_name)

    test_max_chunk_duration_ms = 10 * 1000 # 10 second chunks for testing

    # --- Mocked transcribe_chunk_openai function setup ---
    # We need to store the original function to restore it later
    original_transcribe_chunk_openai_function = transcribe_chunk_openai
    mock_call_count = 0

    def mocked_transcribe_chunk_openai_for_test(chunk_file_path: str, language: str = None):
        global mock_call_count # Use global to modify the script-level variable
        mock_call_count += 1
        logger.info(f"MOCKED transcribe_chunk_openai called for: {chunk_file_path} (Call #{mock_call_count})")

        # Simulate segments based on which chunk is being processed
        # These timestamps are relative to the start of the chunk itself.
        if mock_call_count == 1: # Mock for chunk 1 (0-10s of original audio)
            return {
                "text": "Hello world. This is a test.",
                "segments": [
                    {"id": 0, "seek": 0, "start": 0.0, "end": 2.0, "text": "Hello world."},
                    {"id": 1, "seek": 0, "start": 3.0, "end": 5.0, "text": "This is a test."}
                ],
                "language": language or "en"
            }
        elif mock_call_count == 2: # Mock for chunk 2 (10-20s of original audio)
            return {
                "text": "Second chunk here.",
                "segments": [
                    {"id": 0, "seek": 0, "start": 1.0, "end": 3.0, "text": "Second chunk here."} # e.g., 11s-13s absolute
                ],
                "language": language or "en"
            }
        elif mock_call_count == 3: # Mock for chunk 3 (20-30s of original audio)
            return {
                "text": "Final segment.",
                "segments": [
                    {"id": 0, "seek": 0, "start": 0.5, "end": 2.5, "text": "Final segment."} # e.g., 20.5s-22.5s absolute
                ],
                "language": language or "en"
            }
        else: # Fallback for unexpected calls
            return {"text": "", "segments": [], "language": language or "en"}

    # Decide whether to use mock or real API based on key availability
    use_mock_transcription = True # Default to using the mock
    if client and os.getenv("OPENAI_API_KEY"):
        logger.info("OPENAI_API_KEY is set. Attempting to use REAL OpenAI API calls for testing.")
        use_mock_transcription = False
    else:
        logger.info("OPENAI_API_KEY is NOT set or OpenAI client failed to initialize. Using MOCKED transcription data for testing.")
        # Monkey patch the global transcribe_chunk_openai with our mock version
        # Need to assign to the global name 'transcribe_chunk_openai' in this module's scope
        globals()['transcribe_chunk_openai'] = mocked_transcribe_chunk_openai_for_test


    # --- Test Execution ---
    try:
        # Import Sine generator
        from pydub.generators import Sine

        if not os.path.exists(dummy_file_path_reassembly_test):
            try:
                logger.info(f"Creating dummy MP3: {dummy_file_path_reassembly_test}")
                # Create a 30s audio with distinct features in each 10s segment for better mock correlation
                audio_parts = [
                    (Sine(440).to_audio_segment(duration=200, volume=-20)).fade_in(50).fade_out(50), # Beep 1
                    AudioSegment.silent(duration=10000 - 200, frame_rate=44100),
                    (Sine(660).to_audio_segment(duration=300, volume=-20)).fade_in(50).fade_out(50), # Beep 2
                    AudioSegment.silent(duration=10000 - 300, frame_rate=44100),
                    (Sine(880).to_audio_segment(duration=100, volume=-20)).fade_in(50).fade_out(50), # Beep 3
                    AudioSegment.silent(duration=10000 - 100, frame_rate=44100),
                ]
                combined_audio = sum(audio_parts, AudioSegment.empty())
                combined_audio = combined_audio[:test_audio_duration_ms]
                combined_audio.export(dummy_file_path_reassembly_test, format="mp3", bitrate="32k")
                logger.info(f"Dummy MP3 created: {dummy_file_path_reassembly_test}")
            except Exception as e:
                logger.error(f"Error creating dummy MP3: {type(e).__name__} - {e}. Ensure ffmpeg is installed.")
                exit(1)
        else:
            logger.info(f"Using existing dummy MP3: {dummy_file_path_reassembly_test}")

        base_filename = f"test_reassembly_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if use_mock_transcription:
            base_filename = "MOCK_" + base_filename

        txt_path, srt_path, duration, error = process_audio_file(
            dummy_file_path_reassembly_test,
            base_filename,
            language="en",
            max_chunk_duration_ms_override=test_max_chunk_duration_ms # 10s chunks
        )

        if error:
            logger.error(f"Processing failed: {error}")
        else:
            logger.info(f"Processing successful!")
            if txt_path: logger.info(f"TXT file: {txt_path}")
            if srt_path: logger.info(f"SRT file: {srt_path}")
            logger.info(f"Original duration: {duration}s")

            # Verify content if using mock data
            if use_mock_transcription:
                expected_txt_content = "[00:00:00] Hello world.\n[00:00:03] This is a test.\n[00:00:11] Second chunk here.\n[00:00:20] Final segment."
                expected_srt_content_parts = [
                    "1", "00:00:00,000 --> 00:00:02,000", "Hello world.",
                    "2", "00:00:03,000 --> 00:00:05,000", "This is a test.",
                    "3", "00:00:11,000 --> 00:00:13,000", "Second chunk here.", # 1s (relative) + 10s (offset) = 11s
                    "4", "00:00:20,500 --> 00:00:22,500", "Final segment."  # 0.5s (relative) + 20s (offset) = 20.5s
                ]

                if txt_path and os.path.exists(txt_path):
                    with open(txt_path, 'r', encoding='utf-8') as f:
                        actual_txt_content = f.read()
                        logger.info(f"\n--- Content of {txt_path} ---\n{actual_txt_content}")
                        assert actual_txt_content.strip() == expected_txt_content.strip(), "Mocked TXT content mismatch!"
                        logger.info("Mocked TXT content matches expected content.")
                else:
                    logger.error(f"Mock TXT file not created at {txt_path}")

                if srt_path and os.path.exists(srt_path):
                    with open(srt_path, 'r', encoding='utf-8') as f:
                        actual_srt_content = f.read()
                        logger.info(f"\n--- Content of {srt_path} ---\n{actual_srt_content}")
                        # Simple check for parts, more robust would be parsing
                        for part in expected_srt_content_parts:
                            assert part in actual_srt_content, f"Missing part '{part}' in SRT output."
                        logger.info("Mocked SRT content seems to contain all expected parts.")
                else:
                    logger.error(f"Mock SRT file not created at {srt_path}")
            else: # If real API was used, just print path
                if txt_path and os.path.exists(txt_path):
                    with open(txt_path, 'r', encoding='utf-8') as f: logger.info(f"\n--- Content of {txt_path} ---\n{f.read()}")
                if srt_path and os.path.exists(srt_path):
                    with open(srt_path, 'r', encoding='utf-8') as f: logger.info(f"\n--- Content of {srt_path} ---\n{f.read()}")

    finally:
        # Restore original transcribe_chunk_openai function if it was monkey-patched
        if use_mock_transcription:
            globals()['transcribe_chunk_openai'] = original_transcribe_chunk_openai_function
            logger.info("Restored original transcribe_chunk_openai function.")

        # Optional: Clean up dummy audio file created for testing
        # if os.path.exists(dummy_file_path_reassembly_test):
        #     try:
        #         os.remove(dummy_file_path_reassembly_test)
        #         logger.info(f"Cleaned up dummy audio file: {dummy_file_path_reassembly_test}")
        #     except OSError as e:
        #         logger.error(f"Error cleaning up dummy audio file {dummy_file_path_reassembly_test}: {e}")
        logger.info(f"Test files (if created) are in '{RESULTS_DIR}'. Dummy audio '{dummy_file_path_reassembly_test}' may still exist for inspection.")

    logger.info("Test script for reassembly and export finished.")
