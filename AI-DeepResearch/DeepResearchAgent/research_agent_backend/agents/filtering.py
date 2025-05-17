import asyncio
import logging
import random
from typing import List, Dict, Any, Optional, Set
from collections import defaultdict

# Need access to TaskManager to fetch results
# This creates a potential circular dependency if imported directly.
# Pass task_manager instance or necessary methods upon initialization or call.

logger = logging.getLogger(__name__)

class FilteringAgent:
    def __init__(self, task_manager: Optional[Any] = None):
        """Initialize with TaskManager instance to fetch results."""
        self.task_manager = task_manager

    async def run(self, search_task_ids: List[str], current_task_id: str, job_id: str) -> Dict[str, Any]:
        """
        Filters and consolidates results from previous search tasks.

        Args:
            search_task_ids: List of task IDs for the preceding search tasks.
            current_task_id: The ID of the current filtering task.
            job_id: The ID of the parent job.

        Returns:
            Dict containing filtered results, stats, and metadata.

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
        sources_by_id = {}
        error_count = 0
        
        for search_task_id in search_task_ids:
            try:
                # Properly await the result from the task manager
                result = await self.task_manager.get_result(search_task_id)
                if result:
                    # Ensure result is a list (as stored by SearchAgent)
                    if isinstance(result, list):
                        raw_results_list.extend(result)
                        sources_by_id[search_task_id] = len(result)
                        logger.info(f"[Job {job_id} | Task {current_task_id}] Retrieved {len(result)} items from search task {search_task_id}")
                    else:
                        logger.warning(f"[Job {job_id} | Task {current_task_id}] Expected list result from task {search_task_id}, got {type(result)}. Skipping.")
                        error_count += 1
                else:
                    logger.warning(f"[Job {job_id} | Task {current_task_id}] No result found for search task {search_task_id}. It might have failed or been skipped.")
                    error_count += 1
            except Exception as e:
                logger.error(f"[Job {job_id} | Task {current_task_id}] Error retrieving results from task {search_task_id}: {e}", exc_info=True)
                error_count += 1

        if not raw_results_list:
            logger.warning(f"[Job {job_id} | Task {current_task_id}] Filtering Agent: No valid search results found from preceding tasks.")
            empty_result = {
                "filtered_results": [],
                "duplicates_removed": 0,
                "sources_analyzed_count": len(search_task_ids),
                "error_count": error_count,
                "status": "empty"
            }
            await self.task_manager.store_result(current_task_id, empty_result)
            return empty_result

        logger.info(f"[Job {job_id} | Task {current_task_id}] Retrieved a total of {len(raw_results_list)} raw items to filter.")
        
        # 2. Preprocess and clean data
        cleaned_results = []
        skipped_items = 0
        
        for item in raw_results_list:
            # Skip any non-dictionary items or items without URL
            if not isinstance(item, dict) or 'url' not in item:
                skipped_items += 1
                continue
                
            # Ensure all required fields exist
            cleaned_item = {
                'url': item.get('url', ''),
                'title': item.get('title', 'Untitled'),
                'text': item.get('extracted_text', ''),
                'source': item.get('source', 'Unknown'),
                'timestamp': item.get('timestamp', ''),
                'relevance_score': item.get('relevance_score', 0.0)
            }
            
            # Only add items with actual content
            if cleaned_item['url'] and (cleaned_item['text'] or cleaned_item['title']):
                cleaned_results.append(cleaned_item)
            else:
                logger.info(f"[Job {job_id} | Task {current_task_id}] Skipping item with URL: {cleaned_item['url']} due to missing content.")
                skipped_items += 1
                
        logger.info(f"[Job {job_id} | Task {current_task_id}] Preprocessing: kept {len(cleaned_results)} valid items, skipped {skipped_items} invalid items.")
        
        # 3. Perform deduplication based on URL
        url_to_result: Dict[str, Dict[str, Any]] = {}
        content_fingerprints: Set[str] = set()
        content_duplicates = 0
        url_duplicates = 0
        
        for item in cleaned_results:
            url = item['url']
            
            # Check for URL duplicates
            if url in url_to_result:
                url_duplicates += 1
                # If duplicate, keep the one with more content or higher relevance
                existing_item = url_to_result[url]
                if (len(item['text']) > len(existing_item['text']) or 
                    item.get('relevance_score', 0) > existing_item.get('relevance_score', 0)):
                    url_to_result[url] = item
                continue
                
            # Simple content fingerprinting to catch near-duplicates
            # Use first 100 chars of content as a fingerprint, will prolly create a efficient method to create hash of embedding of something to identify simillar documents at high level and cut them down , but have to unit test this method to push this for this agent
            content_fp = item['text'][:100] if len(item['text']) > 100 else item['text']
            if content_fp and content_fp in content_fingerprints:
                content_duplicates += 1
                continue
                
            # If not duplicate, add to our collections
            if content_fp:
                content_fingerprints.add(content_fp)
            url_to_result[url] = item

        filtered_results = list(url_to_result.values())
        total_duplicates = url_duplicates + content_duplicates
        
        # 4. Sort results by relevance if available
        filtered_results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        logger.info(f"[Job {job_id} | Task {current_task_id}] Filtering complete. "
                   f"Kept {len(filtered_results)} unique results, "
                   f"removed {url_duplicates} URL duplicates and {content_duplicates} content duplicates.")

        # 5. Create and store result
        result_payload = {
            "filtered_results": filtered_results,
            "duplicates_removed": total_duplicates,
            "sources_analyzed_count": len(search_task_ids),
            "sources_by_id": sources_by_id,
            "initial_items_count": len(raw_results_list),
            "cleaned_items_count": len(cleaned_results),
            "url_duplicates": url_duplicates,
            "content_duplicates": content_duplicates,
            "skipped_items": skipped_items,
            "error_count": error_count,
            "status": "success"
        }
        
        await self.task_manager.store_result(current_task_id, result_payload)
        logger.info(f"Stored filtered results for task {current_task_id}: {len(filtered_results)} items.")
        return result_payload

# Instantiate the agent - Orchestrator should pass the task_manager instance
filtering_agent = FilteringAgent() 