import asyncio
import os
import logging
from typing import List, Dict, Any, Optional
import aiohttp
from trafilatura import extract
from serpapi import SerpApiClient # Use SerpApi client
import json # Import json for structured logging/results
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
load_dotenv() 
# Load API Key - Ensure this is set in your environment
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")

# --- Constants ---
DEFAULT_NUM_RESULTS = 10
MAX_CONCURRENT_FETCHES = 5
REQUEST_TIMEOUT = 15 # seconds
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

class SearchAgent:
    def __init__(self, task_manager: Optional[Any] = None):
        # Optionally store task_manager if needed directly, but primarily use passed-in task_id
        self.task_manager = task_manager

    async def run(self, query: str, task_id: str, job_id: str, num_results: int = DEFAULT_NUM_RESULTS) -> None:
        """
        Performs a search using a Meta-Search API (SerpApi), fetches content asynchronously,
        extracts text, and stores results in the TaskManager.

        Args:
            query: The search query.
            task_id: The ID of the current search task.
            job_id: The ID of the parent job.
            num_results: The desired number of search results.

        Returns:
            None. Results are stored via the TaskManager.

        Raises:
            ValueError: If the SerpApi API key is missing.
            RuntimeError: If the search API call fails or major errors occur.
        """
        logger.info(f"[Job {job_id} | Task {task_id}] Search Agent: Starting search for '{query}'...")

        if not SERPAPI_API_KEY:
            logger.error(f"[Job {job_id} | Task {task_id}] SerpApi API key (SERPAPI_API_KEY) not found in environment variables.")
            raise ValueError("SerpApi API key not configured.")

        # 1. Perform Search using SerpApi
        search_results_list = await self._perform_serpapi_search(query, num_results, task_id, job_id)

        if not search_results_list:
            logger.warning(f"[Job {job_id} | Task {task_id}] No search results found for query '{query}'.")
            # Store empty results? Or let the orchestrator handle this?
            # For now, store empty list. Task status will be updated by orchestrator later.
            await self._store_results(task_id, [])
            return # Nothing more to do

        # 2. Asynchronously Fetch and Extract Content
        logger.info(f"[Job {job_id} | Task {task_id}] Fetching content for {len(search_results_list)} URLs...")
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)
        fetch_tasks = []

        # Use a single session for connection pooling
        async with aiohttp.ClientSession(headers={'User-Agent': USER_AGENT}) as session:
            for result_item in search_results_list:
                url = result_item.get('link')
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


    async def _perform_serpapi_search(self, query: str, num_results: int, task_id: str, job_id: str) -> List[Dict[str, Any]]:
        """Performs the actual search using SerpApi client."""
        params = {
            "q": query,
            "num": num_results,
            "api_key": SERPAPI_API_KEY,
            "engine": "google", # Specify engine (e.g., google, bing)
            # Add other parameters like location, gl, hl etc. if needed
        }
        try:
            logger.debug(f"[Job {job_id} | Task {task_id}] Calling SerpApi with query: {query}")
            client = SerpApiClient(params)
            results = client.get_dict() # Synchronous client call, consider async version if library supports it

            if "error" in results:
                 error_msg = results["error"]
                 logger.error(f"[Job {job_id} | Task {task_id}] SerpApi search failed: {error_msg}")
                 raise RuntimeError(f"SerpApi Error: {error_msg}")

            organic_results = results.get("organic_results", [])
            logger.info(f"[Job {job_id} | Task {task_id}] SerpApi returned {len(organic_results)} organic results.")
            return organic_results

        except Exception as e:
            logger.error(f"[Job {job_id} | Task {task_id}] Error during SerpApi call: {e}", exc_info=True)
            # Re-raise as a runtime error for the orchestrator to catch
            raise RuntimeError(f"Failed to execute search via SerpApi: {e}")


    async def _fetch_and_extract(self, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore, url: str, search_result_item: Dict[str, Any], task_id: str, job_id: str) -> Optional[Dict[str, Any]]:
        """Fetches HTML content from a URL and extracts text using trafilatura."""
        async with semaphore: # Limit concurrency
            try:
                logger.debug(f"[Job {job_id} | Task {task_id}] Fetching URL: {url}")
                async with session.get(url, timeout=REQUEST_TIMEOUT, ssl=False) as response: # Added ssl=False for potential SSL issues
                    response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
                    html_content = await response.text()

                    # Extract text
                    extracted_text = extract(html_content, include_comments=False, include_tables=False)

                    if extracted_text:
                        logger.debug(f"[Job {job_id} | Task {task_id}] Successfully extracted text from {url} (length: {len(extracted_text)})")
                        return {
                            'url': url,
                            'title': search_result_item.get('title', ''),
                            'extracted_text': extracted_text,
                            'raw_snippet': search_result_item.get('snippet', '')
                        }
                    else:
                        logger.warning(f"[Job {job_id} | Task {task_id}] Trafilatura failed to extract main content from {url}. Skipping.")
                        return None

            except aiohttp.ClientError as e:
                logger.warning(f"[Job {job_id} | Task {task_id}] HTTP fetch error for {url}: {e}")
                return None
            except asyncio.TimeoutError:
                logger.warning(f"[Job {job_id} | Task {task_id}] Timeout fetching URL: {url}")
                return None
            except Exception as e:
                logger.error(f"[Job {job_id} | Task {task_id}] Error processing URL {url}: {e}", exc_info=False) # Log error but don't spam traceback for every URL failure
                return None

    async def _store_results(self, task_id: str, results: List[Dict[str, Any]]):
        """Stores the processed results in the TaskManager."""
        if not self.task_manager:
             logger.error(f"TaskManager reference not available in SearchAgent. Cannot store results for task {task_id}.")
             # This indicates an initialization problem.
             # For now, we'll try to import and use the global instance if available (not ideal)
             try:
                 from task_manager import task_manager # Assuming a global instance might exist
                 if task_manager:
                      await task_manager.store_result(task_id, results)
                      logger.info(f"Stored {len(results)} processed results for task {task_id} using globally accessed TaskManager.")
                 else:
                      raise ImportError("Global task_manager not found.")
             except ImportError as e:
                  logger.critical(f"Failed to store results for task {task_id}. TaskManager not available: {e}")
                  # In a real scenario, this might need to raise an exception to halt the process cleanly.
                  # For now, log critical error and proceed.
                  pass
        else:
            # Use the instance variable if it was provided during initialization
            await self.task_manager.store_result(task_id, results)
            logger.info(f"Stored {len(results)} processed results for task {task_id} using provided TaskManager instance.")


# Instantiate the agent (consider dependency injection later)
# This global instantiation might be problematic if task_manager isn't ready
# We will rely on the Orchestrator passing the correct task_manager instance or method access.
# A factory function or dependency injection framework would be better.
# For now, modify the run method to potentially receive the store_result callback.
# Let's adjust Orchestrator to pass the storage mechanism.

# search_agent = SearchAgent() # Defer instantiation or handle dependencies
