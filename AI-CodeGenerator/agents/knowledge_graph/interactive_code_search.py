import os
import subprocess
import uuid  # For unique session IDs
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))  # Adding project root to path
from agents.knowledge_graph.knowledge_graph_agent import KnowledgeGraphAgent
from agents.base.agent_interface import AgentInput, AgentOutput, AgentStatus
from datetime import datetime
import requests

def clone_github_repo(repo_name, access_token, local_path):
    """Reused from github_agent.py: Clone a GitHub repo using access token."""
    repo_url = f"https://{access_token}@github.com/{repo_name}.git"
    if os.path.exists(local_path):
        print(f"Local path {local_path} already exists. Pulling updates...")
        subprocess.run(["git", "-C", local_path, "pull"], check=True)
    else:
        print(f"Cloning {repo_name} to {local_path}...")
        subprocess.run(["git", "clone", repo_url, local_path], check=True)

def main():
    # Initialize the agent
    agent = KnowledgeGraphAgent()

    # Get GitHub access token
    access_token = input("Enter your GitHub access token: ").strip()
    repos = []
    try:
        response = requests.get("https://api.github.com/user/repos", headers={"Authorization": f"token {access_token}"}, params={"per_page": 100})
        if response.status_code == 200:
            repos = response.json()
            print("Fetched {} repositories.".format(len(repos)))
        else:
            print(f"Error fetching repositories: {response.status_code} - {response.json().get('message')}")
    except Exception as e:
        print(f"Error fetching repositories: {e}")

    while True:
        print("\nEnter repository number (1 to {}, 'list' to show repositories, or 'quit' to exit):".format(len(repos)))
        selection = input().strip().lower()
        if selection == 'quit':
            break
        elif selection == 'list':
            if not repos:
                print("No repositories available.")
            else:
                for i, repo in enumerate(repos, 1):
                    print(f"{i}. {repo['full_name']}")
            continue
        try:
            num = int(selection)
            if 1 <= num <= len(repos):
                repo_name = repos[num - 1]['full_name']
            else:
                print("Invalid number.")
                continue
        except ValueError:
            print("Invalid input.")
            continue

        # Generate unique session and local path
        session_id = str(uuid.uuid4())
        local_path = os.path.join("cloned_repos", repo_name.replace("/", "_"))

        # Clone repo
        try:
            clone_github_repo(repo_name, access_token, local_path)
        except subprocess.CalledProcessError as e:
            print(f"Error cloning repo: {e}")
            continue

        # Analyze repo (create embeddings)
        print(f"Analyzing repository: {repo_name}...")
        analyze_input = {"operation": "analyze_repository", "repository_path": local_path}
        analyze_output = agent.process(AgentInput(agent_id="knowledge_graph_agent", session_id=session_id, data=analyze_input,timestamp=datetime.now()))
        
        if analyze_output.status.value != "success":
            error_msg = analyze_output.data.get('error', 'Unknown error occurred')
            print(f"Error analyzing repo: {error_msg}")
            if 'Failed to initialize embedding model' in error_msg:
                print("Suggestion: Make sure transformers and torch are properly installed")
            continue
            
        total_chunks = analyze_output.data.get('total_chunks', 0)
        files_processed = analyze_output.data.get('files_processed', 0)
        total_files_found = analyze_output.data.get('total_files_found', 0)
        chunk_distribution = analyze_output.data.get('chunk_distribution', {})
        warnings = analyze_output.data.get('warnings')
        failed_files = analyze_output.data.get('failed_files', [])
        
        print(f"\\n🎉 Repository analyzed successfully!")
        print(f"📊 Analysis Summary:")
        print(f"   • Total chunks created: {total_chunks}")
        print(f"   • Files processed: {files_processed}/{total_files_found}")
        
        if chunk_distribution:
            print(f"   • Chunk distribution by file:")
            for file, chunk_count in chunk_distribution.items():
                print(f"     - {file}: {chunk_count} chunks")
        
        if warnings:
            print(f"\\n⚠️  Warning: {warnings}")
            if failed_files:
                print(f"   Failed files: {failed_files[:5]}{'...' if len(failed_files) > 5 else ''}")
                
        print(f"\\n💡 You can now ask questions about the repository!")

        # Interactive questioning loop
        while True:
            query = input("\nAsk a question about the repo (or 'next' for new repo, 'quit' to exit): ").strip()
            if query.lower() == 'quit':
                agent.process(AgentInput(agent_id="knowledge_graph_agent", session_id=session_id, data={"operation": "cleanup_session"}, timestamp=datetime.now()))
                return  # Exit entirely
            elif query.lower() == 'next':
                agent.process(AgentInput(agent_id="knowledge_graph_agent", session_id=session_id, data={"operation": "cleanup_session"}, timestamp=datetime.now()))
                break  # Move to next repo

            # Search
            search_input = {"operation": "search_code", "query": query, "max_results": 5}
            search_output = agent.process(AgentInput(agent_id="knowledge_graph_agent", session_id=session_id, data=search_input, timestamp=datetime.now()))
            
            if search_output.status.value != "success":
                error_msg = search_output.data.get('error', 'Unknown search error')
                print(f"Error searching: {error_msg}")
                continue

            results = search_output.data.get("results", [])
            if not results:
                print("No results found.")
            else:
                print(f"\nTop {len(results)} results:")
                for idx, res in enumerate(results, 1):
                    chunk = res["chunk"]
                    file_path = chunk.get('file_path', 'Unknown file')
                    start_line = chunk.get('start_line', '?')
                    end_line = chunk.get('end_line', '?')
                    similarity = res.get('similarity', 0)
                    text = chunk.get('text', 'No text available')
                    
                    print(f"\n{idx}. File: {file_path} (Lines {start_line}-{end_line})")
                    print(f"   Similarity: {similarity:.3f}")
                    print(f"   Snippet: {text[:200]}{'...' if len(text) > 200 else ''}")
                    print("-" * 60)

if __name__ == "__main__":
    main()