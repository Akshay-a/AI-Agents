"""
GitHub Agent Test Script
Test script to demonstrate GitHub agent functionality.
"""

import os
import sys
import json
from typing import Optional

# Add project root to Python path for imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)
#added above change to fix the import error, instead of passing PYTHONPATH=. PYTHON3 TEST_AGENT.py -> setting the path to project root to make this program work 
from agents.github.github_agent import GitHubAgent
from agents.base.agent_interface import agent_registry

def main():
    """Main test function for GitHub Agent"""
    print("=== GitHub Agent Test ===\n")
    
    # Initialize GitHub agent
    config = {
        'workspace_base': '/tmp/github_agent_test'
    }
    
    github_agent = GitHubAgent(config=config)
    
    # Register agent in the global registry
    agent_registry.register_agent(github_agent)
    
    print(f"✅ GitHub Agent initialized with ID: {github_agent.agent_id}")
    print(f"📁 Workspace: {config['workspace_base']}\n")
    
    # Get GitHub token from user
    github_token = get_github_token()
    if not github_token:
        print("❌ No GitHub token provided. Exiting.")
        return
    
    try:
        # Test 1: Authentication
        print("🔐 Testing GitHub Authentication...")
        auth_result = test_authentication(github_agent, github_token)
        if not auth_result:
            return
        
        # Test 2: List repositories
        print("\n📋 Testing Repository Listing...")
        repos = test_list_repositories(github_agent)
        if not repos:
            return
        
        # Test 3: Clone repository (optional)
        print("\n🔄 Testing Repository Cloning...")
        clone_test = input("Would you like to test repository cloning? (y/n): ").strip().lower()
        if clone_test == 'y':
            test_clone_repository(github_agent, repos)
        
        print("\n✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
    
    finally:
        # Cleanup
        print("\n🧹 Cleaning up...")
        #cleanup_test_data(github_agent)

def get_github_token() -> Optional[str]:
    """Get GitHub token from user input or environment variable"""
    
    # Try environment variable first
    token = os.getenv('GITHUB_TOKEN')
    if token:
        print("✅ Found GitHub token in environment variable")
        return token
    
    # Ask user for token
    print("Please provide your GitHub Personal Access Token:")
    print("(You can create one at: https://github.com/settings/tokens)")
    print("Required scopes: repo (for private repos) or public_repo (for public repos)")
    
    token = input("GitHub Token: ").strip()
    
    if not token:
        print("❌ No token provided")
        return None
    
    return token

def test_authentication(github_agent: GitHubAgent, token: str) -> bool:
    """Test GitHub authentication"""
    try:
        # Test authentication
        result = github_agent.execute({
            'operation': 'authenticate',
            'github_token': token
        })
        
        if result.status.value == 'success':
            user_data = result.data['user']
            print(f"✅ Authentication successful!")
            print(f"   User: {user_data['name']} (@{user_data['login']})")
            print(f"   Email: {user_data.get('email', 'Not public')}")
            print(f"   Public repos: {user_data['public_repos']}")
            print(f"   Private repos: {user_data['private_repos']}")
            return True
        else:
            print(f"❌ Authentication failed: {result.error_message}")
            return False
            
    except Exception as e:
        print(f"❌ Authentication error: {str(e)}")
        return False

def test_list_repositories(github_agent: GitHubAgent) -> Optional[list]:
    """Test repository listing"""
    try:
        # List repositories
        result = github_agent.execute({
            'operation': 'list_repositories',
            'sort_by': 'updated'
        })
        
        if result.status.value == 'success':
            repos = result.data['repositories']
            total_count = result.data['total_count']
            
            print(f"✅ Found {total_count} repositories")
            print(f"   Execution time: {result.execution_time_ms}ms")
            
            # Display top 5 repositories
            print("\n📦 Top 5 repositories (by last update):")
            for i, repo in enumerate(repos[:5], 1):
                print(f"   {i}. {repo['full_name']}")
                print(f"      Language: {repo.get('language', 'Unknown')}")
                print(f"      Size: {repo['size']} KB")
                print(f"      Last updated: {repo['last_commit']}")
                print(f"      Tech stack: {', '.join(repo['technology_stack']) if repo['technology_stack'] else 'Unknown'}")
                print()
            
            return repos
        else:
            print(f"❌ Repository listing failed: {result.error_message}")
            return None
            
    except Exception as e:
        print(f"❌ Repository listing error: {str(e)}")
        return None

def test_clone_repository(github_agent: GitHubAgent, repos: list) -> bool:
    """Test repository cloning"""
    try:
        if not repos:
            print("❌ No repositories available for cloning")
            return False
        
        # Let user select a repository
        print("Available repositories for cloning:")
        for i, repo in enumerate(repos[:10], 1):  # Show top 10
            print(f"   {i}. {repo['full_name']} ({repo.get('language', 'Unknown')}) - {repo['size']} KB")
        
        selection = input(f"\nSelect repository (1-{min(10, len(repos))}): ").strip()
        
        try:
            index = int(selection) - 1
            if index < 0 or index >= min(10, len(repos)):
                raise ValueError("Invalid selection")
            
            selected_repo = repos[index]
        except (ValueError, IndexError):
            print("❌ Invalid selection")
            return False
        
        print(f"\n🔄 Cloning repository: {selected_repo['full_name']}")
        
        # Generate session ID
        import uuid
        session_id = str(uuid.uuid4())
        
        # Clone repository
        result = github_agent.execute({
            'operation': 'clone_repository',
            'repository_url': selected_repo['clone_url'],
            'branch': selected_repo['default_branch'],
            'session_id': session_id
        }, session_id=session_id)
        
        if result.status.value == 'success':
            clone_data = result.data
            analysis = clone_data['analysis']
            
            print(f"✅ Repository cloned successfully!")
            print(f"   Local path: {clone_data['local_path']}")
            print(f"   Branch: {clone_data['branch']}")
            print(f"   Commit: {clone_data['commit_hash'][:8]}...")
            print(f"   Execution time: {result.execution_time_ms}ms")
            
            # Display repository analysis
            print(f"\n📊 Repository Analysis:")
            print(f"   Total files: {analysis['total_files']}")
            print(f"   Source files: {analysis['source_files']}")
            print(f"   Config files: {analysis['config_files']}")
            print(f"   Documentation files: {analysis['documentation_files']}")
            
            if analysis['entry_points']:
                print(f"   Entry points: {', '.join(analysis['entry_points'])}")
            
            if analysis['dependencies']:
                print(f"   Dependencies: {', '.join(analysis['dependencies'].keys())}")
            
            # Show file types
            if analysis['file_types']:
                print(f"\n📁 File types:")
                for ext, count in sorted(analysis['file_types'].items(), key=lambda x: x[1], reverse=True)[:5]:
                    if ext:  # Skip empty extensions
                        print(f"   {ext}: {count} files")
            
            return True
        else:
            print(f"❌ Repository cloning failed: {result.error_message}")
            return False
            
    except Exception as e:
        print(f"❌ Repository cloning error: {str(e)}")
        return False

def cleanup_test_data(github_agent: GitHubAgent):
    """Clean up test data and temporary files"""
    try:
        # Get all sessions and clean them up
        workspace_base = github_agent.workspace_base
        if os.path.exists(workspace_base):
            import shutil
            shutil.rmtree(workspace_base)
            print(f"✅ Cleaned up workspace: {workspace_base}")
        else:
            print("ℹ️  No cleanup needed")
    except Exception as e:
        print(f"⚠️  Cleanup warning: {str(e)}")

def demo_agent_registry():
    """Demonstrate agent registry functionality"""
    print("\n=== Agent Registry Demo ===")
    
    # List registered agents
    agents = agent_registry.list_agents()
    print(f"📋 Registered agents: {', '.join(agents)}")
    
    # Get agent status
    for agent_id in agents:
        status = agent_registry.get_agent_status(agent_id)
        print(f"   {agent_id}: {status.value if status else 'Unknown'}")

if __name__ == "__main__":
    try:
        main()
        demo_agent_registry()
    except KeyboardInterrupt:
        print("\n\n👋 Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc() 