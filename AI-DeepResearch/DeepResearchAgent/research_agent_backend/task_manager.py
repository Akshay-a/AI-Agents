import logging
import uuid
from typing import Dict, Any, List, Optional, Set
from collections import defaultdict
import asyncio
import json # For potential result serialization/deserialization if not handled by DB layer

from models import Task, TaskStatus, TaskType, TaskInputData
# Import the Database manager and potentially the models if needed for type hints
from database_layer.database import Database

logger = logging.getLogger(__name__)

class TaskManager:
    """Manages the lifecycle and state of tasks within research jobs using a database."""
    #This now has been migrated to use DB for persistence across restarts and also to enable viewing history 
    def __init__(self, database: Database):
        """Initialize the TaskManager with a database connection manager."""
        self.db = database
        # In-memory storage is removed
        # self.tasks: Dict[str, Task] = {}
        # self.task_results: Dict[str, Any] = {}
        # self.job_tasks: Dict[str, List[str]] = defaultdict(list)
        logger.info("TaskManager initialized with Database instance.")

    async def add_task(
        self,
        job_id: str,
        sequence_order: int,
        task_input: TaskInputData,
    ) -> Task:
        """Adds a new task to the database and returns the corresponding Task model."""
        task_id = str(uuid.uuid4())
        new_task = Task(
            task_id=task_id,
            job_id=job_id,
            sequence_order=sequence_order,
            task_type=task_input.task_type,
            description=task_input.description,
            parameters=task_input.parameters,
            status=TaskStatus.PENDING # Ensure it starts as PENDING
            # created_at and updated_at are handled by default_factory in Task model or DB trigger
        )

        try:
            await self.db.create_task(
                task_id=new_task.task_id,
                job_id=new_task.job_id,
                sequence_order=new_task.sequence_order,
                task_type=new_task.task_type.value, # Pass enum value
                description=new_task.description,
                parameters=new_task.parameters # Pass the dict directly, handler serializes
            )
            logger.info(f"Added task {new_task.task_id} for job {job_id} to database.")
            # Return the Pydantic model instance we created
            return new_task
        except Exception as e:
            logger.error(f"Failed to add task {task_id} for job {job_id} to DB: {e}", exc_info=True)
            # Depending on desired behavior, maybe raise or return None/error indicator
            raise # Re-raise the exception for the caller (Orchestrator) to handle

    async def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        error_message: Optional[str] = None
    ) -> None:
        """Updates the status and optionally the error message of a task in the database."""
        try:
            await self.db.update_task_status(task_id, status.value, error_message)
            logger.debug(f"Updated task {task_id} status to {status.value} in database.")
        except Exception as e:
            logger.error(f"Failed to update status for task {task_id} in DB: {e}", exc_info=True)
            raise

    async def store_result(self, task_id: str, result: Any) -> None:
        """Stores the result of a completed task in the database."""
        try:
            # The db handler method should handle JSON serialization
            await self.db.update_task_result(task_id, result)
            logger.debug(f"Stored result for task {task_id} in database.")
        except Exception as e:
            logger.error(f"Failed to store result for task {task_id} in DB: {e}", exc_info=True)
            raise

    async def get_task(self, task_id: str) -> Optional[Task]:
        """Retrieves a single task from the database by its ID."""
        try:
            task_data = await self.db.get_task(task_id)
            if task_data:
                # Convert dict from DB back to Pydantic model
                return Task(**task_data)
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve task {task_id} from DB: {e}", exc_info=True)
            return None # Or raise?

    async def get_result(self, task_id: str) -> Optional[Any]:
        """Retrieves the result of a specific task from the database."""
        task = await self.get_task(task_id) # Reuse get_task which handles deserialization
        if task:
            return task.result
        # We could also add a specific db.get_task_result method if results are large
        # and we want to avoid fetching the full task object.
        # For now, reusing get_task is simpler.
        return None

    async def get_all_tasks_for_job(self, job_id: str) -> List[Task]:
        """Retrieves all tasks associated with a job_id from the database, ordered by sequence."""
        try:
            tasks_data = await self.db.get_tasks_by_job_id(job_id)
            # Convert list of dicts from DB to list of Pydantic models
            return [Task(**task_data) for task_data in tasks_data]
        except Exception as e:
            logger.error(f"Failed to retrieve tasks for job {job_id} from DB: {e}", exc_info=True)
            return [] # Return empty list on error

    async def get_next_pending_task_for_job(self, job_id: str) -> Optional[Task]:
        """Finds the next task marked as PENDING for a specific job from the database."""
        try:
            task_data = await self.db.get_next_pending_task(job_id)
            if task_data:
                return Task(**task_data)
            return None
        except Exception as e:
            logger.error(f"Failed to get next pending task for job {job_id} from DB: {e}", exc_info=True)
            return None

    async def get_completed_tasks_for_job(self, job_id: str, task_type: Optional[TaskType] = None) -> List[Task]:
        """Retrieves all completed tasks for a job, optionally filtered by type."""
        if task_type:
            try:
                tasks_data = await self.db.get_completed_tasks_by_type(job_id, task_type.value)
                return [Task(**task_data) for task_data in tasks_data]
            except Exception as e:
                logger.error(f"Failed to get completed {task_type.value} tasks for job {job_id}: {e}", exc_info=True)
                return []
        else:
            # If no type specified, get all completed tasks (needs a new DB method or filter here)
            # Option 1: Add db.get_completed_tasks(job_id)
            # Option 2: Filter results from get_all_tasks_for_job (potentially inefficient)
            # Let's assume we need all completed for now, so filter results of get_all_tasks:
            try:
                all_tasks = await self.get_all_tasks_for_job(job_id)
                return [task for task in all_tasks if task.status == TaskStatus.COMPLETED]
            except Exception as e:
                logger.error(f"Failed to get all completed tasks for job {job_id}: {e}", exc_info=True)
                return []

    async def has_running_tasks(self, job_id: str) -> bool:
        """Checks if there are any tasks currently RUNNING for the job in the database."""
        try:
            count = await self.db.count_tasks_by_status(job_id, TaskStatus.RUNNING.value)
            return count > 0
        except Exception as e:
            logger.error(f"Failed to count running tasks for job {job_id}: {e}", exc_info=True)
            return False # Assume no running tasks on error

    async def has_errored_tasks(self, job_id: str) -> bool:
        """Checks if any task associated with the job has ERRORED in the database."""
        try:
            count = await self.db.count_tasks_by_status(job_id, TaskStatus.ERROR.value)
            return count > 0
        except Exception as e:
            logger.error(f"Failed to count errored tasks for job {job_id}: {e}", exc_info=True)
            return False # Assume no errored tasks on error

    # --- Methods below might be obsolete or need rethinking with DB backend ---

    # def get_job_id_for_task(self, task_id: str) -> Optional[str]:
    #     """Finds the job ID associated with a given task ID."""
    #     # This would require fetching the task from DB
    #     task = asyncio.run(self.get_task(task_id)) # Careful with running async like this
    #     return task.job_id if task else None

    # def is_job_complete(self, job_id: str) -> bool:
    #     """Checks if all tasks for a given job ID are in a terminal state (COMPLETED, ERROR, SKIPPED)."""
    #     # Need to fetch all tasks for the job from DB
    #     tasks = asyncio.run(self.get_all_tasks_for_job(job_id))
    #     if not tasks:
    #         logger.warning(f"No tasks found for job {job_id} when checking completion.")
    #         return False # Or True if no tasks means complete?
    #     return all(task.status in [TaskStatus.COMPLETED, TaskStatus.ERROR, TaskStatus.SKIPPED] for task in tasks)

    # def get_final_report_task(self, job_id: str) -> Optional[Task]:
    #     """Finds the final REPORT task for a job."""
    #     # Need to fetch tasks from DB
    #     report_tasks = asyncio.run(self.get_completed_tasks_for_job(job_id, TaskType.REPORT))
    #     if report_tasks:
    #         return report_tasks[-1] # Assume last one if multiple?
    #     return None

# Note: Removed methods relying on internal state (job_tasks, etc.)
# and commented out methods that would require synchronous DB calls within async methods
# or need to be reimplemented carefully using the async db methods.
# The Orchestrator will likely handle job completion logic based on task statuses from DB.