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
    """Saves the current state of tasks to todo.md"""
    try:
        # Ensure the directory exists (useful if TODO_FILENAME includes a path)
        os.makedirs(os.path.dirname(TODO_FILENAME) or '.', exist_ok=True)

        with open(TODO_FILENAME, "w", encoding="utf-8") as f:
            f.write("# Research Task Todo List\n\n")
            if not tasks:
                f.write("No tasks defined yet.\n")
                return

            # Maybe sort tasks or group them later; for now, just list them
            for task_id, task in tasks.items():
                marker = get_status_marker(task.status)
                f.write(f"- {marker} {task.description} `(ID: {task_id})`\n")
                if task.status == TaskStatus.ERROR and task.error_message:
                    f.write(f"  - **Error:** {task.error_message}\n")
                elif task.status == TaskStatus.COMPLETED and task.result:
                     # Optionally add brief result summary if available and simple
                     # f.write(f"  - Result: {str(task.result)[:50]}...\n")
                     pass

        logger.info(f"Successfully saved {len(tasks)} tasks to {TODO_FILENAME}")

    except IOError as e:
        logger.error(f"Failed to save tasks to {TODO_FILENAME}: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while saving tasks: {e}")


# --- Loading tasks from MD ---
# This is more complex due to parsing. We can defer implementing this
# until we need to resume state from a previous run.
# For now, the app will always start with an empty task list.

# def load_tasks_from_md(filename="todo.md") -> Dict[str, Task]:
#     """Loads tasks from todo.md (basic implementation needed)"""
#     # Placeholder: Needs careful parsing of markers, descriptions, IDs
#     logger.warning("Loading tasks from MD is not fully implemented yet.")
#     return {}