"""
Integration Tests for Code Generation Agent

Tests the complete system integration including:
1. Context manager optimization
2. Tool system integration
3. Iterative execution workflows
4. Agent coordination
"""

import unittest
import tempfile
import shutil
import os
import sys
from unittest.mock import Mock, patch

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.code_generation import (
    CodeGenerationAgent, 
    ContextManager, 
    ToolSystem,
    IterativeExecutor,
    CodeValidator
)
from agents.base.agent_interface import agent_registry


class TestCodeGenerationAgent(unittest.TestCase):
    """Test the main CodeGenerationAgent functionality"""
    
    def setUp(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.session_id = "test_session_123"
        
        # Create test agent with mock LLM
        config = {
            'max_tokens': 1000,
            'max_iterations': 2,
            'cache_dir': os.path.join(self.temp_dir, 'cache')
        }
        self.agent = CodeGenerationAgent(config)
        
        # Mock the LLM handler
        self.agent.llm_handler = self._create_mock_llm()
    
    def tearDown(self):
        """Cleanup test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_mock_llm(self):
        """Create mock LLM handler"""
        mock_llm = Mock()
        mock_llm.generate_initial_code.return_value = """
def validate_email(email):
    \"\"\"Validate email address using regex.\"\"\"
    import re
    
    if not email or not isinstance(email, str):
        return False
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))
"""
        return mock_llm
    
    def test_agent_initialization(self):
        """Test agent initializes correctly"""
        self.assertEqual(self.agent.agent_id, "code_generation_agent")
        self.assertIsInstance(self.agent.context_manager, ContextManager)
        self.assertIsInstance(self.agent.tool_system, ToolSystem)
        self.assertIsInstance(self.agent.iterative_executor, IterativeExecutor)
        self.assertIn('generate_code', self.agent.supported_operations)
    
    def test_basic_code_generation(self):
        """Test basic code generation functionality"""
        input_data = {
            'operation': 'generate_code',
            'requirements': 'Create a function to validate email addresses',
            'target_language': 'python',
            'session_id': self.session_id
        }
        
        result = self.agent.execute(input_data, self.session_id)
        
        self.assertEqual(result.status.value, 'success')
        self.assertIn('generated_code', result.data)
        self.assertIn('validate_email', result.data['generated_code'])
        self.assertTrue(result.data['success'])
    
    def test_requirements_analysis(self):
        """Test requirements analysis functionality"""
        input_data = {
            'operation': 'analyze_requirements',
            'requirements': 'Build a REST API with database integration and authentication'
        }
        
        result = self.agent.execute(input_data, self.session_id)
        
        self.assertEqual(result.status.value, 'success')
        analysis = result.data['analysis']
        self.assertIn('complexity_score', analysis)
        self.assertIn('technical_keywords', analysis)
        self.assertIn('suggested_approach', analysis)
        self.assertGreater(analysis['complexity_score'], 0)
    
    def test_input_validation(self):
        """Test input validation"""
        # Test missing requirements
        input_data = {
            'operation': 'generate_code',
            'session_id': self.session_id
            # Missing 'requirements'
        }
        
        result = self.agent.execute(input_data, self.session_id)
        self.assertEqual(result.status.value, 'error')
        
        # Test unsupported operation
        input_data = {
            'operation': 'unsupported_operation',
            'requirements': 'test',
            'session_id': self.session_id
        }
        
        result = self.agent.execute(input_data, self.session_id)
        self.assertEqual(result.status.value, 'error')


class TestContextManager(unittest.TestCase):
    """Test context management and optimization"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.context_manager = ContextManager(
            max_tokens=1000,
            cache_dir=os.path.join(self.temp_dir, 'cache')
        )
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_context_item_creation(self):
        """Test creating context items"""
        content = "Test code content"
        item = self.context_manager.create_context_item(
            content=content,
            item_type='legacy_code',
            source='test_file.py'
        )
        
        self.assertEqual(item.content, content)
        self.assertEqual(item.item_type, 'legacy_code')
        self.assertEqual(item.source, 'test_file.py')
        self.assertGreater(item.tokens_estimate, 0)
        self.assertIsNotNone(item.fingerprint)
    
    def test_context_window_building(self):
        """Test building optimized context windows"""
        items = []
        
        # Create multiple context items
        for i in range(5):
            item = self.context_manager.create_context_item(
                content=f"Content {i} " * 20,  # Create content of varying sizes
                item_type='search_result',
                source=f'file_{i}.py',
                priority=i + 5
            )
            items.append(item)
        
        context_window = self.context_manager.build_context_window(items)
        
        self.assertIsNotNone(context_window.fingerprint)
        self.assertGreater(len(context_window.items), 0)
        self.assertLessEqual(context_window.total_tokens, self.context_manager.available_tokens)
        
        # Check items are sorted by priority
        priorities = [item.priority for item in context_window.items]
        self.assertEqual(priorities, sorted(priorities, reverse=True))
    
    def test_context_deduplication(self):
        """Test context item deduplication"""
        # Create duplicate items
        item1 = self.context_manager.create_context_item(
            content="Same content",
            item_type='legacy_code',
            source='file1.py'
        )
        
        item2 = self.context_manager.create_context_item(
            content="Same content",
            item_type='legacy_code',
            source='file1.py'  # Same source, should be deduplicated
        )
        
        items = [item1, item2]
        context_window = self.context_manager.build_context_window(items)
        
        # Should only have one item after deduplication
        self.assertEqual(len(context_window.items), 1)
    
    def test_cache_functionality(self):
        """Test context caching"""
        items = [
            self.context_manager.create_context_item(
                content="Test content",
                item_type='user_requirement',
                source='test'
            )
        ]
        
        context_window, cached_response = self.context_manager.get_or_create_context(items)
        
        # First call should have no cached response
        self.assertIsNone(cached_response)
        
        # Cache a response
        test_response = "Cached LLM response"
        self.context_manager.cache_llm_response(context_window, test_response)
        
        # Second call should return cached response
        context_window2, cached_response2 = self.context_manager.get_or_create_context(items)
        self.assertEqual(cached_response2, test_response)


