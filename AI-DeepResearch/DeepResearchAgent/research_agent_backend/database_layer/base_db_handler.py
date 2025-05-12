from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, List, Union


class BaseDBHandler(ABC):
    """
    Abstract base class defining the interface for database interactions.
    All concrete database handlers must implement these methods.
    """
    
    @abstractmethod
    async def connect(self) -> None:
        """Establish a connection to the database."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close the database connection."""
        pass
    
    @abstractmethod
    async def initialize_schema(self) -> None:
        """Initialize the database schema (create tables if they don't exist)."""
        pass
    
    @abstractmethod
    async def get_job_by_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a job by its ID.
        
        Args:
            job_id: The unique identifier of the job
            
        Returns:
            The job data as a dictionary, or None if not found
        """
        pass
    
    @abstractmethod
    async def create_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new job in the database.
        
        Args:
            job_data: A dictionary containing the job data
            
        Returns:
            The created job data including any generated IDs
        """
        pass
    
    @abstractmethod
    async def update_job_status(self, job_id: str, status: str) -> bool:
        """
        Update the status of a job.
        
        Args:
            job_id: The unique identifier of the job
            status: The new status value
            
        Returns:
            True if the update was successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_task_by_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a task by its ID.
        
        Args:
            task_id: The unique identifier of the task
            
        Returns:
            The task data as a dictionary, or None if not found
        """
        pass
    
    @abstractmethod
    async def create_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new task in the database.
        
        Args:
            task_data: A dictionary containing the task data
            
        Returns:
            The created task data including any generated IDs
        """
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    async def get_tasks_by_job_id(self, job_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all tasks associated with a job.
        
        Args:
            job_id: The unique identifier of the job
            
        Returns:
            A list of task dictionaries
        """
        pass 