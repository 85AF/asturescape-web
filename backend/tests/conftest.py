# backend/tests/conftest.py
import sys
import os

# Add project root to sys.path to allow absolute imports like 'from backend.main'
PROJECT_ROOT_CONFTEST = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT_CONFTEST not in sys.path:
    sys.path.insert(0, PROJECT_ROOT_CONFTEST)

import pytest
import pytest_asyncio
from typing import Generator, AsyncGenerator
import os
import shutil
import logging

from httpx import AsyncClient
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy import event
from sqlalchemy.engine import Engine # Add this import
from fastapi import FastAPI

# Import the main app and functions from your backend code
from backend.main import app as main_app
from backend.database import get_session as main_get_session
# Import constants for DB paths to avoid hardcoding them again
# These are the paths the main app uses, which we might need to consider if lifespan creates DB
# from backend.database import DATABASE_PATH as MAIN_APP_DATABASE_PATH # Not strictly needed if engine is patched
# from backend.database import SQLITE_DB_DIR as MAIN_APP_SQLITE_DB_DIR # Not strictly needed

logger = logging.getLogger(__name__)
# Ensure logging is configured for tests if not already by other modules
if not logger.hasHandlers(): # Check specific logger first
    if not logging.getLogger().hasHandlers(): # Then check root logger
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


# Use a separate test database and directory
TEST_DB_SUBDIR = "test_db_data_pytest"
# Correctly make TEST_SQLITE_DB_DIR relative to the project root /app
# __file__ is /app/backend/tests/conftest.py
# os.path.dirname(__file__) is /app/backend/tests
# os.path.dirname(os.path.dirname(__file__)) is /app/backend
# os.path.dirname(os.path.dirname(os.path.dirname(__file__))) is /app
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEST_SQLITE_DB_DIR_ABSOLUTE = os.path.join(PROJECT_ROOT, TEST_DB_SUBDIR)
TEST_SQLITE_FILE_NAME = "test_transcription_jobs.db"
TEST_DATABASE_PATH = os.path.join(TEST_SQLITE_DB_DIR_ABSOLUTE, TEST_SQLITE_FILE_NAME)
TEST_DATABASE_URL = f"sqlite:///{TEST_DATABASE_PATH}"

logger.info(f"Pytest: Test database URL: {TEST_DATABASE_URL}")

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment_session():
    logger.info(f"Pytest session setup: Ensuring test DB directory {TEST_SQLITE_DB_DIR_ABSOLUTE} is clean.")
    if os.path.exists(TEST_SQLITE_DB_DIR_ABSOLUTE):
        shutil.rmtree(TEST_SQLITE_DB_DIR_ABSOLUTE)
    os.makedirs(TEST_SQLITE_DB_DIR_ABSOLUTE, exist_ok=True)
    try:
        os.chmod(TEST_SQLITE_DB_DIR_ABSOLUTE, 0o777) # Ensure writable
        logger.info(f"Pytest: Created and chmodded test DB directory: {TEST_SQLITE_DB_DIR_ABSOLUTE}")
    except Exception as e:
        logger.warning(f"Pytest: Could not chmod test DB directory {TEST_SQLITE_DB_DIR_ABSOLUTE}: {e}")

    yield

    logger.info(f"Pytest session teardown: Cleaning up test DB directory {TEST_SQLITE_DB_DIR_ABSOLUTE}.")
    if os.path.exists(TEST_SQLITE_DB_DIR_ABSOLUTE):
        shutil.rmtree(TEST_SQLITE_DB_DIR_ABSOLUTE, ignore_errors=True)
        logger.info(f"Pytest: Cleaned up test DB directory: {TEST_SQLITE_DB_DIR_ABSOLUTE}")


