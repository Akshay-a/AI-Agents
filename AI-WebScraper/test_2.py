import asyncio
import os
import json
from typing import List, Dict, Any, Optional
from app import SearchAgent
import re
from datetime import datetime
from pathlib import Path
from groq import Groq

# Sample URL to crawl (same as in test.py)
SAMPLE_URL = "https://opir.columbia.edu/sites/opir.columbia.edu/files/content/Common%20Data%20Set/2023-24_Columbia_College_and_Columbia_Engineering_CDS.pdf"
SAMPLE_QUESTION = "Can allow students to postpone enrollment after admission? IF yes, what is the maximum period of Postponment?"

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
        'title': 'Columbia college General Info',
        'snippet': 'FAQ on columbia university'
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
    #Intermittent Step:
    print("\n2. Running Intermittent step to test context...")
    #llm_response = await get_llm_response(SAMPLE_QUESTION, processed_results[0]['extracted_text'])
    #if llm_response:
    #    print("\nLLM Response for extracted text to test normal llm response without embeddings:")
    #    print(llm_response)
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
        n_results=20, #setting this since chunks might me small & not have enough context
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
        
        # Combine all search results into a single context
        combined_context = "\n\n---\n\n".join(
            f"Source: {result.get('metadata', {}).get('source', 'N/A')}\n"
            f"Relevance Score: {1 - result.get('distance', 0):.2f}\n\n"
            f"{result.get('text', 'No content')}"
            for result in search_results
        )
        
        for i, result in enumerate(search_results, 1):
            output_content += f"## Result {i}\n"
            output_content += f"**Source:** {result.get('metadata', {}).get('source', 'N/A')}\n"
            output_content += f"**Relevance Score:** {1 - result.get('distance', 0):.2f}\n\n"
            output_content += result.get('text', 'No content')
            output_content += "\n\n---\n\n"
        
        # Step 5: Get LLM response
        print("\n5. Getting LLM response...")
        llm_response = await get_llm_response(SAMPLE_QUESTION, combined_context)
        
        if llm_response:
            print("\nLLM Response:")
            print("-" * 80)
            print(llm_response)
            print("-" * 80)
            
            # Add LLM response to the markdown output
            output_content += "# LLM Response\n\n"
            output_content += llm_response
        else:
            output_content += "\n# Error: Could not get LLM response\n"
        
        filename = f"rag_search_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        save_markdown(output_content, filename=filename)
        print(f"\nSearch results and LLM response saved to: {filename}.md")

async def get_llm_response(question: str, context: str, model: str = "llama-3.1-8b-instant") -> Optional[str]:
    try:
        client = Groq(api_key=os.environ["GROQ_API_KEY"])
        
        # Prepare the prompt with context and question
        prompt = f"""You are a helpful assistant that answers questions based on the provided context.
        
        Context:
        {context}
        
        Question: {question}
        
        Answer the question based on the context above. If the context doesn't contain the answer, say "No,Do Web Search" """
        
        # Make the API call
        completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that provides accurate and concise answers based on the given context."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model=model,
            temperature=0.3,
            max_tokens=1024,
            top_p=1,
            stream=False,
            stop=None,
        )
        
        return completion.choices[0].message.content
        
    except Exception as e:
        print(f"Error in LLM inference: {str(e)}")
        return None

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
