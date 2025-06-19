# backend/main.py
from fastapi import (
    FastAPI, Depends, HTTPException, UploadFile, File, BackgroundTasks, WebSocket, WebSocketDisconnect,
    Path
)
from sqlmodel import Session, select
import os
import shutil
import logging
from typing import List, Optional
from datetime import datetime

# Configure basic logging
# Ensure this runs before other modules that might also try to configure logging
if not logging.getLogger().handlers: # Check if root logger has handlers
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Corrected import path for DATABASE_PATH and SQLITE_DB_DIR
from .database import engine, create_db_and_tables, get_session, DATABASE_PATH, SQLITE_DB_DIR
from .models import Job, JobCreate, JobRead, JobStatus, JobUpdate
# from .transcribe import process_audio_file # Temporarily unused
# from .websocket_manager import manager # Temporarily unused

# Temp directory for uploads (still needed for full functionality later)
TEMP_UPLOAD_DIR = "temp_uploads"
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)


def lifespan(app: FastAPI):
    logger.info("Lifespan event: STARTUP")
    logger.info(f"Target DB directory: {SQLITE_DB_DIR}") # SQLITE_DB_DIR from database.py
    logger.info(f"Target DB path: {DATABASE_PATH}")   # DATABASE_PATH from database.py
    create_db_and_tables()

    logger.info("Attempting direct DB write test after startup initialization...")
    try:
        # Use the get_session dependency pattern correctly for testing
        session_generator = get_session()
        session = next(session_generator)
        try:
            test_job = Job(filename="startup_test.mp3", status=JobStatus.PENDING)
            session.add(test_job)
            session.commit()
            session.refresh(test_job)
            logger.info(f"Direct DB write test successful. Job ID: {test_job.id}, Path: {DATABASE_PATH}")

            # Clean up the test job
            session.delete(test_job)
            session.commit()
            logger.info("Cleaned up direct DB write test job.")
        except Exception as e_inner:
            logger.error(f"Direct DB write test FAILED: {e_inner}", exc_info=True)
            session.rollback() # Rollback on error
        finally:
            session.close() # Ensure session is closed

    except Exception as e:
        logger.error(f"Direct DB write test FAILED (outer scope): {e}", exc_info=True)
        logger.error(f"Please check permissions on {DATABASE_PATH} and its directory {os.path.dirname(DATABASE_PATH)}.")

    logger.info("Lifespan event: STARTUP complete.")
    yield
    logger.info("Lifespan event: SHUTDOWN")

app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# SIMPLIFIED create_transcription_job_endpoint for DB write testing
@app.post("/jobs/", response_model=JobRead, status_code=201)
async def create_dummy_job_for_db_test(session: Session = Depends(get_session)):
    logger.info(f"Attempting to create a dummy job in /jobs/ endpoint. DB: {DATABASE_PATH}")
    try:
        dummy_filename = f"test_job_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}.mp3"
        # JobCreate requires filename and can take status. original_file_path is Optional.
        job_create_payload = JobCreate(filename=dummy_filename, status=JobStatus.PENDING)

        # Create Job instance from JobCreate payload
        # SQLModel uses model_validate to create an instance of the table model from a Pydantic model
        db_job = Job.model_validate(job_create_payload)
        # Or, more explicitly if JobCreate is just a Pydantic model and Job is SQLModel:
        # db_job = Job(filename=job_create_data.filename, status=job_create_data.status)
        # The current model structure should work with model_validate as JobCreate inherits JobBase (SQLModel)

        session.add(db_job)
        session.commit()
        session.refresh(db_job)
        logger.info(f"Successfully created dummy job ID: {db_job.id}, Filename: {db_job.filename}")

        # For testing, immediately update status to completed (simulates some processing)
        db_job.status = JobStatus.COMPLETED
        db_job.updated_at = datetime.utcnow() # Manually update updated_at for JobUpdate
        session.add(db_job)
        session.commit()
        session.refresh(db_job)
        logger.info(f"Updated dummy job {db_job.id} status to COMPLETED.")

        return db_job
    except Exception as e:
        logger.error(f"Failed to create dummy job in /jobs/ endpoint: {e}", exc_info=True)
        # Log current permissions of DB file and directory if error occurs
        if os.path.exists(DATABASE_PATH):
            try:
                logger.error(f"Permissions of {DATABASE_PATH}: {oct(os.stat(DATABASE_PATH).st_mode)}")
            except Exception as stat_e:
                logger.error(f"Could not stat {DATABASE_PATH}: {stat_e}")
        if os.path.exists(SQLITE_DB_DIR):
            try:
                logger.error(f"Permissions of {SQLITE_DB_DIR}: {oct(os.stat(SQLITE_DB_DIR).st_mode)}")
            except Exception as stat_e:
                logger.error(f"Could not stat {SQLITE_DB_DIR}: {stat_e}")
        raise HTTPException(status_code=500, detail=f"Database operation failed: {str(e)}")

@app.get("/jobs/{job_id}", response_model=JobRead)
async def read_job_endpoint(job_id: int = Path(..., gt=0), session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.get("/jobs/", response_model=List[JobRead])
async def read_jobs_endpoint(session: Session = Depends(get_session), skip: int = 0, limit: int = 100):
    statement = select(Job).order_by(Job.id.desc()).offset(skip).limit(limit)
    jobs = session.exec(statement).all()
    return jobs

# --- WebSocket Endpoint (code from previous step, can be uncommented later) ---
# from .websocket_manager import manager as ws_manager # alias to avoid conflict if any
# @app.websocket("/ws/job_status/{job_id}")
# async def websocket_endpoint(
#     websocket: WebSocket,
#     job_id: int = Path(..., gt=0)
# ):
#     await ws_manager.connect(websocket, job_id)
#     try:
#         while True:
#             data = await websocket.receive_text()
#             logger.info(f"Received WebSocket message from {websocket.client} for job {job_id}: {data}")
#     except WebSocketDisconnect as e:
#         logger.info(f"WebSocket disconnected by client: {websocket.client} for job {job_id}. Code: {e.code}, Reason: '{e.reason if e.reason else 'No reason provided'}'")
#     except Exception as e:
#         logger.error(f"Exception in WebSocket for job {job_id}, client {websocket.client}: {type(e).__name__} - {e}", exc_info=True)
#     finally:
#         ws_manager.disconnect(websocket, job_id)
#         logger.info(f"WebSocket connection resources cleaned up for job {job_id}, client {websocket.client}")

# Note: The `run_transcription_job` and related file processing logic
# (including `TEMP_UPLOAD_DIR` actual usage and `process_audio_file` import)
# are temporarily simplified/commented out to focus on the DB write issue.
# They will be restored once the DB write is confirmed working.
# The `create_transcription_job_endpoint` currently does not take a file for this test.