class TestToolSystem(unittest.TestCase):
    """Test tool system integration"""
    
    def setUp(self):
        self.tool_system = ToolSystem()
        self.session_id = "test_session"
    
    def test_tool_registration(self):
        """Test tool registration and discovery"""
        tools = self.tool_system.list_tools()
        
        # Should have the default tools
        expected_tools = ['search', 'file_ops', 'code_analysis']
        for tool in expected_tools:
            self.assertIn(tool, tools)
    
    def test_tool_descriptions(self):
        """Test getting tool descriptions"""
        descriptions = self.tool_system.get_tool_descriptions()
        
        for tool_name in self.tool_system.list_tools():
            self.assertIn(tool_name, descriptions)
            self.assertIn('description', descriptions[tool_name])
            self.assertIn('parameters', descriptions[tool_name])
    
    def test_code_analysis_tool(self):
        """Test code analysis tool"""
        test_code = """
def hello_world():
    print("Hello, World!")
    return True
"""
        
        result = self.tool_system.execute_tool(
            'code_analysis',
            self.session_id,
            operation='analyze_patterns',
            code=test_code,
            language='python'
        )
        
        self.assertTrue(result.success)
        self.assertIn('design_patterns', result.data)
        self.assertIn('code_smells', result.data)


class TestCodeValidator(unittest.TestCase):
    """Test code validation functionality"""
    
    def setUp(self):
        self.validator = CodeValidator(enable_docker_execution=True)
    
    def test_valid_python_code(self):
        """Test validation of valid Python code"""
        valid_code = """
def greet(name: str) -> str:
    \"\"\"Greet a person by name.\"\"\"
    if not name:
        raise ValueError("Name cannot be empty")
    return f"Hello, {name}!"
"""
        
        result = self.validator.validate(valid_code, "Create a greeting function")
        
        self.assertTrue(result.is_valid)
        self.assertGreater(result.confidence_score, 0.5)
        self.assertIsInstance(result.issues, list)
        self.assertIsInstance(result.suggestions, list)
    
    def test_invalid_python_code(self):
        """Test validation of invalid Python code"""
        invalid_code = """
def broken_function(
    print("This has syntax errors"
    return invalid syntax
"""
        
        result = self.validator.validate(invalid_code, "Create a function")
        
        self.assertFalse(result.is_valid)
        self.assertLess(result.confidence_score, 0.5)
        self.assertGreater(len(result.issues), 0)
    
    def test_requirements_matching(self):
        """Test requirements matching analysis"""
        code_with_api = """
import requests

def call_api(url: str) -> dict:
    response = requests.get(url)
    return response.json()
"""
        
        api_requirements = "Create a function that calls a REST API"
        result = self.validator.validate(code_with_api, api_requirements)
        
        # Should match API requirements well
        self.assertGreater(result.requirements_match, 0.5)
    
    def test_security_analysis(self):
        """Test security issue detection"""
        insecure_code = """
import os

def dangerous_function(user_input):
    return eval(user_input)  # Dangerous!
"""
        
        result = self.validator.validate(insecure_code, "Process user input")
        
        # Should detect security issues
        security_issues = [issue for issue in result.detailed_issues 
                         if issue.category == 'security']
        self.assertGreater(len(security_issues), 0)


class TestIterativeExecutor(unittest.TestCase):
    """Test iterative execution workflow"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.context_manager = ContextManager(cache_dir=os.path.join(self.temp_dir, 'cache'))
        self.tool_system = ToolSystem()
        
        # Mock LLM handler
        self.mock_llm = Mock()
        self.mock_llm.generate_initial_code.return_value = """
