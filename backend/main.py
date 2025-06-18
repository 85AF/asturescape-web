# backend/main.py
from fastapi import (
    FastAPI, Depends, HTTPException, UploadFile, File, BackgroundTasks, WebSocket, WebSocketDisconnect,
    Path # Added Path for job_id validation
)
from sqlmodel import Session, select # Added select for query
import os
import shutil # For saving uploaded file temporarily
import logging # For logging
from typing import List, Optional # For list response model & optional query params
from datetime import datetime # For unique filenames

# Configure basic logging if not already set up by another module
# This check is important if main.py could be imported elsewhere.
if not logging.getLogger(__name__).hasHandlers(): # Check specific logger
    if not logging.getLogger().hasHandlers(): # Check root logger as fallback
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


from .database import engine, create_db_and_tables, get_session, SQLITE_FILE_NAME
from .models import Job, JobCreate, JobRead, JobStatus, JobUpdate
from .transcribe import process_audio_file # Orchestrator function
from .websocket_manager import manager # Import the global manager

# Temp directory for uploads
TEMP_UPLOAD_DIR = "temp_uploads"
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)

# Lifespan function for DB initialization
def lifespan(app: FastAPI):
    logger.info("Lifespan event: Creating database and tables...")
    create_db_and_tables()

    # Ensure the database file is writable
    db_file_path = f"/app/{SQLITE_FILE_NAME}"
    if os.path.exists(db_file_path):
        try:
            os.chmod(db_file_path, 0o666) # Read/Write for owner, group, others
            logger.info(f"Set permissions for {db_file_path} to 666.")
        except Exception as e:
            logger.error(f"Could not chmod {db_file_path}: {e}")
    else:
        logger.warning(f"Database file {db_file_path} not found immediately after create_db_and_tables during lifespan startup.")

    yield
    logger.info("Lifespan event: Application shutdown.")
    # Optional: Clean up temp_uploads directory on shutdown
    # if os.path.exists(TEMP_UPLOAD_DIR):
    #     try:
    #         shutil.rmtree(TEMP_UPLOAD_DIR)
    #         logger.info(f"Cleaned up {TEMP_UPLOAD_DIR}")
    #     except Exception as e:
    #         logger.error(f"Error cleaning up {TEMP_UPLOAD_DIR}: {e}")

app = FastAPI(lifespan=lifespan)

# --- Background Task for Transcription ---
async def run_transcription_job(job_id: int, file_path: str, original_filename: str, language: Optional[str] = None):
    with Session(engine) as session_local:
        try:
            logger.info(f"Background task started for job_id: {job_id}, file: {file_path}")
            await manager.send_job_update(job_id, {"status": JobStatus.PROCESSING.value, "message": "Starting transcription process..."})

            job = session_local.get(Job, job_id)
            if not job:
                logger.error(f"Job {job_id} not found in DB for background task.")
                await manager.send_job_update(job_id, {"status": JobStatus.FAILED.value, "message": f"Job {job_id} not found."})
                return

            job.status = JobStatus.PROCESSING
            job.updated_at = datetime.utcnow()
            session_local.add(job)
            session_local.commit()
            session_local.refresh(job)

            sane_filename = "".join(c if c.isalnum() or c in ['.', '_', '-'] else '_' for c in original_filename)
            base_output_filename = f"job_{job_id}_{os.path.splitext(sane_filename)[0]}"

            await manager.send_job_update(job_id, {"status": JobStatus.PROCESSING.value, "progress": 25, "message": "Audio chunking complete, starting transcription..."})

            txt_path, srt_path, duration_s, error_msg = process_audio_file(
                original_audio_path=file_path,
                base_output_filename=base_output_filename,
                language=language
            )

            await manager.send_job_update(job_id, {"status": JobStatus.PROCESSING.value, "progress": 75, "message": "Transcription finished, generating output files..."})

            job = session_local.get(Job, job_id)
            if not job: # Should not happen, but defensive check
                 logger.error(f"Job {job_id} disappeared from DB during processing.")
                 await manager.send_job_update(job_id, {"status": JobStatus.FAILED.value, "message": f"Job {job_id} lost during processing."})
                 return

            if error_msg:
                logger.error(f"Transcription failed for job_id {job_id}: {error_msg}")
                job_update_failure = JobUpdate(status=JobStatus.FAILED, error_message=error_msg, updated_at=datetime.utcnow())
                for key, value in job_update_failure.model_dump(exclude_unset=True).items():
                    setattr(job, key, value)
                await manager.send_job_update(job_id, {"status": JobStatus.FAILED.value, "message": error_msg})
            else:
                logger.info(f"Transcription successful for job_id {job_id}. TXT: {txt_path}, SRT: {srt_path}")
                job_update_success = JobUpdate(
                    status=JobStatus.COMPLETED,
                    result_txt_path=txt_path,
                    result_srt_path=srt_path,
                    duration_seconds=duration_s,
                    updated_at=datetime.utcnow()
                )
                for key, value in job_update_success.model_dump(exclude_unset=True).items():
                    setattr(job, key, value)
                await manager.send_job_update(job_id, {
                    "status": JobStatus.COMPLETED.value,
                    "message": "Transcription complete.",
                    "txt_path": txt_path,
                    "srt_path": srt_path,
                    "duration": duration_s
                })

            session_local.add(job)
            session_local.commit()
            session_local.refresh(job)

        except Exception as e:
            logger.exception(f"Unhandled exception in background task for job_id {job_id}: {e}")
            try:
                # Ensure session_local is still valid or get a new one
                if session_local.is_active:
                    job_to_fail = session_local.get(Job, job_id)
                else: # If session became inactive due to the error, get a new one
                    with Session(engine) as new_session:
                        job_to_fail = new_session.get(Job, job_id)
                        if job_to_fail:
                            job_to_fail.status = JobStatus.FAILED
                            job_to_fail.error_message = str(e)
                            job_to_fail.updated_at = datetime.utcnow()
                            new_session.add(job_to_fail)
                            new_session.commit()

                if job_to_fail and not session_local.is_active: # If original session died, use a new one to update
                    with Session(engine) as new_session:
                        job_to_fail = new_session.get(Job, job_id)
                        if job_to_fail: # Check again if job exists
                            job_to_fail.status = JobStatus.FAILED
                            job_to_fail.error_message = str(e)
                            job_to_fail.updated_at = datetime.utcnow()
                            new_session.add(job_to_fail)
                            new_session.commit()
                elif job_to_fail : # Original session is still active
                    job_to_fail.status = JobStatus.FAILED
                    job_to_fail.error_message = str(e)
                    job_to_fail.updated_at = datetime.utcnow()
                    session_local.add(job_to_fail)
                    session_local.commit()

                await manager.send_job_update(job_id, {"status": JobStatus.FAILED.value, "message": f"An unexpected error occurred: {str(e)}"})
            except Exception as e_final_fail:
                 logger.error(f"Failed to update job {job_id} to FAILED status after unhandled exception: {e_final_fail}")
        finally:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.info(f"Cleaned up temporary upload file: {file_path}")
                except OSError as e_clean:
                    logger.error(f"Error cleaning up temporary file {file_path}: {e_clean}")
            logger.info(f"Background task finished for job_id: {job_id}")


