import asyncio
import os
import json
from typing import List, Dict, Any
from app import SearchAgent
import re
from datetime import datetime
from pathlib import Path

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

async def test_extraction():
    # Initialize the search agent
    agent = SearchAgent()
    
    # Define test URLs with their titles
    test_urls = [
        {
            'title': 'Columbia University',
            'link': 'https://opir.columbia.edu/sites/opir.columbia.edu/files/content/Common%20Data%20Set/2023-24_Columbia_College_and_Columbia_Engineering_CDS.pdf',
            #'link': 'https://www.commondatasets.fyi/columbia',
            'snippet': 'common data set for 2023 2024'
        }]
    
    
    # Call the extraction method
    print("Starting extraction...")
    try:
        results = await agent._extract_with_crawl4ai(test_urls)
        
        # Print results
        print("\n" + "="*50)
        print("EXTRACTION RESULTS")
        print("="*50)
        
        for i, result in enumerate(results, 1):
            print(f"\nResult {i}:")
            print(f"Title: {result.get('title', 'N/A')}")
            print(f"URL: {result.get('url', 'N/A')}")
            print(f"Success: {result.get('success', False)}")
            
            if result.get('success'):
                # Print first 200 chars of extracted text
                text = result.get('extracted_text', '')
                print("\nExtracted Text (first 200 chars):")
                #below has actuall dervied data from llm strategy
                print(text[:8000] + ("..." if len(text) > 200 else ""))
                
                # Save and print markdown content if available
                #this is whole dump of file data
                if 'markdown' in result and result['markdown']:
                    md = result['markdown']
                    print("\nMarkdown Content (first 200 chars):")
                    print(md[:200] + ("..." if len(md) > 200 else ""))
                    
                    # Save the full markdown to a file
                    filename = f"{result.get('title', 'extracted')}.md"
                    save_markdown(md, filename=filename)
            else:
                print(f"Error: {result.get('error', 'Unknown error')}")
            
            print("\n" + "-"*50)
            
    except Exception as e:
        print(f"Error during extraction: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Make sure GROQ_API_KEY is set
    if not os.getenv("GROQ_API_KEY"):
        print("Error: GROQ_API_KEY environment variable is not set")
        print("Please set it before running the test:")
        print("export GROQ_API_KEY='your-api-key-here'")
    else:
        asyncio.run(test_extraction())
