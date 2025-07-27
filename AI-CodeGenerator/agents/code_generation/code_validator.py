"""
Code Validator for Generated Code

Validates generated code for syntax, logic, quality, and adherence to requirements.
Provides feedback for iterative improvement with Docker-based execution validation.
"""

import ast
import re
import subprocess
import tempfile
import os
import sys
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

# Add parent directories to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import Docker execution capability
try:
    from docker_runner import execute_code
    DOCKER_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Docker execution not available: {e}")
    DOCKER_AVAILABLE = False

# Import config with fallback
try:
    import config
    CONFIG_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Config module not available: {e}")
    CONFIG_AVAILABLE = False


class ValidationLevel(Enum):
    """Validation severity levels"""
    ERROR = "error"      # Critical issues that prevent execution
    WARNING = "warning"  # Issues that may cause problems
    INFO = "info"       # Style and improvement suggestions


@dataclass
class ValidationIssue:
    """Individual validation issue"""
    level: ValidationLevel
    message: str
    line_number: Optional[int] = None
    category: str = "general"  # syntax, logic, style, security, performance
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """Complete validation result"""
    is_valid: bool
    confidence_score: float  # 0.0 to 1.0
    issues: List[str]  # Simplified issue messages
    suggestions: List[str]  # Improvement suggestions
    detailed_issues: List[ValidationIssue]
    execution_test: Optional[bool] = None  # Can the code execute?
    execution_feedback: Optional[str] = None  # Detailed execution results/errors
    requirements_match: Optional[float] = None  # How well does it match requirements?
    metadata: Optional[Dict[str, Any]] = None


