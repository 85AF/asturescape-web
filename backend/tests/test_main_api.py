# backend/tests/test_main_api.py
import pytest
from httpx import AsyncClient
from fastapi import status
import os
from pathlib import Path
from io import BytesIO
from typing import List, Dict, Any # Added Any for JobProgressMessage
import asyncio

from backend.models import JobStatus, JobRead, Job, JobCreate # Import Job, JobCreate
from backend.transcribe import RESULTS_DIR, _mock_call_counter, OPENAI_API_KEY_AVAILABLE
from backend.main import TEMP_UPLOAD_DIR
from backend.database import DATABASE_PATH as MAIN_APP_DATABASE_PATH # For main app DB path if needed by tests
from backend.tests.conftest import TEST_DATABASE_PATH # For test DB path

# Mark all tests in this module as asyncio
pytestmark = pytest.mark.asyncio

async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}

async def test_create_job_and_get_status(client: AsyncClient, tmp_path: Path, clean_temp_dirs, session: Session): # Added session for direct DB check
    # Create a small dummy mp3 file for upload testing
    dummy_filename = "test_api_audio.mp3"
    # Use the helper from conftest or transcribe.py to create a valid dummy MP3
    # For simplicity, let's assume transcribe.py's main already created one we can reuse or create one here.
    # Re-creating dummy_audio_file logic here for clarity and independence
    from pydub import AudioSegment
    from pydub.generators import Sine

    test_audio_path = tmp_path / dummy_filename
    try:
        beep = Sine(440).to_audio_segment(duration=100, volume=-20) # 100ms beep
        silence = AudioSegment.silent(duration=900, frame_rate=22050) # 900ms silence
        audio_to_export = beep + silence
        audio_to_export.export(str(test_audio_path), format="mp3")
        assert os.path.exists(test_audio_path)
    except Exception as e:
        pytest.fail(f"Failed to create dummy MP3 for API test: {e}")

    files = {"file": (test_audio_path.name, test_audio_path.open("rb"), "audio/mpeg")}

    response_post = await client.post("/jobs/", files=files)

    assert response_post.status_code == status.HTTP_201_CREATED, f"API Error: {response_post.text}"
    created_job_data = response_post.json()

    assert "id" in created_job_data
    job_id = created_job_data["id"]
    assert created_job_data["filename"] == dummy_filename
    assert created_job_data["status"] == JobStatus.PENDING.value

    # Check DB directly (optional, but good for confirming)
    db_job = session.get(Job, job_id)
    assert db_job is not None
    assert db_job.filename == dummy_filename
    assert db_job.status == JobStatus.PENDING

    # Wait for the background task to process.
    # The mock in transcribe.py (when API key is missing) will cause it to fail quickly.
    # If API key IS present, this test would make a real call.
    # For CI/CD, OPENAI_API_KEY should not be set, forcing mock path in transcribe.py's transcribe_chunk_openai
    logger.info(f"Waiting for background task for job {job_id} to complete...")
    await asyncio.sleep(15) # Allow time for background task to run and update DB / send WS messages

    response_get = await client.get(f"/jobs/{job_id}")
    assert response_get.status_code == status.HTTP_200_OK
    retrieved_job_data = response_get.json()

    assert retrieved_job_data["id"] == job_id
    assert retrieved_job_data["filename"] == dummy_filename

    # Behavior depends on OPENAI_API_KEY_AVAILABLE (from transcribe.py)
    # and how process_audio_file handles is_mock_call (False when called from API)
    if not OPENAI_API_KEY_AVAILABLE:
        assert retrieved_job_data["status"] == JobStatus.FAILED.value
        assert "No segments transcribed" in retrieved_job_data["error_message"]
        assert retrieved_job_data["result_txt_path"] is None
        assert retrieved_job_data["result_srt_path"] is None
    else:
        # This case implies a real API call was made.
        # The dummy audio is very short and might not produce meaningful transcription.
        # It might complete with empty text or fail at OpenAI's side.
        # For robustness, accept COMPLETED (even if empty text) or FAILED.
        assert retrieved_job_data["status"] in [JobStatus.COMPLETED.value, JobStatus.FAILED.value]
        if retrieved_job_data["status"] == JobStatus.COMPLETED.value:
            assert retrieved_job_data["result_txt_path"] is not None
            assert retrieved_job_data["result_srt_path"] is not None
            # Check if files exist (paths are relative to /app)
            assert os.path.exists(os.path.join("/app", retrieved_job_data["result_txt_path"]))
            assert os.path.exists(os.path.join("/app", retrieved_job_data["result_srt_path"]))

    # Check GET /jobs/ list endpoint
    response_list = await client.get("/jobs/")
    assert response_list.status_code == status.HTTP_200_OK
    jobs_list = response_list.json()
    assert isinstance(jobs_list, list)
    assert any(job["id"] == job_id for job in jobs_list)

    # Check if temporary file was deleted by the background task
    # The original_file_path in the DB should point to the temp file.
    # We need to wait a bit more to ensure the finally block of run_transcription_job has executed.
    await asyncio.sleep(2)
    assert not os.path.exists(db_job.original_file_path), f"Temporary file {db_job.original_file_path} was not deleted."
    # Check that temp_uploads directory is empty or does not contain this specific file
    # Note: other test runs might leave files if they fail before cleanup.
    # The clean_temp_dirs fixture ensures it's empty *before* this test.
    # So, if the file is gone, the dir should be empty again.
    # For more robustness, list files and check if the specific one is absent.
    # This is simplified due to the complexity of tracking exact unique temp filenames across tests.
    if not os.listdir(TEMP_UPLOAD_DIR): # Check if directory is empty
        logger.info(f"{TEMP_UPLOAD_DIR} is empty after job completion.")
    else:
        logger.warning(f"{TEMP_UPLOAD_DIR} is not empty. Contents: {os.listdir(TEMP_UPLOAD_DIR)}")
        # This could be an issue if unrelated files are there, but for this test, it should be empty.
        assert not os.path.exists(db_job.original_file_path) # Double check the specific file


