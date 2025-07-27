"""
Iterative Executor for Code Generation Agent

Handles the iterative loop of code generation where the agent can:
1. Call tools to gather information
2. Generate code based on context
3. Validate generated code
4. Self-correct and iterate
"""

import time
import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import logging

from .context_manager import ContextManager, ContextItem
from .tool_system import ToolSystem, ToolResult
from .code_validator import CodeValidator, ValidationResult


class ExecutionState(Enum):
    """States of the iterative execution process"""
    INITIALIZING = "initializing"
    GATHERING_CONTEXT = "gathering_context"  
    GENERATING_CODE = "generating_code"
    VALIDATING_CODE = "validating_code"
    CORRECTING_CODE = "correcting_code"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ExecutionResult:
    """Result of an iterative execution cycle"""
    success: bool
    final_code: str
    execution_state: ExecutionState
    iterations: int
    total_time_ms: int
    context_items: List[ContextItem]
    tool_calls: List[Dict[str, Any]]
    validation_results: List[ValidationResult]
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class IterationStep:
    """Single step in the iteration process"""
    step_type: str  # 'tool_call', 'code_generation', 'validation', 'correction'
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    success: bool
    timestamp: datetime
    execution_time_ms: int
    error_message: Optional[str] = None


class IterativeExecutor:
    """Orchestrates the iterative code generation process"""
    
    def __init__(self, context_manager: ContextManager, tool_system: ToolSystem, 
                 llm_handler, max_iterations: int = 5, enable_docker_execution: bool = True,
                 docker_timeout: int = None):
        self.context_manager = context_manager
        self.tool_system = tool_system
        self.llm_handler = llm_handler
        self.max_iterations = max_iterations
        
        # Configure Docker execution for validation
        self.code_validator = CodeValidator(
            enable_docker_execution=enable_docker_execution,
            docker_timeout=docker_timeout
        )
        self.logger = logging.getLogger(__name__)
        
        # Execution state
        self.current_iteration = 0
        self.execution_state = ExecutionState.INITIALIZING
        self.context_items: List[ContextItem] = []
        self.tool_calls: List[Dict[str, Any]] = []
        self.iteration_steps: List[IterationStep] = []
    
    def execute(self, session_id: str, user_requirements: str, 
                initial_context: Optional[List[ContextItem]] = None) -> ExecutionResult:
        """Execute the iterative code generation process"""
        start_time = time.time()
        
        try:
            self.logger.info(f"Starting iterative execution for session: {session_id}")
            
            # Initialize execution
            self.current_iteration = 0
            self.execution_state = ExecutionState.INITIALIZING
            self.context_items = initial_context or []
            self.tool_calls = []
            self.iteration_steps = []
            
            # Add user requirements to context
            user_req_item = self.context_manager.create_context_item(
                content=user_requirements,
                item_type='user_requirement',
                source='user_input'
            )
            self.context_items.append(user_req_item)
            
            # Main iteration loop
            final_code = ""
            validation_results = []
            
            for iteration in range(self.max_iterations):
                self.current_iteration = iteration
                self.logger.info(f"Starting iteration {iteration + 1}/{self.max_iterations}")
                
                try:
                    # Step 1: Gather context and analyze requirements
                    if iteration == 0:
                        self.execution_state = ExecutionState.GATHERING_CONTEXT
                        self._gather_initial_context(session_id, user_requirements)
                    
                    # Step 2: Generate code
                    self.execution_state = ExecutionState.GENERATING_CODE
                    generated_code = self._generate_code(session_id, iteration)
                    
                    if not generated_code:
                        self.logger.error(f"Code generation failed at iteration {iteration + 1}")
                        continue
                    
                    # Step 3: Validate generated code
                    self.execution_state = ExecutionState.VALIDATING_CODE
                    validation_result = self._validate_code(generated_code, user_requirements)
                    validation_results.append(validation_result)
                    
                    # Step 4: Check if code is acceptable
                    if validation_result.is_valid and validation_result.confidence_score > 0.8:
                        self.logger.info(f"Code generation successful at iteration {iteration + 1}")
                        final_code = generated_code
                        self.execution_state = ExecutionState.COMPLETED
                        break
                    
                    # Step 5: Add validation feedback to context for next iteration
                    if iteration < self.max_iterations - 1:
                        self.execution_state = ExecutionState.CORRECTING_CODE
                        self._add_correction_context(generated_code, validation_result)
                    else:
                        # Last iteration - use code even if not perfect
                        final_code = generated_code
                        self.execution_state = ExecutionState.COMPLETED
                
                except Exception as e:
                    self.logger.error(f"Error in iteration {iteration + 1}: {e}")
                    if iteration == self.max_iterations - 1:
                        self.execution_state = ExecutionState.FAILED
                        break
                    continue
            
            total_time = int((time.time() - start_time) * 1000)
            
            return ExecutionResult(
                success=bool(final_code and self.execution_state == ExecutionState.COMPLETED),
                final_code=final_code,
                execution_state=self.execution_state,
                iterations=self.current_iteration + 1,
                total_time_ms=total_time,
                context_items=self.context_items,
                tool_calls=self.tool_calls,
                validation_results=validation_results,
                metadata={
                    'session_id': session_id,
                    'max_iterations': self.max_iterations,
                    'iteration_steps': [step.__dict__ for step in self.iteration_steps]
                }
            )
        
        except Exception as e:
            self.logger.error(f"Fatal error in iterative execution: {e}")
            total_time = int((time.time() - start_time) * 1000)
            
            return ExecutionResult(
                success=False,
                final_code="",
                execution_state=ExecutionState.FAILED,
                iterations=self.current_iteration,
                total_time_ms=total_time,
                context_items=self.context_items,
                tool_calls=self.tool_calls,
                validation_results=[],
                error_message=str(e)
            )
    
    def _gather_initial_context(self, session_id: str, user_requirements: str) -> None:
        """Gather initial context by searching and analyzing the codebase"""
        self.logger.info("Gathering initial context from codebase")
        
        # Step 1: Search for relevant code based on requirements
        search_result = self._call_tool(
            'search',
            session_id,
            query=user_requirements,
            search_type='search_code',
            max_results=5
        )
        
        if search_result.success and search_result.data.get('results'):
            for result in search_result.data['results'][:3]:  # Limit to top 3
                context_item = self.context_manager.create_context_item(
                    content=result.get('relevance_snippet', result.get('content', '')),
                    item_type='search_result',
                    source=f"search:{result.get('file_path', 'unknown')}"
                )
                self.context_items.append(context_item)
        
        # Step 2: Look for specific patterns or functions mentioned in requirements
        pattern_keywords = self._extract_keywords(user_requirements)
        for keyword in pattern_keywords[:3]:  # Limit to 3 keywords
            pattern_result = self._call_tool(
                'search',
                session_id,
                query=keyword,
                search_type='find_patterns',
                max_results=2
            )
            
            if pattern_result.success and pattern_result.data.get('results'):
                for result in pattern_result.data['results'][:2]:
                    context_item = self.context_manager.create_context_item(
                        content=result.get('relevance_snippet', result.get('content', '')),
                        item_type='search_result',
                        source=f"pattern:{keyword}"
                    )
                    self.context_items.append(context_item)
        
        # Step 3: Get session info to understand repository structure
        session_info_result = self._call_tool(
            'file_ops',
            session_id,
            operation='get_session_info'
        )
        
        if session_info_result.success:
            session_info = session_info_result.data
            context_item = self.context_manager.create_context_item(
                content=f"Repository structure: {json.dumps(session_info, indent=2)}",
                item_type='other',
                source='session_info',
                priority=6
            )
            self.context_items.append(context_item)
    
    def _generate_code(self, session_id: str, iteration: int) -> str:
        """Generate code using the LLM with current context"""
        self.logger.info(f"Generating code for iteration {iteration + 1}")
        
        # Build context window
        context_window, cached_response = self.context_manager.get_or_create_context(self.context_items)
        
        # Check for cached response
        if cached_response:
            self.logger.info("Using cached LLM response")
            return self._extract_code_from_response(cached_response)
        
        # Create prompt
        prompt = self._build_generation_prompt(context_window, iteration)
        
        # Call LLM
        try:
            response = self._call_llm(prompt, context_window)
            
            if response:
                # Cache the response
                self.context_manager.cache_llm_response(context_window, response)
                
                # Extract code from response
                generated_code = self._extract_code_from_response(response)
                
                # Add generated code to context for future iterations
                if generated_code:
                    code_item = self.context_manager.create_context_item(
                        content=generated_code,
                        item_type='generated_code',
                        source=f'iteration_{iteration + 1}',
                        priority=7
                    )
                    self.context_items.append(code_item)
                
                return generated_code
            
        except Exception as e:
            self.logger.error(f"LLM call failed: {e}")
            
        return ""
    
    def _validate_code(self, code: str, requirements: str) -> ValidationResult:
        """Validate the generated code"""
        self.logger.info("Validating generated code")
        
        return self.code_validator.validate(code, requirements)
    
    def _add_correction_context(self, failed_code: str, validation_result: ValidationResult) -> None:
        """Add correction context for the next iteration"""
        self.logger.info("Adding correction context for next iteration")
        
        # Add validation feedback
        feedback_content = f"Issues: {'; '.join(validation_result.issues)}"
        if validation_result.suggestions:
            feedback_content += f"\nSuggestions: {'; '.join(validation_result.suggestions)}"
        
        # Add detailed execution feedback if available
        if validation_result.execution_feedback:
            feedback_content += f"\n\nExecution Results: {validation_result.execution_feedback}"
            
        # Add failed code for reference
        feedback_content += f"\n\nFailed Code:\n```python\n{failed_code}\n```"
        
        feedback_item = self.context_manager.create_context_item(
            content=feedback_content,
            item_type='validation_result',
            source=f'validation_iteration_{self.current_iteration + 1}',
            priority=9
        )
        self.context_items.append(feedback_item)
        
        # If there was an execution failure, add specific correction guidance
        if validation_result.execution_test is False and validation_result.execution_feedback:
            execution_guidance = (
                "🔧 EXECUTION FAILURE DETECTED: The code failed to run properly in the execution environment. "
                "Focus on fixing runtime errors, missing imports, incorrect logic, or dependency issues. "
                "Ensure the code can execute successfully without errors."
            )
            
            guidance_item = self.context_manager.create_context_item(
                content=execution_guidance,
                item_type='correction_guidance',
                source=f'execution_failure_iteration_{self.current_iteration + 1}',
                priority=9
            )
            self.context_items.append(guidance_item)
        
        # If there are specific error patterns, search for examples
        if validation_result.issues:
            for issue in validation_result.issues[:2]:  # Limit to 2 issues
                if 'syntax' in issue.lower() or 'error' in issue.lower():
                    # Search for similar issues and solutions
                    fix_result = self._call_tool(
                        'search',
                        'current_session',  # Use current session
                        query=f"fix {issue}",
                        search_type='search_code',
                        max_results=2
                    )
                    
                    if fix_result.success and fix_result.data.get('results'):
                        for result in fix_result.data['results']:
                            fix_item = self.context_manager.create_context_item(
                                content=result.get('relevance_snippet', ''),
                                item_type='search_result',
                                source=f"fix_example:{issue}",
                                priority=8
                            )
                            self.context_items.append(fix_item)
    
    def _call_tool(self, tool_name: str, session_id: str, **kwargs) -> ToolResult:
        """Call a tool and record the call"""
        start_time = time.time()
        
        result = self.tool_system.execute_tool(tool_name, session_id, **kwargs)
        
        execution_time = int((time.time() - start_time) * 1000)
        
        # Record tool call
        tool_call = {
            'tool_name': tool_name,
            'session_id': session_id,
            'parameters': kwargs,
            'success': result.success,
            'execution_time_ms': execution_time,
            'timestamp': datetime.now().isoformat(),
            'error_message': result.error_message
        }
        self.tool_calls.append(tool_call)
        
        # Record iteration step
        step = IterationStep(
            step_type='tool_call',
            input_data={'tool_name': tool_name, 'parameters': kwargs},
            output_data=result.data if result.success else {},
            success=result.success,
            timestamp=datetime.now(),
            execution_time_ms=execution_time,
            error_message=result.error_message
        )
        self.iteration_steps.append(step)
        
        return result
    
    def _call_llm(self, prompt: str, context_window) -> str:
        """Call the LLM with the given prompt"""
        start_time = time.time()
        
        try:
            # Use the existing LLM handler
            response = self.llm_handler.generate_initial_code(prompt)
            
            execution_time = int((time.time() - start_time) * 1000)
            
            # Record iteration step
            step = IterationStep(
                step_type='code_generation',
                input_data={'prompt_tokens': len(prompt.split()), 'context_fingerprint': context_window.fingerprint},
                output_data={'response_length': len(response) if response else 0},
                success=bool(response),
                timestamp=datetime.now(),
                execution_time_ms=execution_time,
                error_message=None if response else "No response from LLM"
            )
            self.iteration_steps.append(step)
            
            return response or ""
        
        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            
            step = IterationStep(
                step_type='code_generation',
                input_data={'prompt_tokens': len(prompt.split())},
                output_data={},
                success=False,
                timestamp=datetime.now(),
                execution_time_ms=execution_time,
                error_message=str(e)
            )
            self.iteration_steps.append(step)
            
            raise
    
    def _build_generation_prompt(self, context_window, iteration: int) -> str:
        """Build the prompt for code generation"""
        base_prompt = context_window.to_prompt()
        
        if iteration == 0:
            instruction = """
## Task
Based on the above context, generate clean, working code that fulfills the user requirements.

Requirements:
1. Write complete, executable code
2. Include necessary imports and dependencies
3. Follow best practices and patterns shown in the context
4. Add appropriate comments and documentation
5. Handle edge cases and errors appropriately

Please provide only the code in a markdown code block.
"""
        else:
            instruction = f"""
## Task (Iteration {iteration + 1})
The previous code attempt had issues. Based on the validation feedback and context above, 
generate improved code that addresses the identified problems.

Focus on:
1. Fixing the specific issues mentioned in the validation feedback
2. Improving code quality and structure
3. Ensuring the code meets all user requirements
4. Learning from the provided examples and patterns

Please provide only the corrected code in a markdown code block.
"""
        
        return base_prompt + instruction
    
    def _extract_code_from_response(self, response: str) -> str:
        """Extract code from LLM response"""
        # Use existing utility function if available
        try:
            from utils import extract_python_code
            return extract_python_code(response) or ""
        except ImportError:
            # Fallback: simple markdown code block extraction
            import re
            
            # Find code blocks
            code_pattern = r'```(?:python|py)?\s*\n(.*?)```'
            matches = re.findall(code_pattern, response, re.DOTALL)
            
            if matches:
                return matches[0].strip()
            
            # If no code blocks, try to find python-like content
            lines = response.split('\n')
            code_lines = []
            in_code = False
            
            for line in lines:
                if any(keyword in line for keyword in ['def ', 'class ', 'import ', 'from ']):
                    in_code = True
                if in_code:
                    code_lines.append(line)
            
            return '\n'.join(code_lines).strip()
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract key technical keywords from requirements text"""
        # Simple keyword extraction
        technical_words = []
        
        import re
        words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', text.lower())
        
        # Filter for technical-sounding words
        technical_indicators = [
            'api', 'database', 'function', 'class', 'method', 'algorithm',
            'data', 'process', 'handle', 'manage', 'convert', 'parse',
            'authenticate', 'validate', 'encrypt', 'decode', 'serialize',
            'framework', 'library', 'module', 'service', 'client', 'server'
        ]
        
        for word in words:
            if len(word) > 3 and (
                word in technical_indicators or
                word.endswith(('ing', 'tion', 'ment', 'er', 'or'))
            ):
                if word not in technical_words:
                    technical_words.append(word)
        
        return technical_words[:10]  # Return top 10 keywords
    
    def get_execution_status(self) -> Dict[str, Any]:
        """Get current execution status"""
        return {
            'current_iteration': self.current_iteration,
            'execution_state': self.execution_state.value,
            'total_context_items': len(self.context_items),
            'total_tool_calls': len(self.tool_calls),
            'total_steps': len(self.iteration_steps)
        } 