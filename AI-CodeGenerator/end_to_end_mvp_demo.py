#!/usr/bin/env python3
"""
🚀 AI Code Generator MVP - End-to-End Demo

This script demonstrates the complete workflow:
1. GitHub authentication and repository selection
2. Knowledge graph building from codebase
3. Interactive user requests (migration/enhancement)
4. AI-powered code generation with execution validation

Requirements:
- GitHub personal access token
- Docker running (for code execution validation)
- Python packages: see requirements.txt
"""

import os
import sys
import time
import json
from datetime import datetime
from typing import Dict, Any, List

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agents.github.github_agent import GitHubAgent
from agents.knowledge_graph.knowledge_graph_agent import KnowledgeGraphAgent
from agents.code_generation.code_generation_agent import CodeGenerationAgent
from agents.base.agent_interface import agent_registry


class MVPDemo:
    """End-to-end MVP demonstration"""
    
    def __init__(self):
        self.session_id = f"mvp_demo_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.github_agent = None
        self.kg_agent = None
        self.codegen_agent = None
        self.selected_repo = None
        self.repo_analysis = None
        
        print("🚀 AI Code Generator MVP Demo")
        print("=" * 60)
        print("Welcome! This demo will:")
        print("  1. 🔐 Connect to your GitHub account")
        print("  2. 📁 Let you choose a repository to work with")
        print("  3. 🧠 Analyze your codebase with AI")
        print("  4. 💬 Ask what you'd like to improve or migrate")
        print("  5. 🤖 Generate production-ready code for you")
        print()
        print(f"Session ID: {self.session_id}")
        print("=" * 60)
    
    def setup_agents(self):
        """Initialize and register all agents"""
        print("\n🔧 Setting up AI agents...")
        
        # GitHub Agent
        github_config = {
            'workspace_base': f'/tmp/mvp_demo_{self.session_id}'
        }
        self.github_agent = GitHubAgent(github_config)
        agent_registry.register_agent(self.github_agent)
        print("✅ GitHub Agent initialized")
        
        # Knowledge Graph Agent  
        self.kg_agent = KnowledgeGraphAgent()
        agent_registry.register_agent(self.kg_agent)
        print("✅ Knowledge Graph Agent initialized")
        
        # Code Generation Agent
        codegen_config = {
            'max_tokens': 32000,
            'max_iterations': 3,
            'enable_docker_execution': True,
            'docker_timeout': 120,
            'cache_dir': f'/tmp/mvp_codegen_cache_{self.session_id}'
        }
        self.codegen_agent = CodeGenerationAgent(codegen_config)
        agent_registry.register_agent(self.codegen_agent)
        print("✅ Code Generation Agent initialized")
        
        print("🎯 All agents ready!")
    
    def github_authentication(self):
        """Handle GitHub authentication"""
        print("\n🔐 Step 1: GitHub Authentication")
        print("-" * 40)
        
        # Check for token in environment first
        github_token = os.getenv('GITHUB_TOKEN')
        
        if github_token:
            print(f"✅ Found GitHub token in environment (ends with ...{github_token[-4:]})")
            confirm = input("Use this token? (y/n): ").strip().lower()
            if confirm not in ['y', 'yes']:
                github_token = None
        
        if not github_token:
            print("\n🔑 Please enter your GitHub Personal Access Token")
            print("   📋 Create one at: https://github.com/settings/tokens")
            print("   🔧 Required scopes: 'repo' (for private) or 'public_repo' (for public)")
            print("   💡 Tip: Set GITHUB_TOKEN environment variable to skip this step")
            print()
            github_token = input("GitHub Token: ").strip()
        
        if not github_token:
            print("❌ GitHub token is required for this demo")
            return False
        
        try:
            # Authenticate
            result = self.github_agent.execute({
                'operation': 'authenticate',
                'github_token': github_token
            }, self.session_id)
            
            if result.status.value == 'success':
                user_info = result.data['user']
                print(f"✅ Successfully authenticated as: {user_info['login']}")
                print(f"   Name: {user_info.get('name', 'N/A')}")
                print(f"   Public repos: {user_info['public_repos']}")
                print(f"   Private repos: {user_info['private_repos']}")
                return True
            else:
                print(f"❌ Authentication failed: {result.error_message}")
                return False
                
        except Exception as e:
            print(f"❌ Authentication error: {str(e)}")
            return False
    
    def select_repository(self):
        """List and select a repository"""
        print("\n📁 Step 2: Choose Your Repository")
        print("-" * 40)
        
        try:
            # List repositories
            result = self.github_agent.execute({
                'operation': 'list_repositories',
                'sort_by': 'updated'  # Most recently updated first
            }, self.session_id)
            
            if result.status.value != 'success':
                print(f"❌ Failed to list repositories: {result.error_message}")
                return False
            
            repositories = result.data['repositories'][:10]  # Show top 10
            
            if not repositories:
                print("❌ No repositories found")
                return False
            
            print(f"📋 Your repositories (showing top 10, sorted by activity):")
            print()
            
            for i, repo in enumerate(repositories, 1):
                stars = repo.get('stargazers_count', 0)
                language = repo.get('language', 'Unknown')
                updated = repo.get('updated_at', '')[:10]  # Just the date
                private = "🔒" if repo.get('private', False) else "🌍"
                
                print(f"{i:2d}. {private} {repo['name']}")
                print(f"     Language: {language} | Stars: {stars} | Updated: {updated}")
                print(f"     {repo.get('description', 'No description')[:80]}...")
                print()
            
            # Let user select
            while True:
                try:
                    choice = input(f"Select repository (1-{len(repositories)}) or 'q' to quit: ").strip()
                    
                    if choice.lower() == 'q':
                        return False
                    
                    repo_index = int(choice) - 1
                    if 0 <= repo_index < len(repositories):
                        self.selected_repo = repositories[repo_index]
                        print(f"\n✅ Selected: {self.selected_repo['name']}")
                        print(f"   📋 Description: {self.selected_repo.get('description', 'No description')}")
                        print(f"   🛠️  Language: {self.selected_repo.get('language', 'Unknown')}")
                        print()
                        confirm = input("Proceed with this repository? (y/n): ").strip().lower()
                        if confirm in ['y', 'yes']:
                            return True
                        else:
                            print("Let's choose a different repository...")
                            continue
                    else:
                        print(f"Please enter a number between 1 and {len(repositories)}")
                        
                except ValueError:
                    print("Please enter a valid number")
                    
        except Exception as e:
            print(f"❌ Repository selection error: {str(e)}")
            return False
    
    def clone_and_analyze_repository(self):
        """Clone repository and build knowledge graph"""
        print(f"\n🧠 Step 3: Analyzing Repository - {self.selected_repo['name']}")
        print("-" * 60)
        
        try:
            # Clone repository
            print("📥 Cloning repository...")
            clone_result = self.github_agent.execute({
                'operation': 'clone_repository',
                'repository_url': self.selected_repo['clone_url'],
                'branch': self.selected_repo.get('default_branch', 'main')
            }, self.session_id)
            
            if clone_result.status.value != 'success':
                print(f"❌ Failed to clone repository: {clone_result.error_message}")
                return False
            
            repo_path = clone_result.data['local_path']
            print(f"✅ Repository cloned to: {repo_path}")
            
            # Analyze repository structure
            analysis = clone_result.data.get('analysis', {})
            print(f"📊 Repository Analysis:")
            print(f"   Total files: {analysis.get('total_files', 0)}")
            print(f"   Code files: {analysis.get('code_files', 0)}")
            print(f"   Main language: {analysis.get('primary_language', 'Unknown')}")
            
            # Build knowledge graph
            print("\n🧠 Building knowledge graph...")
            kg_result = self.kg_agent.execute({
                'operation': 'analyze_repository',
                'repository_path': repo_path
            }, self.session_id)
            
            if kg_result.status.value != 'success':
                print(f"❌ Failed to analyze repository: {kg_result.error_message}")
                return False
            
            self.repo_analysis = kg_result.data
            stats = self.repo_analysis['statistics']
            
            print(f"✅ Knowledge graph built successfully!")
            print(f"📈 Analysis Statistics:")
            print(f"   Total chunks: {stats['total_chunks']}")
            print(f"   Languages: {', '.join(stats['language_distribution'].keys())}")
            print(f"   Chunk types: {', '.join(stats['chunk_type_distribution'].keys())}")
            
            return True
            
        except Exception as e:
            print(f"❌ Repository analysis error: {str(e)}")
            return False
    
    def get_user_request(self):
        """Get user's coding request"""
        print(f"\n💬 Step 4: What Can I Help You With?")
        print("-" * 50)
        
        print("I can help you with two main types of requests:")
        print()
        print("1. 🔄 Code Migration")
        print("   Convert your code between different languages or frameworks")
        print("   Examples: Flask → FastAPI, JavaScript → TypeScript, Java → Python")
        print()
        print("2. ⚡ Code Enhancement") 
        print("   Improve your existing code with modern best practices")
        print("   Examples: Add error handling, optimize performance, add type hints")
        
        while True:
            try:
                choice = input("\nSelect option (1 or 2): ").strip()
                
                if choice == '1':
                    return self._get_migration_request()
                elif choice == '2':
                    return self._get_enhancement_request()
                else:
                    print("Please select either 1 (Migration) or 2 (Enhancement)")
                    
            except KeyboardInterrupt:
                print("\n👋 Demo cancelled by user")
                return None
    
    def _get_migration_request(self):
        """Get migration-specific request"""
        print("\n🔄 Code Migration Request")
        print("=" * 30)
        print("Let's set up your migration project!")
        print()
        print("💡 Popular migration examples:")
        print("   • Flask → FastAPI (Python web frameworks)")
        print("   • JavaScript → TypeScript (add type safety)")  
        print("   • Express.js → Fastify (Node.js frameworks)")
        print("   • Spring Boot → Quarkus (Java frameworks)")
        print()
        
        source_lang = input("📤 What are you migrating FROM (source language/framework)? ").strip()
        target_lang = input("📥 What are you migrating TO (target language/framework)? ").strip()
        
        print(f"\n🎯 You want to migrate from {source_lang} to {target_lang}")
        specific_request = input("Any specific requirements or features to focus on? (optional): ").strip()
        
        requirements = f"""
        Migrate code from {source_lang} to {target_lang}.
        Specific requirements: {specific_request}
        
        Please:
        1. Analyze the current codebase structure
        2. Identify key components to migrate
        3. Convert the code while preserving functionality
        4. Follow {target_lang} best practices
        5. Ensure the migrated code is production-ready
        """
        
        return {
            'operation': 'migrate_code',
            'requirements': requirements,
            'source_language': source_lang,
            'target_language': target_lang
        }
    
    def _get_enhancement_request(self):
        """Get enhancement-specific request"""
        print("\n⚡ Code Enhancement Request")
        print("=" * 30)
        print("Let's improve your codebase!")
        print()
        print("🚀 Popular enhancement types:")
        print("   • Error handling & logging")
        print("   • Performance optimization")
        print("   • Type hints & documentation")
        print("   • Security improvements")
        print("   • Code refactoring & cleanup")
        print()
        
        enhancement_type = input("🛠️  What type of enhancement would you like? ").strip()
        specific_files = input("Any specific files to focus on? (leave empty for AI to choose): ").strip()
        
        requirements = f"""
        Enhance the existing codebase with: {enhancement_type}
        
        Focus areas:
        1. Code quality improvements
        2. Performance optimizations
        3. Better error handling
        4. Documentation and type hints
        5. Modern best practices
        
        {f"Focus on these files: {specific_files}" if specific_files else "Analyze and suggest files to enhance"}
        """
        
        return {
            'operation': 'enhance_code',
            'requirements': requirements,
            'target_files': specific_files.split(',') if specific_files else []
        }
    

    
    def process_user_request(self, request):
        """Process user's coding request"""
        print(f"\n🤖 Step 5: AI Code Generation")
        print("-" * 50)
        
        try:
            # Add repository context to request
            if self.repo_analysis:
                request['context_hints'] = [
                    f"Repository: {self.selected_repo['name']}",
                    f"Primary language: {self.selected_repo.get('language', 'Unknown')}",
                    f"Total files analyzed: {self.repo_analysis['statistics']['total_files']}",
                    "Use existing code patterns and architecture when possible"
                ]
            
            request['session_id'] = self.session_id
            
            print("🔄 AI is working on your request...")
            print("   📝 Analyzing your repository structure")
            print("   🧠 Understanding your codebase patterns") 
            print("   ⚡ Generating optimized code")
            print("   🐳 Testing code in Docker container")
            print("   ⏳ This may take 30-60 seconds...")
            
            start_time = time.time()
            
            # Execute the request
            result = self.codegen_agent.execute(request, self.session_id)
            
            execution_time = time.time() - start_time
            
            if result.status.value == 'success':
                self._display_successful_result(result.data, execution_time)
                return True
            else:
                print(f"❌ Request failed: {result.error_message}")
                return False
                
        except Exception as e:
            print(f"❌ Processing error: {str(e)}")
            return False
    
    def _display_successful_result(self, data, execution_time):
        """Display successful code generation results"""
        print(f"\n🎉 Code generation completed successfully!")
        print(f"⏱️  Execution time: {execution_time:.1f} seconds")
        print("-" * 60)
        
        # Show execution summary
        if 'execution_summary' in data:
            summary = data['execution_summary']
            print(f"📊 Generation Summary:")
            print(f"   Iterations: {summary.get('iterations', 'N/A')}")
            print(f"   Context items used: {summary.get('context_items_used', 'N/A')}")
            print(f"   Tool calls made: {summary.get('tool_calls_made', 'N/A')}")
        
        # Show validation results
        if 'validation_results' in data and data['validation_results']:
            final_validation = data['validation_results'][-1]
            confidence = final_validation.get('confidence_score', 0)
            print(f"✅ Final confidence score: {confidence:.2f}/1.0")
            
            # Show execution validation if available
            metadata = final_validation.get('metadata', {})
            if 'execution_test' in metadata:
                execution_status = "✅ PASSED" if metadata['execution_test'] else "❌ FAILED"
                print(f"🐳 Docker execution test: {execution_status}")
                
                if 'execution_feedback' in metadata:
                    feedback = metadata['execution_feedback'][:100]
                    print(f"📋 Execution feedback: {feedback}...")
        
        # Show generated code
        code_key = None
        for key in ['generated_code', 'enhanced_code', 'migrated_code', 'fixed_code']:
            if key in data and data[key]:
                code_key = key
                break
        
        if code_key:
            print(f"\n📄 {code_key.replace('_', ' ').title()}:")
            print("=" * 60)
            code = data[code_key]
            
            # Truncate very long code for display
            if len(code) > 2000:
                print(code[:2000])
                print(f"\n... (truncated, showing first 2000 characters of {len(code)} total)")
            else:
                print(code)
            print("=" * 60)
        
        # Show output file info
        if 'output_info' in data and data['output_info']:
            output_info = data['output_info']
            print(f"\n💾 Code saved to: {output_info.get('full_path', 'N/A')}")
            print(f"📁 Output directory: {output_info.get('directory', 'N/A')}")
        
        # Show suggestions if any
        if 'validation_results' in data and data['validation_results']:
            final_validation = data['validation_results'][-1]
            if final_validation.get('suggestions'):
                print(f"\n💡 Suggestions for improvement:")
                for i, suggestion in enumerate(final_validation['suggestions'][:3], 1):
                    print(f"   {i}. {suggestion}")
    
    def cleanup(self):
        """Clean up resources"""
        print(f"\n🧹 Cleaning up session: {self.session_id}")
        
        try:
            # Cleanup GitHub workspace
            if self.github_agent:
                self.github_agent.execute({
                    'operation': 'cleanup_session',
                    'session_id': self.session_id
                }, self.session_id)
            
            # Cleanup Knowledge Graph
            if self.kg_agent:
                self.kg_agent.execute({
                    'operation': 'cleanup_session'
                }, self.session_id)
            
            # Cleanup Code Generation
            if self.codegen_agent:
                self.codegen_agent.execute({
                    'operation': 'cleanup_session'
                }, self.session_id)
            
            print("✅ Cleanup completed")
            
        except Exception as e:
            print(f"⚠️ Cleanup warning: {str(e)}")
    
    def run(self):
        """Run the complete MVP demo"""
        try:
            # Setup
            self.setup_agents()
            
            # GitHub authentication
            if not self.github_authentication():
                return
            
            # Repository selection
            if not self.select_repository():
                return
            
            # Repository analysis
            if not self.clone_and_analyze_repository():
                return
            
            # User request loop
            while True:
                request = self.get_user_request()
                if request is None:
                    break
                
                success = self.process_user_request(request)
                
                # Ask if user wants to make another request
                if success:
                    print(f"\n❓ Would you like to make another request? (y/n): ", end="")
                    another = input().strip().lower()
                    if another not in ['y', 'yes']:
                        break
                else:
                    print(f"\n❓ Would you like to try again? (y/n): ", end="")
                    retry = input().strip().lower()
                    if retry not in ['y', 'yes']:
                        break
            
            print(f"\n🎯 MVP Demo completed!")
            print("Thank you for trying the AI Code Generator!")
            
        except KeyboardInterrupt:
            print(f"\n\n👋 Demo interrupted by user")
        except Exception as e:
            print(f"\n❌ Demo error: {str(e)}")
        finally:
            self.cleanup()


def main():
    """Main entry point"""
    # Check requirements
    print("🔍 Checking requirements...")
    
    try:
        import docker
        client = docker.from_env()
        client.ping()
        print("✅ Docker is available")
    except Exception as e:
        print(f"⚠️ Docker not available: {e}")
        print("   Code execution validation will be limited")
    
    # Check environment
    if not os.getenv('GOOGLE_API_KEY'):
        print("⚠️ GOOGLE_API_KEY not found in environment")
        print("   Please set your Google API key for Gemini")
        print("   export GOOGLE_API_KEY='your-api-key-here'")
        return
    
    # Run demo
    demo = MVPDemo()
    demo.run()


if __name__ == "__main__":
    main() 