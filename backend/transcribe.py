# backend/transcribe.py
import os
import shutil
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError
from pydub.generators import Sine # Ensure Sine is imported at the top level
import logging
import tempfile
import math
from openai import OpenAI
from datetime import datetime, timedelta # For SRT timestamp formatting
from typing import Optional, List # Ensure List is imported for type hints

# Configure logging
if not logging.getLogger(__name__).hasHandlers() and not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Constants ---
MAX_CHUNK_DURATION_MS_CONFIG = 28 * 60 * 1000
MAX_CHUNK_SIZE_BYTES = 24 * 1024 * 1024
RESULTS_DIR = "transcription_results"
os.makedirs(RESULTS_DIR, exist_ok=True)

# --- OpenAI Client Initialization ---
try:
    client = OpenAI()
    OPENAI_API_KEY_AVAILABLE = bool(os.getenv("OPENAI_API_KEY"))
    if not OPENAI_API_KEY_AVAILABLE:
        logger.warning("OPENAI_API_KEY environment variable not set. Mocking may be used if 'is_mock_call=True' is passed to transcribe_chunk_openai.")
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {e}")
    client = None
    OPENAI_API_KEY_AVAILABLE = False

# Module-level counter for mocked calls, primarily for the __main__ test scenario
_mock_call_counter = 0

def split_audio_into_chunks(audio_file_path: str, max_chunk_duration_ms: int = MAX_CHUNK_DURATION_MS_CONFIG) -> tuple[List[str], float | None]:
    try:
        logger.info(f"Loading audio file: {audio_file_path}")
        audio = AudioSegment.from_file(audio_file_path)
        total_duration_seconds = len(audio) / 1000.0
        logger.info(f"Audio file loaded successfully. Duration: {total_duration_seconds:.2f}s")
    except CouldntDecodeError as e:
        logger.error(f"Could not decode audio file: {audio_file_path}. Error: {e}")
        if "ffmpeg" in str(e).lower() or "could not read metadata" in str(e).lower() :
            logger.error("This error might be due to ffmpeg not being installed or not found in PATH.")
        return [], None
    except FileNotFoundError:
        logger.error(f"Audio file not found: {audio_file_path}")
        return [], None
    except Exception as e:
        logger.error(f"Error loading audio file {audio_file_path}: {type(e).__name__} - {e}")
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
        end_position_ms_duration = current_position_ms + max_chunk_duration_ms
        actual_end_position_ms = min(end_position_ms_duration, len(audio))
        chunk_segment = audio[current_position_ms:actual_end_position_ms]

        if len(chunk_segment) == 0:
            logger.warning("Empty chunk segment generated during splitting, skipping.")
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
                logger.warning(f"Chunk {chunk_count} is 0 bytes ({chunk_file_path}). This may cause API issues.")
            if file_size_bytes > MAX_CHUNK_SIZE_BYTES:
                 logger.warning(f"Chunk {chunk_count} ({file_size_bytes / (1024*1024):.2f}MB) exceeds MAX_CHUNK_SIZE_BYTES ({MAX_CHUNK_SIZE_BYTES / (1024*1024):.2f}MB).")
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

def _get_mock_transcription_data(call_count: int, language: Optional[str] = "en") -> dict:
    """Provides mock transcription data based on call count."""
    logger.info(f"Generating mock data for call_count: {call_count}")
    if call_count == 1:
        return {
            "text": "Hello world. This is a test.",
            "segments": [
                {"id": 0, "seek": 0, "start": 0.0, "end": 2.0, "text": " Hello world."},
                {"id": 1, "seek": 0, "start": 3.0, "end": 5.0, "text": " This is a test. "}
            ], "language": language or "en"
        }
    elif call_count == 2:
        return {
            "text": "Mocked: Second chunk here.",
            "segments": [{"id": 0, "seek": 0, "start": 1.0, "end": 3.0, "text": " Second chunk here. "}],
            "language": language or "en"
        }
    elif call_count == 3:
        return {
            "text": "Mocked: Final segment.",
            "segments": [{"id": 0, "seek": 0, "start": 0.5, "end": 2.5, "text": " Final segment. "}],
            "language": language or "en"
        }
    return {"text": "Mocked: Additional chunk.", "segments": [{"id":0, "seek":0, "start":0.0, "end":1.0, "text":"More data."}], "language": language or "en"}