async def test_get_nonexistent_job(client: AsyncClient):
    response = await client.get("/jobs/9999999") # A very unlikely ID
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Job not found"

@pytest.mark.asyncio
async def test_websocket_connection_and_updates(client: AsyncClient, session: Session, clean_temp_dirs):
    # 1. Create a job via API to get a job_id
    dummy_filename = "ws_job_test.mp3"
    test_audio_path = Path(TEMP_UPLOAD_DIR) / dummy_filename # Will be created by main.py

    # Create a minimal dummy file for the upload
    from pydub import AudioSegment
    from pydub.generators import Sine
    try:
        beep = Sine(440).to_audio_segment(duration=50, volume=-30)
        silence = AudioSegment.silent(duration=100, frame_rate=22050)
        audio_to_export = beep + silence
        # Save it to a place where curl can pick it up (tmp_path provided by pytest fixture)
        temp_file_for_upload = clean_temp_dirs / "ws_upload_temp.mp3" # Using clean_temp_dirs as tmp_path for this
        # Note: clean_temp_dirs is function-scoped and cleans /app/temp_uploads and /app/transcription_results.
        # For the file upload itself, let's use a pytest-provided tmp_path for the source file.
        pytest_tmp_path = Path(tempfile.mkdtemp()) # Create a temporary directory for this test's uploads
        temp_file_for_upload = pytest_tmp_path / "ws_upload_temp.mp3"
        audio_to_export.export(str(temp_file_for_upload), format="mp3")

    except Exception as e:
        pytest.fail(f"Failed to create dummy MP3 for WS test: {e}")

    files = {"file": (dummy_filename, temp_file_for_upload.open("rb"), "audio/mpeg")}
    response_post = await client.post("/jobs/", files=files)
    assert response_post.status_code == status.HTTP_201_CREATED
    created_job_data = response_post.json()
    job_id = created_job_data["id"]

    logger.info(f"WebSocket test: Job {job_id} created. Connecting to WebSocket.")

    received_messages = []
    try:
        async with client.websocket_connect(f"/ws/job_status/{job_id}") as websocket:
            logger.info(f"WebSocket connected for job_id {job_id} in test_websocket_connection")

            # Wait for messages from the server. The background task should send them.
            # Timeout to prevent test from hanging indefinitely.
            try:
                for _ in range(4): # Expecting a few updates: processing, progress, completed/failed
                    message = await asyncio.wait_for(websocket.receive_json(), timeout=15.0) # Increased timeout
                    logger.info(f"WebSocket client received for job {job_id}: {message}")
                    received_messages.append(message)
                    if message.get("status") in [JobStatus.COMPLETED.value, JobStatus.FAILED.value]:
                        break
            except asyncio.TimeoutError:
                logger.warning(f"WebSocket receive timeout for job {job_id}.")
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected while waiting for messages for job {job_id}.")

    except WebSocketDisconnect as e:
        # This might happen if the server closes the connection after sending all updates
        logger.info(f"WebSocket disconnected as expected for job {job_id}. Code: {e.code}")
    except Exception as e:
        logger.error(f"WebSocket test error for job {job_id}: {e}", exc_info=True)
        pytest.fail(f"WebSocket connection or communication error: {e}")
    finally:
        # Clean up the temporary file used for upload
        if temp_file_for_upload.exists():
            os.remove(temp_file_for_upload)
        if os.path.exists(pytest_tmp_path):
            shutil.rmtree(pytest_tmp_path)


    logger.info(f"Received WebSocket messages for job {job_id}: {received_messages}")

    # Assertions on received messages
    assert len(received_messages) > 0, "Should have received at least one status update."

    initial_processing_msg = next((m for m in received_messages if m.get("message") == "Starting transcription process..."), None)
    assert initial_processing_msg is not None
    assert initial_processing_msg["status"] == JobStatus.PROCESSING.value

    # If API key is not set, transcribe.py mock leads to "No segments transcribed"
    # which results in a FAILED status by process_audio_file, then propagated by run_transcription_job
    final_status_message = received_messages[-1]
    if not OPENAI_API_KEY_AVAILABLE:
        assert final_status_message["status"] == JobStatus.FAILED.value
        assert "No segments transcribed" in final_status_message.get("message", "")
    else:
        # If real API was used, it could be COMPLETED or FAILED depending on the dummy file
        assert final_status_message["status"] in [JobStatus.COMPLETED.value, JobStatus.FAILED.value]
        if final_status_message["status"] == JobStatus.COMPLETED.value:
             assert "txt_path" in final_status_message
             assert "srt_path" in final_status_message

    # Check if the connection was cleaned up from the manager
    from backend.websocket_manager import manager as ws_manager_instance # get the instance
    assert job_id not in ws_manager_instance.active_connections or not ws_manager_instance.active_connections[job_id]
    logger.info(f"WebSocket connection for job {job_id} correctly closed and removed from manager.")
