import asyncio
import logging
from typing import List

logger = logging.getLogger(__name__)

class PlanningAgent:
    async def run(self, topic: str, job_id: str) -> List[str]:
        """
        Simulates the planning phase.
        Returns a list of sub-task descriptions.
        """
        logger.info(f"[Job {job_id}] Planning Agent: Starting planning for topic '{topic}'...")
        await asyncio.sleep(2) # Simulate work

        # Simulate generating sub-tasks
        sub_tasks = [
            f"Search: Key concepts of '{topic}'",
            f"Search: History of '{topic}'",
            f"Search: Current challenges in '{topic}'",
            f"Filter: Consolidate search results for '{topic}'",
            # Add Analyze/Report tasks later if Planner defines the whole flow
        ]
        logger.info(f"[Job {job_id}] Planning Agent: Generated {len(sub_tasks)} sub-tasks.")
        return sub_tasks

# Instantiate the agent (or manage instantiation differently later)
planning_agent = PlanningAgent()