@app.get("/health")
async def health_check():
    return {"status": "ok"}

# --- API Endpoints (/jobs) ---
@app.post("/jobs/", response_model=JobRead, status_code=201)
async def create_transcription_job_endpoint(
    *,
    session: Session = Depends(get_session),
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
    # language: Optional[str] = Form(None)
):
    # Ensure unique filename for temp storage to avoid conflicts
    unique_suffix = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    # Sanitize filename from client
    sane_client_filename = "".join(c if c.isalnum() or c in ['.', '_', '-'] else '_' for c in file.filename)
    temp_file_name = f"job_upload_{unique_suffix}_{sane_client_filename}"
    temp_file_path = os.path.join(TEMP_UPLOAD_DIR, temp_file_name)

    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"File '{file.filename}' uploaded to '{temp_file_path}'.")
    except Exception as e:
        logger.error(f"Failed to save uploaded file {file.filename}: {e}")
        if os.path.exists(temp_file_path): # Attempt cleanup on failure
            os.remove(temp_file_path)
        raise HTTPException(status_code=500, detail=f"Could not save uploaded file: {e}")
    finally:
        await file.close()

    job_create_data = JobCreate(
        filename=file.filename,
        original_file_path=temp_file_path,
        status=JobStatus.PENDING
        # created_at and updated_at will be set by default in Job model
    )
    db_job = Job.model_validate(job_create_data)

    session.add(db_job)
    try:
        session.commit()
        session.refresh(db_job)
    except Exception as e:
        session.rollback()
        logger.error(f"Database commit error for job {file.filename}: {e}", exc_info=True)
        # Clean up the saved file if DB commit fails
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise HTTPException(status_code=500, detail=f"Error saving job to database: {str(e)}")

    logger.info(f"Job created in DB with ID: {db_job.id} for file: {db_job.filename}")

    language_param_for_task = None
    background_tasks.add_task(run_transcription_job, db_job.id, temp_file_path, db_job.filename, language_param_for_task)
    logger.info(f"Background task added for job_id: {db_job.id}")

    return db_job


@app.get("/jobs/{job_id}", response_model=JobRead)
async def read_job_endpoint(job_id: int = Path(..., gt=0), session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.get("/jobs/", response_model=List[JobRead])
async def read_jobs_endpoint(session: Session = Depends(get_session), skip: int = 0, limit: int = 100):
    statement = select(Job).offset(skip).limit(limit)
    jobs = session.exec(statement).all()
    return jobs


# --- WebSocket Endpoint ---
@app.websocket("/ws/job_status/{job_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    job_id: int = Path(..., gt=0)
):
    await manager.connect(websocket, job_id)
    try:
        while True:
            data = await websocket.receive_text()
            logger.info(f"Received WebSocket message from {websocket.client} for job {job_id}: {data}")
            # Example: could be a ping or other client-side message.
            # await websocket.send_text(f"Pong: {data}")
    except WebSocketDisconnect:
        # Log the disconnect reason if available and specific codes
        disconnect_reason = websocket.client_state.name # WAITING, CONNECTED, DISCONNECTED, etc.
        if hasattr(websocket, 'close_code'):
             disconnect_reason += f" (code: {websocket.close_code})"
        logger.info(f"WebSocket disconnected by client: {websocket.client} for job {job_id} (reason: {disconnect_reason})")
    except Exception as e:
        logger.error(f"Exception in WebSocket for job {job_id}, client {websocket.client}: {type(e).__name__} - {e}", exc_info=True)
    finally:
        manager.disconnect(websocket, job_id)
        logger.info(f"WebSocket connection resources cleaned up for job {job_id}, client {websocket.client}")

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
# 3. Connect a WebSocket client (e.g., using a browser console, wscat, or a simple Python script) to:
#    ws://localhost:8000/ws/job_status/{job_id}
# 4. Observe messages pushed from the server as the background task progresses.
