"""
Tool System for Code Generation Agent

Provides the agent with access to various tools for codebase analysis,
file operations, and integration with existing agents.
"""

import os
import ast
import json
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
import logging
from dataclasses import dataclass
import time

from ..base.agent_interface import agent_registry
from ..github.github_agent import GitHubAgent
from ..knowledge_graph.knowledge_graph_agent import KnowledgeGraphAgent


@dataclass
class ToolResult:
    """Result from a tool execution"""
    success: bool
    data: Dict[str, Any]
    error_message: Optional[str] = None
    tool_name: str = ""
    execution_time_ms: int = 0


class BaseTool(ABC):
    """Base class for all tools"""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"tool.{name}")
    
    @abstractmethod
    def execute(self, session_id: str, **kwargs) -> ToolResult:
        """Execute the tool with given parameters"""
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """Get tool description for the agent"""
        pass
    
    @abstractmethod
    def get_parameters(self) -> Dict[str, Any]:
        """Get tool parameter schema"""
        pass


class SearchTool(BaseTool):
    """Tool for searching the indexed codebase using the knowledge graph agent"""
    
    def __init__(self):
        super().__init__("search")
        self.kg_agent = None
    
    def _get_kg_agent(self) -> KnowledgeGraphAgent:
        """Get knowledge graph agent instance"""
        if self.kg_agent is None:
            self.kg_agent = agent_registry.get_agent("knowledge_graph_agent")
            if self.kg_agent is None:
                # Create agent if not registered
                self.kg_agent = KnowledgeGraphAgent()
                agent_registry.register_agent(self.kg_agent)
        return self.kg_agent
    
    def execute(self, session_id: str, **kwargs) -> ToolResult:
        """Execute semantic search on the codebase"""
        try:
            start_time = time.time()
            
            query = kwargs.get('query', '')
            search_type = kwargs.get('search_type', 'search_code')  # search_code, find_functions, find_classes, find_patterns
            max_results = kwargs.get('max_results', 10)
            filters = kwargs.get('filters', {})
            
            if not query:
                return ToolResult(
                    success=False,
                    data={},
                    error_message="Query parameter is required",
                    tool_name=self.name
                )
            
            kg_agent = self._get_kg_agent()
            
            # Prepare input data based on search type
            input_data = {
                'operation': search_type,
                'query': query,
                'max_results': max_results,
                'filters': filters
            }
            
            result = kg_agent.execute(input_data, session_id)
            execution_time = int((time.time() - start_time) * 1000)
            
            if result.status.value == 'success':
                return ToolResult(
                    success=True,
                    data=result.data,
                    tool_name=self.name,
                    execution_time_ms=execution_time
                )
            else:
                return ToolResult(
                    success=False,
                    data=result.data,
                    error_message=result.error_message,
                    tool_name=self.name,
                    execution_time_ms=execution_time
                )
        
        except Exception as e:
            self.logger.error(f"Search tool error: {e}")
            return ToolResult(
                success=False,
                data={},
                error_message=str(e),
                tool_name=self.name
            )
    
    def get_description(self) -> str:
        return """Search the indexed codebase for relevant code, functions, classes, or patterns.
        Supports semantic search to find code based on natural language descriptions."""
    
    def get_parameters(self) -> Dict[str, Any]:
        return {
            'query': {'type': 'string', 'required': True, 'description': 'Search query or description'},
            'search_type': {
                'type': 'string', 
                'required': False, 
                'default': 'search_code',
                'enum': ['search_code', 'find_functions', 'find_classes', 'find_patterns'],
                'description': 'Type of search to perform'
            },
            'max_results': {'type': 'integer', 'required': False, 'default': 10, 'description': 'Maximum number of results'},
            'filters': {'type': 'object', 'required': False, 'description': 'Additional filters (language, file_path, etc.)'}
        }


