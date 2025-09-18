import asyncio
import os
import json
from typing import List, Dict, Any, Optional
from app import SearchAgent
from rag_manager import RAGManager
import re
from datetime import datetime
from pathlib import Path
from groq import Groq

# Sample URL to crawl (same as in test.py)
SAMPLE_URL_1 = "https://opir.columbia.edu/sites/opir.columbia.edu/files/content/Common%20Data%20Set/2023-24_Columbia_College_and_Columbia_Engineering_CDS.pdf"
SAMPLE_URL_2 = "https://bpb-us-e1.wpmucdn.com/sites.harvard.edu/dist/6/210/files/2025/06/HarvardUniversity_CDS_2024-2025.pdf"
SAMPLE_QUESTION = "Can Columbia University allow students to postpone enrollment after admission? IF yes, what is the maximum period of Postponment?"

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
    Test the complete RAG workflow using RAGManager directly with URL-based filtering
    """
    print("Starting RAG workflow test...")
    
    # Initialize the RAG manager
    print("Initializing RAGManager...")
    try:
        rag_manager = RAGManager(persist_directory="./test_rag_db")
        print("RAGManager initialized successfully.")
    except Exception as e:
        print(f"Error initializing RAGManager: {str(e)}")
        return
    
    # Step 1: Process and store URLs
    print("1. Processing URLs and storing in vector database...")
    urls = [SAMPLE_URL_1, SAMPLE_URL_2]
    
    # First, use SearchAgent just for crawling and extraction
    agent = SearchAgent()
    search_results = [{'link': url, 'title': url} for url in urls]
    processed_results = await agent._extract_with_crawl4ai(search_results)
    
    # Store extracted content in RAG with URL metadata
    for result in processed_results:
        if result.get('success'):
            content = result.get('extracted_text', '')
            if not content:
                content = result.get('markdown', '')
            
            if content:
                # Store with URL in metadata for filtering
                url = result.get('url')
                chunks_stored = rag_manager.store_document(
                    content=[content],  # Pass as list for consistent handling
                    url=url,
                    question="dataset_context",
                    title=result.get('title', ''),
                    source_type='pdf' if agent._is_pdf_url(url) else 'web',
                    metadata={'source_url': url}  # Add URL to metadata for filtering
                )
                print(f"Stored {chunks_stored} chunks for {url}")

    # Step 2: Interactive Q&A loop
    print("\nEntering interactive Q&A mode. Type 'exit' to quit.")
    while True:
        # Get user question
        question = input("\nEnter your question (or 'exit' to quit): ")
        if question.lower() == 'exit':
            break

        print(f"\nSearching for: {question}")
        try:
            # Create where clause to filter by our specific URLs
            where = {
                "$or": [{"url": url} for url in urls]  # Search in any of our URLs
            }
            
            # Search with URL filtering
            search_results = rag_manager.search(
                query=question,
                question=None,  # Don't filter by question since we're using URL filtering
                n_results=5,
                where=where,  # Apply URL filter
                filter_by_question=False  # Disable question filtering since we're using URLs
            )

            if not search_results:
                print("No relevant information found.")
                continue

            # Combine search results into context
            combined_context = "\n\n---\n\n".join(
                f"Source: {result.get('metadata', {}).get('url', 'N/A')}\n"
                f"Relevance Score: {1 - result.get('distance', 0):.2f}\n\n"
                f"{result.get('text', 'No content')}"
                for result in search_results
            )

            # Get LLM response
            llm_response = await get_llm_response(question, combined_context)
            
            # Print the response
            print("\nAnswer:")
            print("-" * 80)
            print(llm_response if llm_response else "Could not generate a response.")
            print("-" * 80)

            # Save the interaction to a markdown file
            output_content = f"# Q&A Interaction\n\n"
            output_content += f"**Question:** {question}\n\n"
            output_content += f"**Answer:**\n{llm_response}\n\n"
            output_content += f"**Sources:**\n"
            for result in search_results:
                output_content += f"- {result.get('metadata', {}).get('url', 'N/A')} (Score: {1 - result.get('distance', 0):.2f})\n"

            filename = f"rag_search_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            save_markdown(output_content, filename=filename)

        except Exception as e:
            print(f"Error during search: {str(e)}")
    
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
