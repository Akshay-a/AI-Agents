import logging
from typing import Dict, Optional, List, Any
from models import Task, TaskStatus, StatusUpdate, UserCommand ,TaskType
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

    async def add_task(
        self,
        description: str,
        task_type: TaskType,
        parameters: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None
    ) -> Task:
        """Adds a new task ."""
        new_task = Task(
            description=description,
            task_type=task_type,
            parameters=parameters if parameters is not None else {}, # Ensure parameters is a dict
            job_id=job_id
        )
        self.tasks[new_task.id] = new_task
        logger.info(f"[Job {job_id}] Added Task (ID: {new_task.id}): Type={task_type.value}, Desc='{description}'")
        save_tasks_to_md(self.tasks) # have to make this async if file I/O becomes slow

        #update_message = StatusUpdate(
        #    task_id=new_task.id,
        #    status=new_task.status,
        #    detail=f"Task '{new_task.description}' ({task_type.value}) created for job {job_id}.",
        #    job_id=job_id
        #).dict()
        ## Ensure job_id is in the broadcast message (redundant with model but safe)
        #update_message['job_id'] = job_id
        #await self.connection_manager.broadcast_json(update_message)
        return new_task


    async def add_task_old(self, description: str, job_id: Optional[str] = None) -> Task:
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
    ):
        task = self.tasks.get(task_id)
        if not task:
            logger.error(f"Task ID {task_id} not found for status update.")
            return

        task.status = status
        task.error_message = error_message if status == TaskStatus.ERROR else None

        logger.info(f"[Job {task.job_id}] Updating task {task_id} ({task.description}) to {status}. Detail: {detail}")
        save_tasks_to_md(self.tasks)

        ##update_message = StatusUpdate(
        #    task_id=task_id,
       ##     status=task.status,
        #    detail=detail or f"Task status changed to {status}",
        #    job_id=task.job_id # Include job_id
       # ).dict()
        #update_message['job_id'] = task.job_id # Ensure again
        #await self.connection_manager.broadcast_json(update_message)



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

    def get_completed_tasks_for_job(self, job_id: str, task_type: Optional[TaskType] = None) -> List[Task]:
        """Gets completed tasks for a job, optionally filtering by type."""
        completed = []
        for task in self.tasks.values():
            if task.job_id == job_id and task.status == TaskStatus.COMPLETED:
                if task_type is None or task.task_type == task_type:
                    logger.info(f"Found completed task {task.id} with type {task.task_type} for job {job_id}")
                    completed.append(task)
        return completed
        
    def get_completed_task_results_for_job(self, job_id: str, task_type: Optional[TaskType] = None) -> List[Any]:
        """Gets results of completed tasks for a job, optionally filtering by type."""
        results = []
        for task in self.tasks.values():
            if task.job_id == job_id and task.status == TaskStatus.COMPLETED:
                if task_type is None or task.task_type == task_type:
                    if task.id in self.task_results:
                        logger.info(f"Task {task.id} has task type {task.task_type} and status {task.status} and result is available")
                        results.append(self.task_results[task.id])
                    else:
                        logger.warning(f"Task {task.id} is completed but has no stored result")
        return results

    async def handle_user_command(self, command_data: dict):
        """Handles commands like skip/resume, now potentially job-level."""
        try:
            # Use Pydantic validation
            command = UserCommand(**command_data)
            logger.info(f"Processing command: {command.command} (TaskID: {command.task_id}, JobID: {command.job_id})")

            if not self.orchestrator:
                 logger.error("Orchestrator reference not set in TaskManager. Cannot handle commands.")
                 # Maybe send feedback to user via websocket?
                 return

            # Determine target job ID
            target_job_id = command.job_id
            if not target_job_id and command.task_id:
                 task = self.get_task(command.task_id)
                 if task:
                     target_job_id = task.job_id

            if not target_job_id:
                 logger.warning(f"Received command '{command.command}' without sufficient context (JobID or valid TaskID).")
                 # Send feedback?
                 return

            # Route command to orchestrator based on target job
            if command.command == "skip" and command.task_id:
                 task_to_skip = self.get_task(command.task_id)
                 if task_to_skip and task_to_skip.job_id == target_job_id:
                     if task_to_skip.status in [TaskStatus.ERROR, TaskStatus.PENDING, TaskStatus.RUNNING]:
                         await self.orchestrator.skip_task_and_resume(target_job_id, command.task_id)
                     else:
                         logger.warning(f"Cannot skip task {command.task_id} in status {task_to_skip.status}")
                         # Send feedback?
                 else:
                      logger.warning(f"Skip command received for task {command.task_id}, but it doesn't exist or belong to inferred job {target_job_id}.")

            elif command.command == "resume":
                 # Resume applies at the job level
                 await self.orchestrator.resume(target_job_id)

            else:
                logger.warning(f"Unknown command received: {command.command}")
                # Send feedback?

        except Exception as e:
            logger.error(f"Error processing user command {command_data}: {e}", exc_info=True)
            # Send error feedback to user?