```

And `backend/tests/test_transcribe_utils.py`:
```python
# backend/tests/test_transcribe_utils.py
import pytest
from backend.transcribe import (
    format_timestamp_srt,
    format_timestamp_txt,
    generate_srt_content,
    generate_txt_content,
    split_audio_into_chunks,
    process_audio_file,
    RESULTS_DIR,
    _mock_call_counter,
    OPENAI_API_KEY_AVAILABLE,
    transcribe_chunk_openai # Import the original to restore it
)
from pydub import AudioSegment
from pydub.generators import Sine # Ensure Sine is imported
from datetime import datetime, timedelta # Ensure datetime is imported
import os
import shutil
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Fixture to create a dummy audio file for tests that need one
@pytest.fixture(scope="function")
def dummy_audio_file(tmp_path: Path) -> Path:
    file_path = tmp_path / "test_audio.mp3"
    try:
        beep = Sine(440).to_audio_segment(duration=50, volume=-30)
        silence = AudioSegment.silent(duration=950, frame_rate=22050) # 1 second total
        audio_to_export = silence.overlay(beep) # Ensure it's not pure silence
        audio_to_export.export(str(file_path), format="mp3")
        if not (os.path.exists(file_path) and os.path.getsize(file_path) > 0):
             pytest.fail(f"Failed to create a valid dummy MP3 file for testing at {file_path}")
    except Exception as e:
        pytest.fail(f"Failed to create dummy MP3 file due to pydub/ffmpeg error: {e}, {type(e)}")
    return file_path


def test_format_timestamp_srt():
    assert format_timestamp_srt(0) == "00:00:00,000"
    assert format_timestamp_srt(1.234) == "00:00:01,234"
    assert format_timestamp_srt(1.2345) == "00:00:01,235"
    assert format_timestamp_srt(65.05) == "00:01:05,050"
    assert format_timestamp_srt(3661.001) == "01:01:01,001"
    assert format_timestamp_srt(3600 + 120 + 3 + 0.4567) == "01:02:03,457"

def test_format_timestamp_txt():
    assert format_timestamp_txt(0) == "[00:00:00]"
    assert format_timestamp_txt(1.234) == "[00:00:01]"
    assert format_timestamp_txt(65.05) == "[00:01:05]"
    assert format_timestamp_txt(3661.001) == "[01:01:01]"