def transcribe_chunk_openai(chunk_file_path: str, language: str = None, is_mock_call: bool = False) -> dict | None:
    """
    Transcribes a single audio chunk. Uses mock data if is_mock_call is True.
    If is_mock_call is False and OPENAI_API_KEY_AVAILABLE is False, it returns None.
    """
    global _mock_call_counter

    if is_mock_call:
        _mock_call_counter += 1
        logger.info(f"MOCKED (is_mock_call=True) transcribe_chunk_openai called for: {chunk_file_path} (Call #{_mock_call_counter})")
        return _get_mock_transcription_data(_mock_call_counter, language)

    # Actual OpenAI client logic
    if not client:
        logger.error("OpenAI client is not initialized. Cannot transcribe.")
        return None
    if not OPENAI_API_KEY_AVAILABLE:
        logger.error("OpenAI API key not available for real transcription call. Ensure OPENAI_API_KEY is set for live mode.")
        return None

    if not os.path.exists(chunk_file_path):
        logger.error(f"Chunk file not found for transcription: {chunk_file_path}")
        return None
    if os.path.getsize(chunk_file_path) == 0:
        logger.error(f"Chunk file is 0 bytes, cannot be transcribed: {chunk_file_path}")
        return None

    logger.info(f"Transcribing chunk via REAL API: {chunk_file_path}...")
    try:
        with open(chunk_file_path, "rb") as audio_file:
            transcript_params = {
                "model": "whisper-1",
                "file": audio_file,
                "response_format": "verbose_json",
                "timestamp_granularities": ["segment"]
            }
            if language:
                transcript_params["language"] = language

            transcription_object = client.audio.transcriptions.create(**transcript_params)

        logger.info(f"Successfully transcribed chunk via REAL API: {chunk_file_path}")
        return transcription_object.model_dump()

    except Exception as e:
        logger.error(f"Error during OpenAI API call for chunk {chunk_file_path}: {type(e).__name__} - {e}")
        return None

def cleanup_chunks(chunk_paths: list[str]):
    if not chunk_paths:
        logger.info("No chunk paths provided for cleanup.")
        return
    if not chunk_paths[0] or not isinstance(chunk_paths[0], str):
        logger.warning(f"First chunk path is invalid or not a string: {chunk_paths[0]}. Cannot determine directory for cleanup.")
        return

    temp_dir = os.path.dirname(chunk_paths[0])
    if os.path.exists(temp_dir) and os.path.isdir(temp_dir) and temp_dir.startswith(tempfile.gettempdir()): # Safety check
        try:
            shutil.rmtree(temp_dir)
            logger.info(f"Successfully removed temporary chunk directory: {temp_dir}")
        except OSError as e:
            logger.error(f"Error deleting temporary chunk directory {temp_dir}: {e}")
    # else: # This log can be noisy if temp_dir was already cleaned or never created for empty file
    #     logger.warning(f"Temporary directory {temp_dir} not found, not a directory, or not in temp. Skipping cleanup.")


# --- New Formatting and Re-assembly Functions ---

def format_timestamp_srt(seconds: float) -> str:
    """Converts seconds to SRT timestamp format HH:MM:SS,mmm."""
    if not isinstance(seconds, (int, float)) or seconds < 0:
        logger.warning(f"Invalid seconds value for SRT timestamp: {seconds}. Returning zero timestamp.")
        seconds = 0
    delta = timedelta(seconds=seconds)
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds_val = divmod(remainder, 60)
    milliseconds = int(round(delta.microseconds / 1000))
    return f"{hours:02}:{minutes:02}:{seconds_val:02},{milliseconds:03}"

def format_timestamp_txt(seconds: float) -> str:
    """Converts seconds to [HH:MM:SS] format for TXT file."""
    if not isinstance(seconds, (int, float)) or seconds < 0:
        logger.warning(f"Invalid seconds value for TXT timestamp: {seconds}. Returning zero timestamp.")
        seconds = 0
    delta = timedelta(seconds=seconds)
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds_val = divmod(remainder, 60)
    return f"[{hours:02}:{minutes:02}:{seconds_val:02}]"

