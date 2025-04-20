
import asyncio
import os
import logging
from typing import List, Dict, Any, Optional
import aiohttp
from trafilatura import extract
from duckduckgo_search import AsyncDDGS  # Use DuckDuckGo search
import json # Import json for structured logging/results
import random # For jitter in retry logic
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Constants ---
DEFAULT_NUM_RESULTS = 20
MAX_CONCURRENT_FETCHES = 5
REQUEST_TIMEOUT = 25 # seconds
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

class SearchAgent:
    def __init__(self, task_manager: Optional[Any] = None):
        # Optionally store task_manager if needed directly, but primarily use passed-in task_id
        self.task_manager = task_manager

    async def run(self, query: str, task_id: str, job_id: str, num_results: int = DEFAULT_NUM_RESULTS) -> None:
        """
        Performs a search using DuckDuckGo, fetches content asynchronously,
        extracts text, and stores results in the TaskManager.

        Args:
            query: The search query.
            task_id: The ID of the current search task.
            job_id: The ID of the parent job.
            num_results: The desired number of search results.

        Returns:
            None. Results are stored via the TaskManager.

        Raises:
            RuntimeError: If the search API call fails or major errors occur.
        """
        logger.info(f"[Job {job_id} | Task {task_id}] Search Agent: Starting search for '{query}' using DuckDuckGo...")

        # 1. Perform Search using DuckDuckGo  , replaced below method with new retry method to handle rate limits
        search_results_list = await self._perform_duckduckgo_search_with_retry(query, num_results, task_id, job_id)

        if not search_results_list:
            logger.warning(f"[Job {job_id} | Task {task_id}] No search results found for query '{query}'.")
            await self._store_results(task_id, [])
            return # Nothing more to do

        # 2. Asynchronously Fetch and Extract Content
        logger.info(f"[Job {job_id} | Task {task_id}] Fetching content for {len(search_results_list)} URLs...")
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)
        fetch_tasks = []

        # **Use a single session for connection pooling -> aiohttp when requesting multiple URLs, it tries to open and close conn for each req so we are pooling connections for efficientcy**
        async with aiohttp.ClientSession(headers={'User-Agent': USER_AGENT}) as session:
            for result_item in search_results_list:
                url = result_item.get('link') # Changed from 'href' to 'link' to match DuckDuckGo's response structure
                if url:
                    fetch_tasks.append(
                        self._fetch_and_extract(session, semaphore, url, result_item, task_id, job_id)
                    )

            processed_results = await asyncio.gather(*fetch_tasks)

        # Filter out None values (from failed fetches/extractions)
        final_results = [res for res in processed_results if res]
        logger.info(f"[Job {job_id} | Task {task_id}] Successfully processed {len(final_results)} out of {len(search_results_list)} search results.")

        # 3. Store Results
        await self._store_results(task_id, final_results)

        logger.info(f"[Job {job_id} | Task {task_id}] Search Agent: Finished processing for query '{query}'. Results stored.")


    async def _perform_duckduckgo_search(self, query: str, num_results: int, task_id: str, job_id: str) -> List[Dict[str, Any]]:
        """Performs the actual search using the duckduckgo_search library."""
        try:
            logger.info(f"[Job {job_id} | Task {task_id}] Calling DuckDuckGo search with query: {query}")
            results = []
            async with AsyncDDGS() as ddgs:
                 async for r in ddgs.text(query, max_results=num_results):
                     # Adapt the result structure to match what _fetch_and_extract expects
                     results.append({
                         'link': r.get('href'), # Original key is 'href'
                         'title': r.get('title'),
                         'snippet': r.get('body'), # Original key is 'body'
                         # Add any other fields from 'r' if needed later
                     })

            logger.info(f"[Job {job_id} | Task {task_id}] DuckDuckGo returned {len(results)} results.")
            return results

        except Exception as e:
            logger.error(f"[Job {job_id} | Task {task_id}] Error during DuckDuckGo search call: {e}", exc_info=True)
            # Re-raise as a runtime error for the orchestrator to catch
            raise RuntimeError(f"Failed to execute search via DuckDuckGo: {e}")
    
    async def _perform_duckduckgo_search_with_retry(self, query: str, num_results: int, task_id: str, job_id: str, max_retries: int = 3, initial_delay: float = 2.0) -> List[Dict[str, Any]]:
        """Performs DDG search with exponential backoff on rate limit errors."""
        retries = 0
        delay = initial_delay
        while retries <= max_retries:
            try:
                logger.info(f"[Job {job_id} | Task {task_id}] Attempting DuckDuckGo search (Attempt {retries + 1}/{max_retries + 1})...")
                results = []
                # Use timeout within DDGS context manager if available, otherwise rely on overall request timeout
                async with AsyncDDGS(timeout=20) as ddgs: # Added timeout
                     search_results: List[Dict[str, Any]] = ddgs.text(query, max_results=num_results)
                     for r in search_results:
                         results.append({
                             'link': r.get('href'),
                             'title': r.get('title'),
                             'snippet': r.get('body'),
                         })

                logger.info(f"[Job {job_id} | Task {task_id}] DuckDuckGo search successful on attempt {retries + 1}. Found {len(results)} results.")
                return results

            # Catch the specific RuntimeError potentially indicating rate limit, or broader exceptions
            except Exception as e:
                # Check if the error message likely indicates a rate limit (based on the observed error)
                # This is fragile as the error message could change. A better check would be specific exception type if library provided one.
                is_rate_limit_error = "Ratelimit" in str(e) or "rate limit" in str(e).lower() or (isinstance(e, RuntimeError) and "DuckDuckGo" in str(e))

                if is_rate_limit_error and retries < max_retries:
                    retries += 1
                    # Add jitter: random small variation to the delay
                    jitter = delay * random.uniform(0.1, 0.5)
                    wait_time = delay + jitter
                    logger.warning(f"[Job {job_id} | Task {task_id}] Rate limit detected (or suspected) on attempt {retries}. Retrying in {wait_time:.2f} seconds... Error: {e}")
                    await asyncio.sleep(wait_time)
                    delay *= 2 # Exponential backoff
                else:
                    # Max retries reached or it's a different kind of error
                    logger.error(f"[Job {job_id} | Task {task_id}] Error during DuckDuckGo search call after {retries + 1} attempts: {e}", exc_info=True)
                    # Re-raise as a runtime error for the orchestrator to catch
                    raise RuntimeError(f"Failed to execute search via DuckDuckGo after {retries + 1} attempts: {e}")

        # Should not be reached if max_retries > 0, but as a fallback
        logger.error(f"[Job {job_id} | Task {task_id}] Exhausted all retries for DuckDuckGo search.")
        raise RuntimeError("Exhausted all retries for DuckDuckGo search.")


    async def _fetch_and_extract(self, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore, url: str, search_result_item: Dict[str, Any], task_id: str, job_id: str) -> Optional[Dict[str, Any]]:
        """Fetches HTML content from a URL and extracts text using trafilatura."""
        async with semaphore: # Limit concurrency
            try:
                logger.info(f"[Job {job_id} | Task {task_id}] Fetching URL: {url}")
                # Some sites might block non-browser user agents, keep the standard one
                async with session.get(url, timeout=REQUEST_TIMEOUT, ssl=False, allow_redirects=True) as response: # Added allow_redirects
                    # Check if the content type suggests it's downloadable (PDF, DOC etc.) rather than HTML
                    content_type = response.headers.get('Content-Type', '').lower()
                    if not ('html' in content_type or 'text' in content_type) and response.status == 200:
                         logger.warning(f"[Job {job_id} | Task {task_id}] Skipping non-HTML content type '{content_type}' for URL: {url}")
                         return None # Skip non-HTML content that trafilatura likely can't handle

                    response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
                    html_content = await response.text()

                    # Extract text
                    # Use favor_recall=True for potentially more text, though maybe less precise main content
                    extracted_text = extract(html_content, include_comments=False, include_tables=True, favor_recall=True) # Keep tables, might be relevant

                    if extracted_text:
                        logger.debug(f"[Job {job_id} | Task {task_id}] Successfully extracted text from {url} (length: {len(extracted_text)})")
                        return {
                            'url': url,
                            'title': search_result_item.get('title', ''),
                            'extracted_text': extracted_text,
                            'raw_snippet': search_result_item.get('snippet', '') # Changed from 'raw_snippet'
                        }
                    else:
                        logger.warning(f"[Job {job_id} | Task {task_id}] Trafilatura failed to extract main content from {url}. Using raw snippet as fallback.")
                        # Fallback: Use the snippet from search results if extraction fails
                        raw_snippet = search_result_item.get('snippet')
                        if raw_snippet:
                             return {
                                'url': url,
                                'title': search_result_item.get('title', ''),
                                'extracted_text': raw_snippet, # Use snippet as extracted text
                                'raw_snippet': raw_snippet
                            }
                        else:
                            logger.warning(f"[Job {job_id} | Task {task_id}] No content extracted and no raw snippet available for {url}. Skipping.")
                            return None


            except aiohttp.ClientResponseError as e:
                 # Log specific HTTP errors
                 logger.warning(f"[Job {job_id} | Task {task_id}] HTTP error {e.status} for {url}: {e.message}")
                 return None
            except aiohttp.ClientError as e:
                 # General client errors (connection issues, etc.)
                 logger.warning(f"[Job {job_id} | Task {task_id}] Client error fetching {url}: {e}")
                 return None
            except asyncio.TimeoutError:
                logger.warning(f"[Job {job_id} | Task {task_id}] Timeout fetching URL: {url}")
                return None
            except Exception as e:
                # Catch-all for unexpected errors during fetch/extraction
                logger.error(f"[Job {job_id} | Task {task_id}] Error processing URL {url}: {e}", exc_info=False) # Log error but don't spam traceback
                return None

    async def _store_results(self, task_id: str, results: List[Dict[str, Any]]):
        """Stores the processed results in the TaskManager."""
        if not self.task_manager:
             logger.error(f"TaskManager reference not available in SearchAgent. Cannot store results for task {task_id}.")
             # This indicates an initialization problem. Attempt to use global instance as fallback.
             try:
                 # Dynamic import might hide dependency issues, use cautiously.
                 from ..task_manager import task_manager # Adjusted import path assuming task_manager.py is one level up
                 if task_manager:
                      await task_manager.store_result(task_id, results)
                      logger.info(f"Stored {len(results)} processed results for task {task_id} using globally accessed TaskManager.")
                 else:
                      raise ImportError("Global task_manager not found or resolved.")
             except ImportError as e:
                  logger.critical(f"Failed to store results for task {task_id}. TaskManager not available via instance or global import: {e}")
                  # Consider raising an exception here to halt the job if results can't be stored.
                  pass # Current behavior: Log critical error and continue.
        else:
            # Use the instance variable if it was provided during initialization
            await self.task_manager.store_result(task_id, results)
            logger.info(f"Stored {len(results)} processed results for task {task_id} using provided TaskManager instance.")


# Note: Instantiation logic remains outside this class.
# The orchestrator or main script should handle creating SearchAgent instances
# and potentially providing the task_manager dependency.