def validate_input(data):
    \"\"\"Validate input data.\"\"\"
    if not data:
        return False
    return True
"""
        
        self.executor = IterativeExecutor(
            context_manager=self.context_manager,
            tool_system=self.tool_system,
            llm_handler=self.mock_llm,
            max_iterations=2
        )
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_execution_workflow(self):
        """Test complete iterative execution workflow"""
        session_id = "test_execution"
        requirements = "Create a data validation function"
        
        result = self.executor.execute(session_id, requirements)
        
        self.assertIsNotNone(result.final_code)
        self.assertGreater(result.iterations, 0)
        self.assertLessEqual(result.iterations, self.executor.max_iterations)
        self.assertGreater(result.total_time_ms, 0)
        self.assertGreater(len(result.validation_results), 0)
    
    def test_keyword_extraction(self):
        """Test technical keyword extraction"""
        text = "Create a REST API with database authentication and JSON parsing"
        keywords = self.executor._extract_keywords(text)
        
        expected_keywords = ['api', 'database', 'authentication', 'json', 'parsing']
        for keyword in expected_keywords:
            self.assertIn(keyword, keywords)


class TestSystemIntegration(unittest.TestCase):
    """Test complete system integration"""
    
    def setUp(self):
        """Setup complete system"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Clear agent registry
        agent_registry._agents.clear()
        
        # Setup code generation agent
        config = {
            'max_tokens': 2000,
            'max_iterations': 2,
            'cache_dir': os.path.join(self.temp_dir, 'cache')
        }
        self.codegen_agent = CodeGenerationAgent(config)
        
        # Mock LLM
        self.codegen_agent.llm_handler = Mock()
        self.codegen_agent.llm_handler.generate_initial_code.return_value = "def test(): pass"
        
        agent_registry.register_agent(self.codegen_agent)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        agent_registry._agents.clear()
    
    def test_end_to_end_workflow(self):
        """Test complete end-to-end workflow"""
        session_id = "integration_test"
        
        # 1. Analyze requirements
        analysis_result = self.codegen_agent.execute({
            'operation': 'analyze_requirements',
            'requirements': 'Create a simple calculator function with error handling'
        }, session_id)
        
        self.assertEqual(analysis_result.status.value, 'success')
        
        # 2. Generate code
        generation_result = self.codegen_agent.execute({
            'operation': 'generate_code',
            'requirements': 'Create a calculator function that adds two numbers',
            'target_language': 'python',
            'session_id': session_id
        }, session_id)
        
        self.assertEqual(generation_result.status.value, 'success')
        
        # 3. Get status
        status_result = self.codegen_agent.execute({
            'operation': 'get_generation_status',
            'session_id': session_id
        }, session_id)
        
        self.assertEqual(status_result.status.value, 'success')
        
        # 4. Cleanup
        cleanup_result = self.codegen_agent.execute({
            'operation': 'cleanup_session',
            'session_id': session_id
        }, session_id)
        
        self.assertEqual(cleanup_result.status.value, 'success')


def run_performance_tests():
    """Run performance tests for context optimization"""
    print("🏃 Running Performance Tests...")
    
    # Test context caching performance
    context_manager = ContextManager()
    
    # Create many context items
    items = []
    for i in range(100):
        item = context_manager.create_context_item(
            content=f"Large content block {i} " * 50,
            item_type='search_result',
            source=f'file_{i}.py'
        )
        items.append(item)
    
    import time
    
    # Test context building performance
    start_time = time.time()
    context_window = context_manager.build_context_window(items)
    build_time = time.time() - start_time
    
    print(f"✅ Context building: {build_time:.3f}s for {len(items)} items")
    print(f"   Final context: {len(context_window.items)} items, {context_window.total_tokens} tokens")
    
    # Test cache hit performance
    start_time = time.time()
    _, cached = context_manager.get_or_create_context(items[:10])
    cache_time = time.time() - start_time
    
    print(f"✅ Cache lookup: {cache_time:.3f}s")
    
    # Cache a response and test retrieval
    context_manager.cache_llm_response(context_window, "test response")
    
    start_time = time.time()
    _, cached = context_manager.get_or_create_context(items)
    cache_hit_time = time.time() - start_time
    
    print(f"✅ Cache hit: {cache_hit_time:.3f}s (should be much faster)")


if __name__ == '__main__':
    print("🧪 Running Code Generation Agent Integration Tests")
    print("=" * 60)
    
    # Run unit tests
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    print("\n" + "=" * 60)
    
    # Run performance tests
    run_performance_tests()
    
    print("\n🎉 All tests completed!")
    print("\nKey Testing Areas Covered:")
    print("✅ Agent initialization and configuration")
    print("✅ Context management and optimization")
    print("✅ Tool system integration")
    print("✅ Code validation and quality analysis")
    print("✅ Iterative execution workflows")
    print("✅ End-to-end system integration")
    print("✅ Performance optimization validation") 