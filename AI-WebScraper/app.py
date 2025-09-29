import asyncio
import os
import logging
from typing import List, Dict, Any, Optional
import json
from ddgs import DDGS
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, LLMConfig, LLMExtractionStrategy
from crawl4ai.processors.pdf import PDFCrawlerStrategy, PDFContentScrapingStrategy
from rag_manager import RAGManager
from groq import Groq
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Constants ---
DEFAULT_NUM_RESULTS = 1
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

    async def get_llm_response(self, question: str, context: str, model: str = "llama-3.1-8b-instant") -> Optional[str]:
        """Get a response from the LLM based on the provided context and question.
        
        Args:
            question: The question to answer
            context: The context to use for generating the response
            model: The LLM model to use (default: "llama-3.1-8b-instant")
            
        Returns:
            The generated response or None if an error occurs
        """
        try:
            if "GROQ_API_KEY" not in os.environ:
                logger.error("GROQ_API_KEY environment variable is not set")
                return None
                
            client = Groq(api_key=os.environ["GROQ_API_KEY"])
            
            # Prepare a general-purpose system prompt
            system_prompt = """You are a helpful AI assistant that delivers clear, direct answers from real-time web sources. Your responses should be:
1. Concise and to the point
2. Written in a natural, conversational tone
3. Include specific quotes or numbers when they add value
4. Optimistic and solution-focused
5. Free of disclaimers or discussions about missing information, don't mention abuot Parts of the question that can't be answered with the available information

Remember: Give direct answers using the information you have. Skip any meta-commentary about sources or limitations."""

            # User prompt combines context and question
            user_prompt = context if "I found several relevant articles" in context else f"""
            Question: {question}
            
            I've searched the web and found this relevant information:
            
            {context}
            
            Please provide a clear answer that:
            1. Directly addresses the question using this information
            2. Includes relevant details that help explain the answer
            3. Notes any parts of the question that can't be answered with the available information
            if the context is not sufficient say "0"
            """
            
            # Make the API call
            completion = client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that provides accurate and concise answers based on the given context."
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                model=model,
                temperature=0.3,
                max_tokens=2048,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0
            )
            
            return completion.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error getting LLM response: {e}", exc_info=True)
            return None

    async def run_async_upsert(self, query: str, num_results: int = DEFAULT_NUM_RESULTS) -> str:
        """
        Optimized version of run() that returns results immediately and handles RAG storage asynchronously.
        Uses parallel processing for URL content extraction and separates DB operations.
        
        Args:
            query: The search query
            num_results: Maximum number of search results to process
            
        Returns:
            String containing search results processed through LLM, while handling storage asynchronously
        """
        logger.info(f"Starting optimized async search for query: {query}")
        try:
            # 1. Quick check in RAG DB first (with short timeout)
            try:
                async with asyncio.timeout(2.0):  # 2 second timeout for RAG search
                    rag_results = await self.search_rag(
                        query=query,
                        question=query,
                        n_results=num_results,
                        filter_by_question=True
                    )
                    if rag_results and len(rag_results) > 0:
                        results_context = "\n\n".join([str(result) for result in rag_results])
                        llm_response = await self.get_llm_response(query, results_context)
                        if llm_response != 0:
                            return llm_response
            except asyncio.TimeoutError:
                logger.info("RAG DB check timed out, proceeding with web search")
                pass
            
            # 2. Perform web search
            search_results_list = await self._perform_duckduckgo_search_with_retry(query, num_results)
            if not search_results_list:
                return "No results found."
                
            # 3. Process URLs in parallel with true concurrency
            async def process_url_optimized(crawler, config, url, result_item):
                try:
                    result = await crawler.arun(url=url, config=config)
                    if not result.success:
                        return None
                    
                    content = result.extracted_content or ""
                    if not content and hasattr(result, 'markdown'):
                        content = result.markdown.raw_markdown if hasattr(result.markdown, 'raw_markdown') else str(result.markdown)
                    
                    return {
                        'url': url,
                        'title': result_item.get('title', ''),
                        'extracted_text': content,
                        'success': True
                    }
                except Exception as e:
                    logger.error(f"Error processing {url}: {e}")
                    return None
                    
            # Setup crawlers and process URLs
            browser_config = BrowserConfig(headless=True)
            llm_config = LLMConfig(
                provider="groq/llama-3.1-8b-instant",
                api_token=os.getenv("GROQ_API_KEY"),
                temperature=0.3,
                max_tokens=12000
            )
            
            extraction_strategy = LLMExtractionStrategy(llm_config=llm_config)
            html_crawl_config = CrawlerRunConfig(extraction_strategy=extraction_strategy)
            
            # Process all URLs concurrently
            async with AsyncWebCrawler(config=browser_config) as crawler:
                tasks = []
                processed_urls = set()
                
                for result in search_results_list:
                    url = result.get('link')
                    if not url:
                        continue
                        
                    # Skip already processed URLs
                    if self.rag_manager.is_url_processed(url):
                        logger.info(f"Skipping already processed URL: {url}")
                        continue
                        
                    task = process_url_optimized(crawler, html_crawl_config, url, result)
                    tasks.append(task)
                    processed_urls.add(url)
                
                if not tasks:
                    logger.info("No new URLs to process after filtering")
                    return "No new content to process. All URLs have already been processed."
                
                results = await asyncio.gather(*tasks)
                results = [r for r in results if r]  # Filter out None results
                
            if not results:
                return "Could not extract content from any URLs."
                
            # 4. Process results with LLM immediately
            # Format content more effectively for LLM understanding
            formatted_content = []
            for r in results:
                if r.get('extracted_text'):
                    article_content = (
                        f"\n=== Article from {r['url']} ===\n"
                        f"Title: {r['title']}\n"
                        f"Content:\n{r['extracted_text']}\n"
                        f"=== End Article ===\n"
                    )
                    formatted_content.append(article_content)
            
            if not formatted_content:
                return "No content could be extracted from the search results."
            
            combined_content = "\n".join(formatted_content)
            
            # Create a more focused prompt for the LLM
            focused_prompt = f"""You are a helpful assistant analyzing recent news articles. Please provide a detailed summary addressing this specific query: "{query}"

Based on the following Web pages:

{combined_content}

Please provide a comprehensive answer that:
1. Summarizes the key points about the rate cut
2. Highlights specific quotes or statements from Powell
3. Mentions any important economic implications
4. Includes relevant dates and numbers

If the information isn't in the articles, only mention what is supported by the sources."""
            
            llm_response = await self.get_llm_response(query, focused_prompt)
            
            # 5. Start async RAG storage without waiting
            asyncio.create_task(self._async_store_in_rag(results, query))
            
            if llm_response == "0" or not llm_response:
                return "Could not extract a clear answer from the content. Please try rephrasing your question."
                
            return llm_response
            
        except Exception as e:
            logger.error(f"Error in async search: {e}", exc_info=True)
            raise RuntimeError(f"Failed to execute async search: {e}")

    async def _async_store_in_rag(self, results: List[Dict[str, Any]], question: str):
        """Asynchronously store results in RAG database without blocking the main flow."""
        storage_status = {
            'total': len(results),
            'successful': 0,
            'failed': 0,
            'stored_urls': [],
            'failed_urls': [],
            'completion_time': None,
            'start_time': None
        }
        
        try:
            storage_status['start_time'] = datetime.datetime.now().isoformat()
            logger.info(f"Starting async RAG storage for {len(results)} results at {storage_status['start_time']}")
            
            for result in results:
                try:
                    if result.get('extracted_text'):
                        content = [result['extracted_text']]
                        url = result['url']
                        title = result['title']
                        
                        # Store document and get chunk count
                        chunk_count = await self.rag_manager.store_document(
                            content=content,
                            url=url,
                            question=question,
                            title=title,
                            source_type='web',
                            metadata={'storage_time': storage_status['start_time']}
                        )
                        
                        storage_status['successful'] += 1
                        storage_status['stored_urls'].append({
                            'url': url,
                            'chunks': chunk_count,
                            'timestamp': datetime.datetime.now().isoformat()
                        })
                        logger.info(f"Successfully stored {chunk_count} chunks for URL: {url}")
                        
                except Exception as e:
                    storage_status['failed'] += 1
                    storage_status['failed_urls'].append({
                        'url': result.get('url'),
                        'error': str(e),
                        'timestamp': datetime.datetime.now().isoformat()
                    })
                    logger.error(f"Error storing result for {result.get('url')}: {e}")
                    continue
            
            storage_status['completion_time'] = datetime.datetime.now().isoformat()
            await self._save_storage_status(storage_status, question)
            
            logger.info(
                f"Completed async RAG storage: {storage_status['successful']}/{storage_status['total']} "
                f"successful, {storage_status['failed']} failed. "
                f"Total time: {self._get_time_diff(storage_status['start_time'], storage_status['completion_time'])}"
            )
            
        except Exception as e:
            logger.error(f"Error in async RAG storage: {e}")
            storage_status['completion_time'] = datetime.datetime.now().isoformat()
            await self._save_storage_status(storage_status, question)

    def _get_time_diff(self, start_time: str, end_time: str) -> str:
        """Calculate time difference between two ISO format timestamps."""
        start = datetime.datetime.fromisoformat(start_time)
        end = datetime.datetime.fromisoformat(end_time)
        diff = end - start
        return f"{diff.total_seconds():.2f}s"

    async def _save_storage_status(self, status: Dict, question: str):
        """Save storage status to a file for later verification."""
        try:
            status_dir = "storage_status"
            os.makedirs(status_dir, exist_ok=True)
            
            filename = f"storage_status_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = os.path.join(status_dir, filename)
            
            with open(filepath, 'w') as f:
                json.dump({
                    'question': question,
                    'status': status,
                    'summary': {
                        'total_urls': status['total'],
                        'successful_urls': status['successful'],
                        'failed_urls': status['failed'],
                        'total_time': self._get_time_diff(status['start_time'], status['completion_time'])
                    }
                }, f, indent=2)
                
            logger.info(f"Storage status saved to {filepath}")
        except Exception as e:
            logger.error(f"Error saving storage status: {e}")

    async def verify_storage(self, question: str) -> Dict:
        """
        Verify the storage status for a specific question.
        Returns details about stored documents and their chunks.
        """
        try:
            # Search for documents related to the question
            results = await self.search_rag(
                query=question,
                question=question,
                n_results=100,  # Increase to get all related documents
                filter_by_question=True
            )
            
            verification = {
                'question': question,
                'total_documents': len(results),
                'documents': []
            }
            
            for result in results:
                doc_info = {
                    'url': result.get('metadata', {}).get('url', 'N/A'),
                    'title': result.get('metadata', {}).get('title', 'N/A'),
                    'storage_time': result.get('metadata', {}).get('storage_time', 'N/A'),
                    'chunk_size': len(result.get('text', '')),
                }
                verification['documents'].append(doc_info)
            
            return verification
            
        except Exception as e:
            logger.error(f"Error verifying storage: {e}")
            return {'error': str(e)}

    async def run(self, query: str, num_results: int = DEFAULT_NUM_RESULTS) -> str:
        """
        Performs a search by first checking the vector database for relevant results.
        If no relevant results are found, falls back to DuckDuckGo search.
        
        Args:
            query: The search query.
            num_results: Maximum number of search results to process.
            
        Returns:
            String containing search results, either from vector DB or web search,
            processed through an LLM for better clarity.
        """
        logger.info(f"Starting search for query: {query}")

        try:
            # 1. First try to get results from the vector database
            logger.info("Searching vector database...")
            rag_results = await self.search_rag(
                query=query,
                question=query,  # Use the query as the question for filtering
                n_results=num_results,
                filter_by_question=True
            )

            # If we have relevant results from the vector database, process them with LLM
            if rag_results and len(rag_results) > 0:
                logger.info(f"Found {len(rag_results)} relevant results in vector database")
                # Convert results to string and process with LLM
                results_context = "\n\n".join([str(result) for result in rag_results])
                llm_response = await self.get_llm_response(query, results_context)
                if llm_response!=0 : return llm_response or f"Here's what I found:\n\n{results_context}"

            # 2. If no results from vector DB, perform web search
            logger.info("No relevant results in vector database, performing web search...")
            search_results_list = await self._perform_duckduckgo_search_with_retry(query, num_results)
            if not search_results_list:
                logger.warning(f"No search results found for query: {query}")
                return "No results found in vector database or web search."

            # 3. Extract content using crawl4AI with LLM strategy
            processed_results = await self._extract_with_crawl4ai(search_results_list)
            
            if not processed_results:
                logger.warning("No content could be extracted from search results")
                return "No content could be extracted from search results."
                
            logger.info(f"Successfully processed {len(processed_results)} out of {len(search_results_list)} search results.")
            
            # 4. Store the new results in the vector database
            stored_results = await self._store_results(processed_results, query)
            logger.info(f"Stored {len(stored_results)} new results in vector database.")
            
            # 5. Format the results using LLM for better clarity
            results_context = "\n\n".join([str(result) for result in stored_results])
            llm_response = await self.get_llm_response(query, results_context)
            return llm_response or f"Here's what I found:\n\n{results_context}"

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
                #results.extend(await asyncio.to_thread(sync_search, page=2))
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
        
    async def run_batch_urls(self, urls: List[str], context: str) -> str:
        """Process a list of URLs directly, extracting their content and storing in the vector database.
        
        Args:
            urls: List of URLs to process
            context: Context description for storing the documents (should be passed since it is added as metadata field)
            
        Returns:
            Summary of the processing results
        """
        if not urls:
            return "No URLs provided for processing."
            
        try:
            # Filter out already processed URLs
            unprocessed_urls = []
            processed_urls = []
            
            for url in urls:
                if self.rag_manager.is_url_processed(url):
                    logger.info(f"Skipping already processed URL: {url}")
                    processed_urls.append(url)
                else:
                    unprocessed_urls.append(url)
            
            if not unprocessed_urls:
                return "All provided URLs have already been processed."
            
            # Convert unprocessed URLs to search result format
            search_results = [{'link': url, 'title': url} for url in unprocessed_urls]
            
            # Add info about skipped URLs to the context
            if processed_urls:
                context = f"{context}\n\nNote: {len(processed_urls)} URLs were skipped as they were already processed."
            
            # Extract content using existing crawler
            processed_results = await self._extract_with_crawl4ai(search_results)
            
            if not processed_results:
                return "No content could be extracted from the provided URLs."
                
            # Store results in vector database
            stored_results = await self._store_results_in_rag(processed_results, context)
            
            # Return summary
            success_count = sum(1 for r in processed_results if r.get('success', False))
            return f"Successfully processed {success_count} out of {len(urls)} URLs. Content stored in vector database."
            
        except Exception as e:
            logger.error(f"Error processing URLs: {e}", exc_info=True)
            raise RuntimeError(f"Failed to process URLs: {e}")

    async def _store_results(self, results: List[Dict[str, Any]], question: str) -> str:
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
        search_results = await self.search_rag(
                            query=question,
                            question=question,
                            n_results=3, #setting this since chunks might me small & not have enough context
                            filter_by_question=True)
        
        if search_results:
            # Combine all search results into a single context
            combined_context = "\n\n---\n\n".join(
                f"Source: {result.get('metadata', {}).get('source', 'N/A')}\n"
                f"Relevance Score: {1 - result.get('distance', 0):.2f}\n\n"
                f"{result.get('text', 'No content')}"
                for result in search_results
            )
            print(f"combined context is {combined_context}")

            # Get LLM response
            llm_response = await self.get_llm_response(question, combined_context)
            if llm_response:
                result['llm_response'] = llm_response
            else:
                result['llm_response'] = combined_context   
        if not results:
            logger.warning("No results to process")
            return 'None'
            
        logger.info(f"Processed {len(results)} search results")
        # Return the first result's llm_response if available, otherwise return the first result
        if results and 'llm_response' in results[0]:
            return results[0]['llm_response']
        return results[0] if results else 'No results found'


