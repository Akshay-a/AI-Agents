import logging
from typing import List, Dict
from models import Task, TaskStatus
import os # Import os module
import json

# Funcionts are no longer used for tracking coz of the
# database integration that is done to remember restarts. Task state is now managed in the database.
# The functions here can be kept for potential future use (e.g., generating
# a markdown report FROM the database for quick inspection) or removed entirely.

logger = logging.getLogger(__name__)
TODO_FILENAME = "todo.md"

def get_status_marker(status: TaskStatus) -> str:
    if status == TaskStatus.COMPLETED:
        return "[x]"
    elif status == TaskStatus.PENDING:
        return "[ ]"
    elif status == TaskStatus.RUNNING:
        return "[>]" # Indicate running
    elif status == TaskStatus.ERROR:
        return "[E]" # Indicate error
    elif status == TaskStatus.SKIPPED:
        return "[S]" # Indicate skipped
    return "[?]"

def save_tasks_to_md(tasks: Dict[str, Task]):
    """
    (Obsolete for State Tracking) Saves the current state of tasks to a Markdown file.
    This function no longer represents the source of truth.
    It could be adapted to read from the database if this file format is still desired.
    """
    logger.warning(f"save_tasks_to_md called, but {TODO_FILENAME} is no longer the source of truth for task state.")
    # If you still want to generate this file from the current in-memory view (which might be stale or incomplete):
    # try:
    #     # Group tasks by job_id for better organization
    #     tasks_by_job = {}
    #     for task_id, task in tasks.items():
    #         job_id = task.job_id or "UNKNOWN_JOB"
    #         if job_id not in tasks_by_job:
    #             tasks_by_job[job_id] = []
    #         tasks_by_job[job_id].append(task)

    #     with open(TODO_FILENAME, "w", encoding="utf-8") as f:
    #         f.write("# Research Agent Tasks (Snapshot - Not Source of Truth)\n\n")
    #         f.write("**Note:** Task state is now managed in the database. This file is a snapshot only.\n\n")
            
    #         if not tasks_by_job:
    #             f.write("*No tasks found in this snapshot.*\n")
    #             return

    #         for job_id, job_tasks in sorted(tasks_by_job.items()):
    #             f.write(f"## Job: {job_id}\n\n")
    #             # Sort tasks within a job (e.g., by creation time or sequence if available)
    #             # Sorting requires tasks to have comparable attributes.
    #             # Simple sort by ID for now if sequence_order isn't readily available here.
    #             sorted_tasks = sorted(job_tasks, key=lambda t: t.task_id)

    #             for task in sorted_tasks:
    #                 status_icon = " "
    #                 if task.status == TaskStatus.COMPLETED:
    #                     status_icon = "x"
    #                 elif task.status == TaskStatus.ERROR:
    #                     status_icon = "!"
    #                 elif task.status == TaskStatus.SKIPPED:
    #                     status_icon = "~"
    #                 elif task.status == TaskStatus.RUNNING:
    #                     status_icon = ">"
                        
    #                 f.write(f"- [{status_icon}] **{task.task_type.value}:** {task.description} `(ID: {task.task_id})`")
    #                 if task.status == TaskStatus.ERROR and task.error_message:
    #                     f.write(f" - **Error:** {task.error_message}")
    #                 f.write("\n")
    #             f.write("\n")
        
    #     logger.debug(f"Snapshot of tasks saved to {TODO_FILENAME} (Not source of truth). Note: This may not reflect DB state.")

    # except IOError as e:
    #     logger.error(f"Error saving tasks snapshot to {TODO_FILENAME}: {e}")
    # except Exception as e:
    #      logger.exception(f"An unexpected error occurred while saving tasks snapshot to {TODO_FILENAME}: {e}")
    pass # Do nothing by default now

def load_tasks_from_md() -> Dict[str, Task]:
    """
    (Obsolete) Loads tasks from a Markdown file. 
    This should not be used as the database is the source of truth.
    """
    logger.error(f"load_tasks_from_md called, but {TODO_FILENAME} is obsolete. Database is the source of truth.")
    # Returning empty dict as loading from this file is no longer valid.
    return {}

# Consider removing this file entirely or adapting save_tasks_to_md
# to query the database and generate the report if needed.