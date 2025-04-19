import asyncio
import random
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class SearchAgent:
    async def run(self, query: str, job_id: str, task_id: str) -> Dict[str, Any]:
        """
        Simulates searching the web for a query.
        Can randomly fail.
        Returns simulated search results (e.g., list of URLs or snippets).
        """
        logger.info(f"[Job {job_id} | Task {task_id}] Search Agent: Starting search for '{query}'...")
        await asyncio.sleep(random.uniform(2, 4)) # Simulate network latency

        # Simulate potential failure
        if random.random() < 0.15: # 15% chance of failure
             error_msg = f"Simulated search API failure for query: '{query}'"
             logger.error(f"[Job {job_id} | Task {task_id}] Search Agent: {error_msg}")
             raise ValueError(error_msg)

        # Simulate successful results
        results = {
            "query": query,
            "results": [
                f"http://example.com/{query.replace(' ', '_')}_result1",
                f"http://example.com/{query.replace(' ', '_')}_result2_from_{random.randint(1,100)}",
                f"http://duplicate.com/{query.replace(' ', '_')}",
                f"http://another-site.org/related_to_{query.replace(' ', '_')}"
            ],
            "count": 4
        }
        logger.info(f"[Job {job_id} | Task {task_id}] Search Agent: Found {results['count']} results for '{query}'.")
        return results

# Instantiate the agent
search_agent = SearchAgent()