class CodeValidator:
    """Validates generated code for quality and correctness"""
    
    def __init__(self, enable_docker_execution: bool = True, docker_timeout: int = None):
        self.logger = logging.getLogger(__name__)
        
        # Execution validation settings
        self.enable_docker_execution = enable_docker_execution and DOCKER_AVAILABLE
        self.docker_timeout = docker_timeout or (config.DOCKER_TIMEOUT_SECONDS if DOCKER_AVAILABLE and CONFIG_AVAILABLE else 30)
        
        if self.enable_docker_execution:
            self.logger.info("Docker execution validation enabled")
        else:
            self.logger.warning("Docker execution validation disabled - using compilation-only checking")
        
        # Validation weights for confidence score
        # Increased weight for execution test since it's more comprehensive now
        self.weights = {
            'syntax_valid': 0.25,
            'execution_test': 0.35,  # Increased from 0.25
            'requirements_match': 0.25,
            'code_quality': 0.15     # Decreased from 0.2
        }
    
    def validate(self, code: str, requirements: str, language: str = "python") -> ValidationResult:
        """Validate code against requirements and quality standards"""
        self.logger.info("Starting code validation")
        
        detailed_issues = []
        metadata = {}
        
        try:
            # Step 1: Syntax validation
            syntax_valid, syntax_issues = self._validate_syntax(code, language)
            detailed_issues.extend(syntax_issues)
            metadata['syntax_valid'] = syntax_valid
            
            # Step 2: Execution test (if syntax is valid)
            execution_test = None
            execution_feedback = None
            if syntax_valid and language == "python":
                execution_test, execution_feedback = self._test_execution(code)
                metadata['execution_test'] = execution_test
                metadata['execution_feedback'] = execution_feedback
                
                # Add execution feedback as validation issue if execution failed
                if not execution_test and execution_feedback:
                    detailed_issues.append(ValidationIssue(
                        level=ValidationLevel.ERROR,
                        message=f"Execution failed: {execution_feedback}",
                        category="execution",
                        suggestion="Review the error message and fix the runtime issues in the code."
                    ))
            
            # Step 3: Requirements matching
            requirements_match = self._check_requirements_match(code, requirements)
            metadata['requirements_match'] = requirements_match
            
            # Step 4: Code quality analysis
            quality_score, quality_issues = self._analyze_code_quality(code, language)
            detailed_issues.extend(quality_issues)
            metadata['code_quality'] = quality_score
            
            # Step 5: Security analysis
            security_issues = self._analyze_security(code, language)
            detailed_issues.extend(security_issues)
            
            # Step 6: Performance analysis
            performance_issues = self._analyze_performance(code, language)
            detailed_issues.extend(performance_issues)
            
            # Calculate confidence score
            confidence_score = self._calculate_confidence_score(metadata)
            
            # Determine if code is valid (no critical errors)
            critical_errors = [issue for issue in detailed_issues if issue.level == ValidationLevel.ERROR]
            is_valid = len(critical_errors) == 0 and syntax_valid
            
            # Extract simplified messages
            issues = [issue.message for issue in detailed_issues if issue.level in [ValidationLevel.ERROR, ValidationLevel.WARNING]]
            suggestions = [issue.suggestion for issue in detailed_issues if issue.suggestion]
            
            result = ValidationResult(
                is_valid=is_valid,
                confidence_score=confidence_score,
                issues=issues,
                suggestions=suggestions,
                detailed_issues=detailed_issues,
                execution_test=execution_test,
                execution_feedback=execution_feedback,
                requirements_match=requirements_match,
                metadata=metadata
            )
            
            self.logger.info(
                f"Validation complete: valid={is_valid}, confidence={confidence_score:.2f}, "
                f"issues={len(issues)}, suggestions={len(suggestions)}"
            )
            
            return result
        
        except Exception as e:
            self.logger.error(f"Validation failed: {e}")
            return ValidationResult(
                is_valid=False,
                confidence_score=0.0,
                issues=[f"Validation error: {str(e)}"],
                suggestions=[],
                detailed_issues=[ValidationIssue(
                    level=ValidationLevel.ERROR,
                    message=f"Validation failed: {str(e)}",
                    category="validation"
                )],
                metadata={'error': str(e)}
            )
    
    def _validate_syntax(self, code: str, language: str) -> Tuple[bool, List[ValidationIssue]]:
        """Validate code syntax"""
        issues = []
        
        if language == "python":
            try:
                ast.parse(code)
                return True, issues
            except SyntaxError as e:
                issues.append(ValidationIssue(
                    level=ValidationLevel.ERROR,
                    message=f"Syntax error: {e.msg}",
                    line_number=e.lineno,
                    category="syntax",
                    suggestion="Check for missing colons, parentheses, or indentation issues"
                ))
                return False, issues
            except Exception as e:
                issues.append(ValidationIssue(
                    level=ValidationLevel.ERROR,
                    message=f"Parse error: {str(e)}",
                    category="syntax"
                ))
                return False, issues
        
        # For other languages, basic checks
        elif language in ["javascript", "typescript"]:
            # Basic JS syntax checks
            if code.count('{') != code.count('}'):
                issues.append(ValidationIssue(
                    level=ValidationLevel.ERROR,
                    message="Mismatched curly braces",
                    category="syntax"
                ))
                return False, issues
            
            if code.count('(') != code.count(')'):
                issues.append(ValidationIssue(
                    level=ValidationLevel.ERROR,
                    message="Mismatched parentheses", 
                    category="syntax"
                ))
                return False, issues
        
        return True, issues
    
    def _test_execution(self, code: str) -> Tuple[bool, Optional[str]]:
        """Test if Python code can execute without errors using Docker isolation"""
        
        if not self.enable_docker_execution:
            # Fallback to compilation-only checking
            return self._test_compilation_only(code), None
        
        try:
            self.logger.info("Testing code execution in Docker container")
            
            # Execute code in Docker container
            stdout, stderr, exit_code = execute_code(code)
            
            # Check execution results
            execution_successful = (exit_code == 0)
            
            if execution_successful:
                self.logger.info("Code executed successfully in Docker")
                execution_feedback = f"✅ Code executed successfully. Output: {stdout[:200]}..." if stdout else "✅ Code executed successfully with no output."
            else:
                self.logger.warning(f"Code execution failed in Docker. Exit code: {exit_code}")
                error_msg = stderr or "Unknown execution error"
                execution_feedback = f"❌ Execution failed (exit code {exit_code}): {error_msg[:300]}..."
                
                # Log detailed error for debugging
                self.logger.debug(f"Execution details - STDOUT: {stdout}, STDERR: {stderr}")
            
            return execution_successful, execution_feedback
            
        except Exception as e:
            self.logger.error(f"Docker execution test failed: {e}")
            execution_feedback = f"❌ Docker execution error: {str(e)[:200]}..."
            return False, execution_feedback
    
    def _test_compilation_only(self, code: str) -> bool:
        """Fallback method for compilation-only testing when Docker is unavailable"""
        try:
            # Create a temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_file:
                temp_file.write(code)
                temp_file_path = temp_file.name
            
            try:
                # Try to import/compile the code
                result = subprocess.run(
                    ['python', '-m', 'py_compile', temp_file_path],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                success = result.returncode == 0
                
                if not success:
                    self.logger.warning(f"Code compilation failed: {result.stderr}")
                
                return success
            
            finally:
                # Clean up temp file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
        
        except Exception as e:
            self.logger.warning(f"Compilation test failed: {e}")
            return False
    
    def _check_requirements_match(self, code: str, requirements: str) -> float:
        """Check how well the code matches the requirements"""
        if not requirements.strip():
            return 0.5  # Neutral if no requirements
        
        score = 0.0
        factors = 0
        
        # Extract keywords from requirements
        req_keywords = self._extract_technical_keywords(requirements.lower())
        
        if req_keywords:
            # Check keyword presence in code
            code_lower = code.lower()
            matched_keywords = sum(1 for keyword in req_keywords if keyword in code_lower)
            keyword_score = matched_keywords / len(req_keywords)
            score += keyword_score * 0.3
            factors += 0.3
        
        # Check for common requirement patterns
        requirement_patterns = {
            'function': ['def ', 'function'],
            'class': ['class '],
            'api': ['api', 'request', 'response', 'http'],
            'database': ['database', 'db', 'sql', 'query'],
            'file': ['file', 'open', 'read', 'write'],
            'data': ['data', 'json', 'csv', 'parse'],
            'error handling': ['try:', 'except', 'error', 'exception'],
            'validation': ['validate', 'check', 'verify']
        }
        
        matched_patterns = 0
        total_patterns = 0
        
        for pattern_name, pattern_keywords in requirement_patterns.items():
            if any(keyword in requirements.lower() for keyword in pattern_keywords):
                total_patterns += 1
                if any(keyword in code.lower() for keyword in pattern_keywords):
                    matched_patterns += 1
        
        if total_patterns > 0:
            pattern_score = matched_patterns / total_patterns
            score += pattern_score * 0.4
            factors += 0.4
        
        # Check code structure complexity vs requirements complexity
        req_complexity = len(requirements.split()) / 10  # Rough complexity measure
        code_complexity = self._estimate_code_complexity(code)
        
        if req_complexity > 0:
            complexity_ratio = min(code_complexity / req_complexity, 2.0)  # Cap at 2x
            complexity_score = 1.0 - abs(1.0 - complexity_ratio)  # Prefer close to 1:1 ratio
            score += complexity_score * 0.3
            factors += 0.3
        
        return score / factors if factors > 0 else 0.5
    
    def _analyze_code_quality(self, code: str, language: str) -> Tuple[float, List[ValidationIssue]]:
        """Analyze code quality and return score + issues"""
        issues = []
        quality_factors = []
        
        if language == "python":
            quality_factors, issues = self._analyze_python_quality(code)
        elif language in ["javascript", "typescript"]:
            quality_factors, issues = self._analyze_js_quality(code)
        
        # Calculate overall quality score
        quality_score = sum(quality_factors) / len(quality_factors) if quality_factors else 0.5
        
        return quality_score, issues
    
    def _analyze_python_quality(self, code: str) -> Tuple[List[float], List[ValidationIssue]]:
        """Analyze Python-specific code quality"""
        issues = []
        factors = []
        
        try:
            tree = ast.parse(code)
            
            # Factor 1: Function and class organization
            functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
            classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
            
            if functions or classes:
                factors.append(0.8)  # Good organization
            else:
                factors.append(0.4)  # Script-style code
                issues.append(ValidationIssue(
                    level=ValidationLevel.INFO,
                    message="Consider organizing code into functions or classes",
                    category="style",
                    suggestion="Break code into reusable functions"
                ))
            
            # Factor 2: Documentation
            docstrings = 0
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    if (ast.get_docstring(node)):
                        docstrings += 1
            
            total_definitions = len(functions) + len(classes)
            if total_definitions > 0:
                doc_ratio = docstrings / total_definitions
                factors.append(doc_ratio)
                
                if doc_ratio < 0.5:
                    issues.append(ValidationIssue(
                        level=ValidationLevel.INFO,
                        message="Consider adding docstrings to functions and classes",
                        category="style",
                        suggestion="Add docstrings to explain function/class purpose"
                    ))
            else:
                factors.append(0.5)  # Neutral for scripts
            
            # Factor 3: Error handling
            try_blocks = [node for node in ast.walk(tree) if isinstance(node, ast.Try)]
            has_error_handling = len(try_blocks) > 0
            
            if has_error_handling:
                factors.append(0.9)
            else:
                factors.append(0.6)
                issues.append(ValidationIssue(
                    level=ValidationLevel.WARNING,
                    message="No error handling found",
                    category="logic",
                    suggestion="Add try-except blocks for error handling"
                ))
            
            # Factor 4: Import organization
            imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
            if imports:
                factors.append(0.7)
            else:
                factors.append(0.8)  # Might not need imports
            
            # Factor 5: Complexity check
            complexity = len(list(ast.walk(tree)))
            if complexity < 50:
                factors.append(0.9)  # Simple and readable
            elif complexity < 150:
                factors.append(0.7)  # Moderate complexity
            else:
                factors.append(0.5)  # High complexity
                issues.append(ValidationIssue(
                    level=ValidationLevel.WARNING,
                    message="Code complexity is high",
                    category="style",
                    suggestion="Consider breaking into smaller functions"
                ))
        
        except Exception as e:
            self.logger.warning(f"Quality analysis failed: {e}")
            factors = [0.5]
        
        return factors, issues
    
    def _analyze_js_quality(self, code: str) -> Tuple[List[float], List[ValidationIssue]]:
        """Analyze JavaScript/TypeScript code quality (simplified)"""
        issues = []
        factors = []
        
        # Basic quality checks
        lines = code.split('\n')
        
        # Factor 1: Function organization
        function_count = len(re.findall(r'function\s+\w+|const\s+\w+\s*=\s*\([^)]*\)\s*=>', code))
        if function_count > 0:
            factors.append(0.8)
        else:
            factors.append(0.4)
            issues.append(ValidationIssue(
                level=ValidationLevel.INFO,
                message="Consider organizing code into functions",
                category="style"
            ))
        
        # Factor 2: Error handling
        has_try_catch = 'try' in code and 'catch' in code
        if has_try_catch:
            factors.append(0.9)
        else:
            factors.append(0.6)
            issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                message="No error handling found",
                category="logic"
            ))
        
        # Factor 3: Comments
        comment_lines = sum(1 for line in lines if line.strip().startswith('//') or '/*' in line)
        if comment_lines > len(lines) * 0.1:  # At least 10% comments
            factors.append(0.8)
        else:
            factors.append(0.6)
        
        return factors, issues
    
    def _analyze_security(self, code: str, language: str) -> List[ValidationIssue]:
        """Analyze code for security issues"""
        issues = []
        
        if language == "python":
            # Check for dangerous functions
            dangerous_patterns = {
                'eval(': 'Use of eval() can execute arbitrary code',
                'exec(': 'Use of exec() can execute arbitrary code',
                'subprocess.call': 'Direct subprocess calls can be dangerous',
                'os.system': 'os.system() can execute arbitrary commands',
                'input(': 'Consider validating user input'
            }
            
            for pattern, message in dangerous_patterns.items():
                if pattern in code:
                    issues.append(ValidationIssue(
                        level=ValidationLevel.WARNING if pattern == 'input(' else ValidationLevel.ERROR,
                        message=message,
                        category="security",
                        suggestion="Use safer alternatives or add input validation"
                    ))
        
        return issues
    
    def _analyze_performance(self, code: str, language: str) -> List[ValidationIssue]:
        """Analyze code for performance issues"""
        issues = []
        
        if language == "python":
            # Check for common performance issues
            if code.count('for ') > 2 and 'range(' in code:
                issues.append(ValidationIssue(
                    level=ValidationLevel.INFO,
                    message="Multiple nested loops detected",
                    category="performance",
                    suggestion="Consider optimizing nested loops or using vectorized operations"
                ))
            
            if '+=' in code and 'str' in code:
                issues.append(ValidationIssue(
                    level=ValidationLevel.INFO,
                    message="String concatenation in loop detected",
                    category="performance",
                    suggestion="Consider using join() for string concatenation"
                ))
        
        return issues
    
    def _calculate_confidence_score(self, metadata: Dict[str, Any]) -> float:
        """Calculate overall confidence score"""
        score = 0.0
        
        # Syntax validation (critical)
        if metadata.get('syntax_valid', False):
            score += self.weights['syntax_valid']
        
        # Execution test
        execution_test = metadata.get('execution_test')
        if execution_test is True:
            score += self.weights['execution_test']
        elif execution_test is False:
            score += self.weights['execution_test'] * 0.3  # Partial credit
        else:
            score += self.weights['execution_test'] * 0.7  # Neutral if not tested
        
        # Requirements match
        req_match = metadata.get('requirements_match', 0.5)
        score += self.weights['requirements_match'] * req_match
        
        # Code quality
        quality = metadata.get('code_quality', 0.5)
        score += self.weights['code_quality'] * quality
        
        return min(1.0, max(0.0, score))
    
    def _extract_technical_keywords(self, text: str) -> List[str]:
        """Extract technical keywords from text"""
        # Simple keyword extraction
        import re
        words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', text)
        
        technical_indicators = [
            'api', 'database', 'function', 'class', 'method', 'algorithm',
            'data', 'process', 'handle', 'manage', 'convert', 'parse',
            'authenticate', 'validate', 'encrypt', 'decode', 'serialize',
            'framework', 'library', 'module', 'service', 'client', 'server',
            'request', 'response', 'json', 'xml', 'csv', 'file', 'directory',
            'error', 'exception', 'try', 'catch', 'import', 'export'
        ]
        
        return [word for word in words if word.lower() in technical_indicators]
    
    def _estimate_code_complexity(self, code: str) -> float:
        """Estimate code complexity (simplified)"""
        # Simple complexity metrics
        lines = len([line for line in code.split('\n') if line.strip()])
        functions = len(re.findall(r'def\s+\w+|function\s+\w+', code))
        classes = len(re.findall(r'class\s+\w+', code))
        conditions = len(re.findall(r'\bif\b|\bfor\b|\bwhile\b', code))
        
        # Normalize to a 0-10 scale
        complexity = (lines / 10) + (functions * 2) + (classes * 3) + (conditions * 1.5)
        return min(10.0, complexity) 