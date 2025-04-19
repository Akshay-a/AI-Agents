import asyncio
import logging
from typing import Dict, Optional, List, Any
from enum import Enum

from models import Task, TaskStatus
from task_manager import TaskManager # Assuming TaskManager handles status updates/broadcasts
from agents.planning import planning_agent # Import agent instances
from agents.search import search_agent
from agents.filtering import filtering_agent
# Import other agents later (Analysis, Reporting)

logger = logging.getLogger(__name__)

class JobStatus(str, Enum): # This Enum is heart of managing all the jobs and their states
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED" # Paused due to error, waiting for user , in this scenario orchestrator agent handles receving input from user and directs accordingly
    COMPLETED = "COMPLETED"
    FAILED = "FAILED" # Failed definitively

class Orchestrator:
    def __init__(self, task_manager: TaskManager):
        self.task_manager = task_manager
        # Track running/paused jobs. Key: job_id (initial task ID), Value: Status/Event
        self.active_jobs: Dict[str, JobStatus] = {}
        self.pause_events: Dict[str, asyncio.Event] = {}
        self.job_tasks: Dict[str, asyncio.Task] = {} # To manage background tasks -> start with researching about task (that is the first task)

    async def start_job(self, initial_task_id: str, topic: str):
        """Initiates and runs the research flow for a given job"""
        if initial_task_id in self.active_jobs:
            logger.warning(f"Job {initial_task_id} is already active.")
            return

        logger.info(f"Starting job {initial_task_id} for topic: {topic}")
        self.active_jobs[initial_task_id] = JobStatus.RUNNING
        self.pause_events[initial_task_id] = asyncio.Event() # Initially unset (not paused)

        # Run the main flow in a background task
        job_task = asyncio.create_task(
            self._run_research_flow(initial_task_id),
            name=f"Job-{initial_task_id}"
        )
        self.job_tasks[initial_task_id] = job_task
        await self.broadcast_job_status(initial_task_id, JobStatus.RUNNING, f"Job started for topic: {topic}")


    async def _run_research_flow(self, job_id: str):
        """The main execution loop for a research job"""
        try:
            while self.active_jobs.get(job_id) == JobStatus.RUNNING:
                # Check if paused
                if self.pause_events[job_id].is_set():
                    logger.info(f"Job {job_id} is paused. Waiting for resume signal...")
                    await self.broadcast_job_status(job_id, JobStatus.PAUSED, "Paused due to error. Waiting for user input.")
                    await self.pause_events[job_id].wait() # Wait until event is cleared
                    # Once resumed, check status again in case job was cancelled/failed
                    if self.active_jobs.get(job_id) != JobStatus.RUNNING:
                         logger.info(f"Job {job_id} resume detected, but status is now {self.active_jobs.get(job_id)}. Exiting loop.")
                         break
                    logger.info(f"Job {job_id} resumed.")
                    await self.broadcast_job_status(job_id, JobStatus.RUNNING, "Job resumed by user.")


                next_task = self.task_manager.get_next_pending_task_for_job(job_id)

                if not next_task:
                    # Check if there are still RUNNING tasks for this job
                    if self.task_manager.has_running_tasks(job_id):
                        logger.info(f"Job {job_id}: No pending tasks, but some are still running. Waiting...")
                        await asyncio.sleep(2) # Wait 2 sec briefly for running tasks to finish
                        continue
                    else:
                        logger.info(f"Job {job_id}: No more pending or running tasks found.")
                        # TODO:Add final synthesis/reporting steps here later
                        # For now, assume completion if no errors occurred
                        if not self.task_manager.has_errored_tasks(job_id):
                             logger.info(f"Job {job_id} completed successfully.")
                             self.active_jobs[job_id] = JobStatus.COMPLETED
                             await self.broadcast_job_status(job_id, JobStatus.COMPLETED, "All tasks completed successfully.")
                        else:
                             logger.warning(f"Job {job_id} finished, but with errors.")
                             self.active_jobs[job_id] = JobStatus.FAILED # Or maybe COMPLETED_WITH_ERRORS
                             await self.broadcast_job_status(job_id, JobStatus.FAILED, "Job finished, but some tasks failed or were skipped.")
                        break # Exit the loop

                await self.task_manager.update_task_status(next_task.id, TaskStatus.RUNNING, detail="Orchestrator picked up task.")

                try:
                    result = await self._dispatch_task(next_task)
                    # Handle result (e.g., add new tasks from planner)
                    await self._handle_task_completion(next_task, result)

                except Exception as e:
                    logger.error(f"Error executing task {next_task.id} ({next_task.description}): {e}", exc_info=False) # Keep log cleaner
                    error_msg = str(e)
                    await self.task_manager.update_task_status(next_task.id, TaskStatus.ERROR, error_message=error_msg, detail="Task failed during execution.")
                    # Pause the job
                    self.pause_events[job_id].set() # Set the event flag to pause the loop

                await asyncio.sleep(0.3) # Small delay to prevent tight loop if needed

        except asyncio.CancelledError:
             logger.info(f"Job {job_id} task was cancelled.")
             self.active_jobs[job_id] = JobStatus.FAILED
             await self.broadcast_job_status(job_id, JobStatus.FAILED, "Job execution was cancelled.")
        except Exception as e:
            logger.exception(f"Critical error in research flow for job {job_id}: {e}") # Log full traceback
            self.active_jobs[job_id] = JobStatus.FAILED
            await self.broadcast_job_status(job_id, JobStatus.FAILED, f"Critical error occurred: {e}")
        finally:
            logger.info(f"Exiting research flow loop for job {job_id}. Final status: {self.active_jobs.get(job_id)}")
            # Clean up resources associated with the job
            self.pause_events.pop(job_id, None)
            self.job_tasks.pop(job_id, None)
            # Don't remove from active_jobs immediately, keep final status


    async def _dispatch_task(self, task: Task) -> Any:
        """Calls the appropriate simulated agent based on task description."""
        logger.info(f"Dispatching task: {task.description}")
        # Basic routing based on description keywords
        desc_lower = task.description.lower()

        if "plan research" in desc_lower:
             # Extract topic (simple parsing, needs improvement)
             topic = task.description.split(":")[-1].strip()
             return await planning_agent.run(topic=topic, job_id=task.job_id)
        elif "search:" in desc_lower:
             query = task.description.split(":")[-1].strip()
             return await search_agent.run(query=query, job_id=task.job_id, task_id=task.id)
        elif "filter:" in desc_lower:
             # Need to gather results from preceding search tasks
             search_tasks = self.task_manager.get_completed_tasks_for_job(task.job_id, description_contains="Search:")
             search_results = [st.result for st in search_tasks if st.result]
             return await filtering_agent.run(search_results=search_results, job_id=task.job_id, task_id=task.id)
        # --- Add cases for Analysis, Reporting agents later ---
        else:
             #TODO : Add more sophisticated routing or error handling
             logger.warning(f"No agent found to handle task: {task.description}. Skipping.")
             return None # Or raise an error

    async def _handle_task_completion(self, task: Task, result: Any):
        """Processes the result of a completed task."""
        await self.task_manager.update_task_status(task.id, TaskStatus.COMPLETED, result=result, detail="Task completed successfully.")

        # If the planning task completed, add the new sub-tasks
        if "plan research" in task.description.lower() and isinstance(result, list):
            logger.info(f"Planning task {task.id} completed. Adding {len(result)} sub-tasks for job {task.job_id}.")
            for sub_task_desc in result:
                # Add Analysis/Report tasks here if they aren't in the planner's output yet
                if "analyze" not in sub_task_desc.lower() and "generate report" not in sub_task_desc.lower() and "filter" not in sub_task_desc.lower():
                    # Basic dependency: Ensure filter runs after searches
                    pass # Dependencies need more robust handling

                await self.task_manager.add_task(description=sub_task_desc, job_id=task.job_id)

            # Maybe add fixed Analysis/Report tasks after planning automatically?
            await self.task_manager.add_task(description=f"Analyze & Synthesize findings for job {task.job_id}", job_id=task.job_id)
            await self.task_manager.add_task(description=f"Generate report for job {task.job_id}", job_id=task.job_id)


    async def resume(self, job_id: str):
        """Resumes a paused job."""
        if job_id in self.pause_events and self.pause_events[job_id].is_set():
             logger.info(f"Received resume command for paused job {job_id}.")
             self.active_jobs[job_id] = JobStatus.RUNNING # Ensure status is RUNNING
             self.pause_events[job_id].clear() # Clear the event to allow the loop to continue
             # Don't broadcast here, the loop will broadcast upon resuming
        else:
             logger.warning(f"Received resume command for job {job_id}, but it was not paused or doesn't exist.")

    async def skip_task_and_resume(self, job_id: str, task_id: str):
         """Marks a task as skipped and potentially resumes the job."""
         logger.info(f"Received skip command for task {task_id} in job {job_id}.")
         await self.task_manager.update_task_status(task_id, TaskStatus.SKIPPED, detail="Task skipped by user.")
         # If the job was paused specifically because *this task* failed, resume it.
         if job_id in self.pause_events and self.pause_events[job_id].is_set():
              # Check if the paused state was due to this task (may need better state tracking)
              # Simple assumption: if paused, skipping an error task should allow resume
              logger.info(f"Job {job_id} was paused, resuming after skipping task {task_id}.")
              await self.resume(job_id)


    async def broadcast_job_status(self, job_id: str, status: JobStatus, detail: str):
        """Broadcasts overall job status updates via WebSocket."""
        message = {
            "type": "job_status",
            "job_id": job_id,
            "status": status.value,
            "detail": detail
        }
        await self.task_manager.connection_manager.broadcast_json(message) # Use TM's connection mgr