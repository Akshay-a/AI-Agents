-- Schema for the Research Agent Database (SQLite compatible)

CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    user_query TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')),
    final_report_path TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    sequence_order INTEGER NOT NULL,
    task_type TEXT NOT NULL, --  SEARCH, REASON, FILTER, SYNTHESIZE, REPORT
    description TEXT NOT NULL,
    parameters TEXT, -- Store as JSON string
    status TEXT NOT NULL CHECK(status IN ('PENDING', 'RUNNING', 'COMPLETED', 'ERROR', 'SKIPPED')),
    result TEXT, -- Store as JSON string
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE -- Ensure tasks are deleted if job is deleted
);

-- Indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_tasks_job_status ON tasks (job_id, status);
CREATE INDEX IF NOT EXISTS idx_tasks_job_sequence ON tasks (job_id, sequence_order);

-- Trigger to update 'updated_at' timestamp on jobs table update
-- can add later based on requirment
-- Trigger to update 'updated_at' timestamp on tasks table update
