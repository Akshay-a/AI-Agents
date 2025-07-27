"""
Example Usage of Code Generation Agent

Demonstrates the intelligent code generation agent with:
1. Context optimization and caching
2. Tool-based iterative workflows  
3. Integration with GitHub and Knowledge Graph agents
4. Self-correcting code generation
"""

import os
import sys
import logging
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.code_generation import CodeGenerationAgent
from agents.github.github_agent import GitHubAgent
from agents.knowledge_graph.knowledge_graph_agent import KnowledgeGraphAgent
from agents.base.agent_interface import agent_registry


def setup_logging():
    """Setup logging for the example"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('code_generation_example.log')
        ]
    )


def setup_agents():
    """Setup and register all required agents"""
    print("🚀 Setting up agents...")
    
    # Create and register GitHub agent
    github_config = {
        'workspace_base': '/tmp/github_workspace_demo'
    }
    github_agent = GitHubAgent(github_config)
    agent_registry.register_agent(github_agent)
    
    # Create and register Knowledge Graph agent
    kg_agent = KnowledgeGraphAgent()
    agent_registry.register_agent(kg_agent)
    
    # Create and register Code Generation agent
    codegen_config = {
        'max_tokens': 32000,
        'max_iterations': 3,  # Reduced for demo
        'cache_dir': '/tmp/codegen_cache_demo',
        'enable_docker_execution': True,  # Enable Docker-based execution validation
        'docker_timeout': 60  # Timeout for code execution in seconds
    }
    codegen_agent = CodeGenerationAgent(codegen_config)
    agent_registry.register_agent(codegen_agent)
    
    print("✅ All agents registered successfully")
    return github_agent, kg_agent, codegen_agent


def demo_basic_code_generation(codegen_agent: CodeGenerationAgent, session_id: str):
    """Demonstrate basic code generation"""
    print("\n📝 Demo 1: Basic Code Generation")
    print("=" * 50)
    
    requirements = """
    Create a Python function that validates email addresses using regex.
    The function should:
    1. Accept an email string as input
    2. Return True if valid, False if invalid
    3. Handle edge cases like empty strings
    4. Include proper error handling
    5. Add comprehensive docstring
    """
    
    # Generate code
    result = codegen_agent.execute({
        'operation': 'generate_code',
        'requirements': requirements,
        'target_language': 'python',
        'session_id': session_id,
        'context_hints': [
            'Use re module for regex patterns',
            'Follow PEP 8 style guidelines'
        ]
    }, session_id)
    
    if result.status.value == 'success':
        data = result.data
        print(f"✅ Code generation successful!")
        print(f"   Iterations: {data['execution_summary']['iterations']}")
        print(f"   Execution time: {data['execution_summary']['execution_time_ms']}ms")
        print(f"   Final confidence: {data['validation_results'][-1]['confidence_score']:.2f}")
        
        print("\n📄 Generated Code:")
        print("```python")
        print(data['generated_code'])
        print("```")
        
        if data['output_info']:
            print(f"\n💾 Code saved to: {data['output_info']['full_path']}")
    else:
        print(f"❌ Code generation failed: {result.error_message}")


def demo_code_enhancement(codegen_agent: CodeGenerationAgent, session_id: str):
    """Demonstrate code enhancement capabilities"""
    print("\n🔧 Demo 2: Code Enhancement")
    print("=" * 50)
    
    # Simulate existing legacy code
    existing_code = """
def calc(x, y, op):
    if op == '+':
        return x + y
    elif op == '-':
        return x - y
    elif op == '*':
        return x * y
    elif op == '/':
        return x / y
    else:
        return 'error'