class FileOperationTool(BaseTool):
    """Tool for reading, writing, and analyzing files"""
    
    def __init__(self):
        super().__init__("file_ops")
        self.github_agent = None
    
    def _get_github_agent(self) -> GitHubAgent:
        """Get GitHub agent instance"""
        if self.github_agent is None:
            self.github_agent = agent_registry.get_agent("github_repository_agent")
            if self.github_agent is None:
                # Create agent if not registered  
                self.github_agent = GitHubAgent()
                agent_registry.register_agent(self.github_agent)
        return self.github_agent
    
    def execute(self, session_id: str, **kwargs) -> ToolResult:
        """Execute file operations"""
        try:
            start_time = time.time()
            
            operation = kwargs.get('operation', 'read')
            file_path = kwargs.get('file_path', '')
            content = kwargs.get('content', '')
            target_dir = kwargs.get('target_dir', '')
            
            if operation == 'read':
                return self._read_file(session_id, file_path, start_time)
            elif operation == 'write':
                return self._write_file(session_id, file_path, content, target_dir, start_time)
            elif operation == 'analyze':
                return self._analyze_file(session_id, file_path, start_time)
            elif operation == 'list_files':
                return self._list_files(session_id, kwargs.get('directory', ''), start_time)
            elif operation == 'get_session_info':
                return self._get_session_info(session_id, start_time)
            else:
                return ToolResult(
                    success=False,
                    data={},
                    error_message=f"Unsupported operation: {operation}",
                    tool_name=self.name
                )
        
        except Exception as e:
            self.logger.error(f"File operation tool error: {e}")
            return ToolResult(
                success=False,
                data={},
                error_message=str(e),
                tool_name=self.name
            )
    
    def _read_file(self, session_id: str, file_path: str, start_time: float) -> ToolResult:
        """Read file content"""
        github_agent = self._get_github_agent()
        session_info = github_agent.get_session_info(session_id)
        
        if not session_info or not session_info['repository_exists']:
            return ToolResult(
                success=False,
                data={},
                error_message="No repository found for this session",
                tool_name=self.name
            )
        
        full_path = os.path.join(session_info['repository_dir'], file_path)
        
        if not os.path.exists(full_path):
            return ToolResult(
                success=False,
                data={},
                error_message=f"File not found: {file_path}",
                tool_name=self.name
            )
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            execution_time = int((time.time() - start_time) * 1000)
            
            return ToolResult(
                success=True,
                data={
                    'file_path': file_path,
                    'content': content,
                    'size_bytes': len(content.encode('utf-8')),
                    'lines': content.count('\n') + 1
                },
                tool_name=self.name,
                execution_time_ms=execution_time
            )
        
        except Exception as e:
            return ToolResult(
                success=False,
                data={},
                error_message=f"Error reading file: {str(e)}",
                tool_name=self.name
            )
    
    def _write_file(self, session_id: str, file_path: str, content: str, target_dir: str, start_time: float) -> ToolResult:
        """Write file content to a new directory"""
        if not target_dir:
            target_dir = f"/tmp/code_generation_output/{session_id}"
        
        # Create target directory
        os.makedirs(target_dir, exist_ok=True)
        
        full_path = os.path.join(target_dir, file_path)
        
        # Create subdirectories if needed
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            execution_time = int((time.time() - start_time) * 1000)
            
            return ToolResult(
                success=True,
                data={
                    'file_path': file_path,
                    'full_path': full_path,
                    'target_dir': target_dir,
                    'size_bytes': len(content.encode('utf-8')),
                    'lines': content.count('\n') + 1
                },
                tool_name=self.name,
                execution_time_ms=execution_time
            )
        
        except Exception as e:
            return ToolResult(
                success=False,
                data={},
                error_message=f"Error writing file: {str(e)}",
                tool_name=self.name
            )
    
    def _analyze_file(self, session_id: str, file_path: str, start_time: float) -> ToolResult:
        """Analyze file structure and extract metadata"""
        read_result = self._read_file(session_id, file_path, start_time)
        
        if not read_result.success:
            return read_result
        
        content = read_result.data['content']
        analysis = {
            'file_path': file_path,
            'language': self._detect_language(file_path),
            'size_bytes': len(content.encode('utf-8')),
            'lines': content.count('\n') + 1,
            'functions': [],
            'classes': [],
            'imports': [],
            'complexity_score': 0
        }
        
        # Perform language-specific analysis
        if analysis['language'] == 'python':
            analysis.update(self._analyze_python_file(content))
        elif analysis['language'] in ['javascript', 'typescript']:
            analysis.update(self._analyze_js_file(content))
        
        execution_time = int((time.time() - start_time) * 1000)
        
        return ToolResult(
            success=True,
            data=analysis,
            tool_name=self.name,
            execution_time_ms=execution_time
        )
    
    def _list_files(self, session_id: str, directory: str, start_time: float) -> ToolResult:
        """List files in repository directory"""
        github_agent = self._get_github_agent()
        session_info = github_agent.get_session_info(session_id)
        
        if not session_info or not session_info['repository_exists']:
            return ToolResult(
                success=False,
                data={},
                error_message="No repository found for this session",
                tool_name=self.name
            )
        
        base_path = session_info['repository_dir']
        if directory:
            full_path = os.path.join(base_path, directory)
        else:
            full_path = base_path
        
        if not os.path.exists(full_path):
            return ToolResult(
                success=False,
                data={},
                error_message=f"Directory not found: {directory}",
                tool_name=self.name
            )
        
        files = []
        directories = []
        
        try:
            for item in os.listdir(full_path):
                item_path = os.path.join(full_path, item)
                relative_path = os.path.join(directory, item) if directory else item
                
                if os.path.isfile(item_path):
                    files.append({
                        'name': item,
                        'path': relative_path,
                        'size': os.path.getsize(item_path),
                        'language': self._detect_language(item)
                    })
                elif os.path.isdir(item_path) and not item.startswith('.'):
                    directories.append({
                        'name': item,
                        'path': relative_path
                    })
            
            execution_time = int((time.time() - start_time) * 1000)
            
            return ToolResult(
                success=True,
                data={
                    'directory': directory,
                    'files': files,
                    'directories': directories,
                    'total_files': len(files),
                    'total_directories': len(directories)
                },
                tool_name=self.name,
                execution_time_ms=execution_time
            )
        
        except Exception as e:
            return ToolResult(
                success=False,
                data={},
                error_message=f"Error listing directory: {str(e)}",
                tool_name=self.name
            )
    
    def _get_session_info(self, session_id: str, start_time: float) -> ToolResult:
        """Get session information"""
        github_agent = self._get_github_agent()
        session_info = github_agent.get_session_info(session_id)
        
        execution_time = int((time.time() - start_time) * 1000)
        
        if session_info:
            return ToolResult(
                success=True,
                data=session_info,
                tool_name=self.name,
                execution_time_ms=execution_time
            )
        else:
            return ToolResult(
                success=False,
                data={},
                error_message="Session not found",
                tool_name=self.name,
                execution_time_ms=execution_time
            )
    
    def _detect_language(self, filename: str) -> str:
        """Detect programming language from filename"""
        ext = Path(filename).suffix.lower()
        
        lang_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.cs': 'csharp',
            '.go': 'go',
            '.rs': 'rust',
            '.php': 'php',
            '.rb': 'ruby',
            '.json': 'json',
            '.xml': 'xml',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.md': 'markdown',
            '.txt': 'text'
        }
        
        return lang_map.get(ext, 'unknown')
    
    def _analyze_python_file(self, content: str) -> Dict[str, Any]:
        """Analyze Python file using AST"""
        try:
            tree = ast.parse(content)
            functions = []
            classes = []
            imports = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.append({
                        'name': node.name,
                        'line': node.lineno,
                        'args': [arg.arg for arg in node.args.args],
                        'decorators': [d.id if isinstance(d, ast.Name) else str(d) for d in node.decorator_list]
                    })
                elif isinstance(node, ast.ClassDef):
                    classes.append({
                        'name': node.name,
                        'line': node.lineno,
                        'bases': [base.id if isinstance(base, ast.Name) else str(base) for base in node.bases],
                        'methods': [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                    })
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append({'module': alias.name, 'alias': alias.asname, 'type': 'import'})
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    for alias in node.names:
                        imports.append({'module': f"{module}.{alias.name}", 'alias': alias.asname, 'type': 'from'})
            
            # Simple complexity score based on node count
            complexity_score = len(list(ast.walk(tree))) // 10
            
            return {
                'functions': functions,
                'classes': classes,
                'imports': imports,
                'complexity_score': complexity_score
            }
        
        except Exception as e:
            self.logger.warning(f"Error analyzing Python file: {e}")
            return {
                'functions': [],
                'classes': [],
                'imports': [],
                'complexity_score': 0,
                'analysis_error': str(e)
            }
    
    def _analyze_js_file(self, content: str) -> Dict[str, Any]:
        """Basic JavaScript file analysis (simplified)"""
        # Simple regex-based analysis for JavaScript
        import re
        
        functions = []
        classes = []
        imports = []
        
        # Find function declarations
        func_pattern = r'function\s+(\w+)\s*\([^)]*\)'
        for match in re.finditer(func_pattern, content):
            functions.append({
                'name': match.group(1),
                'line': content[:match.start()].count('\n') + 1,
                'type': 'function'
            })
        
        # Find arrow functions
        arrow_pattern = r'const\s+(\w+)\s*=\s*\([^)]*\)\s*=>'
        for match in re.finditer(arrow_pattern, content):
            functions.append({
                'name': match.group(1),
                'line': content[:match.start()].count('\n') + 1,
                'type': 'arrow_function'
            })
        
        # Find class declarations
        class_pattern = r'class\s+(\w+)'
        for match in re.finditer(class_pattern, content):
            classes.append({
                'name': match.group(1),
                'line': content[:match.start()].count('\n') + 1
            })
        
        # Find imports
        import_pattern = r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]'
        for match in re.finditer(import_pattern, content):
            imports.append({
                'module': match.group(1),
                'line': content[:match.start()].count('\n') + 1
            })
        
        return {
            'functions': functions,
            'classes': classes,
            'imports': imports,
            'complexity_score': len(functions) + len(classes)
        }
    
    def get_description(self) -> str:
        return """Perform file operations like reading, writing, analyzing files in the repository.
        Can read source files, write generated code to target directories, and analyze code structure."""
    
    def get_parameters(self) -> Dict[str, Any]:
        return {
            'operation': {
                'type': 'string',
                'required': True,
                'enum': ['read', 'write', 'analyze', 'list_files', 'get_session_info'],
                'description': 'File operation to perform'
            },
            'file_path': {'type': 'string', 'required': False, 'description': 'Path to the file'},
            'content': {'type': 'string', 'required': False, 'description': 'Content to write (for write operation)'},
            'target_dir': {'type': 'string', 'required': False, 'description': 'Target directory for writing files'},
            'directory': {'type': 'string', 'required': False, 'description': 'Directory to list (for list_files operation)'}
        }


