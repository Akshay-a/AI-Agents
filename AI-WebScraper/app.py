import asyncio
import os
import logging
from typing import List, Dict, Any, Optional
import json
from ddgs import DDGS
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, LLMConfig, LLMExtractionStrategy
from crawl4ai.processors.pdf import PDFCrawlerStrategy, PDFContentScrapingStrategy
from rag_manager import RAGManager
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Constants ---
DEFAULT_NUM_RESULTS = 20
MAX_CONCURRENT_FETCHES = 5
REQUEST_TIMEOUT = 25  # seconds

class SearchAgent:
    def __init__(self, rag_db_path: str = "./chroma_db"):
        """Initialize the SearchAgent.
        
        Args:
            rag_db_path: Path to store the RAG vector database
        """
        # Initialize the RAG manager for storing and retrieving documents
        self.rag_manager = RAGManager(persist_directory=rag_db_path)

    async def run(self, query: str, num_results: int = DEFAULT_NUM_RESULTS) -> List[Dict[str, Any]]:
        """
        Performs a search using DuckDuckGo, fetches content asynchronously,
        extracts text using crawl4AI with LLM strategy, and returns the results.

        Args:
            query: The search query.
            num_results: Maximum number of search results to process.
            
        Returns:
            List of processed search results with extracted content and question context
        """
        logger.info(f"Starting search for query: {query}")

        try:
            # 1. Perform Search
            search_results_list = await self._perform_duckduckgo_search_with_retry(query, num_results)
            if not search_results_list:
                logger.warning(f"No search results found for query: {query}")
                return []

            # 2. Extract content using crawl4AI with LLM strategy
            processed_results = await self._extract_with_crawl4ai(search_results_list)
            
            logger.info(f"Successfully processed {len(processed_results)} out of {len(search_results_list)} search results.")
            
            # Store and return results with question context
            stored_results = await self._store_results(processed_results, query)
            logger.info(f"Finished processing query: '{query}'. {len(stored_results)} results available.")
            return stored_results

        except Exception as e:
            logger.error(f"Error during search and processing: {e}", exc_info=True)
            raise RuntimeError(f"Failed to execute search and process results: {e}")
    
    async def search_rag(
        self, 
        query: str, 
        question: Optional[str] = None,
        n_results: int = 5,
        filter_by_question: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search the RAG database for relevant content.
        
        Args:
            query: The search query
            question: Optional question to filter results by (defaults to None)
            n_results: Number of results to return (default: 5)
            filter_by_question: Whether to filter results by the question (default: True)
            
        Returns:
            List of relevant documents with metadata
        """
        try:
            return self.rag_manager.search(
                query=query,
                question=question,
                n_results=n_results,
                filter_by_question=filter_by_question
            )
        except Exception as e:
            logger.error(f"Error searching RAG database: {e}")
            return []

    async def _perform_duckduckgo_search(self, query: str, num_results: int) -> List[Dict[str, Any]]:
        """Performs the actual search using the duckduckgo_search library.
        
        Args:
            query: The search query string
            num_results: Maximum number of results to return
            
        Returns:
            List of search result dictionaries
        """
        try:
            logger.info(f"Searching DuckDuckGo for: {query}")
            
            # Run the synchronous DDGS in a thread to avoid blocking
            def sync_search():
                with DDGS() as ddgs:
                    return [{
                        'link': r.get('href'),
                        'title': r.get('title'),
                        'snippet': r.get('body'),
                    } for r in ddgs.text(query, max_results=num_results)]
            
            # Run the synchronous function in a thread pool
            results = await asyncio.to_thread(sync_search)
            
            logger.info(f"DuckDuckGo search returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Error during DuckDuckGo search: {e}", exc_info=True)
            raise RuntimeError(f"Failed to execute search via DuckDuckGo: {e}")
    
    async def _perform_duckduckgo_search_with_retry(self, query: str, num_results: int, max_retries: int = 3, initial_delay: float = 2.0) -> List[Dict[str, Any]]:
        """Performs DDG search with exponential backoff on rate limit errors.
        
        Args:
            query: The search query string
            num_results: Maximum number of results to return
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay between retries in seconds
            
        Returns:
            List of search result dictionaries
        """
        import random
        retries = 0
        delay = initial_delay
        
        def sync_search(page: int):
            with DDGS() as ddgs:
                return [{
                    'link': r.get('href'),
                    'title': r.get('title'),
                    'snippet': r.get('body'),
                } for r in ddgs.text(query,region='us-en',  # US English 
                    safesearch='off',  # Allow all results
                    timelimit='y'#pull latest
                    ,max_results=num_results, backend='google',page=page)]
        
        while retries <= max_retries:
            try:
                logger.info(f"Attempting DuckDuckGo search (Attempt {retries + 1}/{max_retries + 1})...")
                # Run the synchronous function in a thread pool
                results = await asyncio.to_thread(sync_search, page=1)
                results.extend(await asyncio.to_thread(sync_search, page=2))
                #will check again if needed for page 3
                #results.extend(await asyncio.to_thread(sync_search, page=3))
                logger.info(f"Successfully retrieved {len(results)} results")
                logger.info(f"results are {results}")
                return results

            # Catch the specific RuntimeError potentially indicating rate limit, or broader exceptions
            except Exception as e:
                # Check if the error message likely indicates a rate limit (based on the observed error)
                is_rate_limit_error = "Ratelimit" in str(e) or "rate limit" in str(e).lower() or (isinstance(e, RuntimeError) and "DuckDuckGo" in str(e))

                if is_rate_limit_error and retries < max_retries:
                    retries += 1
                    # Add jitter: random small variation to the delay
                    jitter = delay * random.uniform(0.1, 0.5)
                    wait_time = delay + jitter
                    logger.warning(f"Rate limit detected (or suspected) on attempt {retries}. Retrying in {wait_time:.2f} seconds... Error: {e}")
                    await asyncio.sleep(wait_time)
                    delay *= 2  # Exponential backoff
                else:
                    # Max retries reached or it's a different kind of error
                    logger.error(f"Error during DuckDuckGo search call after {retries + 1} attempts: {e}", exc_info=True)
                    # Re-raise as a runtime error for the orchestrator to catch
                    raise RuntimeError(f"Failed to execute search via DuckDuckGo after {retries + 1} attempts: {e}")

        # Should not be reached if max_retries > 0, but as a fallback
        logger.error("Exhausted all retries for DuckDuckGo search.")
        raise RuntimeError("Exhausted all retries for DuckDuckGo search.")

    def _is_pdf_url(self, url: str) -> bool:
        """Determine if URL points to a PDF file.
        
        Args:
            url: URL to check
            
        Returns:
            True if URL appears to be a PDF, False otherwise
        """
        url = url.lower()
        # Check file extension
        if url.endswith('.pdf'):
            return True
            
        # Check for common PDF URL patterns
        pdf_patterns = [
            '/pdf/',
            'filetype=pdf',
            'format=pdf',
            '.pdf?',
            '.pdf#'
        ]
        
        return any(pattern in url for pattern in pdf_patterns)

    async def _extract_with_crawl4ai(self, search_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract content from URLs using crawl4AI with appropriate strategy based on URL type.
        
        Args:
            search_results: List of search result dictionaries containing URLs
            
        Returns:
            List of dictionaries with extracted content
        """
        logger.info(f"Extracting content from {len(search_results)} URLs using crawl4AI")
        
        # Configure browser for crawling
        browser_config = BrowserConfig(
            headless=True
           # browser=["edge"],
            #browser_args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        
        # Create LLM configuration for GROQ with Llama 8B
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            raise ValueError("GROQ_API_KEY environment variable is required for LLM extraction")
            
        llm_config = LLMConfig(
            provider="groq/llama-3.1-8b-instant",
            api_token=groq_api_key,
            temperature=0.3,
            max_tokens=12000
        )
        
        # Create LLM extraction strategy for regular HTML content
        extraction_strategy = LLMExtractionStrategy(
            llm_config=llm_config,
            instruction="""Extract the main content of the page with high precision. 
            Focus on the primary article, key information, and relevant data. 
            Exclude navigation menus, footers, advertisements, and other non-essential elements.
            Preserve important formatting, tables, and lists when present.
            For code snippets, ensure they are properly formatted and complete."""
        )
        
        # Create crawler configuration for regular HTML content
        html_crawl_config = CrawlerRunConfig(
            extraction_strategy=extraction_strategy,
            wait_until="domcontentloaded"
        )
        
        # Create PDF crawler strategy with default settings
        pdf_crawler_strategy = PDFCrawlerStrategy()
        pdf_scraping_strategy = PDFContentScrapingStrategy()
        
        # Create crawler configuration for PDFs
        pdf_crawl_config = CrawlerRunConfig(
            scraping_strategy=pdf_scraping_strategy
        )
        
        # Process URLs concurrently
        processed_results = []
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)
        
        # Separate PDF and HTML URLs
        pdf_results = []
        html_results = []
        
        for result in search_results:
            url = result.get('link')
            if not url:
                continue
                
            if self._is_pdf_url(url):
                pdf_results.append(result)
            else:
                html_results.append(result)
        
        # Process HTML URLs
        async with AsyncWebCrawler(config=browser_config) as crawler:
            tasks = []
            for result_item in html_results:
                url = result_item.get('link')
                if url:
                    task = self._process_url(crawler, html_crawl_config, semaphore, url, result_item, is_pdf=False)
                    tasks.append(task)
            
            # Process PDF URLs with PDF strategy
            async with AsyncWebCrawler(crawler_strategy=pdf_crawler_strategy) as pdf_crawler:
                for result_item in pdf_results:
                    url = result_item.get('link')
                    if url:
                        task = self._process_url(pdf_crawler, pdf_crawl_config, semaphore, url, result_item, is_pdf=True)
                        tasks.append(task)
                
                # Gather all results
                if tasks:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for result in results:
                        if isinstance(result, Exception):
                            logger.warning(f"Error processing URL: {result}")
                        elif result:
                            # Store the raw content before any processing
                            result['raw_content'] = result.get('extracted_text', '')
                            processed_results.append(result)
        
        return processed_results

    async def _process_url(self, crawler: AsyncWebCrawler, crawl_config: CrawlerRunConfig, 
                         semaphore: asyncio.Semaphore, url: str, 
                         search_result_item: Dict[str, Any], is_pdf: bool = False) -> Optional[Dict[str, Any]]:
        """Process a single URL with crawl4AI.
        
        Args:
            crawler: The AsyncWebCrawler instance
            crawl_config: Crawler configuration with LLM extraction strategy
            semaphore: Semaphore for limiting concurrency
            url: URL to process
            search_result_item: Original search result data
            is_pdf: Whether the URL is a PDF (default: False)
            
        Returns:
            Dictionary with extracted content or None if processing failed
        """
        async with semaphore:
            try:
                logger.info(f"Processing URL: {url}")
                
                # Run the crawler
                result = await crawler.arun(url=url, config=crawl_config)
                
                if not result.success:
                    error_msg = getattr(result, 'error_message', 'Unknown error')
                    logger.warning(f"Failed to crawl {url}: {error_msg}")
                    return {
                        'url': url,
                        'title': search_result_item.get('title', ''),
                        'extracted_text': '',
                        'raw_snippet': search_result_item.get('snippet', ''),
                        'success': False,
                        'error': error_msg
                    }
                
                # Extract the content based on whether it's a PDF or HTML
                if is_pdf:
                    # For PDFs, we get the content directly from the result
                    extracted_content = result.extracted_content or ""
                    
                    # Try to extract markdown if available, otherwise use the content as is
                    if hasattr(result, 'markdown') and result.markdown:
                        if hasattr(result.markdown, 'raw_markdown'):
                            markdown_content = result.markdown.raw_markdown
                        else:
                            markdown_content = str(result.markdown)
                    else:
                        markdown_content = extracted_content
                        
                    # Clean up the extracted text
                    extracted_text = '\n'.join(line.strip() for line in extracted_content.split('\n') if line.strip())
                else:
                    # For HTML, process as before
                    extracted_content = result.extracted_content or ""
                    markdown_content = ""
                    
                    # Get markdown content for HTML
                    if hasattr(result, 'markdown') and result.markdown:
                        if hasattr(result.markdown, 'raw_markdown'):
                            markdown_content = result.markdown.raw_markdown
                        else:
                            markdown_content = str(result.markdown)
                    
                    # Process extracted content, handling both string and list content types
                    # If content is a string, try to parse as JSON
                    if isinstance(extracted_content, str):
                        try:
                            content_data = json.loads(extracted_content)
                            if isinstance(content_data, list):
                                # Handle list of content blocks
                                extracted_text = "\n\n".join(
                                    str(block.get("content", "")) 
                                    for block in content_data 
                                    if isinstance(block, dict) and "content" in block
                                )
                            else:
                                extracted_text = extracted_content
                        except json.JSONDecodeError:
                            extracted_text = extracted_content
                    # If content is already a list, process it directly
                    elif isinstance(extracted_content, list):
                        extracted_text = "\n\n".join(
                            str(block.get("content", "") if isinstance(block, dict) else block)
                            for block in extracted_content
                        )
                    else:
                        extracted_text = str(extracted_content)
                
                return {
                    'url': url,
                    'title': search_result_item.get('title', ''),
                    'extracted_text': extracted_text,
                    'raw_snippet': search_result_item.get('snippet', ''),
                    'success': True,
                    'markdown': markdown_content
                }
                
            except Exception as e:
                logger.error(f"Error processing URL {url}: {str(e)}", exc_info=True)
                return {
                    'url': url,
                    'title': search_result_item.get('title', ''),
                    'extracted_text': '',
                    'raw_snippet': search_result_item.get('snippet', ''),
                    'success': False,
                    'error': str(e)
                }

    async def _store_results_in_rag(self, results: List[Dict[str, Any]], question: str) -> List[Dict[str, Any]]:
        """Store search results in the RAG vector database with question-based indexing.
        
        Args:
            results: List of search result dictionaries to store
            question: The original search question/query
            
        Returns:
            The processed results list with storage status
        """
        if not results:
            return []
            
        processed_results = []
        
        for result in results:
            print(f"link is {result.get('link', '')} or url that is present is {result.get('url', '')}")
            try:
                url = result.get('url', '')
                title = result.get('title', 'Untitled')
                content = result.get('extracted_text', '')
                
                if not content: #few pdfs are stored as raw markdown as extracted_text is empty
                    print(f"extracting markdown since extracted_text is empty")
                    content=result.get('markdown', '')
                
                if not content:
                    result['storage_status'] = 'skipped_no_content'
                    processed_results.append(result)
                    logger.warning(f"Skipping storage for {url}: no content or URL")
                    continue
                    
                # Convert content to list if it's a string
                if isinstance(content, str):
                    # For strings, split into paragraphs for better chunking
                    content = [p.strip() for p in content.split('\n\n') if p.strip()]
                
                # Determine source type (PDF or web)
                is_pdf = self._is_pdf_url(url)
                source_type = 'pdf' if is_pdf else 'web'
                
                # Add question to result metadata
                result_metadata = {
                    'original_result': {k: v for k, v in result.items() 
                                     if k not in ['extracted_text', 'content','markdown']},
                    'search_question': question
                }
                
                # Store in RAG database with question context
                # Convert content to list if it's a single string
                if isinstance(content, str):
                    content = [content]
                elif not isinstance(content, list):
                    content = [str(content)]
                print("=="*50)
                #below has all extracted content
                #print(f"content is {content}")
                print("=="*50)
                chunk_count = self.rag_manager.store_document(
                    content=content,  # Pass as list to preserve chunking
                    url=url,
                    question=question,  # Pass the question for indexing
                    title=title,
                    source_type=source_type,
                    metadata=None
                )
                
                result['storage_status'] = 'success'
                result['chunks_stored'] = chunk_count
                result['question'] = question  # Store question in the result
                
            except Exception as e:
                logger.error(f"Error storing result in RAG database: {e}")
                result['storage_status'] = f'error: {str(e)}'
                
            processed_results.append(result)
            
        return processed_results
        
    async def _store_results(self, results: List[Dict[str, Any]], question: str) -> List[Dict[str, Any]]:
        """Process and return the search results with question-based indexing.
        
        Args:
            results: List of search result dictionaries to process
            question: The original search question/query
            
        Returns:
            The processed results list with question context
        """
        # First store in RAG with question context
        results = await self._store_results_in_rag(results, question)
        
        # Then store in the original format
        # (keeping this for backward compatibility)
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        
        for result in results:
            if not result.get('title') or not result.get('extracted_text'):
                continue
                
            # Create a filename from the title (sanitized)
            filename = "".join(c if c.isalnum() or c in ' _-.' else '_' 
                             for c in result['title']).strip()
            filename = f"{filename}.md" if not filename.endswith('.md') else filename
            filepath = os.path.join(output_dir, filename)
            
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(f"# {result['title']}\n\n")
                    f.write(f"**Source:** {result.get('link', 'N/A')}\n\n")
                    f.write("---\n\n")
                    f.write(result['extracted_text'])
                
                result['saved_to'] = filepath
                logger.info(f"Saved content to {filepath}")
                
            except Exception as e:
                logger.error(f"Error saving file {filepath}: {e}")
                result['save_error'] = str(e)
        
        return results
        if not results:
            logger.warning("No results to process")
            return []
            
        logger.info(f"Processed {len(results)} search results")
        return results


async def main():
    # Get search query from command line arguments
    import sys
    if len(sys.argv) < 2:
        print("Usage: python app.py <search_query>")
        return
    
    query = " ".join(sys.argv[1:])
    
    # Create search agent and run search
    agent = SearchAgent()
    results = await agent.run(query, num_results=5)  # Limit to 5 results for demo
    
    # Print summarized results
    print(f"\n\n===== SEARCH RESULTS FOR: '{query}' =====\n")
    for i, result in enumerate(results, 1):
        print(f"{i}. {result['title']}")
        print(f"   URL: {result['url']}")
        print(f"   Status: {'✓ Success' if result['success'] else '✗ Failed'}")
        if not result['success']:
            print(f"   Error: {result.get('error', 'Unknown error')}")
        else:
            # Show first 500 characters of extracted content as summary
            content_preview = result['extracted_text'][:500] + "..." if len(result['extracted_text']) > 500 else result['extracted_text']
            print(f"   Content Preview: {content_preview}")
        print()


if __name__ == "__main__":
    asyncio.run(main())