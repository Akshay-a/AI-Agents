import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple

from llm_providers import BaseLLMProvider
# Assume prompt library has FINAL_SYNTHESIS_PROMPT_TEMPLATE, DOCUMENT_SUMMARY_PROMPT_TEMPLATE
from llm_providers.prompt_library import format_final_synthesis_prompt, format_document_summary_prompt
from task_manager import TaskManager
# Optional: for embedding filtering
# from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# --- Configuration Constants (Adjust based on LLM/Setup) ---
# Example assuming Gemini 1.5 Pro's 1M token window
CONTEXT_WINDOW_LIMIT = 1000000
OUTPUT_BUFFER = 8192 # Reserve ample space for the output generation
MAX_CONTEXT_TOKENS = CONTEXT_WINDOW_LIMIT - OUTPUT_BUFFER
# Relevance filtering threshold (adjust based on embedding model/method)
RELEVANCE_THRESHOLD = 0.7
# Max concurrent LLM calls for summarizing overflow docs
MAX_CONCURRENT_SUMMARIES = 5
# Max tokens for a single doc summary call (should be much smaller than main window)
MAX_SUMMARY_INPUT_TOKENS = 128000 # e.g., for models with 128k context

class AnalysisAgent:
    def __init__(self, llm_provider: BaseLLMProvider, task_manager: TaskManager):
        self.llm_provider = llm_provider
        self.task_manager = task_manager
        # Optional: Initialize embedding model if using that filtering method
        # self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2') # Example
        logger.info(f"AnalysisAgent initialized. Max context tokens for synthesis: {MAX_CONTEXT_TOKENS}")

    async def run(self, topic: str, filter_task_id: str, current_task_id: str, job_id: str) -> None:
        """Main entry point for the analysis agent."""
        logger.info(f"[Job {job_id} | Task {current_task_id}] Analysis Agent: Starting context-maximized analysis for topic '{topic}'")

        # 1. Get Filtered Documents
        documents = self._get_filtered_documents(filter_task_id, job_id, current_task_id)
        if not documents: return # Error handled in getter

        # 2. Filter & Prioritize
        relevant_docs = await self._filter_and_prioritize(documents, topic, job_id, current_task_id)
        if not relevant_docs:
            logger.warning(f"[Job {job_id} | Task {current_task_id}] No relevant documents found after filtering/prioritization.")
            await self.task_manager.store_result(current_task_id, {"report": "No relevant documents found to generate a report."})
            return

        # 3. Pack Context & Synthesize
        try:
            final_report = await self._pack_context_and_synthesize(relevant_docs, topic, job_id, current_task_id)
            logger.info(f"[Job {job_id} | Task {current_task_id}] Successfully generated final report.")
            await self.task_manager.store_result(current_task_id, {"report": final_report})
        except Exception as e:
            logger.exception(f"[Job {job_id} | Task {current_task_id}] Failed during synthesis phase: {e}")
            await self.task_manager.store_result(current_task_id, {"error": f"Report synthesis failed: {e}"})
            raise # Re-raise for orchestrator to catch

    def _get_filtered_documents(self, filter_task_id: str, job_id: str, current_task_id: str) -> List[Dict[str, Any]]:
        """Retrieves and validates documents from the filter task result."""
        filtered_result = self.task_manager.get_result(filter_task_id)
        if not filtered_result or not isinstance(filtered_result, dict):
            logger.error(f"[Job {job_id} | Task {current_task_id}] Invalid or missing result from filter task {filter_task_id}.")
            raise ValueError("Filtering step did not produce valid results.")

        documents: List[Dict[str, Any]] = filtered_result.get("filtered_results", [])
        if not documents:
            logger.warning(f"[Job {job_id} | Task {current_task_id}] No documents found in filter task result.")
            # Store empty report? Or let run() handle it? Let run() handle.
            return []

        logger.info(f"[Job {job_id} | Task {current_task_id}] Retrieved {len(documents)} documents from filter task {filter_task_id}.")
        return documents

    async def _filter_and_prioritize(self, documents: List[Dict[str, Any]], topic: str, job_id: str, current_task_id: str) -> List[Dict[str, Any]]:
        """Filters documents for relevance and prioritizes them."""
        logger.info(f"[Job {job_id} | Task {current_task_id}] Filtering and prioritizing {len(documents)} documents...")
        prioritized_docs = []

        # --- Calculate token counts first ---
        docs_with_tokens = []
        for doc in documents:
            text = doc.get('extracted_text', '')
            if not text: continue
            try:
                token_count = self.llm_provider.count_tokens(text)
                doc['token_count'] = token_count
                docs_with_tokens.append(doc)
            except Exception as e:
                logger.warning(f"[Job {job_id} | Task {current_task_id}] Failed to count tokens for doc {doc.get('url', 'N/A')}: {e}. Skipping.")
                continue

        # --- Relevance Filtering (Example using simple keyword check, replace with embeddings) ---
        topic_keywords = set(topic.lower().split()) # Very basic
        relevant_docs_intermediate = []
        for doc in docs_with_tokens:
            text_lower = doc.get('extracted_text', '').lower()
            # Simple check: count topic keywords in text
            score = sum(1 for keyword in topic_keywords if keyword in text_lower)
            # Normalize score (optional, very crude)
            relevance_score = score / (len(topic_keywords) + 1e-6)

            # --- Replace above with Embedding Similarity ---
            # if self.embedding_model:
            #     try:
            #         topic_embedding = self.embedding_model.encode(topic)
            #         # Encode snippet for speed
            #         snippet = doc.get('extracted_text', '')[:1000] # Encode first ~250 tokens
            #         doc_embedding = self.embedding_model.encode(snippet)
            #         # Calculate cosine similarity (requires numpy or similar)
            #         # relevance_score = util.cos_sim(topic_embedding, doc_embedding)[0][0].item()
            #         relevance_score = 0.0 # Placeholder
            #         logger.debug(f"Doc {doc.get('url', 'N/A')} embedding relevance: {relevance_score:.4f}")
            #     except Exception as e:
            #         logger.warning(f"Failed to calculate embedding relevance for {doc.get('url', 'N/A')}: {e}")
            #         relevance_score = 0.0 # Default score if embedding fails
            # else:
            #     relevance_score = 0.5 # Default if no embedding model

            if relevance_score >= RELEVANCE_THRESHOLD:
                 doc['relevance_score'] = relevance_score
                 relevant_docs_intermediate.append(doc)
            else:
                 logger.info(f"[Job {job_id} | Task {current_task_id}] Filtering out doc {doc.get('url', 'N/A')} due to low relevance score ({relevance_score:.4f} < {RELEVANCE_THRESHOLD}).")


        # --- Prioritization ---
        # Sort by relevance score (descending), maybe break ties with length or other factors
        prioritized_docs = sorted(relevant_docs_intermediate, key=lambda x: x.get('relevance_score', 0.0), reverse=True)

        logger.info(f"[Job {job_id} | Task {current_task_id}] Prioritized {len(prioritized_docs)} relevant documents.")
        return prioritized_docs


    async def _pack_context_and_synthesize(self, relevant_docs: List[Dict[str, Any]], topic: str, job_id: str, current_task_id: str) -> str:
        """Packs context, handles overflow via summarization, and calls final synthesis LLM."""
        logger.info(f"[Job {job_id} | Task {current_task_id}] Packing context for final synthesis...")

        # Estimate base prompt tokens (template structure without content)
        # This is rough, actual prompt formatting function should be more precise
        base_prompt_str = format_final_synthesis_prompt(topic=topic, synthesis_input_text="")
        base_prompt_tokens = self.llm_provider.count_tokens(base_prompt_str)
        available_context_tokens = MAX_CONTEXT_TOKENS - base_prompt_tokens

        prompt_context_docs: List[Dict[str, Any]] = []
        overflow_docs: List[Dict[str, Any]] = []
        current_token_count = 0

        # Pack full documents by priority
        for doc in relevant_docs:
            doc_token_count = doc.get('token_count', 0)
            # Add tokens for formatting (e.g., "--- Source URL: ... --- \n\n")
            formatting_tokens = self.llm_provider.count_tokens(f"\n\n--- Source: {doc.get('url', '')} ---\n\n")

            if current_token_count + doc_token_count + formatting_tokens <= available_context_tokens:
                prompt_context_docs.append(doc)
                current_token_count += doc_token_count + formatting_tokens
            else:
                overflow_docs.append(doc)

        logger.info(f"[Job {job_id} | Task {current_task_id}] Packed {len(prompt_context_docs)} documents as raw text ({current_token_count} tokens). {len(overflow_docs)} documents overflowed.")

        # --- Prepare Synthesis Input ---
        synthesis_input_parts = []
        # Add full text documents
        for doc in prompt_context_docs:
            synthesis_input_parts.append(f"--- Source (Full Text): {doc.get('url', 'N/A')} ---\n\n{doc.get('extracted_text', '')}")

        # Summarize overflow documents if any
        overflow_summaries: List[Tuple[str, str]] = [] # List of (url, summary)
        if overflow_docs:
            logger.info(f"[Job {job_id} | Task {current_task_id}] Summarizing {len(overflow_docs)} overflow documents...")
            overflow_summaries = await self._summarize_overflow_documents(overflow_docs, topic, job_id, current_task_id)
            logger.info(f"[Job {job_id} | Task {current_task_id}] Generated {len(overflow_summaries)} summaries for overflow documents.")

            # Add summaries to input, clearly marked
            for url, summary in overflow_summaries:
                 # Check token count of summary before adding
                 summary_tokens = self.llm_provider.count_tokens(summary)
                 formatting_tokens = self.llm_provider.count_tokens(f"\n\n--- Source (Summary): {url} ---\n\n")
                 if current_token_count + summary_tokens + formatting_tokens <= available_context_tokens:
                      synthesis_input_parts.append(f"--- Source (Summary): {url} ---\n\n{summary}")
                      current_token_count += summary_tokens + formatting_tokens
                 else:
                      logger.warning(f"[Job {job_id} | Task {current_task_id}] Skipping summary from {url} as it would exceed context limit even after packing full texts.")


        synthesis_input_text = "\n\n".join(synthesis_input_parts)

        if not synthesis_input_text:
             logger.error(f"[Job {job_id} | Task {current_task_id}] No content (neither full text nor summaries) could be packed for final synthesis.")
             return "Error: Could not prepare any content for the final report synthesis."

        # --- Final Synthesis Call ---
        logger.info(f"[Job {job_id} | Task {current_task_id}] Making final synthesis LLM call. Total input context tokens approx: {current_token_count + base_prompt_tokens}")
        final_prompt = format_final_synthesis_prompt(topic=topic, synthesis_input_text=synthesis_input_text)

        # Final check on prompt tokens vs limit
        final_prompt_tokens = self.llm_provider.count_tokens(final_prompt)
        if final_prompt_tokens >= CONTEXT_WINDOW_LIMIT - OUTPUT_BUFFER:
             logger.error(f"[Job {job_id} | Task {current_task_id}] CRITICAL: Final synthesis prompt ({final_prompt_tokens} tokens) exceeds effective context limit ({MAX_CONTEXT_TOKENS}). Aborting synthesis.")
             # This indicates a flaw in packing logic or token estimation
             raise ValueError("Final synthesis prompt exceeded context limit.")

        final_report = await self.llm_provider.generate(
            prompt=final_prompt,
            temperature=0.6, # Adjust as needed for synthesis quality
            # Max output is implicitly limited by OUTPUT_BUFFER calculation
            max_output_tokens=OUTPUT_BUFFER - 100 # Final safety buffer
        )
        return final_report.strip()


    async def _summarize_overflow_documents(self, overflow_docs: List[Dict[str, Any]], topic: str, job_id: str, parent_task_id: str) -> List[Tuple[str, str]]:
        """Summarizes documents that didn't fit in the main context window."""
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_SUMMARIES)
        summary_tasks = []

        for doc in overflow_docs:
            summary_tasks.append(
                self._summarize_single_document_wrapper(semaphore, doc, topic, job_id, parent_task_id)
            )

        results = await asyncio.gather(*summary_tasks)
        # Filter out None results (errors) and return list of (url, summary) tuples
        return [(url, summary) for url, summary in results if url and summary]


    async def _summarize_single_document_wrapper(self, semaphore: asyncio.Semaphore, doc: Dict[str, Any], topic: str, job_id: str, parent_task_id: str) -> Optional[Tuple[str, str]]:
         """Applies semaphore and error handling for single doc summarization."""
         url = doc.get('url', 'Unknown URL')
         async with semaphore:
             try:
                 summary = await self._summarize_single_document(doc, topic, job_id, parent_task_id)
                 return (url, summary) if summary else None
             except Exception as e:
                 logger.error(f"[Job {job_id} | Task {parent_task_id}] Error summarizing overflow doc {url}: {e}", exc_info=False)
                 return None


    async def _summarize_single_document(self, doc: Dict[str, Any], topic: str, job_id: str, parent_task_id: str) -> Optional[str]:
         """Calls LLM to summarize a single document."""
         text = doc.get('extracted_text', '')
         url = doc.get('url', 'Unknown URL')
         token_count = doc.get('token_count', 0)

         if not text: return None

         # Check if doc itself exceeds summarization context limit
         if token_count > MAX_SUMMARY_INPUT_TOKENS:
             logger.warning(f"[Job {job_id} | Task {parent_task_id}] Overflow document {url} ({token_count} tokens) is too large even for summarization ({MAX_SUMMARY_INPUT_TOKENS}). Skipping summarization.")
             # TODO: Implement chunking within summarization if needed
             return None # Skip summarization for this doc

         summary_prompt = format_document_summary_prompt(topic=topic, document_text=text, url=url)
         # Estimate prompt tokens to calculate max output for summary
         summary_prompt_tokens = self.llm_provider.count_tokens(summary_prompt)
         max_summary_output = MAX_SUMMARY_INPUT_TOKENS - summary_prompt_tokens - 100 # Buffer

         if max_summary_output < 100: # Need some space for a meaningful summary
              logger.warning(f"[Job {job_id} | Task {parent_task_id}] Summary prompt for {url} leaves too little output space ({max_summary_output} tokens). Skipping.")
              return None

         logger.info(f"[Job {job_id} | Task {parent_task_id}] Calling LLM to summarize overflow doc: {url}")
         summary = await self.llm_provider.generate(
             prompt=summary_prompt,
             temperature=0.3, # Lower temp for factual summary
             max_output_tokens=max_summary_output
         )
         return summary.strip() if summary else None