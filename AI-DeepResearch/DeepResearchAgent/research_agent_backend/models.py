import uuid
from enum import Enum
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"

class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_id: Optional[str] = None # Link task to an overall research job
    description: str
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None
    error_message: Optional[str] = None
    # Could add parent_task_id, sub_tasks list later

class StatusUpdate(BaseModel):
    task_id: str
    status: TaskStatus
    detail: Optional[str] = None # e.g., error message or completion note

class UserCommand(BaseModel):
    command: str # e.g., "resume", "skip", "provide_input"
    task_id: str
    payload: Optional[Any] = None # e.g., user-provided keywords

class InitialTopic(BaseModel):
    topic: str

# ... (keep existing imports and models)

class JobResultsSummary(BaseModel):
    type: str = "job_results_summary" # Message type identifier
    job_id: str
    unique_sources_found: int
    duplicates_removed: int
    sources_analyzed_count: int
    # Optionally include a few example URLs/titles
    top_sources: List[Dict[str, str]] = [] # e.g., [{"title": "...", "url": "..."}, ...]

class FinalReportMessage(BaseModel):
    type: str = "final_report" # Message type identifier
    job_id: str
    report_markdown: str