import os
import json
import sqlite3
import uuid
from typing import Dict, Optional, Any, List, Union
import aiosqlite

from research_agent_backend.database_layer.base_db_handler import BaseDBHandler


class SQLiteHandler(BaseDBHandler):
    """
    SQLite implementation of the database handler interface.
    Uses aiosqlite for async database operations.
    """
    
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
            INSERT INTO jobs (id, user_query, status, report_path)
            VALUES (?, ?, ?, ?)
            """,
            (job_id, user_query, status, report_path)
        )
        await self.connection.commit()
        
        # Return the created job
        return await self.get_job_by_id(job_id)
    
    async def update_job_status(self, job_id: str, status: str) -> bool:
        """Update the status of a job."""
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
        except Exception:
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