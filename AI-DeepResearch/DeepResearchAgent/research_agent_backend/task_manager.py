
import logging
from typing import Dict, Optional, List, Any
from models import Task, TaskStatus, StatusUpdate, UserCommand
from persistence import save_tasks_to_md
from websocket_manager import ConnectionManager

# Avoid direct import of Orchestrator at module level
# from . import orchestrator 

logger = logging.getLogger(__name__)

class TaskManager:
    def __init__(self, connection_manager: ConnectionManager):
        self.tasks: Dict[str, Task] = {}
        self.connection_manager = connection_manager
        self.orchestrator: Optional['Orchestrator'] = None # Type hint without import
        self.task_results: Dict[str, Any] = {} # Stores results keyed by task_id
        save_tasks_to_md(self.tasks) # Save initial empty state

    def set_orchestrator(self, orchestrator):
        from orchestrator import Orchestrator # Import here to avoid circular dependency
        if not self.orchestrator:
            self.orchestrator = orchestrator
        else:
            logger.warning("Orchestrator reference already set.")

    async def add_task(self, description: str, job_id: Optional[str] = None) -> Task:
        new_task = Task(description=description, job_id=job_id)
        self.tasks[new_task.id] = new_task
        logger.info(f"[Job {job_id}] Added task: {new_task.description} (ID: {new_task.id})")
        save_tasks_to_md(self.tasks) # Consider making async

        update_message = StatusUpdate(
            task_id=new_task.id,
            status=new_task.status,
            detail=f"Task '{new_task.description}' created for job {job_id}."
        ).dict()
        update_message['job_id'] = job_id
        await self.connection_manager.broadcast_json(update_message)
        return new_task

    async def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        detail: Optional[str] = None,
        error_message: Optional[str] = None,
        # Remove result from here, it's handled by store_result
    ):
        task = self.tasks.get(task_id)
        if not task:
            logger.error(f"Task ID {task_id} not found for status update.")
            return

        task.status = status
        task.error_message = error_message if status == TaskStatus.ERROR else None
        # task.result is no longer directly set here

        logger.info(f"[Job {task.job_id}] Updating task {task_id} ({task.description}) to {status}. Detail: {detail}")
        save_tasks_to_md(self.tasks) # Consider making async

        update_message = StatusUpdate(
            task_id=task_id,
            status=task.status,
            detail=detail or f"Task status changed to {status}"
        ).dict()
        update_message['job_id'] = task.job_id
        await self.connection_manager.broadcast_json(update_message)


    # --- Result Storage Methods ---
    async def store_result(self, task_id: str, result: Any):
        """Stores the result for a given task ID."""
        if task_id not in self.tasks:
            logger.error(f"Attempted to store result for non-existent task ID: {task_id}")
            return
        task = self.tasks[task_id]
        self.task_results[task_id] = result
        logger.info(f"[Job {task.job_id}] Stored result for task {task_id} ({task.description}). Result type: {type(result).__name__}")
        # Optionally save results to disk or DB here if they are large
        # save_task_result_to_file(task_id, result)

    def get_result(self, task_id: str) -> Optional[Any]:
        """Retrieves the stored result for a given task ID."""
        result = self.task_results.get(task_id)
        if result is None:
             logger.warning(f"No result found for task ID: {task_id}")
        return result

    # --- Existing Methods (Keep as they are) ---
    def get_task(self, task_id: str) -> Optional[Task]:
        """Gets a specific task by ID."""
        return self.tasks.get(task_id)

    def get_all_tasks(self) -> List[Task]:
        return list(self.tasks.values())

    def get_next_pending_task_for_job(self, job_id: str) -> Optional[Task]:
        for task in self.tasks.values():
            if task.job_id == job_id and task.status == TaskStatus.PENDING:
                return task
        return None

    def has_running_tasks(self, job_id: str) -> bool:
        for task in self.tasks.values():
            if task.job_id == job_id and task.status == TaskStatus.RUNNING:
                return True
        return False

    def has_errored_tasks(self, job_id: str) -> bool:
        for task in self.tasks.values():
             if task.job_id == job_id and task.status == TaskStatus.ERROR:
                 return True
        return False

    def get_completed_tasks_for_job(self, job_id: str, description_contains: Optional[str] = None) -> List[Task]:
        """Gets completed tasks for a job, optionally filtering by description."""
        completed = []
        for task in self.tasks.values():
            if task.job_id == job_id and task.status == TaskStatus.COMPLETED:
                if description_contains is None or description_contains.lower() in task.description.lower():
                    completed.append(task)
        return completed

    async def handle_user_command(self, command_data: dict):
        try:
            command = UserCommand(**command_data)
            logger.info(f"Processing command: {command.command} for task {command.task_id}")

            task = self.get_task(command.task_id)
            if not task or not task.job_id:
                 logger.warning(f"Received command for task {command.task_id} which doesn't exist or has no job ID.")
                 await self.connection_manager.broadcast_json({"error": f"Task {command.task_id} not found or missing job ID.", "command": command.command}) # Feedback
                 return

            if not self.orchestrator:
                 logger.error("Orchestrator reference not set in TaskManager. Cannot handle commands properly.")
                 await self.connection_manager.broadcast_json({"error": "Internal server error: Orchestrator not available.", "command": command.command})
                 return

            job_id = task.job_id

            if command.command == "skip":
                 if task.status in [TaskStatus.ERROR, TaskStatus.PENDING, TaskStatus.RUNNING]:
                     await self.orchestrator.skip_task_and_resume(job_id, command.task_id)
                 else:
                     logger.warning(f"Cannot skip task {command.task_id} in status {task.status}")
                     await self.connection_manager.broadcast_json({"warning": f"Cannot skip task {task.id}, status is {task.status}", "task_id": task.id})

            elif command.command == "resume":
                 # Resume command should ideally target the *job*, not just a task within it.
                 # We use the task_id here to find the job_id, then resume the job.
                 await self.orchestrator.resume(job_id)

            # Add more command handling (e.g., provide_input) later
            else:
                logger.warning(f"Unknown command received: {command.command}")
                await self.connection_manager.broadcast_json({"warning": f"Unknown command: {command.command}", "task_id": command.task_id})

        except Exception as e:
            logger.error(f"Error processing user command {command_data}: {e}", exc_info=True)
            # Send error feedback to user
            try:
                await self.connection_manager.broadcast_json({"error": f"Error processing command: {e}"})
            except Exception as ws_err:
                 logger.error(f"Failed to send error feedback via WebSocket: {ws_err}")
