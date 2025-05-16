import asyncio
import logging
from typing import List, Dict, Any, Optional

from llm_providers import BaseLLMProvider # Use the base class
from llm_providers.prompt_library import format_map_prompt, format_reduce_prompt
from task_manager import TaskManager

logger = logging.getLogger(__name__)


CONTEXT_WINDOW_TOKENS = 1000000 # Check actual model limit
MAP_CHUNK_TARGET_TOKENS = 100000 # How large each chunk should ideally be for the Map step
MAP_PROMPT_RESERVE_TOKENS = 1000 # Tokens reserved for the Map prompt template itself
REDUCE_PROMPT_RESERVE_TOKENS = 4000 # Tokens reserved for the Reduce prompt template
MAX_CONCURRENT_MAP_CALLS = 5 # Limit concurrent LLM calls

class AnalysisAgent:
    def __init__(self, llm_provider: BaseLLMProvider, task_manager: TaskManager):
        self.llm_provider = llm_provider
        self.task_manager = task_manager
        # Estimate max tokens for text content based on provider and reserves
        self.max_map_chunk_tokens = MAP_CHUNK_TARGET_TOKENS - MAP_PROMPT_RESERVE_TOKENS
        self.max_reduce_context_tokens = (CONTEXT_WINDOW_TOKENS // 2) - REDUCE_PROMPT_RESERVE_TOKENS # Be conservative for reduce input

    async def run(self, topic: str, filter_task_id: str, current_task_id: str, job_id: str) -> None:
        """
        Runs the analysis and synthesis process using MapReduce.

        Args:
            topic (str): The original research topic.
            filter_task_id (str): The ID of the completed filtering task.
            current_task_id (str): The ID for this analysis task.
            job_id (str): The parent job ID.
        """
        logger.info(f"[Job {job_id} | Task {current_task_id}] Analysis Agent: Starting analysis for topic '{topic}' using results from filter task {filter_task_id}")

        # 1. Get Filtered Documents
        filtered_result = self.task_manager.get_result(filter_task_id)
        if not filtered_result or not isinstance(filtered_result, dict):
            logger.warning(f"[Job {job_id} | Task {current_task_id}] No valid result found for filter task {filter_task_id}. Cannot perform analysis.")
            await self.task_manager.store_result(current_task_id, {"error": "Filtering step did not produce valid results."})
            # Consider marking task as ERROR or SKIPPED
            raise ValueError("Filtering step did not produce valid results.")

        documents: List[Dict[str, Any]] = filtered_result.get("filtered_results", [])
        if not documents:
            logger.warning(f"[Job {job_id} | Task {current_task_id}] No documents found after filtering. Analysis cannot proceed.")
            await self.task_manager.store_result(current_task_id, {"summary": "No documents were found or survived the filtering process."})
            return # Mark as completed with this note

        logger.info(f"[Job {job_id} | Task {current_task_id}] Retrieved {len(documents)} documents for analysis.")

        # 2. Map Phase: Extract relevant info from each document/chunk
        map_tasks = []
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_MAP_CALLS)
        for doc in documents:
            map_tasks.append(self._map_document_wrapper(semaphore, doc, topic, job_id, current_task_id))

        mapped_results_raw = await asyncio.gather(*map_tasks)
        # Filter out None results (errors during mapping)
        mapped_insights = [res for res in mapped_results_raw if res is not None]

        if not mapped_insights:
            logger.error(f"[Job {job_id} | Task {current_task_id}] Map phase failed to extract any relevant information from {len(documents)} documents.")
            await self.task_manager.store_result(current_task_id, {"error": "Failed to extract relevant information from any source document."})
            raise RuntimeError("Map phase produced no usable insights.")

        logger.info(f"[Job {job_id} | Task {current_task_id}] Map phase completed. Got insights from {len(mapped_insights)} sources/chunks.")

        # 3. Reduce Phase: Synthesize mapped insights into a report
        try:
            final_report = await self._reduce_insights(mapped_insights, topic, job_id, current_task_id)
            logger.info(f"[Job {job_id} | Task {current_task_id}] Reduce phase completed. Generated final report.")
            await self.task_manager.store_result(current_task_id, {"report": final_report})

        except Exception as e:
            logger.exception(f"[Job {job_id} | Task {current_task_id}] Reduce phase failed: {e}")
            await self.task_manager.store_result(current_task_id, {"error": f"Failed to synthesize final report: {e}"})
            raise RuntimeError(f"Reduce phase failed: {e}") from e


    async def _map_document_wrapper(self, semaphore: asyncio.Semaphore, document: Dict, topic: str, job_id: str, parent_task_id: str) -> Optional[Dict]:
        """Wrapper to apply semaphore and handle errors for _map_document."""
        async with semaphore:
            try:
                return await self._map_document(document, topic, job_id, parent_task_id)
            except Exception as e:
                url = document.get('url', 'Unknown URL')
                logger.error(f"[Job {job_id} | Task {parent_task_id}] Error mapping document {url}: {e}", exc_info=False)
                return None # Return None on error

    async def _map_document(self, document: Dict, topic: str, job_id: str, parent_task_id: str) -> Optional[Dict]:
        """
        Processes a single document (potentially chunking it) for the Map step.
        Returns a dictionary {'url': str, 'extracted_info': str} or None if irrelevant/error.
        """
        url = document.get('url', 'Unknown Source')
        text = document.get('extracted_text', '')

        if not text:
            logger.warning(f"[Job {job_id} | Task {parent_task_id}] Skipping document {url}: No extracted text.")
            return None

        try:
            # Simple chunking: Process the whole document if it fits, otherwise skip (for now)
            # TODO: Implement more robust chunking based on tokens if needed
            doc_tokens = self.llm_provider.count_tokens(text) # Use provider's tokenizer

            if doc_tokens > self.max_map_chunk_tokens:
                logger.warning(f"[Job {job_id} | Task {parent_task_id}] Document {url} ({doc_tokens} tokens) exceeds map chunk limit ({self.max_map_chunk_tokens}). Skipping this document for now.")
                # In a more robust version, chunk the text here using _chunk_document
                # and process each chunk, then combine results for this source.
                # For simplicity now, we just skip.
                return None

            prompt = format_map_prompt(topic=topic, text_segment=text, url=url)
            logger.info(f"[Job {job_id} | Task {parent_task_id}] Calling LLM (Map) for document {url}...")

            extracted_info = await self.llm_provider.generate(
                prompt=prompt,
                temperature=0.2, # Lower temperature for factual extraction
                max_output_tokens=1024 # Max tokens for the *extracted info*
            )
            extracted_info = extracted_info.strip()

            if extracted_info.upper() == "IRRELEVANT":
                logger.info(f"[Job {job_id} | Task {parent_task_id}] Document {url} marked as irrelevant by LLM.")
                return None # Explicitly return None for irrelevant docs

            logger.info(f"[Job {job_id} | Task {parent_task_id}] Successfully extracted info from {url}.")
            return {"url": url, "extracted_info": extracted_info}

        except Exception as e:
            logger.error(f"[Job {job_id} | Task {parent_task_id}] LLM call failed during Map step for {url}: {e}", exc_info=False)
            # Re-raise or return None? Returning None allows partial results.
            return None


    async def _reduce_insights(self, insights: List[Dict], topic: str, job_id: str, parent_task_id: str) -> str:
        """
        Performs the Reduce step, synthesizing insights into a final report.
        Handles potential need for multi-stage reduction if insights are too large.
        """
        logger.info(f"[Job {job_id} | Task {parent_task_id}] Starting Reduce phase with {len(insights)} insights.")

        # Combine insights text for token check
        combined_text = "\n".join([f"Source: {i.get('url', 'N/A')}\n{i.get('extracted_info', '')}" for i in insights if i.get('extracted_info', '').strip().upper() != "IRRELEVANT"])
        combined_tokens = self.llm_provider.count_tokens(combined_text)

        if combined_tokens > self.max_reduce_context_tokens:
            logger.warning(f"[Job {job_id} | Task {parent_task_id}] Combined insights ({combined_tokens} tokens) exceed reduce limit ({self.max_reduce_context_tokens}). Attempting intermediate summarization.")
            # TODO: Implement multi-stage reduction (summarize insights in batches)
            # For now, we'll just use the formatted prompt which includes truncation logic.
            # A better approach would be to call the LLM recursively on batches of insights.
            pass # Rely on format_reduce_prompt's truncation for now

        prompt = format_reduce_prompt(topic=topic, mapped_insights=insights, max_tokens=self.max_reduce_context_tokens)

        # Check prompt tokens - might still be too large if template is huge
        prompt_tokens = self.llm_provider.count_tokens(prompt)
        available_output_tokens = CONTEXT_WINDOW_TOKENS - prompt_tokens - 100 # Reserve buffer

        if available_output_tokens < 500: # Need reasonable space for output
             logger.error(f"Reduce prompt itself ({prompt_tokens} tokens) leaves too little space for generation ({available_output_tokens} tokens). Cannot proceed.")
             raise ValueError("Reduce prompt too large, cannot generate report.")

        logger.info(f"[Job {job_id} | Task {parent_task_id}] Calling LLM (Reduce) to synthesize final report. Prompt tokens: {prompt_tokens}, Max output: {available_output_tokens}")

        final_report = await self.llm_provider.generate(
            prompt=prompt,
            temperature=0.5, # Slightly higher temp for more fluent synthesis
            max_output_tokens=max(500, available_output_tokens) # Ensure at least 500, use calculated max
        )

        return final_report.strip()

    # --- Optional Chunking Helper (More Advanced) ---
    def _chunk_document(self, text: str, max_chunk_tokens: int) -> List[str]:
        """
        Splits a document text into chunks based on token count.
        (Requires a reliable token counting method from the provider)
        """
        # Placeholder for a more sophisticated chunking strategy
        # Could split by paragraphs, sentences, or fixed token overlaps
        # This is non-trivial to get right.
        logger.warning("Document chunking based on tokens is not fully implemented. Large documents might be skipped.")
        # Simple fallback: return as one chunk if it fits, else maybe just the start?
        if self.llm_provider.count_tokens(text) <= max_chunk_tokens:
            return [text]
        else:
            # Very basic truncation - NEEDS IMPROVEMENT
            # Find suitable split point near max_chunk_tokens
            # For now, just return the beginning (bad strategy)
            estimated_chars = max_chunk_tokens * 4
            return [text[:estimated_chars]]