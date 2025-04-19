import asyncio
import logging
import random
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class FilteringAgent:
    async def run(self, search_results: List[Dict[str, Any]], job_id: str, task_id: str) -> Dict[str, Any]:
        """
        Simulates filtering and consolidating search results.
        Takes a list of result dictionaries from multiple search tasks.
        Returns a consolidated/filtered set of results.
        """
        logger.info(f"[Job {job_id} | Task {task_id}] Filtering Agent: Starting filtering for {len(search_results)} sets of results...")
        await asyncio.sleep(random.uniform(1, 2)) # Simulate work

        if not search_results:
            logger.warning(f"[Job {job_id} | Task {task_id}] Filtering Agent: No search results provided.")
            return {"filtered_results": [], "duplicates_removed": 0, "sources_analyzed": 0}

        all_urls = []
        for result_set in search_results:
            if isinstance(result_set, dict) and 'results' in result_set:
                 all_urls.extend(result_set.get('results', []))

        # Simple duplicate removal
        unique_urls = sorted(list(set(all_urls)))
        duplicates_removed = len(all_urls) - len(unique_urls)

        # Simulate potential failure
        if random.random() < 0.05: # 5% chance of failure
            error_msg = "Simulated filtering process error."
            logger.error(f"[Job {job_id} | Task {task_id}] Filtering Agent: {error_msg}")
            raise RuntimeError(error_msg)

        logger.info(f"[Job {job_id} | Task {task_id}] Filtering Agent: Filtering complete. Kept {len(unique_urls)} unique results, removed {duplicates_removed} duplicates.")

        return {"filtered_results": unique_urls, "duplicates_removed": duplicates_removed, "sources_analyzed": len(search_results)}

# Instantiate the agent
filtering_agent = FilteringAgent()