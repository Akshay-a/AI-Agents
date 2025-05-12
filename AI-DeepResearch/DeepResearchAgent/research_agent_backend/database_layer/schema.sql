-- Schema for the Research Agent Database (SQLite compatible)

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    user_query TEXT NOT NULL,
    status TEXT NOT NULL, -- Maps to JobStatus Enum ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'PAUSED')
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, -- ISO 8601 format "YYYY-MM-DD HH:MM:SS.SSS"
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, -- ISO 8601 format "YYYY-MM-DD HH:MM:SS.SSS"
    final_report_path TEXT,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    task_type TEXT NOT NULL, -- Maps to TaskType Enum ('SEARCH', 'REASON', 'FILTER', 'SYNTHESIZE', 'REPORT')
    description TEXT NOT NULL,
    parameters TEXT, -- JSON string
    status TEXT NOT NULL, -- Maps to TaskStatus Enum ('PENDING', 'RUNNING', 'COMPLETED', 'ERROR', 'SKIPPED')
    result TEXT, -- JSON string or path pointer
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, -- ISO 8601 format "YYYY-MM-DD HH:MM:SS.SSS"
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, -- ISO 8601 format "YYYY-MM-DD HH:MM:SS.SSS"
    sequence_order INTEGER NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

-- Indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_tasks_job_id ON tasks(job_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);

-- Trigger to update 'updated_at' timestamp on jobs table update
-- can add later based on requirment
-- Trigger to update 'updated_at' timestamp on tasks table update