def generate_srt_content(all_segments: list[dict]) -> str:
    """Generates SRT content from a list of segments with absolute timestamps."""
    srt_content_list = []
    for i, segment in enumerate(all_segments):
        start_time = segment.get('start', 0.0)
        end_time = segment.get('end', 0.0)
        text = segment.get('text', '').strip()

        if not isinstance(start_time, (int, float)) or start_time < 0: start_time = 0.0
        if not isinstance(end_time, (int, float)) or end_time < 0: end_time = start_time
        if end_time < start_time: end_time = start_time

        start_time_str = format_timestamp_srt(start_time)
        end_time_str = format_timestamp_srt(end_time)

        if text:
            srt_content_list.append(str(i + 1))
            srt_content_list.append(f"{start_time_str} --> {end_time_str}")
            srt_content_list.append(text)
            srt_content_list.append("")
    return "\n".join(srt_content_list)

def generate_txt_content(all_segments: list[dict]) -> str:
    """Generates TXT content from a list of segments with absolute timestamps."""
    txt_content_list = []
    for segment in all_segments:
        start_time = segment.get('start', 0.0)
        text = segment.get('text', '').strip()
        if not isinstance(start_time, (int, float)) or start_time < 0: start_time = 0.0
        start_time_str = format_timestamp_txt(start_time)
        if text:
            txt_content_list.append(f"{start_time_str} {text}")
    return "\n".join(txt_content_list)

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
    language: Optional[str] = None,
    max_chunk_duration_ms_override: int = MAX_CHUNK_DURATION_MS_CONFIG,
    is_mock_call: bool = False  # Changed from use_mock_logic_if_no_key
) -> tuple[str | None, str | None, float | None, str | None]:
    global _mock_call_counter # This refers to the module-level counter

    logger.info(f"Starting full processing for: {original_audio_path} with base filename: {base_output_filename}. Mock call: {is_mock_call}")

    if is_mock_call: # If this entire process_audio_file call is a mock run
        _mock_call_counter = 0   # Reset the counter for this mock run

    chunk_file_paths, original_duration_s = split_audio_into_chunks(original_audio_path, max_chunk_duration_ms=max_chunk_duration_ms_override)

    if original_duration_s is None:
        err_msg = f"Failed to load or split audio {original_audio_path}. Cannot determine duration."
        logger.error(err_msg)
        if chunk_file_paths:
             cleanup_chunks(chunk_file_paths)
        return None, None, None, err_msg

    if not chunk_file_paths:
        err_msg = f"Audio splitting resulted in no chunks for {original_audio_path}. Duration was {original_duration_s:.2f}s."
        if original_duration_s == 0:
             err_msg = f"Audio file {original_audio_path} is empty or too short to produce chunks."
        logger.warning(err_msg)
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
                 logger.warning(f"Chunk {chunk_path} has zero duration after loading. Advancing offset by expected max chunk duration.")
                 current_time_offset_s += max_chunk_duration_ms_override / 1000.0
                 continue
        except Exception as e:
            logger.error(f"Could not load chunk {chunk_path} to get its duration: {e}. Advancing offset by expected max chunk duration.")
            estimated_chunk_duration = max_chunk_duration_ms_override / 1000.0
            if i == len(chunk_file_paths) -1:
                estimated_chunk_duration = original_duration_s - current_time_offset_s
            current_time_offset_s += max(0, estimated_chunk_duration)
            continue

        # Pass the is_mock_call flag. If OPENAI_API_KEY_AVAILABLE is False, transcribe_chunk_openai will use its mock logic.
        # If OPENAI_API_KEY_AVAILABLE is True, it will attempt a real API call.
        transcription_result = transcribe_chunk_openai(chunk_path, language=language, is_mock_call=is_mock_call)

        if not transcription_result or 'segments' not in transcription_result or not transcription_result['segments']:
            logger.warning(f"Transcription failed or no segments for chunk {chunk_path}. Skipping.")
            current_time_offset_s += chunk_duration_s
            continue

        segments_from_chunk = transcription_result['segments']
        for segment in segments_from_chunk:
            segment_start_abs = segment['start'] + current_time_offset_s
            segment_end_abs = segment['end'] + current_time_offset_s

            if segment_start_abs >= original_duration_s + 1.0:
                logger.warning(f"Segment start {segment_start_abs:.2f}s significantly exceeds total duration {original_duration_s:.2f}s. Skipping segment: {segment.get('text')}")
                continue

            segment['start'] = segment_start_abs
            segment['end'] = min(segment_end_abs, original_duration_s)
            if segment['end'] < segment['start']:
                segment['end'] = segment['start']

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

    logger.info(f"Successfully processed and saved transcriptions for {base_output_filename} (TXT: {txt_filepath}, SRT: {srt_filepath})")
    return txt_filepath, srt_filepath, original_duration_s, final_error_message


