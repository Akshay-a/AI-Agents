"""
Code Generation Agent

Main agent that orchestrates intelligent code generation with context optimization,
tool-based workflows, and iterative self-correction capabilities.
"""

import os
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from ..base.agent_interface import BaseAgent, AgentInput, AgentOutput, AgentStatus
from .context_manager import ContextManager, ContextItem
from .tool_system import ToolSystem
from .iterative_executor import IterativeExecutor, ExecutionResult
from .code_validator import CodeValidator


class CodeGenerationAgent(BaseAgent):
    """
    Intelligent Code Generation Agent with advanced capabilities:
    
    1. Context Optimization: Smart context management with caching to reduce API costs
    2. Tool Integration: Access to codebase search, file operations, and analysis tools
    3. Iterative Workflows: Self-correcting code generation with validation loops
    4. Legacy Code Understanding: Analyzes existing codebase for informed generation
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(agent_id="code_generation_agent", config=config)
        
        # Initialize core components
        self.context_manager = ContextManager(
            max_tokens=config.get('max_tokens', 32000) if config else 32000,
            cache_dir=config.get('cache_dir', '/tmp/code_generation_cache') if config else '/tmp/code_generation_cache'
        )
        
        self.tool_system = ToolSystem()
        # Configure Docker execution based on agent config
        enable_docker = self.config.get('enable_docker_execution', True)
        docker_timeout = self.config.get('docker_timeout', None)
        self.code_validator = CodeValidator(
            enable_docker_execution=enable_docker,
            docker_timeout=docker_timeout
        )
        
        # Initialize LLM handler
        self.llm_handler = self._initialize_llm_handler()
        
        # Initialize iterative executor
        self.iterative_executor = IterativeExecutor(
            context_manager=self.context_manager,
            tool_system=self.tool_system,
            llm_handler=self.llm_handler,
            max_iterations=config.get('max_iterations', 5) if config else 5,
            enable_docker_execution=enable_docker,
            docker_timeout=docker_timeout
        )
        
        # Supported operations
        self.supported_operations = [
            'generate_code',
            'enhance_code',
            'migrate_code',
            'fix_bugs',
            'analyze_requirements',
            'get_generation_status',
            'cleanup_session'
        ]
        
        self.logger.info("Initialized Code Generation Agent with advanced capabilities")
    
    def validate_input(self, agent_input: AgentInput) -> bool:
        """Validate input for code generation operations"""
        data = agent_input.data
        operation = data.get('operation')
        
        if operation not in self.supported_operations:
            self.logger.error(f"Unsupported operation: {operation}")
            return False
        
        # Operation-specific validation
        if operation in ['generate_code', 'enhance_code', 'migrate_code', 'fix_bugs']:
            if 'requirements' not in data:
                self.logger.error(f"Missing requirements for {operation}")
                return False
            
            if 'session_id' not in data:
                self.logger.error(f"Missing session_id for {operation}")
                return False
        
        elif operation == 'analyze_requirements':
            if 'requirements' not in data:
                self.logger.error("Missing requirements for analysis")
                return False
        
        return True
    
    def process(self, agent_input: AgentInput) -> AgentOutput:
        """Process code generation requests"""
        start_time = agent_input.timestamp
        operation = agent_input.data.get('operation')
        session_id = agent_input.session_id
        
        self.logger.info(f"Processing {operation} for session {session_id}")
        
        try:
            # Route to appropriate handler
            if operation == 'generate_code':
                result = self._generate_code(agent_input.data, session_id)
            elif operation == 'enhance_code':
                result = self._enhance_code(agent_input.data, session_id)
            elif operation == 'migrate_code':
                result = self._migrate_code(agent_input.data, session_id)
            elif operation == 'fix_bugs':
                result = self._fix_bugs(agent_input.data, session_id)
            elif operation == 'analyze_requirements':
                result = self._analyze_requirements(agent_input.data, session_id)
            elif operation == 'get_generation_status':
                result = self._get_generation_status(session_id)
            elif operation == 'cleanup_session':
                result = self._cleanup_session(session_id)
            else:
                raise ValueError(f"Unknown operation: {operation}")
            
            return self._create_success_output(session_id, start_time, result)
            
        except Exception as e:
            self.logger.error(f"Error processing {operation}: {str(e)}")
            return self._create_error_output(session_id, start_time, str(e))
    
    def _generate_code(self, data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Generate new code based on requirements and legacy codebase"""
        requirements = data['requirements']
        target_language = data.get('target_language', 'python')
        context_hints = data.get('context_hints', [])  # Additional context from user
        
        self.logger.info(f"Generating {target_language} code for requirements: {requirements[:100]}...")
        
        # Prepare initial context
        initial_context = []
        
        # Add context hints if provided
        for hint in context_hints:
            context_item = self.context_manager.create_context_item(
                content=hint,
                item_type='user_requirement',
                source='context_hint',
                priority=8
            )
            initial_context.append(context_item)
        
        # Add target language specification
        if target_language != 'python':
            lang_item = self.context_manager.create_context_item(
                content=f"Generate code in {target_language}. Follow {target_language} best practices and conventions.",
                item_type='user_requirement',
                source='language_spec',
                priority=9
            )
            initial_context.append(lang_item)
        
        # Execute iterative generation
        execution_result = self.iterative_executor.execute(
            session_id=session_id,
            user_requirements=requirements,
            initial_context=initial_context
        )
        
        # Save generated code to output directory
        output_info = None
        if execution_result.success and execution_result.final_code:
            output_info = self._save_generated_code(
                session_id,
                execution_result.final_code,
                f"generated_{target_language}_code",
                target_language
            )
        
        return {
            'operation': 'generate_code',
            'success': execution_result.success,
            'generated_code': execution_result.final_code,
            'target_language': target_language,
            'execution_summary': {
                'iterations': execution_result.iterations,
                'execution_time_ms': execution_result.total_time_ms,
                'final_state': execution_result.execution_state.value,
                'context_items_used': len(execution_result.context_items),
                'tool_calls_made': len(execution_result.tool_calls)
            },
            'validation_results': [
                {
                    'is_valid': vr.is_valid,
                    'confidence_score': vr.confidence_score,
                    'issues': vr.issues,
                    'suggestions': vr.suggestions
                } for vr in execution_result.validation_results
            ],
            'output_info': output_info,
            'requirements': requirements,
            'session_id': session_id
        }
    
    def _enhance_code(self, data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Enhance existing code with improvements and modern practices"""
        requirements = data['requirements']
        existing_code = data.get('existing_code', '')
        file_path = data.get('file_path', '')
        
        self.logger.info(f"Enhancing code: {file_path or 'inline code'}")
        
        # If file path provided, read the existing code
        if file_path and not existing_code:
            file_result = self.tool_system.execute_tool(
                'file_ops',
                session_id,
                operation='read',
                file_path=file_path
            )
            
            if file_result.success:
                existing_code = file_result.data['content']
            else:
                raise ValueError(f"Could not read file: {file_path}")
        
        if not existing_code:
            raise ValueError("No existing code provided for enhancement")
        
        # Prepare enhancement context
        initial_context = []
        
        # Add existing code as legacy context
        legacy_item = self.context_manager.create_context_item(
            content=existing_code,
            item_type='legacy_code',
            source=file_path or 'provided_code',
            priority=9
        )
        initial_context.append(legacy_item)
        
        # Analyze existing code
        analysis_result = self.tool_system.execute_tool(
            'code_analysis',
            session_id,
            operation='analyze_patterns',
            code=existing_code
        )
        
        if analysis_result.success:
            analysis_item = self.context_manager.create_context_item(
                content=f"Code analysis: {analysis_result.data}",
                item_type='other',
                source='code_analysis',
                priority=7
            )
            initial_context.append(analysis_item)
        
        # Try specialized enhancement method first
        try:
            self.logger.info("Using specialized LLM enhancement method")
            enhanced_code = self.llm_handler.enhance_code(
                existing_code=existing_code,
                enhancement_requirements=requirements,
                language="python"
            )
            
            # Create a simple execution result for successful enhancement
            from .iterative_executor import ExecutionResult, ExecutionState
            execution_result = ExecutionResult(
                success=True,
                final_code=enhanced_code,
                iterations=1,
                total_time_ms=0,
                execution_state=ExecutionState.COMPLETED,
                validation_results=[],
                iteration_steps=[]
            )
            
        except Exception as e:
            self.logger.warning(f"Specialized enhancement failed: {e}, falling back to iterative method")
            
            # Fallback to iterative method
            enhancement_requirements = f"""
            Enhance the following code based on these requirements: {requirements}
            
            Focus on:
            1. Improving code quality and readability
            2. Adding error handling and validation
            3. Implementing modern best practices
            4. Optimizing performance where possible
            5. Adding comprehensive documentation
            
            Original code requirements: {requirements}
            """
            
            # Execute enhancement using iterative executor
            execution_result = self.iterative_executor.execute(
                session_id=session_id,
                user_requirements=enhancement_requirements,
                initial_context=initial_context
            )
        
        # Save enhanced code
        output_info = None
        if execution_result.success and execution_result.final_code:
            output_info = self._save_generated_code(
                session_id,
                execution_result.final_code,
                f"enhanced_{os.path.basename(file_path) if file_path else 'code'}",
                'python'
            )
        
        return {
            'operation': 'enhance_code',
            'success': execution_result.success,
            'enhanced_code': execution_result.final_code,
            'original_code': existing_code,
            'file_path': file_path,
            'execution_summary': {
                'iterations': execution_result.iterations,
                'execution_time_ms': execution_result.total_time_ms,
                'final_state': execution_result.execution_state.value
            },
            'validation_results': [
                {
                    'is_valid': vr.is_valid,
                    'confidence_score': vr.confidence_score,
                    'issues': vr.issues,
                    'suggestions': vr.suggestions
                } for vr in execution_result.validation_results
            ],
            'output_info': output_info,
            'requirements': requirements,
            'session_id': session_id
        }
    
    def _migrate_code(self, data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Migrate code from one technology/language to another"""
        requirements = data['requirements']
        source_language = data.get('source_language', 'unknown')
        target_language = data.get('target_language', 'python')
        source_files = data.get('source_files', [])
        
        self.logger.info(f"Migrating from {source_language} to {target_language}")
        
        # Prepare migration context
        initial_context = []
        
                # Read and analyze source files
        source_code_content = ""
        for file_path in source_files[:5]:  # Limit to 5 files to avoid context overflow
            file_result = self.tool_system.execute_tool(
                'file_ops',
                session_id,
                operation='read',
                file_path=file_path
            )
            
            if file_result.success:
                file_content = file_result.data['content']
                source_code_content += f"\n\n// File: {file_path}\n{file_content}"
                
                source_item = self.context_manager.create_context_item(
                    content=file_content,
                    item_type='legacy_code',
                    source=f"source_file:{file_path}",
                    priority=8
                )
                initial_context.append(source_item)

        # Use specialized migration method if source code is available
        if source_code_content.strip():
            self.logger.info("Using specialized LLM migration method")
            try:
                migrated_code = self.llm_handler.migrate_code(
                    source_code=source_code_content,
                    source_language=source_language,
                    target_language=target_language,
                    requirements=requirements
                )
                
                # Create a simple execution result for successful migration
                from .iterative_executor import ExecutionResult, ExecutionState
                execution_result = ExecutionResult(
                    success=True,
                    final_code=migrated_code,
                    iterations=1,
                    total_time_ms=0,
                    execution_state=ExecutionState.COMPLETED,
                    validation_results=[],
                    iteration_steps=[]
                )
                
            except Exception as e:
                self.logger.warning(f"Specialized migration failed: {e}, falling back to iterative method")
                # Fall back to iterative method
                execution_result = self._fallback_iterative_migration(
                    session_id, requirements, source_language, target_language, initial_context
                )
        else:
            # Fall back to iterative method when no source code is available
            self.logger.info("No source code found, using iterative migration method")
            execution_result = self._fallback_iterative_migration(
                session_id, requirements, source_language, target_language, initial_context
            )
        
        # Save migrated code
        output_info = None
        if execution_result.success and execution_result.final_code:
            output_info = self._save_generated_code(
                session_id,
                execution_result.final_code,
                f"migrated_to_{target_language}",
                target_language
            )
        
        return {
            'operation': 'migrate_code',
            'success': execution_result.success,
            'migrated_code': execution_result.final_code,
            'source_language': source_language,
            'target_language': target_language,
            'source_files': source_files,
            'execution_summary': {
                'iterations': execution_result.iterations,
                'execution_time_ms': execution_result.total_time_ms,
                'final_state': execution_result.execution_state.value
            },
            'validation_results': [
                {
                    'is_valid': vr.is_valid,
                    'confidence_score': vr.confidence_score,
                    'issues': vr.issues,
                    'suggestions': vr.suggestions
                } for vr in execution_result.validation_results
            ],
            'output_info': output_info,
            'requirements': requirements,
            'session_id': session_id
        }
    
    def _fallback_iterative_migration(self, session_id: str, requirements: str, source_language: str, 
                                    target_language: str, initial_context: list):
        """Fallback to iterative migration method when specialized migration fails."""
        # Add migration-specific instructions
        migration_requirements = f"""
        Migrate the following {source_language} code to {target_language} according to these requirements: {requirements}
        
        Migration guidelines:
        1. Preserve all functionality and business logic
        2. Follow {target_language} best practices and conventions
        3. Use appropriate {target_language} libraries and frameworks
        4. Maintain code structure and organization
        5. Add proper error handling and documentation
        6. Ensure the migrated code is idiomatic {target_language}
        
        Original migration requirements: {requirements}
        """
        
        # Add target language context
        lang_item = self.context_manager.create_context_item(
            content=f"Target language: {target_language}. Use {target_language} idioms and best practices.",
            item_type='user_requirement',
            source='migration_spec',
            priority=9
        )
        initial_context.append(lang_item)
        
        # Execute migration using iterative executor
        return self.iterative_executor.execute(
            session_id=session_id,
            user_requirements=migration_requirements,
            initial_context=initial_context
        )
    
    def _fix_bugs(self, data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Fix bugs in existing code"""
        requirements = data['requirements']
        buggy_code = data.get('buggy_code', '')
        file_path = data.get('file_path', '')
        error_logs = data.get('error_logs', '')
        
        self.logger.info(f"Fixing bugs in: {file_path or 'inline code'}")
        
        # Read buggy code if file path provided
        if file_path and not buggy_code:
            file_result = self.tool_system.execute_tool(
                'file_ops',
                session_id,
                operation='read',
                file_path=file_path
            )
            
            if file_result.success:
                buggy_code = file_result.data['content']
            else:
                raise ValueError(f"Could not read file: {file_path}")
        
        if not buggy_code:
            raise ValueError("No buggy code provided for fixing")
        
        # Prepare bug fix context
        initial_context = []
        
        # Add buggy code
        buggy_item = self.context_manager.create_context_item(
            content=buggy_code,
            item_type='legacy_code',
            source=file_path or 'buggy_code',
            priority=9
        )
        initial_context.append(buggy_item)
        
        # Add error logs if provided
        if error_logs:
            error_item = self.context_manager.create_context_item(
                content=f"Error logs:\n{error_logs}",
                item_type='validation_result',
                source='error_logs',
                priority=10
            )
            initial_context.append(error_item)
        
        # Analyze code for issues
        issues_result = self.tool_system.execute_tool(
            'code_analysis',
            session_id,
            operation='detect_issues',
            code=buggy_code
        )
        
        if issues_result.success:
            issues_item = self.context_manager.create_context_item(
                content=f"Detected issues: {issues_result.data}",
                item_type='validation_result',
                source='issue_analysis',
                priority=9
            )
            initial_context.append(issues_item)
        
        # Try specialized bug fixing method first
        try:
            self.logger.info("Using specialized LLM bug fixing method")
            fixed_code = self.llm_handler.fix_bugs(
                faulty_code=buggy_code,
                error_message=error_logs,
                requirements=requirements
            )
            
            # Create a simple execution result for successful bug fixing
            from .iterative_executor import ExecutionResult, ExecutionState
            execution_result = ExecutionResult(
                success=True,
                final_code=fixed_code,
                iterations=1,
                total_time_ms=0,
                execution_state=ExecutionState.COMPLETED,
                validation_results=[],
                iteration_steps=[]
            )
            
        except Exception as e:
            self.logger.warning(f"Specialized bug fixing failed: {e}, falling back to iterative method")
            
            # Fallback to iterative method
            bug_fix_requirements = f"""
            Fix the bugs in the provided code based on these requirements: {requirements}
            
            Bug fixing guidelines:
            1. Identify and fix all syntax errors
            2. Resolve logic errors and edge cases
            3. Fix runtime errors and exceptions
            4. Improve error handling
            5. Ensure code meets the specified requirements
            6. Maintain existing functionality while fixing issues
            
            {f"Error logs to address: {error_logs}" if error_logs else ""}
            
            Original requirements: {requirements}
            """
            
            # Execute bug fixing using iterative executor
            execution_result = self.iterative_executor.execute(
                session_id=session_id,
                user_requirements=bug_fix_requirements,
                initial_context=initial_context
            )
        
        # Save fixed code
        output_info = None
        if execution_result.success and execution_result.final_code:
            output_info = self._save_generated_code(
                session_id,
                execution_result.final_code,
                f"fixed_{os.path.basename(file_path) if file_path else 'code'}",
                'python'
            )
        
        return {
            'operation': 'fix_bugs',
            'success': execution_result.success,
            'fixed_code': execution_result.final_code,
            'original_buggy_code': buggy_code,
            'file_path': file_path,
            'error_logs': error_logs,
            'execution_summary': {
                'iterations': execution_result.iterations,
                'execution_time_ms': execution_result.total_time_ms,
                'final_state': execution_result.execution_state.value
            },
            'validation_results': [
                {
                    'is_valid': vr.is_valid,
                    'confidence_score': vr.confidence_score,
                    'issues': vr.issues,
                    'suggestions': vr.suggestions
                } for vr in execution_result.validation_results
            ],
            'output_info': output_info,
            'requirements': requirements,
            'session_id': session_id
        }
    
    def _analyze_requirements(self, data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Analyze requirements and suggest implementation approach"""
        requirements = data['requirements']
        
        self.logger.info("Analyzing requirements and suggesting approach")
        
        # Search for similar patterns in the codebase
        search_result = self.tool_system.execute_tool(
            'search',
            session_id,
            query=requirements,
            search_type='find_patterns',
            max_results=5
        )
        
        similar_patterns = []
        if search_result.success:
            similar_patterns = search_result.data.get('results', [])
        
        # Extract technical keywords
        keywords = self._extract_technical_keywords(requirements)
        
        # Analyze complexity
        complexity_score = self._estimate_requirements_complexity(requirements)
        
        # Suggest implementation approach
        approach = self._suggest_implementation_approach(requirements, similar_patterns, complexity_score)
        
        return {
            'operation': 'analyze_requirements',
            'requirements': requirements,
            'analysis': {
                'technical_keywords': keywords,
                'complexity_score': complexity_score,
                'estimated_effort': self._estimate_effort(complexity_score),
                'similar_patterns_found': len(similar_patterns),
                'similar_patterns': similar_patterns[:3],  # Top 3
                'suggested_approach': approach,
                'recommended_tools': self._recommend_tools(keywords),
                'potential_challenges': self._identify_challenges(requirements)
            },
            'session_id': session_id
        }
    
    def _get_generation_status(self, session_id: str) -> Dict[str, Any]:
        """Get current generation status for a session"""
        # Get execution status from iterative executor
        execution_status = self.iterative_executor.get_execution_status()
        
        # Get context manager stats
        context_stats = self.context_manager.get_context_stats()
        
        # Get tool system info
        available_tools = self.tool_system.get_tool_descriptions()
        
        return {
            'operation': 'get_generation_status',
            'session_id': session_id,
            'execution_status': execution_status,
            'context_manager_stats': context_stats,
            'available_tools': list(available_tools.keys()),
            'agent_capabilities': {
                'supported_operations': self.supported_operations,
                'max_iterations': self.iterative_executor.max_iterations,
                'context_optimization': True,
                'tool_integration': True,
                'iterative_correction': True
            }
        }
    
    def _cleanup_session(self, session_id: str) -> Dict[str, Any]:
        """Clean up session resources"""
        self.logger.info(f"Cleaning up session: {session_id}")
        
        # Cleanup context cache
        self.context_manager.cleanup_cache()
        
        # Cleanup any session-specific tool resources
        # (This would call cleanup on individual tools if they support it)
        
        return {
            'operation': 'cleanup_session',
            'session_id': session_id,
            'cleaned': True,
            'message': 'Session resources cleaned successfully'
        }
    
    def _save_generated_code(self, session_id: str, code: str, filename: str, language: str) -> Dict[str, Any]:
        """Save generated code to output directory"""
        # Determine file extension
        ext_map = {
            'python': '.py',
            'javascript': '.js',
            'typescript': '.ts',
            'java': '.java',
            'cpp': '.cpp',
            'c': '.c',
            'csharp': '.cs',
            'go': '.go',
            'rust': '.rs'
        }
        
        extension = ext_map.get(language.lower(), '.txt')
        full_filename = f"{filename}{extension}"
        
        # Save using file operations tool
        save_result = self.tool_system.execute_tool(
            'file_ops',
            session_id,
            operation='write',
            file_path=full_filename,
            content=code,
            target_dir=f"/tmp/code_generation_output/{session_id}"
        )
        
        if save_result.success:
            return save_result.data
        else:
            self.logger.warning(f"Failed to save generated code: {save_result.error_message}")
            return {'error': save_result.error_message}
    
    def _initialize_llm_handler(self):
        """Initialize LLM handler using the unified LLM service"""
        try:
            from .llm_service import get_llm_service
            llm_service = get_llm_service()
            self.logger.info(f"LLM service initialized, available: {llm_service.llm_available}")
            return llm_service
        except ImportError as e:
            self.logger.warning(f"Failed to import LLM service: {e}, using mock handler")
            return self._create_mock_llm_handler()
    
    def _create_mock_llm_handler(self):
        """Create a mock LLM handler for testing"""
        class MockLLMHandler:
            def generate_initial_code(self, prompt: str) -> str:
                return f"# Generated code based on prompt\n# Prompt: {prompt[:100]}...\nprint('Hello, World!')"
            
            def migrate_code(self, source_code: str, source_language: str, target_language: str, requirements: str) -> str:
                return f"# Mock migration: {source_language} -> {target_language}\nprint('Mock migration result')"
            
            def enhance_code(self, existing_code: str, enhancement_requirements: str, language: str = "python") -> str:
                return f"# Mock enhancement\n{existing_code}\nprint('Mock enhancement added')"
            
            def fix_bugs(self, faulty_code: str, error_message: str, requirements: str) -> str:
                return f"# Mock bug fix\n{faulty_code}\nprint('Mock bug fix applied')"
        
        return MockLLMHandler()
    
    def _extract_technical_keywords(self, text: str) -> List[str]:
        """Extract technical keywords from requirements"""
        import re
        words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', text.lower())
        
        technical_indicators = [
            'api', 'database', 'function', 'class', 'method', 'algorithm',
            'data', 'process', 'handle', 'manage', 'convert', 'parse',
            'authenticate', 'validate', 'encrypt', 'decode', 'serialize',
            'framework', 'library', 'module', 'service', 'client', 'server',
            'web', 'http', 'rest', 'json', 'xml', 'csv', 'file', 'directory'
        ]
        
        return [word for word in words if word in technical_indicators]
    
    def _estimate_requirements_complexity(self, requirements: str) -> float:
        """Estimate complexity of requirements (0-10 scale)"""
        word_count = len(requirements.split())
        technical_words = len(self._extract_technical_keywords(requirements))
        
        # Simple complexity estimation
        complexity = (word_count / 20) + (technical_words * 0.5)
        return min(10.0, complexity)
    
    def _estimate_effort(self, complexity_score: float) -> str:
        """Estimate development effort based on complexity"""
        if complexity_score < 2:
            return "Low (1-2 hours)"
        elif complexity_score < 5:
            return "Medium (2-8 hours)"
        elif complexity_score < 8:
            return "High (1-3 days)"
        else:
            return "Very High (3+ days)"
    
    def _suggest_implementation_approach(self, requirements: str, similar_patterns: List[Dict], complexity_score: float) -> List[str]:
        """Suggest implementation approach"""
        approaches = []
        
        if similar_patterns:
            approaches.append("Adapt existing patterns found in the codebase")
        
        if complexity_score < 3:
            approaches.append("Simple script-based implementation")
        elif complexity_score < 6:
            approaches.append("Modular function-based approach")
        else:
            approaches.append("Object-oriented design with multiple classes")
        
        if 'api' in requirements.lower():
            approaches.append("RESTful API design with proper error handling")
        
        if 'database' in requirements.lower():
            approaches.append("Database abstraction layer with ORM")
        
        approaches.append("Test-driven development with comprehensive unit tests")
        
        return approaches
    
    def _recommend_tools(self, keywords: List[str]) -> List[str]:
        """Recommend tools and libraries based on keywords"""
        recommendations = []
        
        keyword_set = set(keywords)
        
        if keyword_set & {'api', 'web', 'http', 'rest'}:
            recommendations.extend(['FastAPI', 'Flask', 'requests'])
        
        if keyword_set & {'database', 'data'}:
            recommendations.extend(['SQLAlchemy', 'pandas', 'sqlite3'])
        
        if keyword_set & {'json', 'xml', 'csv', 'parse'}:
            recommendations.extend(['json', 'xml.etree', 'csv', 'lxml'])
        
        if keyword_set & {'authenticate', 'validate'}:
            recommendations.extend(['JWT', 'bcrypt', 'pydantic'])
        
        # Always recommend testing and logging
        recommendations.extend(['pytest', 'logging'])
        
        return list(set(recommendations))  # Remove duplicates
    
    def _identify_challenges(self, requirements: str) -> List[str]:
        """Identify potential implementation challenges"""
        challenges = []
        
        req_lower = requirements.lower()
        
        if 'realtime' in req_lower or 'real-time' in req_lower:
            challenges.append("Real-time processing requirements may need careful performance optimization")
        
        if 'scale' in req_lower or 'scalable' in req_lower:
            challenges.append("Scalability requirements need architecture planning")
        
        if 'security' in req_lower or 'secure' in req_lower:
            challenges.append("Security requirements need thorough threat analysis")
        
        if 'integrate' in req_lower or 'integration' in req_lower:
            challenges.append("Integration complexity with existing systems")
        
        if 'migrate' in req_lower or 'migration' in req_lower:
            challenges.append("Data migration and backward compatibility concerns")
        
        if len(requirements.split()) > 100:
            challenges.append("Complex requirements may need iterative development")
        
        return challenges 