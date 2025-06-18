# backend/models.py
from sqlmodel import Field, SQLModel, create_engine
from datetime import datetime
from enum import Enum
from typing import Optional

class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class JobBase(SQLModel):
    filename: str = Field(index=True)
    original_file_path: Optional[str] = None # Temp path of uploaded file, might not be stored long term
    duration_seconds: Optional[float] = None
    status: JobStatus = Field(default=JobStatus.PENDING)
    result_txt_path: Optional[str] = None # Store path on server
    result_srt_path: Optional[str] = None # Store path on server
    error_message: Optional[str] = None # To store any error messages during processing

class Job(JobBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False, sa_column_kwargs={"onupdate": datetime.utcnow})

class JobCreate(JobBase):
    pass

class JobRead(JobBase):
    id: int
    created_at: datetime
    updated_at: datetime

class JobUpdate(SQLModel): # For partial updates
    status: Optional[JobStatus] = None
    duration_seconds: Optional[float] = None
    original_file_path: Optional[str] = None
    result_txt_path: Optional[str] = None
    result_srt_path: Optional[str] = None
    error_message: Optional[str] = None
    # updated_at should be handled by the database or ORM on actual update,
    # or set explicitly in the update logic. Default factory here might not always be what's intended
    # for partial updates unless the field is always meant to be touched.
    # For now, following the provided model.
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# Example of how the engine might be created here or in database.py
# SQLITE_DATABASE_URL = "sqlite:///./transcription_jobs.db"
# engine = create_engine(SQLITE_DATABASE_URL, echo=True) # echo=True for logging SQL

# def create_db_and_tables():
#     SQLModel.metadata.create_all(engine)