if __name__ == '__main__':
    if not logging.getLogger().hasHandlers() and not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    logger.info("Starting test script for transcribe.py - reassembly and export...")

    project_root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if not project_root_dir or project_root_dir == "/": project_root_dir = os.getcwd()

    test_audio_duration_ms = 30 * 1000
    dummy_file_name = "dummy_audio_reassembly_test.mp3"
    dummy_file_path_reassembly_test = os.path.join(project_root_dir, dummy_file_name)

    test_max_chunk_duration_ms = 10 * 1000

    # This global counter is used by the mocked function when is_mock_call=True
    # No need to declare 'global _mock_call_counter' here for assignment,
    # as we are at the module's top level within the if __name__ == '__main__' block.
    _mock_call_counter = 0 # Reset for this specific test run

    # Determine if the test should use mock based on API key availability
    # This flag is passed to process_audio_file to control its behavior.
    should_run_mock_main_test = not OPENAI_API_KEY_AVAILABLE

    if OPENAI_API_KEY_AVAILABLE:
        logger.info("OPENAI_API_KEY is set. __main__ test will attempt REAL OpenAI API calls.")
    else:
        logger.info("OPENAI_API_KEY is NOT set or client failed. __main__ test will use MOCKED transcription data via is_mock_call=True.")

    try:
        from pydub.generators import Sine

        if not os.path.exists(dummy_file_path_reassembly_test):
            try:
                logger.info(f"Creating dummy MP3: {dummy_file_path_reassembly_test}")
                audio_parts = [
                    (Sine(440).to_audio_segment(duration=200, volume=-20)).fade_in(50).fade_out(50),
                    AudioSegment.silent(duration=10000 - 200, frame_rate=44100),
                    (Sine(660).to_audio_segment(duration=300, volume=-20)).fade_in(50).fade_out(50),
                    AudioSegment.silent(duration=10000 - 300, frame_rate=44100),
                    (Sine(880).to_audio_segment(duration=100, volume=-20)).fade_in(50).fade_out(50),
                    AudioSegment.silent(duration=10000 - 100, frame_rate=44100),
                ]
                combined_audio = sum(audio_parts, AudioSegment.empty())
                combined_audio = combined_audio[:test_audio_duration_ms]
                combined_audio.export(dummy_file_path_reassembly_test, format="mp3", bitrate="32k")
                logger.info(f"Dummy MP3 created: {dummy_file_path_reassembly_test}")
            except Exception as e:
                logger.error(f"Error creating dummy MP3: {type(e).__name__} - {e}. Ensure ffmpeg is installed.")
                # Don't exit, let process_audio_file handle missing file if it occurs
        else:
            logger.info(f"Using existing dummy MP3: {dummy_file_path_reassembly_test}")

        base_filename_for_main_test = f"test_direct_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if should_run_mock_main_test: # If API key is not available, mock will be used
             base_filename_for_main_test = "MOCK_" + base_filename_for_main_test

        _mock_call_counter = 0 # Explicitly reset for the test run from __main__

        txt_path, srt_path, duration, error = process_audio_file(
            dummy_file_path_reassembly_test,
            base_filename_for_main_test,
            language="en",
            max_chunk_duration_ms_override=test_max_chunk_duration_ms,
            is_mock_call=should_run_mock_main_test # Pass the flag to control mocking
        )

        if error:
            logger.error(f"__main__ processing failed: {error}")
        else:
            logger.info(f"__main__ processing successful!")
            if txt_path: logger.info(f"TXT file: {txt_path}")
            if srt_path: logger.info(f"SRT file: {srt_path}")
            logger.info(f"Original duration: {duration}s")

            if should_run_mock_main_test:
                expected_txt_content = "[00:00:00] Hello world.\n[00:00:03] This is a test.\n[00:00:11] Second chunk here.\n[00:00:20] Final segment."
                expected_srt_content_parts = [
                    "1", "00:00:00,000 --> 00:00:02,000", "Hello world.",
                    "2", "00:00:03,000 --> 00:00:05,000", "This is a test.",
                    "3", "00:00:11,000 --> 00:00:13,000", "Second chunk here.",
                    "4", "00:00:20,500 --> 00:00:22,500", "Final segment."
                ]

                if txt_path and os.path.exists(txt_path):
                    with open(txt_path, 'r', encoding='utf-8') as f:
                        actual_txt_content = f.read()
                        logger.info(f"\n--- Content of {txt_path} ---\n{actual_txt_content}")
                        assert actual_txt_content.strip() == expected_txt_content.strip(), f"Mocked TXT content mismatch. Expected:\n{expected_txt_content}\nGot:\n{actual_txt_content.strip()}"
                        logger.info("Mocked TXT content matches expected content.")
                else:
                    logger.error(f"Mock TXT file not created at {txt_path}")
                    assert False, f"Mock TXT file not created at {txt_path}"

                if srt_path and os.path.exists(srt_path):
                    with open(srt_path, 'r', encoding='utf-8') as f:
                        actual_srt_content = f.read()
                        logger.info(f"\n--- Content of {srt_path} ---\n{actual_srt_content}")
                        for part in expected_srt_content_parts:
                            assert part in actual_srt_content, f"Missing part '{part}' in SRT output."
                        logger.info("Mocked SRT content seems to contain all expected parts.")
                else:
                    logger.error(f"Mock SRT file not created at {srt_path}")
                    assert False, f"Mock SRT file not created at {srt_path}"
            else:
                logger.info("Real API was used for testing __main__ block. Manual verification of results needed.")
                if txt_path and os.path.exists(txt_path):
                    with open(txt_path, 'r', encoding='utf-8') as f: logger.info(f"\n--- Content of {txt_path} ---\n{f.read()}")
                if srt_path and os.path.exists(srt_path):
                    with open(srt_path, 'r', encoding='utf-8') as f: logger.info(f"\n--- Content of {srt_path} ---\n{f.read()}")

    except Exception as e_main_test:
        logger.error(f"Exception in __main__ test block: {type(e_main_test).__name__} - {e_main_test}", exc_info=True)
    finally:
        # Restore original function only if it was changed (i.e., if mock was used)
        if 'mocked_transcribe_chunk_openai_for_test' in globals() and \
           globals()['transcribe_chunk_openai'] == mocked_transcribe_chunk_openai_for_test:
            globals()['transcribe_chunk_openai'] = original_transcribe_chunk_openai_function
            logger.info("Restored original transcribe_chunk_openai function after __main__ test.")

        logger.info(f"Test files (if any created by __main__) are in '{RESULTS_DIR}'. Dummy audio '{dummy_file_path_reassembly_test}' may still exist for inspection.")

    logger.info("Test script for reassembly and export finished.")

# To run this app (from the /app directory):
# uvicorn backend.main:app --reload --port 8000
# The database 'transcription_jobs.db' will be created in the /app directory.
# You can then send requests to POST /jobs/ and GET /jobs/{job_id}
# e.g. using curl or a tool like Postman.
# POST example with curl:
# curl -X POST -F "file=@/path/to/your/dummyfile.mp3" http://localhost:8000/jobs/
# (replace /path/to/your/dummyfile.mp3 with an actual file path)
#
# To test WebSocket:
# 1. Start the server.
# 2. Create a job using POST /jobs/ and get the job_id.
# 3. Connect a WebSocket client (e.g., using a browser console, or a command-line tool) to:
#    ws://localhost:8000/ws/job_status/{job_id}
# 4. Observe messages pushed from the server as the background task progresses.
#    (Note: `websocat` was not found in the environment, so a different client might be needed for interactive tests)
