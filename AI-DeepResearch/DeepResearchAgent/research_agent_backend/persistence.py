import logging
from typing import List, Dict
from models import Task, TaskStatus
import os # Import os module
import json
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
    """Saves the current state of tasks to todo.md, including type and parameters"""
    try:
        os.makedirs(os.path.dirname(TODO_FILENAME) or '.', exist_ok=True)

        tasks_by_job: Dict[str, List[Task]] = {}
        for task in tasks.values():
             job_key = task.job_id or "Unassigned"
             if job_key not in tasks_by_job:
                 tasks_by_job[job_key] = []
             tasks_by_job[job_key].append(task)

        with open(TODO_FILENAME, "w", encoding="utf-8") as f:
            f.write("# Research Task Todo List\n\n")
            if not tasks:
                f.write("No tasks defined yet.\n")
                return

            sorted_job_ids = sorted(tasks_by_job.keys())

            for job_id in sorted_job_ids:
                f.write(f"## Job ID: {job_id}\n\n")
                job_tasks = tasks_by_job[job_id]
                sorted_tasks = job_tasks # Keep original order for now

                for task in sorted_tasks:
                    marker = get_status_marker(task.status)
                    # --- UPDATED Line to include TaskType ---
                    f.write(f"- {marker} **{task.task_type.value}**: {task.description} `(TaskID: {task.id})`\n")
                    # --- Optionally display parameters ---
                    if task.parameters:
                         try:
                             # Format parameters as compact JSON for readability
                             params_str = json.dumps(task.parameters, separators=(',', ':'))
                             f.write(f"  - Params: `{params_str}`\n")
                         except TypeError:
                              f.write(f"  - Params: (Error formatting parameters)\n")

                    # --- Display Error/Result (keep as before, but results are less likely in Task object now) ---
                    if task.status == TaskStatus.ERROR and task.error_message:
                        f.write(f"  - **Error:** {task.error_message}\n")
                    # Result is now stored separately, maybe add note if result exists in task_manager?
                    # elif task.status == TaskStatus.COMPLETED:
                    #      f.write(f"  - (Result stored separately)\n")
                f.write("\n")

        logger.info(f"Successfully saved {len(tasks)} tasks across {len(tasks_by_job)} jobs to {TODO_FILENAME}")

    except IOError as e:
        logger.error(f"Failed to save tasks to {TODO_FILENAME}: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while saving tasks: {e}", exc_info=True)