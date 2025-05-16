import os
import json
import sqlite3
import uuid
from typing import Dict, Optional, Any, List, Union
import aiosqlite
import threading
import logging
from datetime import datetime, timezone

from database_layer.base_db_handler import BaseDBHandler

logger = logging.getLogger(__name__)

class SqliteHandler():
    """
    SQLite implementation of the database handler interface.
    Uses aiosqlite for async database operations.
    """
    
    _local = threading.local()  # Thread-local storage for connection

    def __init__(self, db_url: str):
        """
        Initialize the SQLite handler with a database URL.
        
        Args:
            db_url: SQLite database URL (e.g., 'sqlite:///./research_agent.db')
        """
        # Extract file path from the URL
        if db_url.startswith('sqlite:///'):
            self.db_path = db_url.replace('sqlite:///', '')
        elif db_url.startswith('sqlite+aiosqlite:///'):
            self.db_path = db_url.replace('sqlite+aiosqlite:///', '')
        else:
            self.db_path = db_url
            
        # Ensure the directory exists
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        
        self.connection = None
        logger.info(f"SQLiteHandler initialized with db_path: {self.db_path}")
    
    def _get_conn(self) -> sqlite3.Connection:
        """Gets or creates a database connection for the current thread."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            try:
                logger.info(f"Creating new SQLite connection for thread {threading.current_thread().name}")
                self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False) # check_same_thread=False needed for multi-threaded access like FastAPI's threadpool
                self._local.conn.row_factory = sqlite3.Row # Return rows as dict-like objects
            except sqlite3.Error as e:
                logger.error(f"Error connecting to database {self.db_path}: {e}", exc_info=True)
                raise
        return self._local.conn

    def close_connection(self):
        """Closes the connection for the current thread."""
        if hasattr(self._local, 'conn') and self._local.conn is not None:
            logger.debug(f"Closing SQLite connection for thread {threading.current_thread().name}")
            self._local.conn.close()
            self._local.conn = None

    def execute_query(self, query: str, params: tuple = (), commit: bool = False) -> Optional[sqlite3.Cursor]:
        """Executes a given SQL query."""
        conn = self._get_conn()
        cursor = None
        try:
            cursor = conn.cursor()
            logger.debug(f"Executing query: {query} with params: {params}")
            cursor.execute(query, params)
            if commit:
                conn.commit()
                logger.debug("Query committed.")
            return cursor
        except sqlite3.Error as e:
            logger.error(f"Database error executing query '{query}' with params {params}: {e}", exc_info=True)
            if conn:
                conn.rollback() # Rollback on error
            # We might want to close the connection on severe errors, but let's retry first.
            # self.close_connection() # Force reconnect on next call
            raise  # Re-raise the exception after logging and rollback

    def fetch_one(self, query: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        """Fetches a single record."""
        cursor = self.execute_query(query, params)
        if cursor:
            return cursor.fetchone()
        return None

    def fetch_all(self, query: str, params: tuple = ()) -> List[sqlite3.Row]:
        """Fetches all records."""
        cursor = self.execute_query(query, params)
        if cursor:
            return cursor.fetchall()
        return []

    def get_schema_version(self) -> int:
        """Gets the current schema version from the database."""
        # Implementation depends on how versioning is managed (e.g., a specific table)
        # Placeholder implementation
        query = "PRAGMA user_version;"
        result = self.fetch_one(query)
        return result[0] if result else 0

    def set_schema_version(self, version: int):
        """Sets the schema version in the database."""
        # Placeholder implementation
        query = f"PRAGMA user_version = {version};"
        self.execute_query(query, commit=True)

    def apply_schema(self, schema_sql: str):
        """Applies the schema SQL script."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            logger.info("Applying database schema...")
            cursor.executescript(schema_sql)
            conn.commit()
            logger.info("Database schema applied successfully.")
        except sqlite3.Error as e:
            logger.error(f"Error applying schema: {e}", exc_info=True)
            conn.rollback()
            raise

    async def connect(self) -> None:
        """Establish a connection to the SQLite database."""
        self.connection = await aiosqlite.connect(self.db_path)
        # Enable foreign keys
        await self.connection.execute("PRAGMA foreign_keys = ON")
        # Use Row factory to get column names in results
        self.connection.row_factory = aiosqlite.Row
    
    async def disconnect(self) -> None:
        """Close the SQLite database connection."""
        if self.connection:
            await self.connection.close()
            self.connection = None
    
    async def initialize_schema(self) -> None:
        logger.info("****** this is being called, something is wrong here")
        """Initialize the database schema (create tables if they don't exist)."""
        if not self.connection:
            await self.connect()
            
        # Create jobs table
        await self.connection.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            user_query TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            report_path TEXT
        )
        """)
        
        # Create tasks table
        await self.connection.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            task_type TEXT NOT NULL,
            description TEXT NOT NULL,
            parameters TEXT,  -- JSON serialized parameters
            status TEXT NOT NULL,
            result TEXT,  -- JSON serialized result
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
        )
        """)
        
        # Create users table for authentication
        await self.connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        await self.connection.commit()
    
    async def get_job_by_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a job by its ID."""
        if not self.connection:
            await self.connect()
            
        async with self.connection.execute(
            "SELECT * FROM jobs WHERE id = ?", (job_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    async def create_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new job in the database."""
        if not self.connection:
            await self.connect()
            
        # Generate a UUID if not provided
        if 'id' not in job_data:
            job_data['id'] = str(uuid.uuid4())
            
        # Set default status if not provided
        if 'status' not in job_data:
            job_data['status'] = 'PENDING'
            
        # Extract fields
        job_id = job_data['id']
        user_query = job_data['user_query']
        status = job_data['status']
        report_path = job_data.get('report_path')
        
        # Insert the job
        await self.connection.execute(
            """
            INSERT INTO jobs (job_id, user_query, status, report_path)
            VALUES (?, ?, ?, ?)
            """,
            (job_id, user_query, status, report_path)
        )
        await self.connection.commit()
        
        # Return the created job
        return await self.get_job_by_id(job_id)
    
    async def update_job_status(self, job_id: str, status: str, detail: Optional[str] = None) -> bool:
        """Update the status of a job and optionally set error message."""
        if not self.connection:
            await self.connect()
            
        try:
            if detail:
                await self.connection.execute(
                    """
                    UPDATE jobs 
                    SET status = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE job_id = ?
                    """,
                    (status, detail, job_id)
                )
            else:
                await self.connection.execute(
                    """
                    UPDATE jobs 
                    SET status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE job_id = ?
                    """,
                    (status, job_id)
                )
            await self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to update job status: {e}")
            return False
    
    async def get_task_by_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a task by its ID."""
        if not self.connection:
            await self.connect()
            
        async with self.connection.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                task_dict = dict(row)
                # Parse JSON fields
                if task_dict.get('parameters'):
                    task_dict['parameters'] = json.loads(task_dict['parameters'])
                if task_dict.get('result'):
                    task_dict['result'] = json.loads(task_dict['result'])
                return task_dict
            return None
    
    async def create_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new task in the database."""
        if not self.connection:
            await self.connect()
            
        # Generate a UUID if not provided
        if 'id' not in task_data:
            task_data['id'] = str(uuid.uuid4())
            
        # Set default status if not provided
        if 'status' not in task_data:
            task_data['status'] = 'PENDING'
            
        # Extract fields
        task_id = task_data['id']
        job_id = task_data['job_id']
        task_type = task_data['task_type']
        description = task_data['description']
        status = task_data['status']
        
        # Serialize JSON fields
        parameters = task_data.get('parameters')
        if parameters:
            parameters = json.dumps(parameters)
            
        result = task_data.get('result')
        if result:
            result = json.dumps(result)
        
        # Insert the task
        await self.connection.execute(
            """
            INSERT INTO tasks (id, job_id, task_type, description, parameters, status, result)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (task_id, job_id, task_type, description, parameters, status, result)
        )
        await self.connection.commit()
        
        # Return the created task
        return await self.get_task_by_id(task_id)
    
    async def update_task_status(self, task_id: str, status: str, result: Optional[Any] = None) -> bool:
        """Update the status and optionally the result of a task."""
        if not self.connection:
            await self.connect()
            
        try:
            # Serialize result if provided
            result_json = None
            if result is not None:
                result_json = json.dumps(result)
                
            if result_json:
                await self.connection.execute(
                    """
                    UPDATE tasks 
                    SET status = ?, result = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (status, result_json, task_id)
                )
            else:
                await self.connection.execute(
                    """
                    UPDATE tasks 
                    SET status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (status, task_id)
                )
                
            await self.connection.commit()
            return True
        except Exception:
            return False
    
    async def get_tasks_by_job_id(self, job_id: str) -> List[Dict[str, Any]]:
        """Retrieve all tasks associated with a job."""
        if not self.connection:
            await self.connect()
            
        tasks = []
        async with self.connection.execute(
            "SELECT * FROM tasks WHERE job_id = ? ORDER BY created_at ASC", (job_id,)
        ) as cursor:
            async for row in cursor:
                task_dict = dict(row)
                # Parse JSON fields
                if task_dict.get('parameters'):
                    task_dict['parameters'] = json.loads(task_dict['parameters'])
                if task_dict.get('result'):
                    task_dict['result'] = json.loads(task_dict['result'])
                tasks.append(task_dict)
                
        return tasks 

    # --- Job Operations ---

    def create_job(self, id: str, user_query: str) -> None:
        """Creates a new job record."""
        now = datetime.now(timezone.utc).isoformat()
        query = """
            INSERT INTO jobs (job_id, user_query, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """
        params = (id, user_query, "RUNNING", now, now)
        self.execute_query(query, params, commit=True)
        logger.info(f"Created new job with ID: {id}")

    def update_job_status(self, job_id: str, status: str, error_message: Optional[str] = None) -> None:
        """Updates the status and error message of a job."""
        now = datetime.now(timezone.utc).isoformat()
        query = """
            UPDATE jobs
            SET status = ?, error_message = ?, updated_at = ?
            WHERE job_id = ?
        """
        params = (status, error_message, now, job_id)
        self.execute_query(query, params, commit=True)
        logger.info(f"Updated job {job_id} status to {status}")

    def update_job_report_path(self, job_id: str, report_path: str) -> None:
        """Updates the final report path for a completed job."""
        now = datetime.now(timezone.utc).isoformat()
        query = """
            UPDATE jobs
            SET final_report_path = ?, updated_at = ?
            WHERE job_id = ?
        """
        params = (report_path, now, job_id)
        self.execute_query(query, params, commit=True)
        logger.info(f"Updated job {job_id} report path to {report_path}")

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a job by its ID."""
        query = "SELECT * FROM jobs WHERE job_id = ?"
        row = self.fetch_one(query, (job_id,))
        return dict(row) if row else None

    def get_all_jobs(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Retrieves all jobs, ordered by creation date descending."""
        query = "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?"
        rows = self.fetch_all(query, (limit, offset))
        return [dict(row) for row in rows]

    # --- Task Operations ---

    def create_task(self, task_id: str, job_id: str, sequence_order: int, task_type: str, description: str, parameters: Optional[Dict[str, Any]]) -> None:
        """Creates a new task record associated with a job."""
        now = datetime.now(timezone.utc).isoformat()
        params_json = json.dumps(parameters) if parameters else None
        query = """
            INSERT INTO tasks (task_id, job_id, sequence_order, task_type, description, parameters, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (task_id, job_id, sequence_order, task_type, description, params_json, "PENDING", now, now)
        self.execute_query(query, params, commit=True)
        logger.info(f"Created new task {task_id} for job {job_id}")

    def update_task_status(self, task_id: str, status: str, error_message: Optional[str] = None) -> None:
        """Updates the status and error message of a task."""
        now = datetime.now(timezone.utc).isoformat()
        query = """
            UPDATE tasks
            SET status = ?, error_message = ?, updated_at = ?
            WHERE task_id = ?
        """
        params = (status, error_message, now, task_id)
        self.execute_query(query, params, commit=True)
        logger.info(f"Updated task {task_id} status to {status}")

    def update_task_result(self, task_id: str, result: Any) -> None:
        """Updates the result of a completed task."""
        now = datetime.now(timezone.utc).isoformat()
        result_json = json.dumps(result) # Ensure result is serializable
        query = """
            UPDATE tasks
            SET result = ?, updated_at = ?
            WHERE task_id = ?
        """
        params = (result_json, now, task_id)
        self.execute_query(query, params, commit=True)
        logger.info(f"Stored result for task {task_id}")

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a task by its ID."""
        query = "SELECT * FROM tasks WHERE task_id = ?"
        row = self.fetch_one(query, (task_id,))
        if row:
            task_dict = dict(row)
            # Deserialize JSON fields
            if task_dict.get('parameters'):
                try:
                    task_dict['parameters'] = json.loads(task_dict['parameters'])
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"Could not decode parameters JSON for task {task_id}: {task_dict.get('parameters')}")
                    task_dict['parameters'] = None # Or handle as error
            if task_dict.get('result'):
                try:
                    task_dict['result'] = json.loads(task_dict['result'])
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"Could not decode result JSON for task {task_id}: {task_dict.get('result')}")
                    task_dict['result'] = None # Or handle as error
            return task_dict
        return None

    def get_tasks_by_job_id(self, job_id: str) -> List[Dict[str, Any]]:
        """Retrieves all tasks for a given job ID, ordered by sequence."""
        query = "SELECT * FROM tasks WHERE job_id = ? ORDER BY sequence_order ASC"
        rows = self.fetch_all(query, (job_id,))
        tasks = []
        for row in rows:
            task_dict = dict(row)
            # Deserialize JSON fields
            if task_dict.get('parameters'):
                 try:
                    task_dict['parameters'] = json.loads(task_dict['parameters'])
                 except (json.JSONDecodeError, TypeError):
                    logger.warning(f"Could not decode parameters JSON for task {task_dict['task_id']}: {task_dict.get('parameters')}")
                    task_dict['parameters'] = None
            # Result is often large, maybe don't load/deserialize it here unless needed?
            # Let's deserialize for now for consistency, optimize later if needed.
            if task_dict.get('result'):
                try:
                    task_dict['result'] = json.loads(task_dict['result'])
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"Could not decode result JSON for task {task_dict['task_id']}: {task_dict.get('result')}")
                    task_dict['result'] = None
            tasks.append(task_dict)
        return tasks

    def get_next_pending_task(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves the next PENDING task for a job, ordered by sequence."""
        query = """
            SELECT * FROM tasks
            WHERE job_id = ? AND status = 'PENDING'
            ORDER BY sequence_order ASC
            LIMIT 1
        """
        row = self.fetch_one(query, (job_id,))
        if row:
            task_dict = dict(row)
            # Deserialize JSON fields
            if task_dict.get('parameters'):
                 try:
                    task_dict['parameters'] = json.loads(task_dict['parameters'])
                 except (json.JSONDecodeError, TypeError):
                    logger.warning(f"Could not decode parameters JSON for task {task_dict['task_id']}: {task_dict.get('parameters')}")
                    task_dict['parameters'] = None
            # Result should be null for pending tasks
            return task_dict
        return None

    def get_completed_tasks_by_type(self, job_id: str, task_type: str) -> List[Dict[str, Any]]:
        """Retrieves all completed tasks for a job, filtered by type."""
        query = """
            SELECT * FROM tasks
            WHERE job_id = ? AND status = 'COMPLETED' AND task_type = ?
            ORDER BY sequence_order ASC
        """
        rows = self.fetch_all(query, (job_id, task_type))
        tasks = []
        for row in rows:
            task_dict = dict(row)
            # Deserialize JSON fields
            if task_dict.get('parameters'):
                 try:
                    task_dict['parameters'] = json.loads(task_dict['parameters'])
                 except (json.JSONDecodeError, TypeError):
                     logger.warning(f"Could not decode parameters JSON for task {task_dict['task_id']}: {task_dict.get('parameters')}")
                     task_dict['parameters'] = None
            if task_dict.get('result'):
                try:
                    task_dict['result'] = json.loads(task_dict['result'])
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"Could not decode result JSON for task {task_dict['task_id']}: {task_dict.get('result')}")
                    task_dict['result'] = None
            tasks.append(task_dict)
        return tasks


    def count_tasks_by_status(self, job_id: str, status: str) -> int:
        """Counts the number of tasks for a job with a specific status."""
        query = "SELECT COUNT(*) FROM tasks WHERE job_id = ? AND status = ?"
        result = self.fetch_one(query, (job_id, status))
        return result[0] if result else 0

    # Potentially add cleanup methods, e.g., delete old jobs/tasks
# // ... existing code ... (rest of the file remains the same for now) 