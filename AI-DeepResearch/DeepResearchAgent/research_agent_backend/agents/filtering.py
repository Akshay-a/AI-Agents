
import asyncio
import logging
import random
from typing import List, Dict, Any, Optional

# Need access to TaskManager to fetch results
# This creates a potential circular dependency if imported directly.
# Pass task_manager instance or necessary methods upon initialization or call.

logger = logging.getLogger(__name__)

class FilteringAgent:
    def __init__(self, task_manager: Optional[Any] = None):
        """Initialize with TaskManager instance to fetch results."""
        self.task_manager = task_manager

    async def run(self, search_task_ids: List[str], current_task_id: str, job_id: str) -> None:
        """
        Filters and consolidates results from previous search tasks.

        Args:
            search_task_ids: List of task IDs for the preceding search tasks.
            current_task_id: The ID of the current filtering task.
            job_id: The ID of the parent job.

        Returns:
            None. Stores the filtered results via TaskManager.

        Raises:
             RuntimeError: If TaskManager is not available or if simulation fails.
        """
        logger.info(f"[Job {job_id} | Task {current_task_id}] Filtering Agent: Starting filtering based on results from tasks: {search_task_ids}")

        if not self.task_manager:
             error_msg = "TaskManager instance not provided to FilteringAgent."
             logger.error(f"[Job {job_id} | Task {current_task_id}] {error_msg}")
             raise RuntimeError(error_msg)

        # 1. Fetch Results from Preceding Search Tasks
        raw_results_list = []
        for search_task_id in search_task_ids:
            result = self.task_manager.get_result(search_task_id)
            if result:
                # Ensure result is a list (as stored by SearchAgent)
                if isinstance(result, list):
                    raw_results_list.extend(result)
                    logger.info(f"[Job {job_id} | Task {current_task_id}] Retrieved {len(result)} items from search task {search_task_id}")
                else:
                    logger.warning(f"[Job {job_id} | Task {current_task_id}] Expected list result from task {search_task_id}, got {type(result)}. Skipping.")
            else:
                logger.warning(f"[Job {job_id} | Task {current_task_id}] No result found for search task {search_task_id}. It might have failed or been skipped.")

        if not raw_results_list:
            logger.warning(f"[Job {job_id} | Task {current_task_id}] Filtering Agent: No valid search results found from preceding tasks.")
            await self._store_filtered_results(current_task_id, [], 0, len(search_task_ids))
            return

        logger.info(f"[Job {job_id} | Task {current_task_id}] Retrieved a total of {len(raw_results_list)} raw items to filter.")
        await asyncio.sleep(random.uniform(0.5, 1.5)) # Simulate work

        # 2. Perform Filtering (Example: Deduplication based on URL)
        unique_results_map: Dict[str, Dict[str, Any]] = {}
        for item in raw_results_list:
            if isinstance(item, dict) and 'url' in item:
                url = item['url']
                if url not in unique_results_map:
                    unique_results_map[url] = item
            else:
                 logger.debug(f"[Job {job_id} | Task {current_task_id}] Skipping item during filtering, not a valid dict with URL: {item}")


        filtered_results = list(unique_results_map.values())
        duplicates_removed = len(raw_results_list) - len(filtered_results)

        # 3. Simulate Potential Failure (Optional)
        if random.random() < 0.05: # 5% chance of failure
            error_msg = "Simulated filtering process error."
            logger.error(f"[Job {job_id} | Task {current_task_id}] Filtering Agent: {error_msg}")
            raise RuntimeError(error_msg)

        logger.info(f"[Job {job_id} | Task {current_task_id}] Filtering complete. Kept {len(filtered_results)} unique results based on URL, removed {duplicates_removed} potential duplicates.")

        # 4. Store Filtered Results
        await self._store_filtered_results(current_task_id, filtered_results, duplicates_removed, len(search_task_ids))

    async def _store_filtered_results(self, task_id: str, results: List[Dict[str, Any]], duplicates: int, sources_count: int):
        """Stores the filtered results and metadata in the TaskManager."""
        if not self.task_manager:
             # This case should ideally be caught earlier, but double-check
             logger.critical(f"Cannot store filtered results for {task_id}: TaskManager unavailable.")
             return

        result_payload = {
            "filtered_results": results,
            "duplicates_removed": duplicates,
            "sources_analyzed_count": sources_count # Count of search tasks used as input
        }
        await self.task_manager.store_result(task_id, result_payload)
        logger.info(f"Stored filtered results for task {task_id}.")

# Instantiate the agent - Orchestrator should pass the task_manager instance
filtering_agent = FilteringAgent() # Orchestrator will set task_manager if needed, or pass it in run
# Modify Orchestrator to pass task_manager to filtering_agent.run or ensure it's set at init.
# Let's stick to initializing it in the orchestrator like SearchAgent for consistency.