async def main():
    # Get URLs from command line arguments
    import sys
    if len(sys.argv) < 2:
        print("Usage: python app.py <url1> [url2 ...]")
        print("Example: python app.py https://example.com https://example.org")
        return 1
    
    urls = sys.argv[1:]
    context = "User provided URLs for analysis"
    
    print(f"Processing {len(urls)} URLs...")
    
    # Create search agent and process URLs
    agent = SearchAgent()
    
    try:
        # Process the provided URLs
        result = await agent.run_batch_urls(urls, context)
        print(f"\n{result}")
        
        # Start interactive chat session
        print("\n" + "="*50)
        print("Interactive Chat Session")
        print("Type 'exit' to end the session")
        print("="*50 + "\n")
        
        while True:
            try:
                # Get user question
                question = input("\nAsk a question about the content (or 'exit' to quit): ").strip()
                
                if question.lower() in ['exit', 'quit', 'q']:
                    print("Ending session. Goodbye!")
                    break
                    
                if not question:
                    continue
                
                print("\nSearching for relevant information...")
                
                # Search RAG for relevant content
                search_results = await agent.search_rag(
                    query=question,
                    question=context,
                    n_results=3,
                    filter_by_question=True
                )
                
                if not search_results:
                    print("No relevant information found in the provided URLs.")
                    continue
                
                # Combine search results into context
                combined_context = "\n\n---\n\n".join(
                    f"Source: {result.get('metadata', {}).get('source', 'N/A')}\n"
                    f"Relevance Score: {1 - result.get('distance', 0):.2f}\n\n"
                    f"{result.get('text', 'No content')}"
                    for result in search_results
                )
                
                # Get LLM response
                print("\nGenerating response...")
                llm_response = await agent.get_llm_response(question, combined_context)
                
                if llm_response:
                    print("\n" + "-"*50)
                    print(llm_response)
                    print("-"*50)
                else:
                    print("Sorry, I couldn't generate a response. Here's the relevant content I found:")
                    print(combined_context)
                
            except KeyboardInterrupt:
                print("\nEnding session. Goodbye!")
                break
            except Exception as e:
                print(f"An error occurred: {e}")
                continue
                
    except Exception as e:
        print(f"Error processing URLs: {e}")
        return 1
        
    return 0


if __name__ == "__main__":
    asyncio.run(main())