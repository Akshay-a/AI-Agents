import logging
from typing import Dict, Any, Optional

from llm_providers import BaseLLMProvider
from task_manager import TaskManager # Needed to store result

logger = logging.getLogger(__name__)

class ReasoningAgent:
    def __init__(self, llm_provider: BaseLLMProvider, task_manager: TaskManager):
        self.llm_provider = llm_provider
        self.task_manager = task_manager

    async def run(self, query: str, task_id: str, job_id: str) -> None:
        """
        Executes a reasoning task using the LLM provider.

        Args:
            query (str): The query/instruction for the LLM.
            task_id (str): The ID of the current reasoning task.
            job_id (str): The parent job ID.

        Returns:
            None. Stores the result via TaskManager.

        Raises:
            RuntimeError: If the LLM call fails.
        """
        logger.info(f"[Job {job_id} | Task {task_id}] Reasoning Agent: Starting reasoning for query: '{query[:100]}...'")

        if not self.llm_provider:
             logger.error(f"[Job {job_id} | Task {task_id}] LLM Provider not available for Reasoning Agent.")
             raise RuntimeError("ReasoningAgent cannot function without an LLM provider.")

        try:
            # Simple prompt - could be enhanced via prompt library
            # For now, just pass the query directly
            response = await self.llm_provider.generate(
                prompt=query, # Use the query directly as the prompt
                temperature=0.5, # Adjust temperature as needed
                max_output_tokens=2048 # Set appropriate limit
            )

            logger.info(f"[Job {job_id} | Task {task_id}] Reasoning successful. Storing result.")
            await self.task_manager.store_result(task_id, {"reasoning_output": response})

        except Exception as e:
            logger.exception(f"[Job {job_id} | Task {task_id}] Error during Reasoning Agent LLM call: {e}")
            # Re-raise the exception for the orchestrator to handle
            raise RuntimeError(f"Reasoning Agent failed: {e}") from e