"""
    
    requirements = """
    Enhance this basic calculator function with:
    1. Proper error handling for division by zero
    2. Type hints and docstring
    3. Support for more operations (power, modulo)
    4. Input validation
    5. Better error messages
    6. Follow modern Python best practices
    """
    
    result = codegen_agent.execute({
        'operation': 'enhance_code',
        'requirements': requirements,
        'existing_code': existing_code,
        'session_id': session_id
    }, session_id)
    
    if result.status.value == 'success':
        data = result.data
        print(f"✅ Code enhancement successful!")
        print(f"   Iterations: {data['execution_summary']['iterations']}")
        print(f"   Final confidence: {data['validation_results'][-1]['confidence_score']:.2f}")
        
        print("\n📄 Enhanced Code:")
        print("```python")
        print(data['enhanced_code'])
        print("```")
    else:
        print(f"❌ Code enhancement failed: {result.error_message}")


def demo_requirements_analysis(codegen_agent: CodeGenerationAgent, session_id: str):
    """Demonstrate requirements analysis"""
    print("\n🔍 Demo 3: Requirements Analysis")
    print("=" * 50)
    
    complex_requirements = """
    Build a REST API for a task management system with the following features:
    1. User authentication with JWT tokens
    2. CRUD operations for tasks (create, read, update, delete)
    3. Task categories and tags
    4. Due date tracking and notifications
    5. User roles (admin, manager, user)
    6. Database persistence with SQLAlchemy
    7. Input validation and error handling
    8. API rate limiting
    9. Comprehensive logging
    10. Unit tests with pytest
    """
    
    result = codegen_agent.execute({
        'operation': 'analyze_requirements',
        'requirements': complex_requirements,
        'session_id': session_id
    }, session_id)
    
    if result.status.value == 'success':
        analysis = result.data['analysis']
        print(f"✅ Requirements analysis complete!")
        
        print(f"\n📊 Analysis Results:")
        print(f"   Complexity Score: {analysis['complexity_score']:.1f}/10")
        print(f"   Estimated Effort: {analysis['estimated_effort']}")
        print(f"   Technical Keywords: {', '.join(analysis['technical_keywords'][:5])}...")
        
        print(f"\n💡 Suggested Approach:")
        for i, approach in enumerate(analysis['suggested_approach'], 1):
            print(f"   {i}. {approach}")
        
        print(f"\n🛠️ Recommended Tools:")
        print(f"   {', '.join(analysis['recommended_tools'][:6])}...")
        
        print(f"\n⚠️ Potential Challenges:")
        for i, challenge in enumerate(analysis['potential_challenges'], 1):
            print(f"   {i}. {challenge}")
    else:
        print(f"❌ Requirements analysis failed: {result.error_message}")


def demo_with_repository_context(github_agent: GitHubAgent, kg_agent: KnowledgeGraphAgent, 
                                codegen_agent: CodeGenerationAgent, session_id: str):
    """Demonstrate code generation with repository context"""
    print("\n🏢 Demo 4: Code Generation with Repository Context")
    print("=" * 50)
    
    # Note: This is a simplified demo. In a real scenario, you would:
    # 1. Authenticate with GitHub
    # 2. Clone a repository  
    # 3. Index it with the knowledge graph agent
    # 4. Generate code using that context
    
    print("📝 This demo shows how the agent would work with repository context:")
    print("   1. Repository would be cloned using GitHub agent")
    print("   2. Codebase would be indexed using Knowledge Graph agent")
    print("   3. Code generation would use existing patterns and structures")
    
    # Simulate having repository context
    requirements = """
    Create a new API endpoint that follows the existing patterns in this codebase.
    The endpoint should handle user profile updates with:
    1. Input validation similar to existing endpoints
    2. Database operations following the repository pattern
    3. Error handling consistent with the codebase
    4. Response formatting matching existing APIs
    """
    
    result = codegen_agent.execute({
        'operation': 'generate_code',
        'requirements': requirements,
        'target_language': 'python',
        'session_id': session_id,
        'context_hints': [
            'Follow existing Flask API patterns',
            'Use the existing user model structure',
            'Apply consistent error handling'
        ]
    }, session_id)
    
    if result.status.value == 'success':
        data = result.data
        print(f"✅ Context-aware code generation successful!")
        print(f"   Context items used: {data['execution_summary']['context_items_used']}")
        print(f"   Tool calls made: {data['execution_summary']['tool_calls_made']}")
        print(f"   Generated code follows repository patterns")
    else:
        print(f"❌ Context-aware generation failed: {result.error_message}")


def demo_execution_validation(codegen_agent: CodeGenerationAgent, session_id: str):
    """Demonstrate Docker-based execution validation"""
    print("\n🐳 Demo 5: Docker Execution Validation")
    print("=" * 50)
    
    # Create requirements that might lead to runtime errors
    challenging_requirements = """
    Create a Python function that:
    1. Calculates factorial using recursion
    2. Handles edge cases for n=0 and n=1
    3. Validates input is a non-negative integer
    4. Raises appropriate errors for invalid inputs
    5. Has a main section that tests the function with values 0, 5, and 10
    6. Print the results in a formatted way
    """
    
    result = codegen_agent.execute({
        'operation': 'generate_code',
        'requirements': challenging_requirements,
        'target_language': 'python',
        'session_id': session_id,
        'context_hints': [
            'Include proper error handling',
            'Add input validation',
            'Include test cases in main section'
        ]
    }, session_id)
    
    if result.status.value == 'success':
        data = result.data
        print(f"✅ Code generation with execution validation successful!")
        print(f"   Iterations: {data['execution_summary']['iterations']}")
        print(f"   Final confidence: {data['validation_results'][-1]['confidence_score']:.2f}")
        
        # Show execution validation details
        final_validation = data['validation_results'][-1]
        if 'execution_feedback' in final_validation.get('metadata', {}):
            feedback = final_validation['metadata']['execution_feedback']
            print(f"   Execution Test: {'✅ PASSED' if final_validation['metadata']['execution_test'] else '❌ FAILED'}")
            print(f"   Execution Details: {feedback[:100]}...")
        
        print("\n📄 Generated Code:")
        print("```python")
        print(data['generated_code'])
        print("```")
    else:
        print(f"❌ Code generation failed: {result.error_message}")


def demo_agent_status_and_cleanup(codegen_agent: CodeGenerationAgent, session_id: str):
    """Demonstrate agent status monitoring and cleanup"""
    print("\n📊 Demo 6: Agent Status and Cleanup")
    print("=" * 50)
    
    # Get agent status
    status_result = codegen_agent.execute({
        'operation': 'get_generation_status',
        'session_id': session_id
    }, session_id)
    
    if status_result.status.value == 'success':
        status = status_result.data
        print(f"✅ Agent Status Retrieved:")
        print(f"   Available Tools: {', '.join(status['available_tools'])}")
        print(f"   Context Cache Size: {status['context_manager_stats']['cache_size']}")
        print(f"   Max Iterations: {status['agent_capabilities']['max_iterations']}")
        print(f"   Features: Context Optimization: {status['agent_capabilities']['context_optimization']}")
        print(f"            Tool Integration: {status['agent_capabilities']['tool_integration']}")
        print(f"            Iterative Correction: {status['agent_capabilities']['iterative_correction']}")
    
    # Cleanup session
    cleanup_result = codegen_agent.execute({
        'operation': 'cleanup_session',
        'session_id': session_id
    }, session_id)
    
    if cleanup_result.status.value == 'success':
        print(f"\n🧹 Session cleanup successful")
    else:
        print(f"\n❌ Session cleanup failed")


def main():
    """Main demonstration function"""
    print("🤖 Code Generation Agent Demo")
    print("=" * 60)
    print("This demo showcases the intelligent code generation agent with:")
    print("• Context optimization and caching")
    print("• Tool-based iterative workflows")
    print("• Self-correcting code generation")
    print("• Docker-based execution validation")
    print("• Integration with existing agents")
    print("=" * 60)
    
    # Setup
    setup_logging()
    session_id = f"demo_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    try:
        # Initialize agents
        github_agent, kg_agent, codegen_agent = setup_agents()
        
        # Run demonstrations
        demo_basic_code_generation(codegen_agent, session_id)
        demo_code_enhancement(codegen_agent, session_id)
        demo_requirements_analysis(codegen_agent, session_id)
        demo_with_repository_context(github_agent, kg_agent, codegen_agent, session_id)
        demo_execution_validation(codegen_agent, session_id)
        demo_agent_status_and_cleanup(codegen_agent, session_id)
        
        print("\n🎉 All demonstrations completed successfully!")
        print("\nKey Features Demonstrated:")
        print("✅ Intelligent code generation with context awareness")
        print("✅ Docker-based execution validation with real runtime feedback")
        print("✅ Iterative self-correction using execution results")
        print("✅ Context optimization with caching (reduces API costs)")
        print("✅ Tool integration for codebase analysis")
        print("✅ Requirements analysis and complexity estimation")
        print("✅ Code enhancement and bug fixing capabilities")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {str(e)}")
        logging.error(f"Demo error: {e}", exc_info=True)
    
    finally:
        print(f"\n📝 Session ID: {session_id}")
        print("📁 Check output directory for generated code files")
        print("📋 Check log file: code_generation_example.log")


if __name__ == "__main__":
    main() 