class CodeAnalysisTool(BaseTool):
    """Tool for advanced code analysis and pattern detection"""
    
    def __init__(self):
        super().__init__("code_analysis")
    
    def execute(self, session_id: str, **kwargs) -> ToolResult:
        """Execute code analysis operations"""
        try:
            start_time = time.time()
            
            operation = kwargs.get('operation', 'analyze_patterns')
            code = kwargs.get('code', '')
            language = kwargs.get('language', 'python')
            
            if operation == 'analyze_patterns':
                return self._analyze_patterns(code, language, start_time)
            elif operation == 'suggest_improvements':
                return self._suggest_improvements(code, language, start_time)
            elif operation == 'detect_issues':
                return self._detect_issues(code, language, start_time)
            elif operation == 'extract_dependencies':
                return self._extract_dependencies(code, language, start_time)
            else:
                return ToolResult(
                    success=False,
                    data={},
                    error_message=f"Unsupported analysis operation: {operation}",
                    tool_name=self.name
                )
        
        except Exception as e:
            self.logger.error(f"Code analysis tool error: {e}")
            return ToolResult(
                success=False,
                data={},
                error_message=str(e),
                tool_name=self.name
            )
    
    def _analyze_patterns(self, code: str, language: str, start_time: float) -> ToolResult:
        """Analyze code patterns and architectural decisions"""
        patterns = {
            'design_patterns': [],
            'architectural_patterns': [],
            'code_smells': [],
            'best_practices': []
        }
        
        if language == 'python':
            patterns.update(self._analyze_python_patterns(code))
        
        execution_time = int((time.time() - start_time) * 1000)
        
        return ToolResult(
            success=True,
            data=patterns,
            tool_name=self.name,
            execution_time_ms=execution_time
        )
    
    def _analyze_python_patterns(self, code: str) -> Dict[str, List[str]]:
        """Analyze Python-specific patterns"""
        patterns = {
            'design_patterns': [],
            'architectural_patterns': [],
            'code_smells': [],
            'best_practices': []
        }
        
        # Simple pattern detection
        if 'class.*Factory' in code:
            patterns['design_patterns'].append('Factory Pattern')
        
        if 'def __enter__' in code and 'def __exit__' in code:
            patterns['design_patterns'].append('Context Manager Pattern')
        
        if '@property' in code:
            patterns['best_practices'].append('Property Decorators Used')
        
        if 'try:' in code and 'except' in code:
            patterns['best_practices'].append('Exception Handling')
        
        if len(code.split('\n')) > 100 and 'class' not in code:
            patterns['code_smells'].append('Large Function/Module')
        
        return patterns
    
    def _suggest_improvements(self, code: str, language: str, start_time: float) -> ToolResult:
        """Suggest code improvements"""
        suggestions = []
        
        if language == 'python':
            # Basic Python improvement suggestions
            if 'global ' in code:
                suggestions.append("Consider avoiding global variables for better code organization")
            
            if code.count('if ') > 5:
                suggestions.append("Consider refactoring complex conditional logic")
            
            if 'print(' in code and 'def ' in code:
                suggestions.append("Consider using logging instead of print statements")
        
        execution_time = int((time.time() - start_time) * 1000)
        
        return ToolResult(
            success=True,
            data={'suggestions': suggestions},
            tool_name=self.name,
            execution_time_ms=execution_time
        )
    
    def _detect_issues(self, code: str, language: str, start_time: float) -> ToolResult:
        """Detect potential issues in code"""
        issues = {
            'syntax_issues': [],
            'logic_issues': [],
            'security_issues': [],
            'performance_issues': []
        }
        
        if language == 'python':
            # Basic issue detection
            if 'eval(' in code:
                issues['security_issues'].append("Use of eval() can be dangerous")
            
            if 'exec(' in code:
                issues['security_issues'].append("Use of exec() can be dangerous")
            
            if code.count('for ') > 3 and 'in range(' in code:
                issues['performance_issues'].append("Multiple nested loops detected")
        
        execution_time = int((time.time() - start_time) * 1000)
        
        return ToolResult(
            success=True,
            data=issues,
            tool_name=self.name,
            execution_time_ms=execution_time
        )
    
    def _extract_dependencies(self, code: str, language: str, start_time: float) -> ToolResult:
        """Extract dependencies from code"""
        dependencies = {
            'imports': [],
            'external_libraries': [],
            'internal_modules': []
        }
        
        if language == 'python':
            import re
            
            # Find import statements
            import_pattern = r'^\s*(?:from\s+(\S+)\s+)?import\s+(.+?)(?:\s+as\s+\S+)?$'
            for line in code.split('\n'):
                match = re.match(import_pattern, line.strip())
                if match:
                    module = match.group(1) or match.group(2).split(',')[0].strip()
                    dependencies['imports'].append(module)
                    
                    # Classify as external or internal
                    if module in ['os', 'sys', 'json', 'time', 'datetime', 're', 'math']:
                        continue  # Standard library
                    elif '.' not in module or module.startswith('.'):
                        dependencies['internal_modules'].append(module)
                    else:
                        dependencies['external_libraries'].append(module)
        
        execution_time = int((time.time() - start_time) * 1000)
        
        return ToolResult(
            success=True,
            data=dependencies,
            tool_name=self.name,
            execution_time_ms=execution_time
        )
    
    def get_description(self) -> str:
        return """Analyze code for patterns, suggest improvements, detect issues, and extract dependencies.
        Provides insights into code quality and architectural decisions."""
    
    def get_parameters(self) -> Dict[str, Any]:
        return {
            'operation': {
                'type': 'string',
                'required': True,
                'enum': ['analyze_patterns', 'suggest_improvements', 'detect_issues', 'extract_dependencies'],
                'description': 'Analysis operation to perform'
            },
            'code': {'type': 'string', 'required': True, 'description': 'Code to analyze'},
            'language': {'type': 'string', 'required': False, 'default': 'python', 'description': 'Programming language'}
        }


