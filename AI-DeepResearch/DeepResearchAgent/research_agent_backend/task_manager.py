import logging
from typing import Dict, Optional, List
from models import Task, TaskStatus, StatusUpdate
from persistence import save_tasks_to_md
from websocket_manager import ConnectionManager

logger = logging.getLogger(__name__)

class TaskManager:
    def __init__(self, connection_manager: ConnectionManager):
        self.tasks: Dict[str, Task] = {} # Store tasks by ID
        self.connection_manager = connection_manager
        # self.tasks = load_tasks_from_md() # Defer loading for now
        # logger.info(f"Loaded {len(self.tasks)} tasks initially.")
        save_tasks_to_md(self.tasks) # Save empty state initially


    async def add_task(self, description: str) -> Task:
        """Adds a new task, saves state, and broadcasts update."""
        new_task = Task(description=description)
        self.tasks[new_task.id] = new_task
        logger.info(f"Added task: {new_task.description} (ID: {new_task.id})")

        save_tasks_to_md(self.tasks)

        update_message = StatusUpdate(
            task_id=new_task.id,
            status=new_task.status,
            detail=f"Task '{new_task.description}' created."
        )
        await self.connection_manager.broadcast_json(update_message.dict())

        return new_task

    async def update_task_status(self, task_id: str, status: TaskStatus, detail: Optional[str] = None, error_message: Optional[str] = None, result: Optional[str] = None):
        """Updates task status, saves state, and broadcasts update."""
        task = self.tasks.get(task_id)
        if not task:
            logger.error(f"Task ID {task_id} not found for status update.")
            return

        task.status = status
        task.error_message = error_message if status == TaskStatus.ERROR else None
        task.result = result if status == TaskStatus.COMPLETED else None
        logger.info(f"Updating task {task_id} to {status}. Detail: {detail}")

        save_tasks_to_md(self.tasks)

        update_message = StatusUpdate(
            task_id=task_id,
            status=task.status,
            detail=detail or f"Task status changed to {status}"
        )
        await self.connection_manager.broadcast_json(update_message.dict())

    def get_task(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)

    def get_all_tasks(self) -> List[Task]:
         # Return tasks, maybe sorted by creation order or status later
        return list(self.tasks.values())

    def get_next_pending_task(self) -> Optional[Task]:
        for task in self.tasks.values():
            if task.status == TaskStatus.PENDING:
                return task
        return None

    async def handle_user_command(self, command_data: dict):
        """Placeholder for handling commands received from WebSocket."""
        try:
            command = UserCommand(**command_data)
            logger.info(f"Processing command: {command.command} for task {command.task_id}")

            task = self.get_task(command.task_id)
            if not task:
                 logger.warning(f"Received command for non-existent task ID: {command.task_id}")
                 # Optionally send feedback to the specific user's WebSocket
                 return

            if command.command == "skip":
                 if task.status == TaskStatus.ERROR or task.status == TaskStatus.PENDING or task.status == TaskStatus.RUNNING: # Allow skipping pending/running/error
                     await self.update_task_status(command.task_id, TaskStatus.SKIPPED, detail="Task skipped by user.")
                 else:
                     logger.warning(f"Cannot skip task {command.task_id} in status {task.status}")
            elif command.command == "resume":
                # This command might trigger the orchestrator to retry or proceed
                # For now, just log it. The orchestrator will handle the actual resume logic.
                logger.info(f"User requested to resume/retry task {command.task_id}. Orchestrator needs to handle this.")
                # Potentially change status back to PENDING if it was in ERROR?
                if task.status == TaskStatus.ERROR:
                     await self.update_task_status(command.task_id, TaskStatus.PENDING, detail="Task marked pending for retry by user.")

            # Add more command handling (e.g., provide_input) later
            else:
                logger.warning(f"Unknown command received: {command.command}")

        except Exception as e:
            logger.error(f"Error processing user command {command_data}: {e}")