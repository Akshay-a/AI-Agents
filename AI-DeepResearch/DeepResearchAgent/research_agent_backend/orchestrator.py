import asyncio
import os
import logging
from typing import Dict, Optional, List, Any, Callable ,Awaitable, Tuple
from enum import Enum
import uuid
import json
from models import Task, TaskStatus , JobResultsSummary , FinalReportMessage, TaskType, TaskSuccessMessage, JobFailedMessage, JobProgressMessage, \
    TaskFailedMessage, TaskInputData
from task_manager import TaskManager # Assuming TaskManager handles status updates/broadcasts
from agents.planning import PlanningAgent # Import agent instances
from agents.search import SearchAgent
from agents.filtering import FilteringAgent
from agents.analysis import AnalysisAgent
from agents.reasoning import ReasoningAgent
from llm_providers import get_provider, BaseLLMProvider
from datetime import datetime, timezone
from pathlib import Path
from config import settings
from websocket_manager import ConnectionManager
from database_layer.database import Database

logger = logging.getLogger(__name__)

SEARCH_TASK_DELAY = 1.5

class JobStatus(str, Enum): # This Enum is heart of managing all the jobs and their states
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED" # Paused due to error, waiting for user , in this scenario orchestrator agent handles receving input from user and directs accordingly
    COMPLETED = "COMPLETED"
    FAILED = "FAILED" # Failed definitively

