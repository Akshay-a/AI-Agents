#!/usr/bin/env python3
"""
Independent Integration Test for Knowledge Graph Agent
Tests the complete pipeline: GitHub clone → Code indexing → Interactive Q&A

This script:
1. Uses GitHub agent to clone a repository
2. Uses Knowledge Graph agent to index the codebase
3. Provides interactive Q&A interface for testing
"""

import os
import sys
import time
import json
import tempfile
import shutil
from datetime import datetime
from typing import Dict, Any, Optional

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from knowledge_graph_agent import KnowledgeGraphAgent, create_sample_agent_input


class CodebaseAnalyzer:
    """Independent codebase analyzer combining direct git cloning and Knowledge Graph agent"""
    
    def __init__(self):
        self.kg_agent = None
        self.session_id = f"integration_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.cloned_repo_path = None
        self.repo_info = None
        
        print("🚀 Initializing Codebase Analyzer")
        print("=" * 60)
        
        # Initialize agents
        self._initialize_agent()
    
    def _initialize_agent(self):
        """Initialize the Knowledge Graph agent"""
        
        print("🔧 Initializing Knowledge Graph Agent...")
        try:
            self.kg_agent = KnowledgeGraphAgent()
            print("✅ Knowledge Graph Agent initialized")
        except Exception as e:
            print(f"❌ Failed to initialize Knowledge Graph Agent: {e}")
            return False
        
        return True
    
    def clone_repository(self, repo_url: str, branch: str = "main") -> bool:
        """Clone a repository using the GitHub agent"""
        
        print(f"\n📁 Cloning Repository: {repo_url}")
        print("-" * 40)
        
        # Check if GitHub agent needs authentication for public repos
        # Try without authentication first for public repositories
        print("🔄 Attempting to clone (public repository)...")
        
        try:
            # For public repositories, we can try direct git clone without GitHub agent
            import git
            import tempfile
            
            # Create temporary directory for cloning
            clone_dir = tempfile.mkdtemp(prefix="integration_test_")
            
            print(f"🔄 Cloning to temporary directory: {clone_dir}")
            
            # Clone the repository directly
            repo = git.Repo.clone_from(repo_url, clone_dir, branch=branch, depth=1)
            
            self.cloned_repo_path = clone_dir
            self.repo_info = {'name': os.path.basename(repo_url.replace('.git', ''))}
            
            print(f"✅ Repository cloned successfully!")
            print(f"   📂 Local path: {self.cloned_repo_path}")
            print(f"   📊 Repository: {self.repo_info.get('name', 'Unknown')}")
            
            # Quick analysis of cloned repository
            total_files = 0
            languages = set()
            
            for root, dirs, files in os.walk(clone_dir):
                # Skip .git directory
                if '.git' in root:
                    continue
                    
                for file in files:
                    if file.endswith(('.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs')):
                        total_files += 1
                        ext = os.path.splitext(file)[1]
                        if ext == '.py':
                            languages.add('Python')
                        elif ext in ['.js', '.jsx']:
                            languages.add('JavaScript')
                        elif ext in ['.ts', '.tsx']:
                            languages.add('TypeScript')
                        elif ext == '.java':
                            languages.add('Java')
                        elif ext in ['.cpp', '.cc', '.cxx']:
                            languages.add('C++')
                        elif ext == '.c':
                            languages.add('C')
                        elif ext == '.go':
                            languages.add('Go')
                        elif ext == '.rs':
                            languages.add('Rust')
            
            print(f"   📈 Code files found: {total_files}")
            print(f"   📈 Languages detected: {list(languages)}")
            
            return True
                
        except Exception as e:
            print(f"❌ Error during repository cloning: {e}")
            print("💡 Make sure the repository URL is correct and publicly accessible")
            return False
    
    def index_codebase(self) -> bool:
        """Index the cloned codebase using the Knowledge Graph agent"""
        
        if not self.cloned_repo_path:
            print("❌ No repository cloned. Please clone a repository first.")
            return False
        
        print(f"\n🔍 Indexing Codebase")
        print("-" * 40)
        
        try:
            # Prepare indexing input
            indexing_input = {
                'repository_path': self.cloned_repo_path
            }
            
            # Create agent input
            agent_input = create_sample_agent_input(
                "analyze_repository",
                indexing_input,
                session_id=self.session_id
            )
            
            # Execute indexing
            print("🔄 Analyzing and indexing repository...")
            start_time = time.time()
            
            result = self.kg_agent.process(agent_input)
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            if result.status.value == 'success':
                print(f"✅ Codebase indexed successfully in {processing_time:.2f} seconds!")
                
                # Show indexing statistics
                stats = result.data.get('statistics', {})
                print(f"   📊 Analysis Summary: {result.data.get('analysis_summary', 'N/A')}")
                print(f"   📁 Files processed: {stats.get('total_files', 0)}")
                print(f"   📝 Lines of code: {stats.get('total_lines', 0)}")
                print(f"   🧩 Code chunks: {stats.get('total_chunks', 0)}")
                print(f"   🌍 Languages found: {list(stats.get('language_distribution', {}).keys())}")
                
                # Show language distribution
                if stats.get('language_distribution'):
                    print(f"   📈 Language distribution:")
                    for lang, count in stats['language_distribution'].items():
                        print(f"      {lang}: {count} chunks")
                
                return True
            else:
                print(f"❌ Failed to index codebase: {result.data.get('error', 'Unknown error')}")
                return False
                
        except Exception as e:
            print(f"❌ Error during codebase indexing: {e}")
            return False
    
    def ask_question(self, question: str) -> Dict[str, Any]:
        """Ask a question about the codebase"""
        
        try:
            # Create search input
            search_input = create_sample_agent_input(
                "search_code",
                {
                    "query": question,
                    "max_results": 5
                },
                session_id=self.session_id
            )
            
            # Execute search
            result = self.kg_agent.process(search_input)
            
            if result.status.value == 'success':
                return {
                    'success': True,
                    'results': result.data.get('results', []),
                    'total_results': result.data.get('total_results', 0),
                    'explanation': result.data.get('explanation', {})
                }
            else:
                return {
                    'success': False,
                    'error': result.data.get('error', 'Unknown error')
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def find_functions(self, query: str) -> Dict[str, Any]:
        """Find functions related to the query"""
        
        try:
            search_input = create_sample_agent_input(
                "find_functions",
                {"query": query, "max_results": 5},
                session_id=self.session_id
            )
            
            result = self.kg_agent.process(search_input)
            
            if result.status.value == 'success':
                return {
                    'success': True,
                    'results': result.data.get('results', []),
                    'total_results': result.data.get('total_results', 0)
                }
            else:
                return {
                    'success': False,
                    'error': result.data.get('error', 'Unknown error')
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def find_classes(self, query: str) -> Dict[str, Any]:
        """Find classes related to the query"""
        
        try:
            search_input = create_sample_agent_input(
                "find_classes",
                {"query": query, "max_results": 5},
                session_id=self.session_id
            )
            
            result = self.kg_agent.process(search_input)
            
            if result.status.value == 'success':
                return {
                    'success': True,
                    'results': result.data.get('results', []),
                    'total_results': result.data.get('total_results', 0)
                }
            else:
                return {
                    'success': False,
                    'error': result.data.get('error', 'Unknown error')
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get current indexing statistics"""
        
        try:
            stats_input = create_sample_agent_input(
                "get_statistics",
                {},
                session_id=self.session_id
            )
            
            result = self.kg_agent.process(stats_input)
            
            if result.status.value == 'success':
                return {
                    'success': True,
                    'statistics': result.data.get('statistics', {})
                }
            else:
                return {
                    'success': False,
                    'error': result.data.get('error', 'Unknown error')
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def cleanup(self):
        """Clean up session data"""
        
        print("\n🧹 Cleaning up session...")
        
        try:
            cleanup_input = create_sample_agent_input(
                "cleanup_session",
                {},
                session_id=self.session_id
            )
            
            result = self.kg_agent.process(cleanup_input)
            
            if result.status.value == 'success':
                print("✅ Knowledge Graph session cleaned up successfully")
            else:
                print(f"⚠️ KG cleanup warning: {result.data.get('error', 'Unknown')}")
        
        except Exception as e:
            print(f"⚠️ Error during KG cleanup: {e}")
        
        # Clean up cloned repository directory
        if self.cloned_repo_path and os.path.exists(self.cloned_repo_path):
            try:
                shutil.rmtree(self.cloned_repo_path)
                print("✅ Temporary repository directory cleaned up")
            except Exception as e:
                print(f"⚠️ Error cleaning up repository directory: {e}")


def interactive_qa_session(analyzer: CodebaseAnalyzer):
    """Interactive Q&A session for testing the codebase understanding"""
    
    print(f"\n💬 Interactive Q&A Session")
    print("=" * 60)
    print("Ask questions about the codebase! Type 'help' for commands or 'quit' to exit.")
    print()
    
    while True:
        try:
            question = input("🤔 Your question: ").strip()
            
            if not question:
                continue
            
            if question.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
            
            elif question.lower() == 'help':
                print("\n📚 Available commands:")
                print("  • Ask any question about the code")
                print("  • 'functions <query>' - Find functions")
                print("  • 'classes <query>' - Find classes") 
                print("  • 'stats' - Show indexing statistics")
                print("  • 'help' - Show this help")
                print("  • 'quit' - Exit")
                continue
            
            elif question.lower() == 'stats':
                print("\n📊 Indexing Statistics:")
                stats_result = analyzer.get_statistics()
                if stats_result['success']:
                    stats = stats_result['statistics']
                    print(f"   Total chunks: {stats.get('total_chunks', 0)}")
                    print(f"   Total files: {stats.get('total_files', 0)}")
                    print(f"   Embedding dimension: {stats.get('embedding_dimension', 0)}")
                    print(f"   Embedder type: {stats.get('embedder_type', 'Unknown')}")
                else:
                    print(f"❌ Error: {stats_result['error']}")
                continue
            
            elif question.lower().startswith('functions '):
                query = question[10:].strip()
                if query:
                    print(f"\n🔍 Finding functions related to: '{query}'")
                    result = analyzer.find_functions(query)
                    _display_search_results(result, "functions")
                continue
            
            elif question.lower().startswith('classes '):
                query = question[8:].strip()
                if query:
                    print(f"\n🔍 Finding classes related to: '{query}'")
                    result = analyzer.find_classes(query)
                    _display_search_results(result, "classes")
                continue
            
            # Regular question
            print(f"\n🔍 Searching for: '{question}'")
            start_time = time.time()
            
            result = analyzer.ask_question(question)
            
            end_time = time.time()
            search_time = end_time - start_time
            
            if result['success']:
                print(f"✅ Found {result['total_results']} results in {search_time:.3f}s:")
                
                if result['total_results'] > 0:
                    for i, res in enumerate(result['results'], 1):
                        similarity = res.get('similarity', 0)
                        file_path = res.get('file_path', 'Unknown')
                        name = res.get('name', 'N/A')
                        chunk_type = res.get('chunk_type', 'unknown')
                        snippet = res.get('snippet', '')
                        
                        print(f"\n   {i}. 📄 {file_path}")
                        print(f"      🏷️  {name} ({chunk_type})")
                        print(f"      🎯 Similarity: {similarity:.3f}")
                        if snippet:
                            print(f"      💬 Snippet: {snippet[:100]}...")
                
                # Show explanation if available
                explanation = result.get('explanation', {})
                if explanation and explanation.get('total', 0) > 0:
                    print(f"\n   📈 Best match: {explanation.get('best_match', {}).get('name', 'N/A')}")
                    print(f"   📊 Avg similarity: {explanation.get('avg_similarity', 0):.3f}")
                    print(f"   📁 Files found: {len(explanation.get('files_found', []))}")
            else:
                print(f"❌ Error: {result['error']}")
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")


def _display_search_results(result: Dict[str, Any], search_type: str):
    """Display search results in a formatted way"""
    
    if result['success']:
        total = result['total_results']
        print(f"   Found {total} {search_type}:")
        
        if total > 0:
            for i, res in enumerate(result['results'], 1):
                name = res.get('name', 'Unknown')
                file_path = res.get('file_path', 'Unknown')
                similarity = res.get('similarity', 0)
                
                print(f"   {i}. {name} in {file_path} (similarity: {similarity:.3f})")
        else:
            print(f"   No {search_type} found matching your query.")
    else:
        print(f"❌ Error: {result['error']}")


def main():
    """Main integration test function"""
    
    print("🧪 Knowledge Graph Agent - Integration Test")
    print("=" * 60)
    print("This test will:")
    print("1. Clone a GitHub repository using direct git")
    print("2. Index the codebase using vector embeddings") 
    print("3. Allow interactive Q&A about the code")
    print()
    
    # Initialize analyzer
    analyzer = CodebaseAnalyzer()
    
    if not analyzer.kg_agent:
        print("❌ Failed to initialize agent. Exiting.")
        return
    
    # Get repository to clone
    print("📝 Repository Configuration")
    print("-" * 30)
    
    # Default test repositories
    default_repos = [
        "https://github.com/psf/requests",          # Python HTTP library
        "https://github.com/expressjs/express",     # Node.js web framework
        "https://github.com/spring-projects/spring-boot",  # Java framework
        "https://github.com/microsoft/vscode",      # Large TypeScript project
        "https://github.com/torvalds/linux"         # Large C project
    ]
    
    print("🎯 Suggested repositories for testing:")
    for i, repo in enumerate(default_repos, 1):
        print(f"   {i}. {repo}")
    
    print("\nChoose a repository:")
    print("• Enter 1-5 to use a suggested repository")
    print("• Enter a custom GitHub URL")
    print("• Press Enter to use requests library (default)")
    
    choice = input("\nYour choice: ").strip()
    
    # Determine repository URL
    if not choice:
        repo_url = default_repos[0]  # Default to requests
        print(f"Using default: {repo_url}")
    elif choice.isdigit() and 1 <= int(choice) <= len(default_repos):
        repo_url = default_repos[int(choice) - 1]
        print(f"Selected: {repo_url}")
    else:
        repo_url = choice
        print(f"Using custom repository: {repo_url}")
    
    # Step 1: Clone repository
    if not analyzer.clone_repository(repo_url):
        print("❌ Failed to clone repository. Exiting.")
        return
    
    # Step 2: Index codebase
    if not analyzer.index_codebase():
        print("❌ Failed to index codebase. Exiting.")
        return
    
    # Step 3: Interactive Q&A
    print("\n🎉 Setup complete! Repository cloned and indexed.")
    print("💡 Try asking questions like:")
    print("   • 'How do I make HTTP requests?'")
    print("   • 'Show me error handling code'") 
    print("   • 'Find authentication functions'")
    print("   • 'Where are the main classes?'")
    print("   • 'functions request' (to find request-related functions)")
    print("   • 'classes http' (to find HTTP-related classes)")
    
    try:
        interactive_qa_session(analyzer)
    finally:
        # Cleanup
        analyzer.cleanup()
    
    print("\n🎉 Integration test completed!")


if __name__ == "__main__":
    main() 