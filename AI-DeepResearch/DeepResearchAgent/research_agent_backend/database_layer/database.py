import os
import json
import uuid
import logging
import aiosqlite
from typing import Dict, Optional, Any, List, Union
from contextlib import asynccontextmanager
from pathlib import Path
import asyncio
from fastapi import Request # To potentially get access to run_in_threadpool

from .sqlite_handler import SqliteHandler # Use the modified synchronous handler
from .base_db_handler import BaseDBHandler
from config import settings # Assuming settings has DB_PATH

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "research_agent.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql" #removed the hardcoded path to make it reusable across other system deployments

class Database:
    """Manages database connections and initialization."""

    _instance: Optional['Database'] = None
    _lock = asyncio.Lock()

    def __init__(self, db_path: str):
        if not hasattr(self, 'initialized'): # Prevent re-initialization
            self.db_path = db_path
            # Use the synchronous SqliteHandler
            self.handler: BaseDBHandler = SqliteHandler(db_path)
            self.initialized = False # Use a flag to track initialization
            logger.info(f"Database instance created with path: {db_path}")

    # Making __new__ async is tricky, using an async factory method instead
    @classmethod
    async def get_instance(cls, db_path: Optional[str] = None) -> 'Database':
        """Gets the singleton Database instance, initializing it asynchronously if needed."""
        if cls._instance is None:
            async with cls._lock:
                # Double-check locking
                if cls._instance is None:
                    if db_path is None:
                        # Use path from settings if not provided
                        db_path = settings.DB_PATH
                        logger.info(f"Database path not provided, using settings: {db_path}")
                    if not db_path:
                        raise ValueError("Database path must be provided either directly or via settings.")

                    cls._instance = cls(db_path)
                    # Initialization needs to be awaited
                    await cls._instance._initialize_database()
        elif not cls._instance.initialized:
             async with cls._lock: # Ensure initialization completes if accessed concurrently
                 if not cls._instance.initialized:
                      await cls._instance._initialize_database()

        return cls._instance

    async def _initialize_database(self):
        """Initializes the database by applying the schema if necessary."""
        if self.initialized:
            logger.debug("Database already initialized.")
            return

        try:
            # Load schema SQL
            if not SCHEMA_PATH.is_file():
                logger.error(f"Schema file not found at {SCHEMA_PATH}")
                raise FileNotFoundError(f"Schema file not found at {SCHEMA_PATH}")

            with open(SCHEMA_PATH, 'r') as f:
                schema_sql = f.read()

            # Apply schema using the handler (synchronous call wrapped in threadpool)
            # Note: Applying schema is typically a startup operation, so blocking might be acceptable,
            # but using threadpool is safer if this runs concurrently with other async tasks.
            # We need access to run_in_threadpool, which is usually via FastAPI request or asyncio.to_thread
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self.handler.apply_schema, schema_sql)
            # Alternative using asyncio.to_thread (Python 3.9+)
            # await asyncio.to_thread(self.handler.apply_schema, schema_sql)

            self.initialized = True
            logger.info("Database initialization completed successfully.")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}", exc_info=True)
            # Reset instance if initialization failed to allow retry?
            # Database._instance = None # Or handle differently
            raise

    async def close(self):
        """Closes the database connection (delegates to handler, wrapped)."""
        if self.handler and hasattr(self.handler, 'close_connection'):
            logger.info("Closing database connection...")
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self.handler.close_connection)
            # await asyncio.to_thread(self.handler.close_connection)
            logger.info("Database connection closed.")
        self.initialized = False # Mark as not initialized after closing

    # --- Convenience methods to access handler (wrapped for async safety) ---
    # These methods demonstrate how to call the synchronous handler methods from async code

    async def execute_query(self, query: str, params: tuple = (), commit: bool = False):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.handler.execute_query, query, params, commit)

    async def fetch_one(self, query: str, params: tuple = ()):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.handler.fetch_one, query, params)

    async def fetch_all(self, query: str, params: tuple = ()):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.handler.fetch_all, query, params)

    # --- Job Operations (Async Wrappers) ---
    async def create_job(self, job_id: str, user_query: str):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.handler.create_job, job_id, user_query)

    async def update_job_status(self, job_id: str, status: str, detail: Optional[str] = None):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.handler.update_job_status, job_id, status, detail)

    async def update_job_report_path(self, job_id: str, report_path: str):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.handler.update_job_report_path, job_id, report_path)

    async def get_job(self, job_id: str):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.handler.get_job, job_id)

    async def get_all_jobs(self, limit: int = 100, offset: int = 0):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.handler.get_all_jobs, limit, offset)

    # --- Task Operations (Async Wrappers) ---
    async def create_task(self, task_id: str, job_id: str, sequence_order: int, task_type: str, description: str, parameters: Optional[Dict[str, Any]]):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.handler.create_task, task_id, job_id, sequence_order, task_type, description, parameters)

    async def update_task_status(self, task_id: str, status: str, error_message: Optional[str] = None):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.handler.update_task_status, task_id, status, error_message)

    async def update_task_result(self, task_id: str, result: Any):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.handler.update_task_result, task_id, result)

    async def get_task(self, task_id: str):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.handler.get_task, task_id)

    async def get_tasks_by_job_id(self, job_id: str):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.handler.get_tasks_by_job_id, job_id)

    async def get_next_pending_task(self, job_id: str):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.handler.get_next_pending_task, job_id)

    async def get_completed_tasks_by_type(self, job_id: str, task_type: str):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.handler.get_completed_tasks_by_type, job_id, task_type)

    async def count_tasks_by_status(self, job_id: str, status: str):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.handler.count_tasks_by_status, job_id, status)

