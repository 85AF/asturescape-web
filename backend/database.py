# backend/database.py
import os
import stat
import logging
from sqlmodel import create_engine, SQLModel, Session
from sqlalchemy import event
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)
# Basic config for this module if not configured by main app yet (e.g. during direct script run)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# New database directory
SQLITE_DB_DIR = "/app/db_data"
SQLITE_FILE_NAME = "transcription_jobs.db"
DATABASE_PATH = os.path.join(SQLITE_DB_DIR, SQLITE_FILE_NAME)
DATABASE_URL = f"sqlite:///{DATABASE_PATH}" # Absolute path

logger.info(f"Database URL set to: {DATABASE_URL}")

engine = create_engine(
    DATABASE_URL,
    echo=True,
    connect_args={"check_same_thread": False}
)

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout = 5000;")
        cursor.execute("PRAGMA synchronous = NORMAL;")
        logger.info("SQLite PRAGMA journal_mode=WAL, busy_timeout=5000, synchronous=NORMAL set.")
    except Exception as e:
        logger.error(f"Failed to set PRAGMA for SQLite: {e}")
    finally:
        cursor.close()

def _ensure_permissions(path, perm_mode, is_dir=False):
    try:
        if is_dir:
            if not os.path.exists(path):
                os.makedirs(path, mode=perm_mode) # exist_ok=True is default for os.makedirs in Python 3.2+
                logger.info(f"Created directory {path} with mode {oct(perm_mode)}.")
            else:
                os.chmod(path, perm_mode)
                logger.info(f"Set permissions {oct(perm_mode)} on existing directory {path}.")
        else: # It's a file
            # Ensure parent directory exists first
            parent_dir = os.path.dirname(path)
            if not os.path.exists(parent_dir):
                 os.makedirs(parent_dir, mode=0o775, exist_ok=True) # rwxrwxr-x for parent
                 logger.info(f"Created parent directory {parent_dir} with mode 0o775.")

            if os.path.exists(path): # Set perms if file exists
                os.chmod(path, perm_mode)
                logger.info(f"Set permissions {oct(perm_mode)} on {path}.")
            # If file doesn't exist, it will be created by SQLAlchemy with umask settings
            # else:
            #    logger.warning(f"File {path} does not exist to set permissions on (this might be okay if it's created by SQLModel).")

    except Exception as e:
        logger.error(f"Failed to set permissions/create dir for {path}: {e}", exc_info=True)


def create_db_and_tables():
    logger.info(f"Initializing database at {DATABASE_PATH}")
    original_umask = os.umask(0o002) # Sets umask to allow group write, retains other restrictions
    logger.info(f"Temporarily set umask to 0o002 (was {oct(original_umask)})")

    try:
        # Ensure the /app/db_data directory exists with 0o775 permissions (rwxrwxr-x)
        # This allows the owner (jules) and group (jules/users) to write.
        _ensure_permissions(SQLITE_DB_DIR, 0o775, is_dir=True)

        SQLModel.metadata.create_all(engine)
        logger.info(f"SQLModel.metadata.create_all() called for DB at {DATABASE_PATH}.")

        if os.path.exists(DATABASE_PATH):
            _ensure_permissions(DATABASE_PATH, 0o664) # rw-rw-r--
            # For WAL mode, -wal and -shm files also need to be writable by the process
            _ensure_permissions(f"{DATABASE_PATH}-shm", 0o664)
            _ensure_permissions(f"{DATABASE_PATH}-wal", 0o664)
            logger.info(f"Database file {DATABASE_PATH} and journal files permissions set to 0o664.")
        else:
            logger.warning(f"Database file {DATABASE_PATH} was not found after create_all(). This is unexpected if tables were meant to be created.")

    except Exception as e:
        logger.error(f"An error occurred during database initialization: {e}", exc_info=True)
    finally:
        os.umask(original_umask)
        logger.info(f"Restored umask to {oct(original_umask)}")

# Dependency to get a DB session
def get_session():
    with Session(engine) as session:
        yield session