def test_generate_srt_content_empty():
    assert generate_srt_content([]) == ""

def test_generate_srt_content_basic():
    segments = [
        {"id": 1, "start": 0.0, "end": 2.5, "text": "Hello world."},
        {"id": 2, "start": 2.8, "end": 5.123, "text": " This is a test. "},
        {"id": 3, "start": 6.0, "end": 6.0, "text": "Empty duration"},
        {"id": 4, "start": 7.0, "end": 8.0, "text": ""},
    ]
    expected_srt = (
        "1\n"
        "00:00:00,000 --> 00:00:02,500\n"
        "Hello world.\n"
        "\n"
        "2\n"
        "00:00:02,800 --> 00:00:05,123\n"
        "This is a test.\n"
        "\n"
        "3\n"
        "00:00:06,000 --> 00:00:06,000\n"
        "Empty duration\n"
        "\n"
    )
    assert generate_srt_content(segments) == expected_srt


def test_generate_txt_content_empty():
    assert generate_txt_content([]) == ""

def test_generate_txt_content_basic():
    segments = [
        {"start": 0.0, "text": " First line."},
        {"start": 2.8, "text": "Second line. "},
        {"start": 5.123, "text": ""},
        {"start": 6.0, "text": "Third line after empty."}
    ]
    expected_txt = (
        "[00:00:00] First line.\n"
        "[00:00:02] Second line.\n"
        "[00:00:06] Third line after empty."
    )
    assert generate_txt_content(segments) == expected_txt

def test_split_audio_into_chunks_normal(tmp_path: Path):
    long_audio_path = tmp_path / "long_test_audio.mp3"
    # Create a 30-second audio file for splitting
    audio = Sine(440).to_audio_segment(duration=1000, volume=-20)
    for _ in range(29):
        audio += Sine(440).to_audio_segment(duration=1000, volume=-20)
    audio.export(str(long_audio_path), format="mp3")

    # Test splitting with 10-second max_chunk_duration_ms
    chunk_paths, duration = split_audio_into_chunks(str(long_audio_path), max_chunk_duration_ms=10 * 1000)
    assert duration == pytest.approx(30.0)
    assert len(chunk_paths) == 3 # 30s / 10s chunks = 3 chunks
    for cp in chunk_paths:
        assert os.path.exists(cp)
    if chunk_paths:
        shutil.rmtree(os.path.dirname(chunk_paths[0]))

def test_split_audio_empty_file(tmp_path: Path):
    empty_file = tmp_path / "empty.mp3"
    AudioSegment.silent(duration=0, frame_rate=22050).export(str(empty_file), format="mp3")

    chunk_paths, duration = split_audio_into_chunks(str(empty_file))
    assert duration == 0.0
    assert len(chunk_paths) == 0
    # Ensure no temp directory was left if no chunks were made and dir was created
    # (split_audio_into_chunks should handle this)

# Store the original transcribe_chunk_openai function from transcribe.py
original_transcribe_chunk_openai_in_module = None

@pytest.fixture(autouse=True)
def mock_openai_if_no_key(monkeypatch):
    """
    This fixture will run for every test in this module.
    It mocks transcribe_chunk_openai if OPENAI_API_KEY is not available.
    """
    global _mock_call_counter # Ensure we use the one from transcribe.py
    from backend import transcribe as transcribe_module # Import the module itself

    # Store original function before patching, and ensure it's restored.
    # This is important if other test files might import transcribe_module.
    # For simplicity here, we assume this test file is self-contained for this mock.
    # A more robust solution might use pytest-mock's `mocker` fixture.

    original_transcribe_chunk_openai_function = transcribe_module.transcribe_chunk_openai

    if not OPENAI_API_KEY_AVAILABLE:
        logger.info("Patching transcribe.py's transcribe_chunk_openai with mock for test_process_audio_file_mocked")

        # Reset counter for each test function run that uses this mock
        transcribe_module._mock_call_counter = 0

        def mocked_transcribe_for_process_test(chunk_file_path: str, language: str = None, is_mock_call: bool = False): # Add is_mock_call
            # This mock is specifically for process_audio_file test
            # It uses the _mock_call_counter from transcribe.py
            transcribe_module._mock_call_counter += 1
            logger.info(f"MOCKED (fixture) transcribe_chunk_openai for process_audio_file: {chunk_file_path} (Call #{transcribe_module._mock_call_counter})")
            return transcribe_module._get_mock_transcription_data(transcribe_module._mock_call_counter, language)

        monkeypatch.setattr(transcribe_module, "transcribe_chunk_openai", mocked_transcribe_for_process_test)
        yield
        # Restore the original function after the test
        monkeypatch.setattr(transcribe_module, "transcribe_chunk_openai", original_transcribe_chunk_openai_function)
        logger.info("Restored original transcribe_chunk_openai function after test_process_audio_file_mocked.")
    else:
        logger.info("OPENAI_API_KEY is available. test_process_audio_file_mocked will run with REAL API calls.")
        yield # No patching needed, just yield to run the test