class Orchestrator:
    def __init__(self, task_manager: TaskManager, websocket_manager: ConnectionManager, database: Database, prompt_library_path: Optional[str] = None):
        self.task_manager = task_manager
        self.websocket_manager = websocket_manager
        self.db = database
        self.active_jobs: Dict[str, JobStatus] = {}
        self.pause_events: Dict[str, asyncio.Event] = {}
        self.job_tasks: Dict[str, asyncio.Task] = {} # To manage background tasks -> start with researching about task (that is the first task)

        try:
             # Assuming GOOGLE_API_KEY is set in .env
             self.llm_provider: BaseLLMProvider = get_provider(provider_name="gemini")
             logger.info(f"Initialized LLM Provider: {self.llm_provider.__class__.__name__} with model {self.llm_provider.get_model_name()}")
        except Exception as e:
             logger.error("Failed to initialize LLM Provider. Analysis Agent will fail.")
             # Handle this more gracefully - maybe prevent job start?
             self.llm_provider = None # Ensure it's None if init fails
        self.planning_agent = PlanningAgent(llm_provider=self.llm_provider) if self.llm_provider else None
        self.search_agent = SearchAgent(task_manager=self.task_manager)
        self.filtering_agent = FilteringAgent(task_manager=self.task_manager) 
        
        if self.llm_provider:
             self.analysis_agent = AnalysisAgent(llm_provider=self.llm_provider, task_manager=self.task_manager)
             self.reasoning_agent = ReasoningAgent(llm_provider=self.llm_provider,task_manager=self.task_manager)
        else:
             self.analysis_agent = None # Analysis won't work
             self.reasoning_agent = None

        self.agent_dispatch: Dict[TaskType, Callable[..., Awaitable[None]]] = {}
        if self.reasoning_agent:
            self.agent_dispatch[TaskType.REASON] = self.reasoning_agent.run
        if self.search_agent:
            self.agent_dispatch[TaskType.SEARCH] = self.search_agent.run
        if self.filtering_agent:
            self.agent_dispatch[TaskType.FILTER] = self._run_filter_agent
        if self.analysis_agent:
            self.agent_dispatch[TaskType.SYNTHESIZE] = self._run_analysis_agent 
        #Not initializing REPORT task here, it's handled in _run_research_flow

        logger.info(f"Agent dispatch map configured: {list(self.agent_dispatch.keys())}")

        # Initialize prompt library
        #if prompt_library_path is None:
        #    prompt_library_path = str(Path(__file__).parent / "llm_providers" / "prompts.json")
        #self.prompt_library = PromptLibrary(file_path=prompt_library_path)
    
    async def start_job(self, user_query: str, client_id: str) -> Tuple[str, List[Task]]:
        """
        Starts a new research job: creates a job record, plans tasks, adds them to the DB,
        and initiates the research flow in the background.
        Returns the job_id and the list of planned Task objects.
        """
        job_id = str(uuid.uuid4())
        logger.info(f"Starting new job {job_id} for query: '{user_query}' from client {client_id}")

        try:
            # 1. Create Job Record in Database
            await self.db.create_job(job_id=job_id, user_query=user_query)
            # The create_job in SqliteHandler sets status to RUNNING and timestamps.
            logger.info(f"Job {job_id} record created in database.")

            # 2. Generate Plan (list of TaskInputData)
            await self.websocket_manager.send_personal_json(
                JobProgressMessage(payload={"job_id": job_id, "message": "Generating research plan..."}).dict(),
                client_id
            )
            planned_tasks_data: List[TaskInputData] = await self.planning_agent.generate_plan(user_query, job_id)
            logger.info(f"***planned tasks are {planned_tasks_data}")
            if not planned_tasks_data:
                logger.warning(f"Job {job_id}: Planning phase did not produce any tasks.")
                await self.db.update_job_status(job_id, JobStatus.FAILED.value, "Planning failed: No tasks generated.")
                await self.websocket_manager.send_personal_json(
                    JobFailedMessage(payload={
                        "job_id": job_id,
                        "error": "Planning failed: No tasks were generated for your query."
                    }).dict(),
                    client_id
                )
                return job_id, []

            # 3. Add Planned Tasks to TaskManager (and thus Database)
            created_tasks: List[Task] = []
            for i, task_input_dict in enumerate(planned_tasks_data):
                try:
                    # Convert the dictionary to a TaskInputData object
                    task_input = TaskInputData(**task_input_dict)
                    task = await self.task_manager.add_task(
                        job_id=job_id,
                        sequence_order=i + 1, # 1-indexed sequence
                        task_input=task_input
                    )
                    created_tasks.append(task)
                except Exception as e:
                    logger.error(f"Job {job_id}: Failed to add planned task {task_input_dict} to DB: {e}", exc_info=True)
                    # If one task fails to be added, we might fail the whole job startup
                    await self.db.update_job_status(job_id, JobStatus.FAILED.value, f"Failed to add task {task_input.description} to database.")
                    await self.websocket_manager.send_personal_json(
                        JobFailedMessage(payload={
                            "job_id": job_id,
                            "error": f"Failed to initialize task: {task_input.description}"
                        }).dict(),
                        client_id
                    )
                    return job_id, [] # Return empty list as job setup failed
            
            logger.info(f"Job {job_id}: Successfully added {len(created_tasks)} planned tasks to the database.")

            # 4. Start _run_research_flow in the background
            background_task = asyncio.create_task(self._run_research_flow(job_id, user_query, client_id))
            self.active_jobs[job_id] = JobStatus.RUNNING
            self.pause_events[job_id] = asyncio.Event() # Initially unset

            await self.websocket_manager.send_personal_json(
                JobProgressMessage(payload={"job_id": job_id, "message": "Research plan generated. Starting execution..."}).dict(),
                client_id
            )
            return job_id, created_tasks # Return the Pydantic Task models

        except Exception as e:
            logger.error(f"Job {job_id}: Failed to start job: {e}", exc_info=True)
            # Ensure job status is FAILED if it was created
            try:
                # Check if job exists before trying to update. Avoids error if create_job failed.
                job_exists = await self.db.get_job(job_id)
                if job_exists:
                    await self.db.update_job_status(job_id, JobStatus.FAILED.value, f"Job startup failed: {str(e)}")
            except Exception as db_e:
                logger.error(f"Job {job_id}: Additionally failed to update job status to FAILED after startup error: {db_e}", exc_info=True)
            
            await self.websocket_manager.send_personal_json(
                JobFailedMessage(payload={"job_id": job_id, "error": f"Failed to start job: {str(e)}"}).dict(),
                client_id
            )
            return job_id, [] # job_id might be new, return empty task list

    async def _run_research_flow(self, job_id: str, user_query: str, client_id: str):
        """Manages the execution of tasks for a given job_id."""
        try:
            logger.info(f"Job {job_id}: Starting research flow.")
            await self.websocket_manager.send_personal_json(
                JobProgressMessage(payload={"job_id": job_id, "message": "Research in progress..."}).dict(), client_id)

            # Track the current phase of research to broadcast appropriate high-level messages
            search_phase_started = False
            filter_phase_started = False
            analysis_phase_started = False

            while True:
                next_task = await self.task_manager.get_next_pending_task_for_job(job_id)
                if not next_task:
                    if await self.task_manager.has_running_tasks(job_id):
                        await asyncio.sleep(1) # Wait for running tasks to complete
                        continue
                    elif await self.task_manager.has_errored_tasks(job_id):
                        logger.warning(f"Job {job_id}: No more pending tasks, but some tasks have errored. Job failed.")
                        await self.db.update_job_status(job_id, JobStatus.FAILED.value, "Job failed due to task errors.")
                        logger.info(f"Job {job_id}: Sending job failed message via websocket")
                        failed_message = JobFailedMessage(payload={
                            "job_id": job_id,
                            "error": "Job failed due to task errors."
                        })
                        await self.websocket_manager.send_personal_json(
                            failed_message.dict(), client_id
                        )
                        return
                    else:
                        logger.info(f"Job {job_id}: All tasks completed.")
                        break # All tasks processed

                # --- Broadcast Phase Updates ---
                if next_task.task_type == TaskType.SEARCH and not search_phase_started:
                    await self.websocket_manager.send_personal_json(
                        JobProgressMessage(payload={"job_id": job_id, "message": "Researching sources..."}).dict(), client_id)
                    search_phase_started = True
                elif next_task.task_type == TaskType.FILTER and not filter_phase_started:
                    await self.websocket_manager.send_personal_json(
                        JobProgressMessage(payload={"job_id": job_id, "message": "Consolidating information..."}).dict(), client_id)
                    filter_phase_started = True
                elif (next_task.task_type == TaskType.SYNTHESIZE or next_task.task_type == TaskType.REASON) and not analysis_phase_started:
                    await self.websocket_manager.send_personal_json(
                        JobProgressMessage(payload={"job_id": job_id, "message": "Analyzing and synthesizing..."}).dict(), client_id)
                    analysis_phase_started = True

                await self.task_manager.update_task_status(next_task.task_id, TaskStatus.RUNNING)
                logger.info(f"Job {job_id}: Executing task {next_task.task_id} ({next_task.task_type.value}: {next_task.description})")
                await self.websocket_manager.send_personal_json(
                    JobProgressMessage(payload={
                        "job_id": job_id,
                        "message": f"Executing task: {next_task.task_type.value} - {next_task.description}"
                    }).dict(), client_id)
                
                try:
                    agent_function = self.agent_dispatch.get(next_task.task_type)
                    if agent_function:
                        # Prepare arguments for the agent method
                        kwargs_for_agent = next_task.parameters.copy() if next_task.parameters else {}
                        kwargs_for_agent['task_id'] = next_task.task_id
                        kwargs_for_agent['job_id'] = job_id

                        # Different agents expect different parameter names
                        if next_task.task_type == TaskType.REASON:
                            # ReasoningAgent.run expects 'query', not 'topic'
                            if 'query' not in kwargs_for_agent and user_query:
                                kwargs_for_agent['query'] = user_query
                        elif next_task.task_type == TaskType.SYNTHESIZE:
                            # AnalysisAgent.run expects 'topic'
                            if 'topic' not in kwargs_for_agent and user_query:
                                kwargs_for_agent['topic'] = user_query

                        # Execute agent function with kwargs
                        task_result = await agent_function(**kwargs_for_agent)
                        
                        # Store result in database
                        if task_result is not None:
                            await self.task_manager.store_result(next_task.task_id, task_result)
                        
                        # Update task status to completed
                        await self.task_manager.update_task_status(next_task.task_id, TaskStatus.COMPLETED)
                        
                        # Send task success message (send the full updated task from DB)
                        completed_task_model = await self.task_manager.get_task(next_task.task_id)
                        if completed_task_model:
                            # Make sure we're sending a proper WebSocketMessage format
                            logger.info(f"Job {job_id}: Sending task success message for task {next_task.task_id}")
                            success_message = TaskSuccessMessage(payload=completed_task_model)
                            await self.websocket_manager.send_personal_json(
                                success_message.dict(), client_id
                            )
                        logger.info(f"Job {job_id}: Task {next_task.task_id} ({next_task.task_type.value}) completed.")
                    elif next_task.task_type == TaskType.REPORT: # REPORT task is special
                        logger.info(f"*******Entered Report Generation logic")
                        # Call our report task handler function
                        report_result = await self._run_report_task(
                            task_id=next_task.task_id,
                            job_id=job_id,
                            **next_task.parameters if next_task.parameters else {}
                        )
                        
                        # Extract the report content from the result
                        if report_result and isinstance(report_result, dict) : #and "report" in report_result:
                            final_report_content = report_result.get("report") # Use .get() for safety
                            if not final_report_content:
                                logger.error(f"Job {job_id}: Report task {next_task.task_id} did not produce 'report' key in its result dict.")
                                final_report_content = "Error: Report generation failed to produce content."
                                # Potentially mark task as error
                                await self.task_manager.update_task_status(next_task.task_id, TaskStatus.ERROR, "Report content not found in result")
                                failed_task_model = await self.task_manager.get_task(next_task.task_id)
                                if failed_task_model:
                                    await self.websocket_manager.send_personal_json(
                                        TaskFailedMessage(payload=failed_task_model).dict(), client_id
                                    )
                                # Continue or raise depending on how critical this is, for now we send the error content.

                            # Save the report to file
                            report_file_path = await self._save_report_to_file(job_id, user_query, final_report_content)
                            
                            # Update the task result with the report path 
                            # Update the result (we don't update status again as _run_report_task already did that)
                            report_result["report_path"] = report_file_path
                            await self.task_manager.store_result(next_task.task_id, report_result)
                            await self.task_manager.update_task_status(next_task.task_id, TaskStatus.COMPLETED) # Ensure status is COMPLETED
                            
                            # Send final report message
                            logger.info(f"Job {job_id}: Sending final report message via websocket")
                            final_report_message = FinalReportMessage(payload={
                                "job_id": job_id,
                                "report_markdown": final_report_content
                            })
                            await self.websocket_manager.send_personal_json(
                                final_report_message.dict(), client_id
                            )
                            logger.info(f"Job {job_id}: Final report generated and saved to {report_file_path}.")
                            # Update job status to COMPLETED in DB
                            await self.db.update_job_status(job_id, JobStatus.COMPLETED.value)
                            logger.info(f"Job {job_id} status updated to COMPLETED in database.")
                            return # Job successfully completed
                        else:
                            logger.error(f"Job {job_id}: Report task {next_task.task_id} did not produce a valid dictionary result or content.")
                            await self.task_manager.update_task_status(next_task.task_id, TaskStatus.ERROR, "Report generation failed to produce valid result")
                            failed_task_model = await self.task_manager.get_task(next_task.task_id)
                            if failed_task_model:
                                await self.websocket_manager.send_personal_json(
                                    TaskFailedMessage(payload=failed_task_model).dict(), client_id
                                )
                            # This will likely lead to job failure in the main loop checks.
                            raise ValueError("Cannot complete report: Invalid report content generated.")
                    else:
                        logger.warning(f"Job {job_id}: No agent function found for task type {next_task.task_type.value}. Skipping.")
                        await self.task_manager.update_task_status(next_task.task_id, TaskStatus.SKIPPED, "No agent for task type")
                        # Optionally send a task skipped message to client if needed
                
                except Exception as e:
                    logger.error(f"Job {job_id}: Error executing task {next_task.task_id} ({next_task.task_type.value}): {e}", exc_info=True)
                    error_message_str = f"Error in {next_task.task_type.value} task: {str(e)}"
                    await self.task_manager.update_task_status(next_task.task_id, TaskStatus.ERROR, error_message_str)
                    failed_task_model = await self.task_manager.get_task(next_task.task_id) # Get the task with updated status and error message
                    if failed_task_model:
                        logger.info(f"Job {job_id}: Sending task failed message for task {next_task.task_id}")
                        await self.websocket_manager.send_personal_json(
                            TaskFailedMessage(payload=failed_task_model).dict(), client_id
                        )
                    # Continue to next task, or job will fail if this was critical (handled by has_errored_tasks check)
                    # No explicit JobFailedMessage here, rely on the check at the beginning of the loop.

            # Final check for job status after loop finishes (e.g. if all tasks completed but no report was generated)
            current_job_details = await self.db.get_job(job_id)
            if current_job_details and current_job_details.get('status') != JobStatus.COMPLETED.value:
                if await self.task_manager.has_errored_tasks(job_id):
                    logger.warning(f"Job {job_id}: Exited research flow with errored tasks. Marking job as FAILED.")
                    await self.db.update_job_status(job_id, JobStatus.FAILED.value, "Job finished with errors in tasks.")
                    await self.websocket_manager.send_personal_json(
                        JobFailedMessage(payload={"job_id": job_id, "error": "Job finished with errors in one or more tasks."}).dict(), client_id)
                else:
                    logger.info(f"Job {job_id}: Exited research flow, no errors reported but not explicitly completed (e.g., no REPORT task). Considering it FAILED for now.")
                    # This state might need more nuanced handling. If all tasks are COMPLETED but no REPORT, is it a success?
                    # For now, if not COMPLETED via REPORT task, mark as FAILED. Needs review based on plan structure.
                    await self.db.update_job_status(job_id, JobStatus.FAILED.value, "Job finished without generating a final report.")
                    logger.info(f"Job {job_id}: Sending job failed message via websocket")
                    failed_message = JobFailedMessage(payload={
                        "job_id": job_id,
                        "error": "Job finished without generating a final report."
                    })
                    await self.websocket_manager.send_personal_json(
                        failed_message.dict(), client_id
                    )

        except asyncio.CancelledError:
            logger.info(f"Job {job_id}: Research flow was cancelled.")
            await self.db.update_job_status(job_id, JobStatus.FAILED.value, "Job cancelled during execution.")
            logger.info(f"Job {job_id}: Sending job cancelled message via websocket")
            cancel_message = JobFailedMessage(payload={
                "job_id": job_id,
                "error": "Job was cancelled."
            })
            await self.websocket_manager.send_personal_json(
                cancel_message.dict(), client_id
            )
        except Exception as e:
            logger.critical(f"Job {job_id}: Unhandled critical error in research flow: {e}", exc_info=True)
            await self.db.update_job_status(job_id, JobStatus.FAILED.value, f"Critical error in research flow: {str(e)}")
            logger.info(f"Job {job_id}: Sending critical error message via websocket")
            error_message = JobFailedMessage(payload={
                "job_id": job_id,
                "error": f"A critical error occurred: {str(e)}"
            })
            await self.websocket_manager.send_personal_json(
                error_message.dict(), client_id
            )
        finally:
            logger.info(f"Job {job_id}: Research flow processing finished.")
            if job_id in self.active_jobs:
                del self.active_jobs[job_id]

    async def _save_report_to_file(self, job_id: str, query: str, report_content: str) -> str:
        """Saves the generated report to a file and updates the job record in DB."""
        # Sanitize query to create a filename
        safe_query = "".join(c if c.isalnum() else "_" for c in query[:50])
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"report_{job_id}_{safe_query}_{timestamp}.md"
        
        output_dir = Path(settings.OUTPUT_DIR) / job_id # Store reports in a job-specific subfolder
        output_dir.mkdir(parents=True, exist_ok=True)
        report_file_path = output_dir / filename

        try:
            with open(report_file_path, "w", encoding="utf-8") as f:
                f.write(report_content)
            logger.info(f"Job {job_id}: Report saved to {report_file_path}")

            # Update the job record with the report path
            await self.db.update_job_report_path(job_id, str(report_file_path))
            logger.info(f"Job {job_id}: Final report path updated in database.")
            return str(report_file_path)
        except IOError as e:
            logger.error(f"Job {job_id}: Error saving report to file {report_file_path}: {e}", exc_info=True)
            # If saving fails, the job might still be considered complete but report path won't be set.
            # We could update job status to FAILED here if report saving is critical.
            # For now, log error and return a placeholder or re-raise.
            raise

    async def _run_filter_agent(self, task_id: str, job_id: str, **kwargs):
        """Wrapper to find inputs (search task IDs) for the filter agent."""
        logger.info(f"Filter wrapper called for task {task_id}, job {job_id}. Kwargs: {kwargs}")
        
        # Get completed search tasks for this job  
        search_tasks = await self.task_manager.get_completed_tasks_for_job(job_id, TaskType.SEARCH)
        search_task_ids = [st.task_id for st in search_tasks]
        
        if not search_task_ids:
            logger.warning(f"[Job {job_id} | Task {task_id}] Filter task found no preceding completed Search tasks.")
            raise ValueError("No completed search tasks found to filter")
        else:
            logger.info(f"[Job {job_id} | Task {task_id}] Filter task using results from {len(search_tasks)} completed search tasks with IDs: {search_task_ids}")

        # Call the actual filter agent run method
        try:
            filter_result = await self.filtering_agent.run(
                search_task_ids=search_task_ids, 
                current_task_id=task_id, 
                job_id=job_id
            )
            
            # Ensure filter_result is properly structured even if it's None or incomplete
            if filter_result is None:
                filter_result = {"filtered_results": [], "duplicates_removed": 0, "sources_analyzed_count": len(search_tasks)}
            elif not isinstance(filter_result.get("filtered_results"), list):
                filter_result["filtered_results"] = []
                
            # Log details about the filtering operation
            logger.info(f"[Job {job_id} | Task {task_id}] Filter completed with {len(filter_result.get('filtered_results', []))} results, " 
                        f"{filter_result.get('duplicates_removed', 0)} duplicates removed")
        except Exception as e:
            logger.error(f"[Job {job_id} | Task {task_id}] Error during filtering: {e}", exc_info=True)
            # Create a fallback filter result
            filter_result = {
                "filtered_results": [],
                "duplicates_removed": 0, 
                "sources_analyzed_count": len(search_tasks),
                "error": str(e),
                "status": "error"
            }

        # Broadcast summary after filter completes successfully 
        if filter_result and isinstance(filter_result, dict):
            filtered_items = filter_result.get("filtered_results", [])
            summary = JobResultsSummary(
                    job_id=job_id,
                    unique_sources_found=len(filtered_items),
                    duplicates_removed=filter_result.get("duplicates_removed", 0),
                    sources_analyzed_count=filter_result.get("sources_analyzed_count", len(search_tasks)),
                    top_sources=[
                        {"title": item.get("title", "N/A"), "url": item.get("url", "N/A")}
                        for item in filtered_items[:5] if isinstance(item, dict)
                    ]
                )
            #await self.broadcast_job_summary(summary)
        
        return filter_result

    async def _run_analysis_agent(self, task_id: str, job_id: str, topic: str, **kwargs):
        """Wrapper to find inputs (preceding filter task ID) for the analysis agent."""
        logger.debug(f"Analysis wrapper called for task {task_id}, job {job_id}. Topic: {topic}. Kwargs: {kwargs}")
        
        # Get the completed filter tasks for this job
        filter_tasks = await self.task_manager.get_completed_tasks_for_job(job_id, TaskType.FILTER)
        
        if not filter_tasks:
            logger.error(f"[Job {job_id} | Task {task_id}] Cannot run Analysis: No preceding completed Filter task found.")
            # Raise error to stop processing this task
            raise ValueError("Preceding Filter task not found or not completed for Analysis.")
        
        # Assume latest completed filter task is the relevant one
        filter_task = filter_tasks[-1]  # Last one is most recent
        filter_task_id = filter_task.task_id
        
        # Get the actual filter result
        filter_result = await self.task_manager.get_result(filter_task_id)
        if not filter_result:
            logger.error(f"[Job {job_id} | Task {task_id}] Filter task {filter_task_id} has no stored result.")
            raise ValueError(f"Filter task {filter_task_id} has no result for Analysis.")
        
        logger.info(f"[Job {job_id} | Task {task_id}] Analysis task using results from Filter Task {filter_task_id}")

        # Call the actual analysis agent run method with the filter result
        analysis_result = await self.analysis_agent.run(
            topic=topic, # Passed from parameters via kwargs_for_agent -> **kwargs
            filter_result=filter_result,  # Pass filter result directly
            current_task_id=task_id,
            job_id=job_id
        )
        
        return analysis_result

    async def _run_report_task(self, task_id: str, job_id: str, source_task_id: Optional[str] = None, **kwargs):
         """
         Handles the REPORT task. Typically finds the result of the preceding
         SYNTHESIZE or REASON task and stores it under the REPORT task's ID.
         If no such task is available, will try to use filter results directly.    
         """
         logger.info(f"Report wrapper called for task {task_id}, job {job_id}. Source: {source_task_id}. Kwargs ignored: {kwargs}")
         report_content = None
         
         if source_task_id:
             # Use specified source if provided
             result_to_report = await self.task_manager.get_result(source_task_id)
             if result_to_report is None:
                 logger.error(f"Report task {task_id} could not find result for specified source task {source_task_id}.")
                   
             else:
                 # Extract content from the specified source
                 if isinstance(result_to_report, dict):
                     report_content = result_to_report.get("report") or result_to_report.get("analysis_output") or result_to_report.get("reasoning_output")
                 elif isinstance(result_to_report, str):
                     report_content = result_to_report # Assume direct string output is the report
         
         # If no report content yet, try to find it from completed tasks
         if not report_content:
             # Find latest completed synthesis or reasoning task
             # Get all task objects from task_manager (not results!)
             synthesis_tasks = await self.task_manager.get_completed_tasks_for_job(job_id, TaskType.SYNTHESIZE)
             reason_tasks = await self.task_manager.get_completed_tasks_for_job(job_id, TaskType.REASON)
             
             potential_tasks = []
             if synthesis_tasks:
                 potential_tasks.extend(synthesis_tasks)
             if reason_tasks:
                 potential_tasks.extend(reason_tasks)
                 
             # Sort by sequence_order to get the latest one
             potential_tasks.sort(key=lambda t: t.sequence_order, reverse=True)
                 
             if potential_tasks:
                 # Use the latest completed task
                 latest_task = potential_tasks[0]
                 source_task_id = latest_task.task_id
                 logger.info(f"Report task {task_id} automatically targeting result from task {source_task_id} (Type: {latest_task.task_type.value})")
                 result_to_report = await self.task_manager.get_result(source_task_id)
                 
                 if result_to_report:
                     # Extract content
                     if isinstance(result_to_report, dict):
                         report_content = result_to_report.get("report") or result_to_report.get("analysis_output") or result_to_report.get("reasoning_output")
                     elif isinstance(result_to_report, str):
                         report_content = result_to_report
         
         # Fallback: if still no report content, try using filter results directly
         if not report_content:
             logger.warning(f"Report task {task_id} could not find a relevant source task. Trying to use filter results as fallback.")
             
             # Get the latest filter task results
             filter_tasks = await self.task_manager.get_completed_tasks_for_job(job_id, TaskType.FILTER)
             
             if filter_tasks:
                 filter_task = filter_tasks[-1]  # Use the latest one
                 filter_result = await self.task_manager.get_result(filter_task.task_id)
                 
                 if filter_result and isinstance(filter_result, dict) and "filtered_results" in filter_result:
                     # Generate a simple report from filter results
                     filtered_items = filter_result.get("filtered_results", [])
                     if filtered_items:
                         logger.info(f"Generating a simple report from {len(filtered_items)} filtered items as fallback.")
                         
                         # Create a simple markdown report listing the sources
                         report_lines = [
                             "# AI Impact on Software Development - Information Sources",
                             "",
                             "The following sources contain information about the impact of AI on software development jobs:",
                             ""
                         ]
                         
                         # Add the sources
                         for i, item in enumerate(filtered_items[:10], 1):  # Top 10 sources
                             title = item.get("title", "Untitled Source")
                             url = item.get("url", "No URL")
                             report_lines.append(f"{i}. [{title}]({url})")
                         
                         report_lines.extend([
                             "",
                             "## Note",
                             "",
                             "This is a simplified report listing sources only. The detailed synthesis could not be completed successfully."
                         ])
                         
                         report_content = "\n".join(report_lines)
         
         # If we have report content, store it
         if report_content and isinstance(report_content, str):
             # Store the extracted or generated content
             result_dict = {"report": report_content}
             await self.task_manager.store_result(task_id, result_dict)
             logger.info(f"Report task {task_id} completed with content from {source_task_id if source_task_id else 'fallback mechanism'}.")
             return result_dict
         
         # If we reached here, we couldn't generate any report
         logger.warning(f"Report task {task_id}: Could not extract or generate any report content.")
         placeholder_report = {"report": "No report could be generated due to missing or invalid source data."}
         await self.task_manager.store_result(task_id, placeholder_report)
         # Return the placeholder report
         return placeholder_report

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

    async def _handle_final_report(self, job_id: str):
        """
        Finds the final report and returns it.
        If found, saves and broadcasts the report.
        Returns the report content on success, None on failure.
        """
        logger.info(f"Job {job_id}: Looking for final report content...")
        
        # First try to find completed REPORT tasks
        report_task = None
        synthesis_task = None
        reason_task = None
        
        # Get all tasks from task_manager (not results!)
        tasks = list(self.task_manager.tasks.values())
        
        # Check tasks in reverse order for the most recent relevant one
        for task in reversed(tasks):
            if task.job_id == job_id and task.status == TaskStatus.COMPLETED:
                if task.task_type == TaskType.REPORT and not report_task:
                    report_task = task
                elif task.task_type == TaskType.SYNTHESIZE and not synthesis_task:
                    synthesis_task = task
                elif task.task_type == TaskType.REASON and not reason_task:
                    reason_task = task

        # Use the highest priority task found (REPORT > SYNTHESIZE > REASON)
        last_relevant_task = report_task or synthesis_task or reason_task

        if last_relevant_task:
             final_result = self.task_manager.get_result(last_relevant_task.id)
             report_markdown = None
             if isinstance(final_result, dict):
                 # Look for common keys
                 report_markdown = final_result.get("report") or final_result.get("analysis_output") or final_result.get("reasoning_output")
             elif isinstance(final_result, str):
                 report_markdown = final_result # Simple string result

             # ADDED LOGGING STARTS HERE
             logger.info(f"Job {job_id}: In _handle_final_report. last_relevant_task: {last_relevant_task.id if last_relevant_task else 'None'} (Type: {last_relevant_task.task_type.value if last_relevant_task else 'None'})")
             logger.info(f"Job {job_id}: In _handle_final_report. final_result from TaskManager for task {last_relevant_task.id if last_relevant_task else 'N/A'}: {final_result}")
             logger.info(f"Job {job_id}: In _handle_final_report. Extracted report_markdown: '{report_markdown}' (Type: {type(report_markdown)})")
             # ADDED LOGGING ENDS HERE

             if isinstance(report_markdown, str) and report_markdown.strip():
                 logger.info(f"Found final report content in task {last_relevant_task.id} (Type: {last_relevant_task.task_type.value}). Saving and broadcasting.")
                 await self._save_report_to_file(job_id, report_markdown)
                 await self._broadcast_final_report(job_id, report_markdown)
                 return report_markdown
             else:
                 logger.warning(f"Job {job_id} finished, but final report from task {last_relevant_task.id} was empty or invalid.")
                 return None
        else:
             logger.warning(f"Job {job_id} finished, but no final REPORT, SYNTHESIZE, or REASON task found with results.")
             return None

    async def _broadcast_final_report(self, job_id: str, report_markdown: str):
        """Broadcasts the final report via WebSocket."""
        logger.info(f"Broadcasting final report for job {job_id} via WebSocket.")
        message = FinalReportMessage(job_id=job_id, report_markdown=report_markdown)
        # Use TaskManager's connection_manager instance
        await self.task_manager.connection_manager.broadcast_json(message.dict())

    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves the status and details of a job from the database."""
        job_details = await self.db.get_job(job_id)
        if job_details:
            # Optionally, enrich with task information if needed by frontend
            # tasks = await self.task_manager.get_all_tasks_for_job(job_id)
            # job_details['tasks'] = [task.dict() for task in tasks]
            return job_details # Returns a dict from the DB handler
        return None

    async def get_all_jobs(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Retrieves all jobs from the database."""
        return await self.db.get_all_jobs(limit=limit, offset=offset)

    async def shutdown(self):
        """Gracefully shuts down active jobs."""
        logger.info("Orchestrator shutdown initiated. Cancelling active jobs...")
        active_job_ids = list(self.active_jobs.keys()) # Get a list of keys before iterating
        for job_id in active_job_ids:
            logger.info(f"Cancelling job {job_id} as part of shutdown...")
            await self.cancel_job(job_id)
        
        # Wait for all active tasks to finish cancellation (or a timeout)
        if self.active_jobs: # Check if any jobs are still tracked (cancel_job should remove them)
            await asyncio.gather(*self.active_jobs.values(), return_exceptions=True)
        logger.info("All active jobs processed during shutdown.")

    async def cancel_job(self, job_id: str):
        """Cancels an active job."""
        if job_id in self.active_jobs:
            task = self.active_jobs[job_id]
            if not task.done():
                task.cancel()
                logger.info(f"Job {job_id}: Cancellation request sent.")
                # The _run_research_flow's finally block should handle DB status update
                try:
                    await task # Allow cancellation to propagate
                except asyncio.CancelledError:
                    logger.info(f"Job {job_id} successfully cancelled.")
            else:
                logger.info(f"Job {job_id}: Was already done, no active cancellation needed.")
        else:
            logger.warning(f"Job {job_id}: Cannot cancel, no active job found.")
            # Check DB for job status if it was already processed or failed
            job_details = await self.db.get_job(job_id)
            if job_details and job_details.get('status') not in [JobStatus.COMPLETED.value, JobStatus.FAILED.value]:
                 await self.db.update_job_status(job_id, JobStatus.FAILED.value, "Job cancelled while not actively running in orchestrator.")

# Example of how Orchestrator might be initialized in main.py:
# async def startup_event():
#     global orchestrator_instance, db_instance
#     db_instance = await Database.get_instance()
#     task_manager_instance = TaskManager(database=db_instance)
#     websocket_manager_instance = ConnectionManager()
#     orchestrator_instance = Orchestrator(
#         task_manager=task_manager_instance,
#         websocket_manager=websocket_manager_instance,
#         database=db_instance
#     )
#     # Potentially connect websocket manager here if it has an init method
#     # await websocket_manager_instance.connect_all_clients_somehow() # if needed

# async def shutdown_event():
#     if orchestrator_instance:
#         await orchestrator_instance.shutdown()
#     if db_instance:
#         await db_instance.close()