@pytest.fixture(scope="function")
def engine_test():
    logger.debug(f"Creating test engine for URL: {TEST_DATABASE_URL}")
    _engine = create_engine(TEST_DATABASE_URL, echo=False, connect_args={"check_same_thread": False})

    @event.listens_for(_engine, "connect")
    def set_sqlite_pragma_test(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA busy_timeout = 5000;")
            cursor.execute("PRAGMA synchronous = NORMAL;")
            cursor.close()
        except Exception as e:
            # Use print as logger might not be fully configured in this specific context/thread
            print(f"Pytest Warning: Failed to set PRAGMA for test SQLite: {e}")

    SQLModel.metadata.create_all(_engine)
    yield _engine
    SQLModel.metadata.drop_all(_engine)
    _engine.dispose()
    logger.debug(f"Test engine disposed and tables dropped for {TEST_DATABASE_URL}")

    # Clean up database files specifically for this test function's DB
    db_files_to_remove = [TEST_DATABASE_PATH, f"{TEST_DATABASE_PATH}-shm", f"{TEST_DATABASE_PATH}-wal"]
    for f_path in db_files_to_remove:
        if os.path.exists(f_path):
            try:
                os.remove(f_path)
                logger.debug(f"Pytest: Removed test DB file {f_path}")
            except OSError as e:
                logger.warning(f"Pytest: Could not remove test DB file {f_path}: {e}")

    # Attempt to remove the directory if it's empty and it's the specific test DB dir
    if os.path.exists(TEST_SQLITE_DB_DIR_ABSOLUTE) and not os.listdir(TEST_SQLITE_DB_DIR_ABSOLUTE):
        try:
            # Only remove if it's the one we created for this test run, not /app
            if TEST_DB_SUBDIR in TEST_SQLITE_DB_DIR_ABSOLUTE:
                 shutil.rmtree(TEST_SQLITE_DB_DIR_ABSOLUTE, ignore_errors=True)
                 logger.debug(f"Pytest: Removed empty test DB directory {TEST_SQLITE_DB_DIR_ABSOLUTE}")
        except OSError: # pragma: no cover
            pass


@pytest.fixture(scope="function")
def session(engine_test: Engine) -> Generator[Session, None, None]:
    with Session(engine_test) as _session:
        yield _session
        # Rollback is good for safety, though function scope often means new DB anyway
        _session.rollback()
        _session.close()


@pytest_asyncio.fixture
async def client(session: Session, engine_test: Engine) -> AsyncGenerator[AsyncClient, None]:
    def get_test_session_override() -> Generator[Session, None, None]:
        yield session

    original_get_session_override = main_app.dependency_overrides.get(main_get_session)
    main_app.dependency_overrides[main_get_session] = get_test_session_override

    # Patch the engine used by lifespan's create_db_and_tables
    from backend import database as main_app_database
    original_main_engine = main_app_database.engine
    original_database_path = main_app_database.DATABASE_PATH
    original_sqlite_db_dir = main_app_database.SQLITE_DB_DIR

    main_app_database.engine = engine_test # Point main app's DB operations to test engine
    main_app_database.DATABASE_PATH = TEST_DATABASE_PATH
    main_app_database.SQLITE_DB_DIR = TEST_SQLITE_DB_DIR_ABSOLUTE

    # Manually trigger lifespan events for the test client context
    async with main_app.router.lifespan_context(main_app):
        async with AsyncClient(app=main_app, base_url="http://test") as ac:
            yield ac

    # Restore original state
    main_app_database.engine = original_main_engine
    main_app_database.DATABASE_PATH = original_database_path
    main_app_database.SQLITE_DB_DIR = original_sqlite_db_dir

    if original_get_session_override:
        main_app.dependency_overrides[main_get_session] = original_get_session_override
    else:
        if main_get_session in main_app.dependency_overrides:
            del main_app.dependency_overrides[main_get_session]


@pytest.fixture(scope="function")
def clean_temp_dirs():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')) # /app

    # These are directories used by the main application logic
    # backend.main.TEMP_UPLOAD_DIR -> /app/temp_uploads
    # backend.transcribe.RESULTS_DIR -> /app/transcription_results (relative to where transcribe.py is, so /app/backend/transcription_results)

    # Corrected paths relative to project_root (/app)
    temp_upload_dir_main = os.path.join(project_root, "temp_uploads")
    results_dir_transcribe = os.path.join(project_root, "transcription_results") # This was /app/backend/transcription_results, should be /app/transcription_results as per transcribe.py

    dirs_to_manage = [temp_upload_dir_main, results_dir_transcribe]

    for d in dirs_to_manage:
        if os.path.exists(d):
            shutil.rmtree(d)
        os.makedirs(d, exist_ok=True)
        try:
            os.chmod(d, 0o777) # Ensure writable for tests
            logger.info(f"Pytest: Cleaned and ensured directory {d}")
        except Exception as e:
            logger.warning(f"Pytest: Could not chmod directory {d}: {e}")

    yield

    for d in dirs_to_manage:
        if os.path.exists(d):
            try:
                shutil.rmtree(d)
                logger.info(f"Pytest: Cleaned up test directory {d}")
            except Exception as e:
                logger.warning(f"Pytest: Could not remove directory {d} during cleanup: {e}")
