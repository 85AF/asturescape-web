# backend/database.py
from sqlmodel import create_engine, SQLModel, Session
import os
from sqlalchemy import event
from sqlalchemy.engine import Engine

SQLITE_FILE_NAME = "transcription_jobs.db"
# Use an explicit absolute path within the /app directory
DATABASE_URL = f"sqlite:////{os.getcwd()}/{SQLITE_FILE_NAME}" # os.getcwd() should be /app when run

# echo=True is good for development, prints SQL statements
# connect_args is needed for SQLite to allow shared access for multiple threads (e.g., BackgroundTasks)
engine = create_engine(DATABASE_URL, echo=True, connect_args={"check_same_thread": False})

# Enable WAL mode for SQLite for better concurrency
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout = 5000;") # Set a busy timeout to 5 seconds
        cursor.execute("PRAGMA synchronous = NORMAL;") # Less aggressive fsyncing
        cursor.close()
        # logger.info("SQLite PRAGMA journal_mode=WAL set.") # Add logger if available or use print
    except Exception as e:
        # logger.error(f"Failed to set PRAGMA journal_mode=WAL: {e}")
        print(f"Failed to set PRAGMA journal_mode=WAL: {e}") # Print if logger not set up here


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

# Dependency to get a DB session
def get_session():
    with Session(engine) as session:
        yield session