class ToolSystem:
    """Central tool system that manages all available tools"""
    
    def __init__(self):
        self.tools: Dict[str, BaseTool] = {}
        self.logger = logging.getLogger(__name__)
        
        # Register built-in tools
        self.register_tool(SearchTool())
        self.register_tool(FileOperationTool())  
        self.register_tool(CodeAnalysisTool())
        
        self.logger.info(f"Initialized tool system with {len(self.tools)} tools")
    
    def register_tool(self, tool: BaseTool) -> None:
        """Register a new tool"""
        self.tools[tool.name] = tool
        self.logger.info(f"Registered tool: {tool.name}")
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get tool by name"""
        return self.tools.get(name)
    
    def list_tools(self) -> List[str]:
        """List all available tool names"""
        return list(self.tools.keys())
    
    def execute_tool(self, tool_name: str, session_id: str, **kwargs) -> ToolResult:
        """Execute a tool with given parameters"""
        tool = self.get_tool(tool_name)
        
        if not tool:
            return ToolResult(
                success=False,
                data={},
                error_message=f"Tool not found: {tool_name}",
                tool_name=tool_name
            )
        
        try:
            self.logger.info(f"Executing tool: {tool_name} for session: {session_id}")
            result = tool.execute(session_id, **kwargs)
            
            if result.success:
                self.logger.info(f"Tool {tool_name} executed successfully")
            else:
                self.logger.warning(f"Tool {tool_name} failed: {result.error_message}")
            
            return result
        
        except Exception as e:
            self.logger.error(f"Error executing tool {tool_name}: {e}")
            return ToolResult(
                success=False,
                data={},
                error_message=str(e),
                tool_name=tool_name
            )
    
    def get_tool_descriptions(self) -> Dict[str, Dict[str, Any]]:
        """Get descriptions and parameters for all tools"""
        descriptions = {}
        
        for name, tool in self.tools.items():
            descriptions[name] = {
                'description': tool.get_description(),
                'parameters': tool.get_parameters()
            }
        
        return descriptions 