import logging
from typing import Dict, Optional, List, Any # Keep existing imports
from models import Task, TaskStatus, StatusUpdate, UserCommand # Keep existing imports
from persistence import save_tasks_to_md # Keep existing imports
from websocket_manager import ConnectionManager # Keep existing imports


#from . import orchestrator
logger = logging.getLogger(__name__)

class TaskManager:
    # Add orchestrator type hint without importing directly at module level
    def __init__(self, connection_manager: ConnectionManager, orchestrator: Optional['Orchestrator'] = None):
        self.tasks: Dict[str, Task] = {}
        self.connection_manager = connection_manager
        self.orchestrator = orchestrator # Store reference
        #BELOW line is still optional IMO
        save_tasks_to_md(self.tasks)

    # Add setter for orchestrator if needed after initialization
    def set_orchestrator(self, orchestrator):
         #removed type hint in this method to avoid circular import issues , and to allow for dynamic assignment
         from orchestrator import Orchestrator # Avoid circular import - use type hinting
         if not self.orchestrator:
              self.orchestrator = orchestrator
         else:
              logger.warning("Orchestrator reference already set.")


    async def add_task(self, description: str, job_id: Optional[str] = None) -> Task: # Add job_id
        """Adds a new task, assigns job_id, saves state, and broadcasts update."""
        new_task = Task(description=description, job_id=job_id) # Assign job_id
        self.tasks[new_task.id] = new_task
        logger.info(f"[Job {job_id}] Added task: {new_task.description} (ID: {new_task.id})")

        save_tasks_to_md(self.tasks) #Have to Consider making save async if it becomes slow

        # Include job_id in the broadcast message
        update_message = StatusUpdate(
            task_id=new_task.id,
            status=new_task.status,
            detail=f"Task '{new_task.description}' created for job {job_id}."
        ).dict() # Use .dict() for pydantic v1
        update_message['job_id'] = job_id # Add job_id to broadcast
        await self.connection_manager.broadcast_json(update_message)

        return new_task

    async def update_task_status(self, task_id: str, status: TaskStatus, detail: Optional[str] = None, error_message: Optional[str] = None, result: Optional[Any] = None):
        """Updates task status, saves state, and broadcasts update."""
        task = self.tasks.get(task_id)
        if not task:
            logger.error(f"Task ID {task_id} not found for status update.")
            return

        task.status = status
        task.error_message = error_message if status == TaskStatus.ERROR else None
        # Store result more reliably
        task.result = result # Store actual result, not just string representation

        logger.info(f"[Job {task.job_id}] Updating task {task_id} to {status}. Detail: {detail}")

        save_tasks_to_md(self.tasks) # Consider making save async

        update_message = StatusUpdate(
            task_id=task_id,
            status=task.status,
            detail=detail or f"Task status changed to {status}"
        ).dict()
        update_message['job_id'] = task.job_id # Add job_id to broadcast
        await self.connection_manager.broadcast_json(update_message)

    # --- Keep get_task, get_all_tasks ---

    def get_all_tasks(self) -> List[Task]:
        """Returns all tasks."""
        return list(self.tasks.values())
    def get_next_pending_task_for_job(self, job_id: str) -> Optional[Task]:
        """Finds the next PENDING task for a specific job."""
        # Simple sequential find for now. Could add priority later.
        for task in self.tasks.values():
            if task.job_id == job_id and task.status == TaskStatus.PENDING:
                return task
        return None

    def has_running_tasks(self, job_id: str) -> bool:
        """Checks if any tasks for the job are currently RUNNING."""
        for task in self.tasks.values():
            if task.job_id == job_id and task.status == TaskStatus.RUNNING:
                return True
        return False

    def has_errored_tasks(self, job_id: str) -> bool:
        """Checks if any tasks for the job are in ERROR state."""
        for task in self.tasks.values():
             if task.job_id == job_id and task.status == TaskStatus.ERROR:
                 return True
        return False

    def get_completed_tasks_for_job(self, job_id: str, description_contains: Optional[str] = None) -> List[Task]:
        """Gets all COMPLETED tasks for a job, optionally filtering by description."""
        completed = []
        for task in self.tasks.values():
            if task.job_id == job_id and task.status == TaskStatus.COMPLETED:
                if description_contains is None or description_contains.lower() in task.description.lower():
                    completed.append(task)
        return completed


    async def handle_user_command(self, command_data: dict):
        """Handles commands from WebSocket, now interacts with Orchestrator."""
        try:
            command = UserCommand(**command_data)
            logger.info(f"Processing command: {command.command} for task {command.task_id}")

            task = self.get_task(command.task_id)
            if not task or not task.job_id:
                 logger.warning(f"Received command for task {command.task_id} which doesn't exist or has no job ID.")
                 # TODO: Send feedback to user via WebSocket
                 return

            if not self.orchestrator:
                 logger.error("Orchestrator reference not set in TaskManager. Cannot handle commands properly.")
                 return

            job_id = task.job_id

            if command.command == "skip":
                 if task.status in [TaskStatus.ERROR, TaskStatus.PENDING, TaskStatus.RUNNING]:
                     # Let orchestrator handle skipping and potentially resuming
                     await self.orchestrator.skip_task_and_resume(job_id, command.task_id)
                 else:
                     logger.warning(f"Cannot skip task {command.task_id} in status {task.status}")
                     # TODO: Send feedback to user

            elif command.command == "resume":
                 # Ask the orchestrator to resume the job if it's paused
                 await self.orchestrator.resume(job_id)

            # Add more command handling (e.g., provide_input) later
            else:
                logger.warning(f"Unknown command received: {command.command}")

        except Exception as e:
            logger.error(f"Error processing user command {command_data}: {e}", exc_info=True)
            # TODO: Send error feedback to user