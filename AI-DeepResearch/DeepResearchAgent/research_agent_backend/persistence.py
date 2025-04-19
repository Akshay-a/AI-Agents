import logging
from typing import List, Dict
from models import Task, TaskStatus
import os # Import os module

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
    """Saves the current state of tasks to todo.md, including job_id"""
    try:
        os.makedirs(os.path.dirname(TODO_FILENAME) or '.', exist_ok=True)

        # Group tasks by job_id for better readability
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

            # Sort jobs (optional, e.g., by job_id)
            sorted_job_ids = sorted(tasks_by_job.keys())

            for job_id in sorted_job_ids:
                f.write(f"## Job ID: {job_id}\n\n")
                job_tasks = tasks_by_job[job_id]
                # Sort tasks within a job (e.g., by description or ID, optional)
                # sorted_tasks = sorted(job_tasks, key=lambda t: t.id)
                sorted_tasks = job_tasks # Keep original order for now

                for task in sorted_tasks:
                    marker = get_status_marker(task.status)
                    f.write(f"- {marker} {task.description} `(TaskID: {task.id})`\n") # Keep TaskID clear
                    if task.status == TaskStatus.ERROR and task.error_message:
                        f.write(f"  - **Error:** {task.error_message}\n")
                    elif task.status == TaskStatus.COMPLETED and task.result:
                         # Avoid printing large results
                         result_str = str(task.result)
                         f.write(f"  - Result: {result_str[:100]}{'...' if len(result_str) > 100 else ''}\n")
                f.write("\n") # Add space between jobs


        logger.info(f"Successfully saved {len(tasks)} tasks across {len(tasks_by_job)} jobs to {TODO_FILENAME}")

    except IOError as e:
        logger.error(f"Failed to save tasks to {TODO_FILENAME}: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while saving tasks: {e}", exc_info=True)


# --- Loading tasks from MD ---
# This is more complex due to parsing. We can defer implementing this
# until we need to resume state from a previous run.
# For now, the app will always start with an empty task list.

# def load_tasks_from_md(filename="todo.md") -> Dict[str, Task]:
#     """Loads tasks from todo.md (basic implementation needed)"""
#     # Placeholder: Needs careful parsing of markers, descriptions, IDs
#     logger.warning("Loading tasks from MD is not fully implemented yet.")
#     return {}