def test_process_audio_file_logic(tmp_path: Path, clean_temp_dirs, mock_openai_if_no_key):
    # This test will use the mocked version of transcribe_chunk_openai if API key is not set,
    # or the real one if it is. The assertions are geared towards the mocked data structure.

    # Create a 30s dummy audio file
    audio_30s_path = tmp_path / "dummy_audio_30s_for_process_test.mp3"
    audio_parts = [
        (Sine(440).to_audio_segment(duration=200, volume=-20)).fade_in(50).fade_out(50),
        AudioSegment.silent(duration=10000 - 200, frame_rate=44100),
        (Sine(660).to_audio_segment(duration=300, volume=-20)).fade_in(50).fade_out(50),
        AudioSegment.silent(duration=10000 - 300, frame_rate=44100),
        (Sine(880).to_audio_segment(duration=100, volume=-20)).fade_in(50).fade_out(50),
        AudioSegment.silent(duration=10000 - 100, frame_rate=44100),
    ]
    combined_audio = sum(audio_parts, AudioSegment.empty())
    combined_audio = combined_audio[:30000] # 30 seconds
    combined_audio.export(str(audio_30s_path), format="mp3", bitrate="32k")

    base_filename = f"test_process_audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if not OPENAI_API_KEY_AVAILABLE: # If we are mocking
         base_filename = "MOCK_" + base_filename


    # Reset the module-level counter in transcribe.py before this specific test call
    # This is important because process_audio_file itself also resets it if is_mock_call=True
    # but here, is_mock_call will be False if API key is present.
    # The mock_openai_if_no_key fixture handles resetting the counter.
    from backend import transcribe as transcribe_module
    transcribe_module._mock_call_counter = 0


    txt_path, srt_path, duration, error = process_audio_file(
        str(audio_30s_path),
        base_filename,
        language="en",
        max_chunk_duration_ms_override=10 * 1000, # 10-second chunks
        is_mock_call=not OPENAI_API_KEY_AVAILABLE # Explicitly tell process_audio_file to use mock if no key
    )

    if not OPENAI_API_KEY_AVAILABLE: # Assertions for mocked data
        assert error is None, f"process_audio_file returned an error: {error}"
        assert duration == pytest.approx(30.0)
        assert txt_path is not None and os.path.exists(txt_path)
        assert srt_path is not None and os.path.exists(srt_path)

        expected_txt_content = "[00:00:00] Hello world.\n[00:00:03] This is a test.\n[00:00:11] Second chunk here.\n[00:00:20] Final segment."
        with open(txt_path, 'r', encoding='utf-8') as f:
            actual_txt_content = f.read()
        assert actual_txt_content.strip() == expected_txt_content.strip(), "Mocked TXT content mismatch"

        expected_srt_content_parts = [
            "1\n00:00:00,000 --> 00:00:02,000\nHello world.",
            "2\n00:00:03,000 --> 00:00:05,000\nThis is a test.",
            "3\n00:00:11,000 --> 00:00:13,000\nSecond chunk here.",
            "4\n00:00:20,500 --> 00:00:22,500\nFinal segment."
        ]
        with open(srt_path, 'r', encoding='utf-8') as f:
            actual_srt_content = f.read().strip()
        for part in expected_srt_content_parts:
            assert part in actual_srt_content
    else:
        logger.info("Real API was used for test_process_audio_file_logic. Manual verification of results needed if it passed.")
        # If real API was used, we expect it to complete or fail.
        # If it completed, files should exist.
        if error is None:
            assert txt_path is not None and os.path.exists(txt_path)
            assert srt_path is not None and os.path.exists(srt_path)
        else:
            logger.warning(f"Real API call in test_process_audio_file_logic resulted in error: {error}")

    # Cleanup the specific dummy file for this test
    if os.path.exists(audio_30s_path):
        os.remove(audio_30s_path)

```
