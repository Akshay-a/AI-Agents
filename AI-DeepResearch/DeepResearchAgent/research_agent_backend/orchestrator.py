import asyncio
import logging
from typing import Dict, Optional, List, Any
from enum import Enum

from models import Task, TaskStatus , JobResultsSummary
from task_manager import TaskManager # Assuming TaskManager handles status updates/broadcasts
from agents.planning import planning_agent # Import agent instances
from agents.search import SearchAgent
from agents.filtering import FilteringAgent
# Import other agents later (Analysis, Reporting)

logger = logging.getLogger(__name__)

SEARCH_TASK_DELAY = 1.5

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
        self.search_agent = SearchAgent(task_manager=self.task_manager)
        self.filtering_agent = FilteringAgent(task_manager=self.task_manager) 

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
        try:
            while self.active_jobs.get(job_id) == JobStatus.RUNNING:
                if self.pause_events[job_id].is_set():
                    logger.info(f"Job {job_id} is paused. Waiting for resume signal...")
                    await self.broadcast_job_status(job_id, JobStatus.PAUSED, "Paused due to error or input required. Waiting for user.")
                    await self.pause_events[job_id].wait()
                    if self.active_jobs.get(job_id) != JobStatus.RUNNING:
                         logger.info(f"Job {job_id} resume detected, but status is now {self.active_jobs.get(job_id)}. Exiting loop.")
                         break
                    logger.info(f"Job {job_id} resumed.")
                    await self.broadcast_job_status(job_id, JobStatus.RUNNING, "Job resumed by user.")

                next_task = self.task_manager.get_next_pending_task_for_job(job_id)  

                if not next_task:
                    if self.task_manager.has_running_tasks(job_id):
                        logger.debug(f"Job {job_id}: No pending tasks, but some are running. Waiting...")
                        await asyncio.sleep(1)
                        continue
                    else:
                        logger.info(f"Job {job_id}: No more pending or running tasks.")
                        if not self.task_manager.has_errored_tasks(job_id):
                             logger.info(f"Job {job_id} completed successfully.")
                             self.active_jobs[job_id] = JobStatus.COMPLETED
                             await self.broadcast_job_status(job_id, JobStatus.COMPLETED, "All tasks completed successfully.")
                        else:
                             logger.warning(f"Job {job_id} finished, but with errors or skipped tasks.")
                             self.active_jobs[job_id] = JobStatus.FAILED
                             await self.broadcast_job_status(job_id, JobStatus.FAILED, "Job finished, but some tasks failed or were skipped.")
                        break # Exit loop

                await self.task_manager.update_task_status(next_task.id, TaskStatus.RUNNING, detail="Orchestrator picked up task.")

                try:
                    # Dispatch the task to the appropriate agent
                    await self._dispatch_task(next_task)

                    # If the dispatch didn't raise an error, check the task status.
                    # If it wasn't marked as skipped during dispatch, mark it completed.
                    current_task = self.task_manager.get_task(next_task.id)
                    if current_task and current_task.status not in [TaskStatus.SKIPPED, TaskStatus.ERROR, TaskStatus.COMPLETED]:
                        await self.task_manager.update_task_status(
                            next_task.id,
                            TaskStatus.COMPLETED,
                            detail="Task completed successfully." # Correct: No result= argument
                        )
                    elif current_task:
                        logger.debug(f"Task {next_task.id} already handled (Status: {current_task.status}). Not marking as completed again.")
                    else:
                        logger.warning(f"Task {next_task.id} not found after dispatch. Cannot update status.")

                except Exception as e:
                    # Handle errors raised *during* dispatch or potentially during the completion update above
                    logger.error(f"Error during execution or completion handling for task {next_task.id} ({next_task.description}): {e}", exc_info=False)
                    error_msg = str(e)
                    # Ensure task exists before updating status to ERROR
                    if self.task_manager.get_task(next_task.id):
                        await self.task_manager.update_task_status(
                            next_task.id,
                            TaskStatus.ERROR,
                            error_message=error_msg,
                            detail=f"Task failed: {error_msg[:100]}..."
                        )
                    else:
                        logger.error(f"Task {next_task.id} not found, cannot mark as ERROR.")

                    # Pause the job
                    self.pause_events[job_id].set()
                    await self.broadcast_job_status(job_id, JobStatus.PAUSED, f"Paused due to error in task {next_task.id}: {error_msg[:100]}...")

                await asyncio.sleep(0.1) # Small delay

        except asyncio.CancelledError:
             logger.info(f"Job {job_id} task was cancelled.")
             self.active_jobs[job_id] = JobStatus.FAILED
             await self.broadcast_job_status(job_id, JobStatus.FAILED, "Job execution was cancelled.")
        except Exception as e:
            logger.exception(f"Critical error in research flow for job {job_id}: {e}")
            self.active_jobs[job_id] = JobStatus.FAILED
            await self.broadcast_job_status(job_id, JobStatus.FAILED, f"Critical error occurred: {e}")
        finally:
            logger.info(f"Exiting research flow loop for job {job_id}. Final status: {self.active_jobs.get(job_id)}")
            self.pause_events.pop(job_id, None)
            self.job_tasks.pop(job_id, None)


    async def _dispatch_task(self, task: Task):
        """Calls the appropriate agent based on task description. Agents now store their own results."""
        logger.info(f"Dispatching task: {task.description} (ID: {task.id}) for Job {task.job_id}")
        desc_lower = task.description.lower()
        task_completed_successfully = False # Flag to track if agent ran without error

        try:
            if "plan research" in desc_lower:
                topic = task.description.split(":")[-1].strip()
                sub_task_descriptions = await planning_agent.run(topic=topic, job_id=task.job_id)
                await self._handle_planning_completion(task, sub_task_descriptions)
                await self.task_manager.store_result(task.id, sub_task_descriptions)
                task_completed_successfully = True

            elif "search:" in desc_lower:
                await asyncio.sleep(SEARCH_TASK_DELAY)  # Simulate delay for search tasks
                query = task.description.split(":")[-1].strip()
                await self.search_agent.run(query=query, task_id=task.id, job_id=task.job_id)
                task_completed_successfully = True
                # Result stored by search_agent internally

            elif "filter:" in desc_lower:
                # Identify preceding search tasks for this job
                search_tasks = self.task_manager.get_completed_tasks_for_job(task.job_id, description_contains="Search:")
                search_task_ids = [st.id for st in search_tasks]

                if not search_task_ids:
                    logger.warning(f"[Job {task.job_id} | Task {task.id}] Filter task found no preceding completed Search tasks.")
                    # Run filter even with empty list to potentially store an empty result
                    await self.filtering_agent.run(search_task_ids=[], current_task_id=task.id, job_id=task.job_id)
                else:
                    logger.info(f"[Job {task.job_id} | Task {task.id}] Filter task will use results from search tasks: {search_task_ids}")
                    await self.filtering_agent.run(search_task_ids=search_task_ids, current_task_id=task.id, job_id=task.job_id)

                # --- START: Add Summary Broadcast ---
                # Check if filter completed and get its result
                filter_result = self.task_manager.get_result(task.id)
                if filter_result and isinstance(filter_result, dict):
                    filtered_items = filter_result.get("filtered_results", [])
                    summary = JobResultsSummary(
                        job_id=task.job_id,
                        unique_sources_found=len(filtered_items),
                        duplicates_removed=filter_result.get("duplicates_removed", 0),
                        sources_analyzed_count=filter_result.get("sources_analyzed_count", len(search_task_ids)),
                        # Get top 5 URLs/titles (if available)
                        top_sources=[
                            {"title": item.get("title", "N/A"), "url": item.get("url", "N/A")}
                            for item in filtered_items[:5] if isinstance(item, dict)
                        ]
                    )
                    await self.broadcast_job_summary(summary)
                    task_completed_successfully = True # Mark as successful if result was processed
                else:
                     logger.warning(f"[Job {task.job_id} | Task {task.id}] Filter task completed, but no valid result dictionary found in TaskManager.")
                     # Still mark as successful if the agent didn't raise an error, even if result missing
                     task_completed_successfully = True
                # --- END: Add Summary Broadcast ---

            elif "analyze" in desc_lower or "synthesize" in desc_lower:
                logger.info(f"[Job {task.job_id} | Task {task.id}] Running Analysis/Synthesis (Not Implemented Yet)")
                await asyncio.sleep(1)
                await self.task_manager.store_result(task.id, {"analysis": "Analysis completed (simulated)."})
                task_completed_successfully = True

            elif "generate report" in desc_lower:
                logger.info(f"[Job {task.job_id} | Task {task.id}] Running Report Generation (Not Implemented Yet)")
                await asyncio.sleep(1)
                await self.task_manager.store_result(task.id, {"report_summary": "Report generated (simulated)."})
                task_completed_successfully = True

            else:
                logger.warning(f"No specific agent logic found for task: '{task.description}'. Marking as skipped.")
                await self.task_manager.update_task_status(task.id, TaskStatus.SKIPPED, detail="No agent handler found for this task type.")
                # Task was skipped, not successfully completed in the normal sense
                task_completed_successfully = False # Explicitly false

            # If the agent ran without raising an exception, mark task completed *if* it wasn't already skipped/errored
            if task_completed_successfully:
                current_task_state = self.task_manager.get_task(task.id)
                if current_task_state and current_task_state.status == TaskStatus.RUNNING:
                    await self.task_manager.update_task_status(
                        task.id,
                        TaskStatus.COMPLETED,
                        detail="Task completed successfully by agent."
                    )
                elif current_task_state:
                     logger.debug(f"Task {task.id} status is already {current_task_state.status}, not marking completed again.")
                else:
                     logger.warning(f"Task {task.id} not found after successful agent run. Cannot mark completed.")


        except Exception as e:
            # Handle errors raised *by the agent execution*
            logger.error(f"Agent execution failed for task {task.id} ({task.description}): {e}", exc_info=True) # Log traceback here
            error_msg = str(e)
            # Ensure task exists before updating status to ERROR
            if self.task_manager.get_task(task.id):
                await self.task_manager.update_task_status(
                    task.id,
                    TaskStatus.ERROR,
                    error_message=error_msg,
                    detail=f"Agent failed: {error_msg[:100]}..."
                )
            else:
                logger.error(f"Task {task.id} not found, cannot mark as ERROR after agent failure.")

            # Pause the job - Moved this responsibility to the main loop (_run_research_flow)
            # self.pause_events[task.job_id].set()
            # await self.broadcast_job_status(task.job_id, JobStatus.PAUSED, f"Paused due to error in task {task.id}: {error_msg[:100]}...")

            # Re-raise the exception so the main loop catches it and pauses
            raise e
    async def _handle_planning_completion(self, planning_task: Task, sub_task_descriptions: List[str]):
        if not isinstance(sub_task_descriptions, list):
             logger.warning(f"Planner for task {planning_task.id} did not return a list of descriptions. Got: {type(sub_task_descriptions)}")
             # Store empty list as result to indicate failure/no output
             await self.task_manager.store_result(planning_task.id, [])
             return

        logger.info(f"Planning task {planning_task.id} completed. Adding {len(sub_task_descriptions)} sub-tasks for job {planning_task.job_id}.")
        for sub_task_desc in sub_task_descriptions:
            await self.task_manager.add_task(description=sub_task_desc, job_id=planning_task.job_id)

        # Add downstream tasks only if planning was successful
        has_analysis = any("analyze" in d.lower() or "synthesize" in d.lower() for d in sub_task_descriptions)
        has_report = any("generate report" in d.lower() for d in sub_task_descriptions)

        # Check existing tasks to avoid adding duplicates if run multiple times
        existing_tasks = self.task_manager.get_all_tasks()
        analysis_exists = any(("analyze" in t.description.lower() or "synthesize" in t.description.lower()) and t.job_id == planning_task.job_id for t in existing_tasks)
        report_exists = any(("generate report" in t.description.lower()) and t.job_id == planning_task.job_id for t in existing_tasks)

        if not has_analysis and not analysis_exists:
             await self.task_manager.add_task(description=f"Analyze & Synthesize findings for job {planning_task.job_id}", job_id=planning_task.job_id)
        if not has_report and not report_exists:
             await self.task_manager.add_task(description=f"Generate report for job {planning_task.job_id}", job_id=planning_task.job_id)

        # Store the generated sub-task descriptions as the result of the planning task
        # Moved this here from _dispatch_task to ensure it happens after adding tasks
        # await self.task_manager.store_result(planning_task.id, sub_task_descriptions)
        # Storing result is now done in _dispatch_task right after planning_agent.run

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

    async def broadcast_job_summary(self, summary: JobResultsSummary):
        """Broadcasts the research results summary via WebSocket."""
        logger.info(f"Broadcasting results summary for Job {summary.job_id}: Found {summary.unique_sources_found} sources.")
        # Use TaskManager's connection_manager instance
        await self.task_manager.connection_manager.broadcast_json(summary.dict())