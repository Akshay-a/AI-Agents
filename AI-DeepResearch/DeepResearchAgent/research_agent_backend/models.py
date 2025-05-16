import uuid
from enum import Enum
from typing import List, Optional, Any, Dict, Union
from pydantic import BaseModel, Field
from datetime import datetime, timezone

class TaskType(str, Enum):
    PLAN = "PLAN" # Represents the initial planning task itself
    REASON = "REASON"
    SEARCH = "SEARCH"
    FILTER = "FILTER"
    SYNTHESIZE = "SYNTHESIZE"
    REPORT = "REPORT"

class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"

class Task(BaseModel):
    """Represents a single task within a research job."""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str
    sequence_order: int # Order of execution within the job
    task_type: TaskType
    description: str
    parameters: Optional[Dict[str, Any]] = None # Input parameters, stored as JSON in DB
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    result: Optional[Any] = None # Output of the task, stored as JSON in DB
    error_message: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Optional: Add validator if needed to ensure parameters/result are JSON serializable
    # @validator('parameters', 'result', pre=True, always=True)
    # def ensure_serializable(cls, v):
    #     if v is not None:
    #         try:
    #             json.dumps(v)
    #         except TypeError:
    #             raise ValueError("Field must be JSON serializable")
    #     return v

class TaskInputData(BaseModel):
    """Data needed to create a task (subset of Task). Used by Planner."""
    task_type: TaskType
    description: str
    parameters: Optional[Dict[str, Any]] = None

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

class JobStatus(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class JobResultsSummary(BaseModel):
    type: str = "job_results_summary" # Message type identifier
    job_id: str
    unique_sources_found: int
    duplicates_removed: int
    sources_analyzed_count: int
    # Optionally include a few example URLs/titles
    top_sources: List[Dict[str, str]] = [] # e.g., [{"title": "...", "url": "..."}, ...]

class Job(BaseModel):
    """Represents a research job initiated by a user query."""
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_query: str
    status: JobStatus = Field(default=JobStatus.IDLE) 
    final_report_path: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tasks: Optional[List[Task]] = None # Optionally embed tasks when retrieving a job

class JobCreationRequest(BaseModel):
    """Data needed to start a new job via API."""
    query: str

class JobCreationResponse(BaseModel):
    """Response sent back after a job is initiated."""
    job_id: str
    message: str
    plan: Optional[List[TaskInputData]] = None # Send the initial plan back

class WebSocketMessage(BaseModel):
    type: str
    payload: Dict[str, Any]

class TaskSuccessMessage(WebSocketMessage):
    type: str = "task_success"
    payload: Task # Send the completed task object

class TaskFailedMessage(WebSocketMessage):
    type: str = "task_failed"
    payload: Task # Send the failed task object, which includes error_message

class FinalReportMessage(WebSocketMessage):
    type: str = "final_report"
    payload: Dict[str, str] # e.g., {"job_id": ..., "report_markdown": ...}

class JobFailedMessage(WebSocketMessage):
    type: str = "job_failed"
    payload: Dict[str, str] # e.g., {"job_id": ..., "error": ...}

class JobProgressMessage(WebSocketMessage):
    type: str = "job_progress"
    payload: Dict[str, str] # e.g., {"job_id": ..., "message": ...}

