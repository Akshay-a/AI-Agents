import os
import json
import uuid
import logging
import aiosqlite
from typing import Dict, Optional, Any, List, Union
from contextlib import asynccontextmanager

from database_layer.base_db_handler import BaseDBHandler

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "research_agent.db"
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")

class Database(BaseDBHandler):
    """
    Implementation of the database handler interface using SQLite.
    Uses aiosqlite for async database operations.
    """
    
    def __init__(self, connection_string: str):
        
        # Extract file path from the connection string
        if connection_string.startswith('sqlite:///'):
            self.db_path = connection_string.replace('sqlite:///', '')
        elif connection_string.startswith('sqlite+aiosqlite:///'):
            self.db_path = connection_string.replace('sqlite+aiosqlite:///', '')
        else:
            self.db_path = connection_string
            
        
        db_dir = os.path.dirname(os.path.abspath(self.db_path))
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"Created database directory: {db_dir}")
            
        self.connection = None
        logger.info(f"Database initialized with path: {self.db_path}")
    
    async def connect(self) -> None:
        """Establish a connection to the database."""
        try:
            self.connection = await aiosqlite.connect(self.db_path)
            # Enable foreign keys
            await self.connection.execute("PRAGMA foreign_keys = ON")
            # Use Row factory to get column names in results
            self.connection.row_factory = aiosqlite.Row
            logger.info(f"Database connection established to {self.db_path}")
        except Exception as e:
            logger.error(f"Error connecting to database {self.db_path}: {e}")
            raise
    
    async def disconnect(self) -> None:
        if self.connection:
            await self.connection.close()
            self.connection = None
            logger.info("Database connection closed.")
    
    async def initialize_schema(self) -> None:
        if not self.connection:
            await self.connect()
        
        try:
            # Read schema from SQL file
            with open(SCHEMA_PATH, 'r') as f:
                schema_sql = f.read()
                
            # Execute schema creation script
            await self.connection.executescript(schema_sql)
            await self.connection.commit()
            logger.info(f"Database schema initialized successfully from {SCHEMA_PATH}.")
        except Exception as e:
            logger.error(f"Error initializing database schema: {e}")
            raise
    
    async def get_job_by_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a job by its ID.
        
        Args:
            job_id: The unique identifier of the job
            
        Returns:
            The job data as a dictionary, or None if not found
        """
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
        """
        Create a new job in the database.
        
        Args:
            job_data: A dictionary containing the job data
            
        Returns:
            The created job data including any generated IDs
        """
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
            INSERT INTO jobs (id, user_query, status, final_report_path)
            VALUES (?, ?, ?, ?)
            """,
            (job_id, user_query, status, report_path)
        )
        await self.connection.commit()
        
        # Return the created job
        return await self.get_job_by_id(job_id)
    
    async def update_job_status(self, job_id: str, status: str) -> bool:
        """
        Update the status of a job.
        
        Args:
            job_id: The unique identifier of the job
            status: The new status value
            
        Returns:
            True if the update was successful, False otherwise
        """
        if not self.connection:
            await self.connect()
            
        try:
            await self.connection.execute(
                """
                UPDATE jobs 
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, job_id)
            )
            await self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating job status: {e}")
            return False
    
    async def get_task_by_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a task by its ID.
        
        Args:
            task_id: The unique identifier of the task
            
        Returns:
            The task data as a dictionary, or None if not found
        """
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
        """
        Create a new task in the database.
        
        Args:
            task_data: A dictionary containing the task data
            
        Returns:
            The created task data including any generated IDs
        """
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
        sequence_order = task_data.get('sequence_order', 0)
        
        # Serialize JSON fields
        parameters = json.dumps(task_data.get('parameters', {})) if task_data.get('parameters') else None
        
        # Insert the task
        await self.connection.execute(
            """
            INSERT INTO tasks (id, job_id, task_type, description, parameters, status, sequence_order)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (task_id, job_id, task_type, description, parameters, status, sequence_order)
        )
        await self.connection.commit()
        
        # Return the created task
        return await self.get_task_by_id(task_id)
    
    async def update_task_status(self, task_id: str, status: str, result: Optional[Any] = None) -> bool:
        """
        Update the status and optionally the result of a task.
        
        Args:
            task_id: The unique identifier of the task
            status: The new status value
            result: Optional result data for completed tasks
            
        Returns:
            True if the update was successful, False otherwise
        """
        if not self.connection:
            await self.connect()
            
        try:
            # Serialize result if provided
            result_json = json.dumps(result) if result is not None else None
            
            await self.connection.execute(
                """
                UPDATE tasks 
                SET status = ?, result = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, result_json, task_id)
            )
            await self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating task status: {e}")
            return False
    
    async def get_tasks_by_job_id(self, job_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all tasks associated with a job.
        
        Args:
            job_id: The unique identifier of the job
            
        Returns:
            A list of task dictionaries
        """
        if not self.connection:
            await self.connect()
            
        tasks = []
        async with self.connection.execute(
            "SELECT * FROM tasks WHERE job_id = ? ORDER BY sequence_order ASC", (job_id,)
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