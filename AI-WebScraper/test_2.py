import asyncio
import os
import json
from typing import List, Dict, Any
from app import SearchAgent
import re
from datetime import datetime
from pathlib import Path

# Sample URL to crawl (same as in test.py)
SAMPLE_URL = "https://undergrad.admissions.columbia.edu/classprofile/2027"
SAMPLE_QUESTION = "what are the Number of applicants admitted under early decision plan?"

def save_markdown(content: str, filename: str = None, output_dir: str = 'output'):
    """
    Save markdown content to a file.
    
    Args:
        content: The markdown content to save
        filename: The name of the output file (without extension). 
                If None, a timestamp will be used.
        output_dir: Directory to save the markdown files. Will be created if it doesn't exist.
    
    Returns:
        Path to the saved file
    """
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Generate filename if not provided
    if not filename:
        # Create a safe filename from the first few words of the content
        safe_name = re.sub(r'[^\w\s-]', '', content[:50].strip())
        safe_name = re.sub(r'[-\s]+', '_', safe_name)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{safe_name}.md"
    elif not filename.endswith('.md'):
        filename += '.md'
    
    # Ensure filename is safe
    filename = re.sub(r'[^\w\-_. ]', '_', filename)
    
    # Write content to file
    filepath = Path(output_dir) / filename
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Saved markdown to: {filepath.absolute()}")
    return str(filepath.absolute())

async def test_rag_workflow():
    """
    Test the complete RAG workflow:
    1. Crawl a sample URL
    2. Store the content in RAG
    3. Search the RAG database with a question
    """
    print("Starting RAG workflow test...")
    
    # Initialize the search agent with a custom RAG database path
    print("Initializing SearchAgent...")
    try:
        agent = SearchAgent(rag_db_path="./test_rag_db")
        print("SearchAgent initialized successfully.")
    except Exception as e:
        print(f"Error initializing SearchAgent: {str(e)}")
        return
    
    # Step 1: Create a mock search result for our URL
    print(f"\n1. Preparing to crawl URL: {SAMPLE_URL}")
    search_result = [{
        'link': SAMPLE_URL,
        'title': 'Columbia University Class Profile',
        'snippet': 'Admissions statistics and class profile for Columbia University'
    }]
    print("Search result prepared.")
    
    print(f"\n1. Crawling URL: {SAMPLE_URL}")
    
    # Step 2: Extract content using crawl4ai
    print("\n2. Extracting content using crawl4ai...")
    try:
        processed_results = await agent._extract_with_crawl4ai(search_result)
        #print(f"Processed results: {processed_results}")
        if not processed_results:
            print("Error: No results returned from content extraction")
            return
          
            
        if not processed_results[0].get('extracted_text'):
            print("Warning: No extracted_text in results. Checking for markdown content...")
            if 'markdown' in processed_results[0]:
                print("Found markdown content, using that instead.")
                processed_results[0]['extracted_text'] = processed_results[0]['markdown']
            else:
                print("No markdown content found either. Available keys:", processed_results[0].keys())
                return
    except Exception as e:
        print(f"Error during content extraction: {str(e)}")
        return
    
    # Step 3: Store in RAG with our sample question
    print(f"\n3. Storing content in RAG with question: {SAMPLE_QUESTION}")
    try:
        stored_results = await agent._store_results(processed_results, SAMPLE_QUESTION)
    except Exception as e:
        print(f"Error during RAG storage: {str(e)}")
        return
    
    # Print storage status
    for result in stored_results:
        status = result.get('storage_status', 'unknown')
        chunks = result.get('chunks_stored', 0)
        print(f"- URL: {result.get('link')}")
        print(f"  Status: {status}")
        print(f"  Chunks stored: {chunks}")
    
    # Step 4: Search the RAG database
    print(f"\n4. Searching RAG with query: '{SAMPLE_QUESTION}'")
    search_results = await agent.search_rag(
        query=SAMPLE_QUESTION,
        question=SAMPLE_QUESTION,
        n_results=3,
        filter_by_question=True
    )
    
    # Print search results
    print(f"\nSearch Results ({len(search_results)}):")
    print("-" * 80)
    
    for i, result in enumerate(search_results, 1):
        print(f"Result {i}:")
        print(f"Source: {result.get('metadata', {}).get('source', 'N/A')}")
        print(f"Relevance Score: {1 - result.get('distance', 0):.2f}")
        print("-" * 40)
        print(result.get('text', 'No content'))
        print("\n" + "=" * 80 + "\n")
    
    # Save the search results to a markdown file
    if search_results:
        output_content = f"# RAG Search Results\n\n"
        output_content += f"**Question:** {SAMPLE_QUESTION}\n\n"
        output_content += f"**Search Results:**\n\n"
        
        for i, result in enumerate(search_results, 1):
            output_content += f"## Result {i}\n"
            output_content += f"**Source:** {result.get('metadata', {}).get('source', 'N/A')}\n"
            output_content += f"**Relevance Score:** {1 - result.get('distance', 0):.2f}\n\n"
            output_content += result.get('text', 'No content')
            output_content += "\n\n---\n\n"
        
        filename = f"rag_search_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        save_markdown(output_content, filename=filename)
        print(f"\nSearch results saved to: {filename}.md")

if __name__ == "__main__":
    # Make sure GROQ_API_KEY is set
    if not os.getenv("GROQ_API_KEY"):
        print("Error: GROQ_API_KEY environment variable is not set")
        print("Please set it before running this script.")
        print("Example: export GROQ_API_KEY='your-api-key'")
        exit(1)
    
    try:
        # Run the test
        asyncio.run(test_rag_workflow())
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
