"""
Smart Code Chunker
Handles intelligent chunking of code files into meaningful segments.
"""

import os
import re
import glob
import logging
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

from .schema import (
    CodeChunk, ChunkType, Language, ChunkingResult, ChunkingConfig, detect_language
)


class CodeChunker:
    """Smart code chunker that creates meaningful code segments"""
    
    def __init__(self, config: Optional[ChunkingConfig] = None):
        self.config = config or ChunkingConfig()
        self.logger = logging.getLogger(__name__)
        self._language_parsers = {
            Language.PYTHON: self._chunk_python,
            Language.JAVASCRIPT: self._chunk_javascript,
            Language.TYPESCRIPT: self._chunk_javascript,  # Same as JS
            Language.JAVA: self._chunk_java,
            Language.CPP: self._chunk_cpp,
            Language.C: self._chunk_cpp,  # Similar to C++
            Language.LABVIEW: self._chunk_labview,
        }
    
    def chunk_repository(self, repo_path: str) -> ChunkingResult:
        """Chunk an entire repository into code segments"""
        
        # Find all code files
        code_files = self._find_code_files(repo_path)
        
        all_chunks = []
        total_lines = 0
        language_stats = defaultdict(int)
        chunk_stats = defaultdict(int)
        
        for file_path in code_files:
            rel_path = os.path.relpath(file_path, repo_path)
            language = detect_language(file_path)
            language_stats[language] += 1
            
            # Chunk the file
            try:
                file_chunks, file_lines = self._chunk_file(file_path, rel_path, language)
                all_chunks.extend(file_chunks)
                total_lines += file_lines
                
                # Update chunk statistics
                for chunk in file_chunks:
                    chunk_stats[chunk.chunk_type] += 1
            except Exception as e:
                self.logger.warning(f"Error processing {rel_path}: {e}")
                continue
        
        return ChunkingResult(
            chunks=all_chunks,
            total_files=len(code_files),
            total_lines=total_lines,
            language_stats=dict(language_stats),
            chunk_stats=dict(chunk_stats)
        )
    
    def _find_code_files(self, repo_path: str) -> List[str]:
        """Find all code files in the repository"""
        code_files = []
        
        # Get all files with code extensions
        for ext in self.config.include_extensions:
            pattern = os.path.join(repo_path, '**', f'*{ext}')
            files = glob.glob(pattern, recursive=True)
            code_files.extend(files)
        
        # Filter out excluded patterns
        filtered_files = []
        for file_path in code_files:
            should_include = True
            
            for exclude_pattern in self.config.exclude_patterns:
                if exclude_pattern in file_path:
                    should_include = False
                    break
            
            if should_include:
                filtered_files.append(file_path)
        
        return filtered_files
    
    def _chunk_file(self, file_path: str, rel_path: str, language: Language) -> Tuple[List[CodeChunk], int]:
        """Chunk a single file into code segments"""
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            return [], 0
        
        lines = content.split('\n')
        total_lines = len(lines)
        
        # Small files get chunked as a whole
        if len(content) <= self.config.small_file_threshold:
            chunk = CodeChunk(
                text=content,
                file_path=rel_path,
                chunk_type=ChunkType.FILE,
                language=language,
                start_line=1,
                end_line=total_lines,
                name=os.path.basename(rel_path),
                metadata={'file_size': len(content)}
            )
            return [chunk], total_lines
        
        # Use language-specific chunking if available
        if language in self._language_parsers:
            chunks = self._language_parsers[language](content, rel_path, language)
        else:
            # Fallback to generic chunking
            chunks = self._chunk_generic(content, rel_path, language)
        
        return chunks, total_lines
    
    def _chunk_python(self, content: str, file_path: str, language: Language) -> List[CodeChunk]:
        """Chunk Python code using AST parsing"""
        import ast
        
        chunks = []
        lines = content.split('\n')
        
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Function chunk
                    start_line = node.lineno
                    end_line = getattr(node, 'end_lineno', start_line + 10)  # Fallback
                    
                    func_content = '\n'.join(lines[start_line-1:end_line])
                    
                    # Extract docstring
                    docstring = None
                    if (node.body and isinstance(node.body[0], ast.Expr) and 
                        isinstance(node.body[0].value, ast.Constant) and 
                        isinstance(node.body[0].value.value, str)):
                        docstring = node.body[0].value.value
                    
                    # Build signature
                    args = [arg.arg for arg in node.args.args]
                    signature = f"def {node.name}({', '.join(args)}):"
                    
                    chunk = CodeChunk(
                        text=func_content,
                        file_path=file_path,
                        chunk_type=ChunkType.FUNCTION,
                        language=language,
                        start_line=start_line,
                        end_line=end_line,
                        name=node.name,
                        signature=signature,
                        docstring=docstring,
                        metadata={
                            'is_async': isinstance(node, ast.AsyncFunctionDef),
                            'arg_count': len(args)
                        }
                    )
                    chunks.append(chunk)
                
                elif isinstance(node, ast.ClassDef):
                    # Class chunk
                    start_line = node.lineno
                    end_line = getattr(node, 'end_lineno', start_line + 20)  # Fallback
                    
                    class_content = '\n'.join(lines[start_line-1:end_line])
                    
                    # Extract class docstring
                    docstring = None
                    if (node.body and isinstance(node.body[0], ast.Expr) and 
                        isinstance(node.body[0].value, ast.Constant) and 
                        isinstance(node.body[0].value.value, str)):
                        docstring = node.body[0].value.value
                    
                    # Build signature
                    bases = [base.id if hasattr(base, 'id') else str(base) for base in node.bases]
                    signature = f"class {node.name}"
                    if bases:
                        signature += f"({', '.join(bases)})"
                    signature += ":"
                    
                    chunk = CodeChunk(
                        text=class_content,
                        file_path=file_path,
                        chunk_type=ChunkType.CLASS,
                        language=language,
                        start_line=start_line,
                        end_line=end_line,
                        name=node.name,
                        signature=signature,
                        docstring=docstring,
                        metadata={
                            'base_classes': bases,
                            'method_count': len([n for n in node.body if isinstance(n, ast.FunctionDef)])
                        }
                    )
                    chunks.append(chunk)
        
        except SyntaxError:
            # If AST parsing fails, fall back to regex
            chunks = self._chunk_python_regex(content, file_path, language)
        
        # If no functions/classes found, chunk by logical blocks
        if not chunks:
            chunks = self._chunk_by_logical_blocks(content, file_path, language)
        
        return chunks
    
    def _chunk_python_regex(self, content: str, file_path: str, language: Language) -> List[CodeChunk]:
        """Fallback Python chunking using regex"""
        chunks = []
        lines = content.split('\n')
        
        # Find function definitions
        func_pattern = r'^(\s*)(def|async def)\s+(\w+)\s*\([^)]*\):'
        class_pattern = r'^(\s*)(class)\s+(\w+)(?:\([^)]*\))?:'
        
        current_chunk = None
        current_indent = None
        
        for i, line in enumerate(lines):
            # Check for function
            func_match = re.match(func_pattern, line)
            if func_match:
                # Save previous chunk
                if current_chunk:
                    chunks.append(current_chunk)
                
                indent, def_type, name = func_match.groups()
                current_indent = len(indent)
                
                current_chunk = {
                    'start_line': i + 1,
                    'name': name,
                    'type': ChunkType.FUNCTION,
                    'lines': [line],
                    'signature': line.strip()
                }
                continue
            
            # Check for class
            class_match = re.match(class_pattern, line)
            if class_match:
                # Save previous chunk
                if current_chunk:
                    chunks.append(current_chunk)
                
                indent, class_keyword, name = class_match.groups()
                current_indent = len(indent)
                
                current_chunk = {
                    'start_line': i + 1,
                    'name': name,
                    'type': ChunkType.CLASS,
                    'lines': [line],
                    'signature': line.strip()
                }
                continue
            
            # Add line to current chunk if within indentation
            if current_chunk:
                line_indent = len(line) - len(line.lstrip())
                if line.strip() == '' or line_indent > current_indent:
                    current_chunk['lines'].append(line)
                else:
                    # End of current chunk
                    chunks.append(current_chunk)
                    current_chunk = None
        
        # Add final chunk
        if current_chunk:
            chunks.append(current_chunk)
        
        # Convert to CodeChunk objects
        result_chunks = []
        for chunk_data in chunks:
            chunk_text = '\n'.join(chunk_data['lines'])
            
            result_chunks.append(CodeChunk(
                text=chunk_text,
                file_path=file_path,
                chunk_type=chunk_data['type'],
                language=language,
                start_line=chunk_data['start_line'],
                end_line=chunk_data['start_line'] + len(chunk_data['lines']) - 1,
                name=chunk_data['name'],
                signature=chunk_data['signature'],
                metadata={'lines_count': len(chunk_data['lines'])}
            ))
        
        return result_chunks
    
    def _chunk_javascript(self, content: str, file_path: str, language: Language) -> List[CodeChunk]:
        """Chunk JavaScript/TypeScript code using regex patterns"""
        chunks = []
        lines = content.split('\n')
        
        # Patterns for JavaScript/TypeScript
        patterns = [
            (r'^\s*(export\s+)?(async\s+)?function\s+(\w+)', ChunkType.FUNCTION),
            (r'^\s*(export\s+)?(default\s+)?class\s+(\w+)', ChunkType.CLASS),
            (r'^\s*(export\s+)?const\s+(\w+)\s*=\s*(async\s+)?\([^)]*\)\s*=>', ChunkType.FUNCTION),
            (r'^\s*(export\s+)?const\s+(\w+)\s*=\s*function', ChunkType.FUNCTION),
        ]
        
        current_chunks = []
        
        for i, line in enumerate(lines):
            for pattern, chunk_type in patterns:
                match = re.match(pattern, line)
                if match:
                    # Extract function/class name from the match groups
                    groups = match.groups()
                    name = groups[-1] if groups else 'unknown'
                    
                    # Find the end of this function/class by tracking braces
                    start_line = i + 1
                    end_line = self._find_js_block_end(lines, i)
                    
                    chunk_text = '\n'.join(lines[i:end_line])
                    
                    chunk = CodeChunk(
                        text=chunk_text,
                        file_path=file_path,
                        chunk_type=chunk_type,
                        language=language,
                        start_line=start_line,
                        end_line=end_line,
                        name=name,
                        signature=line.strip(),
                        metadata={
                            'is_exported': 'export' in line,
                            'is_async': 'async' in line
                        }
                    )
                    chunks.append(chunk)
                    break
        
        return chunks
    
    def _chunk_java(self, content: str, file_path: str, language: Language) -> List[CodeChunk]:
        """Chunk Java code using regex patterns"""
        chunks = []
        lines = content.split('\n')
        
        # Java patterns
        class_pattern = r'^\s*(public|private|protected)?\s*(abstract\s+)?class\s+(\w+)'
        method_pattern = r'^\s*(public|private|protected)\s+(static\s+)?(\w+|\w+<[^>]+>)\s+(\w+)\s*\([^)]*\)'
        
        for i, line in enumerate(lines):
            # Check for class
            class_match = re.match(class_pattern, line)
            if class_match:
                access, abstract, name = class_match.groups()
                start_line = i + 1
                end_line = self._find_java_block_end(lines, i)
                
                chunk_text = '\n'.join(lines[i:end_line])
                
                chunk = CodeChunk(
                    text=chunk_text,
                    file_path=file_path,
                    chunk_type=ChunkType.CLASS,
                    language=language,
                    start_line=start_line,
                    end_line=end_line,
                    name=name,
                    signature=line.strip(),
                    metadata={
                        'access_modifier': access,
                        'is_abstract': bool(abstract)
                    }
                )
                chunks.append(chunk)
                continue
            
            # Check for method
            method_match = re.match(method_pattern, line)
            if method_match:
                access, static, return_type, name = method_match.groups()
                start_line = i + 1
                end_line = self._find_java_block_end(lines, i)
                
                chunk_text = '\n'.join(lines[i:end_line])
                
                chunk = CodeChunk(
                    text=chunk_text,
                    file_path=file_path,
                    chunk_type=ChunkType.FUNCTION,
                    language=language,
                    start_line=start_line,
                    end_line=end_line,
                    name=name,
                    signature=line.strip(),
                    metadata={
                        'access_modifier': access,
                        'return_type': return_type,
                        'is_static': bool(static)
                    }
                )
                chunks.append(chunk)
        
        return chunks
    
    def _chunk_cpp(self, content: str, file_path: str, language: Language) -> List[CodeChunk]:
        """Chunk C/C++ code using regex patterns"""
        chunks = []
        lines = content.split('\n')
        
        # C/C++ patterns
        class_pattern = r'^\s*(class|struct)\s+(\w+)'
        function_pattern = r'^\s*(\w+(?:\s*\*)?|\w+<[^>]+>)\s+(\w+)\s*\([^)]*\)\s*\{'
        
        for i, line in enumerate(lines):
            # Check for class/struct
            class_match = re.match(class_pattern, line)
            if class_match:
                keyword, name = class_match.groups()
                start_line = i + 1
                end_line = self._find_cpp_block_end(lines, i)
                
                chunk_text = '\n'.join(lines[i:end_line])
                
                chunk = CodeChunk(
                    text=chunk_text,
                    file_path=file_path,
                    chunk_type=ChunkType.CLASS,
                    language=language,
                    start_line=start_line,
                    end_line=end_line,
                    name=name,
                    signature=line.strip(),
                    metadata={'type': keyword}
                )
                chunks.append(chunk)
                continue
            
            # Check for function
            func_match = re.match(function_pattern, line)
            if func_match:
                return_type, name = func_match.groups()
                start_line = i + 1
                end_line = self._find_cpp_block_end(lines, i)
                
                chunk_text = '\n'.join(lines[i:end_line])
                
                chunk = CodeChunk(
                    text=chunk_text,
                    file_path=file_path,
                    chunk_type=ChunkType.FUNCTION,
                    language=language,
                    start_line=start_line,
                    end_line=end_line,
                    name=name,
                    signature=line.strip(),
                    metadata={'return_type': return_type}
                )
                chunks.append(chunk)
        
        return chunks
    
    def _chunk_generic(self, content: str, file_path: str, language: Language) -> List[CodeChunk]:
        """Generic chunking for unsupported languages"""
        return self._chunk_by_logical_blocks(content, file_path, language)
    
    def _chunk_by_logical_blocks(self, content: str, file_path: str, language: Language) -> List[CodeChunk]:
        """Chunk content into logical blocks based on line patterns"""
        lines = content.split('\n')
        chunks = []
        
        chunk_size = 50  # Lines per chunk
        overlap = self.config.overlap_lines
        
        for i in range(0, len(lines), chunk_size - overlap):
            start_idx = i
            end_idx = min(i + chunk_size, len(lines))
            
            chunk_lines = lines[start_idx:end_idx]
            chunk_text = '\n'.join(chunk_lines)
            
            if chunk_text.strip():  # Skip empty chunks
                chunk = CodeChunk(
                    text=chunk_text,
                    file_path=file_path,
                    chunk_type=ChunkType.LINES,
                    language=language,
                    start_line=start_idx + 1,
                    end_line=end_idx,
                    metadata={
                        'chunk_index': i // (chunk_size - overlap),
                        'lines_count': len(chunk_lines)
                    }
                )
                chunks.append(chunk)
        
        return chunks
    
    def _find_js_block_end(self, lines: List[str], start_idx: int) -> int:
        """Find the end of a JavaScript block by tracking braces"""
        brace_count = 0
        in_block = False
        
        for i in range(start_idx, len(lines)):
            line = lines[i]
            
            for char in line:
                if char == '{':
                    brace_count += 1
                    in_block = True
                elif char == '}':
                    brace_count -= 1
                    
                    if in_block and brace_count == 0:
                        return i + 1
        
        return min(start_idx + 50, len(lines))  # Fallback
    
    def _find_java_block_end(self, lines: List[str], start_idx: int) -> int:
        """Find the end of a Java block by tracking braces"""
        return self._find_js_block_end(lines, start_idx)  # Same logic
    
    def _find_cpp_block_end(self, lines: List[str], start_idx: int) -> int:
        """Find the end of a C/C++ block by tracking braces"""
        return self._find_js_block_end(lines, start_idx)  # Same logic 

    def _chunk_labview(self, content: str, file_path: str, language: Language) -> List[CodeChunk]:
        """Chunk LabVIEW files (.vi, .lvproj, .ctl, etc.)"""
        chunks = []
        lines = content.split('\n')
        file_name = os.path.basename(file_path)
        file_ext = os.path.splitext(file_path)[1].lower()
        
        # Determine LabVIEW file type and extract relevant information
        if file_ext == '.vi':
            # Virtual Instrument file
            chunks.extend(self._process_labview_vi(content, file_path, lines))
        elif file_ext == '.lvproj':
            # LabVIEW Project file
            chunks.extend(self._process_labview_project(content, file_path, lines))
        elif file_ext == '.ctl':
            # Control file
            chunks.extend(self._process_labview_control(content, file_path, lines))
        elif file_ext in ['.lvlib', '.lvclass']:
            # Library or Class file
            chunks.extend(self._process_labview_library(content, file_path, lines))
        else:
            # Generic LabVIEW file processing
            chunks.extend(self._process_labview_generic(content, file_path, lines))
        
        # If no specific chunks were created, create a generic file chunk
        if not chunks:
            chunks.append(CodeChunk(
                text=content[:self.config.max_chunk_size],
                chunk_type=ChunkType.OTHER,
                start_line=1,
                end_line=len(lines),
                file_path=file_path,
                language=language,
                name=file_name,
                metadata={
                    'file_type': file_ext,
                    'labview_file': True,
                    'total_lines': len(lines)
                }
            ))
        
        return chunks
    
    def _process_labview_vi(self, content: str, file_path: str, lines: List[str]) -> List[CodeChunk]:
        """Process LabVIEW Virtual Instrument (.vi) files"""
        chunks = []
        file_name = os.path.splitext(os.path.basename(file_path))[0]
        
        # Try to parse as XML first
        try:
            if content.strip().startswith('<?xml') or '<VI' in content:
                root = ET.fromstring(content)
                
                # Extract VI information
                vi_info = self._extract_vi_info(root, file_path)
                
                # Create main VI chunk
                chunks.append(CodeChunk(
                    text=f"VI Name: {vi_info.get('name', file_name)}\n"
                         f"Description: {vi_info.get('description', 'No description')}\n"
                         f"Version: {vi_info.get('version', 'Unknown')}\n"
                         f"Controls: {len(vi_info.get('controls', []))}\n"
                         f"Indicators: {len(vi_info.get('indicators', []))}\n"
                         f"Functions: {len(vi_info.get('functions', []))}\n"
                         f"SubVIs: {', '.join(vi_info.get('subvis', []))}",
                    chunk_type=ChunkType.CLASS,  # Treat VI as a class-like entity
                    start_line=1,
                    end_line=len(lines),
                    file_path=file_path,
                    language=Language.LABVIEW,
                    name=vi_info.get('name', file_name),
                    metadata={
                        'vi_type': 'main',
                        'controls': vi_info.get('controls', []),
                        'indicators': vi_info.get('indicators', []),
                        'functions': vi_info.get('functions', []),
                        'subvis': vi_info.get('subvis', []),
                        'description': vi_info.get('description', ''),
                        'file_type': '.vi'
                    }
                ))
                
                # Create chunks for each control and indicator
                for control in vi_info.get('controls', []):
                    chunks.append(CodeChunk(
                        text=f"Control: {control['name']}\nType: {control.get('type', 'Unknown')}\nDescription: {control.get('description', '')}",
                        chunk_type=ChunkType.FUNCTION,
                        start_line=1,
                        end_line=1,
                        file_path=file_path,
                        language=Language.LABVIEW,
                        name=control['name'],
                        metadata={'component_type': 'control', 'data_type': control.get('type', 'Unknown')}
                    ))
                
                for indicator in vi_info.get('indicators', []):
                    chunks.append(CodeChunk(
                        text=f"Indicator: {indicator['name']}\nType: {indicator.get('type', 'Unknown')}\nDescription: {indicator.get('description', '')}",
                        chunk_type=ChunkType.FUNCTION,
                        start_line=1,
                        end_line=1,
                        file_path=file_path,
                        language=Language.LABVIEW,
                        name=indicator['name'],
                        metadata={'component_type': 'indicator', 'data_type': indicator.get('type', 'Unknown')}
                    ))
                
        except (ET.ParseError, Exception):
            # If XML parsing fails, treat as binary or text
            chunks.extend(self._process_labview_binary(content, file_path, lines))
        
        return chunks
    
    def _process_labview_project(self, content: str, file_path: str, lines: List[str]) -> List[CodeChunk]:
        """Process LabVIEW Project (.lvproj) files"""
        chunks = []
        file_name = os.path.splitext(os.path.basename(file_path))[0]
        
        try:
            if content.strip().startswith('<?xml') or '<Project' in content:
                root = ET.fromstring(content)
                
                # Extract project information
                project_info = self._extract_project_info(root, file_path)
                
                # Create main project chunk
                chunks.append(CodeChunk(
                    text=f"Project Name: {project_info.get('name', file_name)}\n"
                         f"Version: {project_info.get('version', 'Unknown')}\n"
                         f"VIs: {len(project_info.get('vis', []))}\n"
                         f"Libraries: {len(project_info.get('libraries', []))}\n"
                         f"Dependencies: {', '.join(project_info.get('dependencies', []))}",
                    chunk_type=ChunkType.CLASS,
                    start_line=1,
                    end_line=len(lines),
                    file_path=file_path,
                    language=Language.LABVIEW,
                    name=project_info.get('name', file_name),
                    metadata={
                        'project_type': 'main',
                        'vis': project_info.get('vis', []),
                        'libraries': project_info.get('libraries', []),
                        'dependencies': project_info.get('dependencies', []),
                        'file_type': '.lvproj'
                    }
                ))
                
        except (ET.ParseError, Exception):
            chunks.extend(self._process_labview_binary(content, file_path, lines))
        
        return chunks
    
    def _process_labview_control(self, content: str, file_path: str, lines: List[str]) -> List[CodeChunk]:
        """Process LabVIEW Control (.ctl) files"""
        chunks = []
        file_name = os.path.splitext(os.path.basename(file_path))[0]
        
        # Control files define custom controls
        chunks.append(CodeChunk(
            text=f"Custom Control: {file_name}\nDefinition: {content[:500]}...",
            chunk_type=ChunkType.CLASS,
            start_line=1,
            end_line=len(lines),
            file_path=file_path,
            language=Language.LABVIEW,
            name=file_name,
            metadata={
                'component_type': 'custom_control',
                'file_type': '.ctl'
            }
        ))
        
        return chunks
    
    def _process_labview_library(self, content: str, file_path: str, lines: List[str]) -> List[CodeChunk]:
        """Process LabVIEW Library (.lvlib) and Class (.lvclass) files"""
        chunks = []
        file_name = os.path.splitext(os.path.basename(file_path))[0]
        file_ext = os.path.splitext(file_path)[1].lower()
        
        try:
            if content.strip().startswith('<?xml') or '<Library' in content or '<LVClass' in content:
                root = ET.fromstring(content)
                
                # Extract library/class information
                lib_info = self._extract_library_info(root, file_path)
                
                chunk_type = ChunkType.CLASS if file_ext == '.lvclass' else ChunkType.OTHER
                component_type = 'class' if file_ext == '.lvclass' else 'library'
                
                chunks.append(CodeChunk(
                    text=f"{component_type.title()}: {lib_info.get('name', file_name)}\n"
                         f"Members: {len(lib_info.get('members', []))}\n"
                         f"Dependencies: {', '.join(lib_info.get('dependencies', []))}",
                    chunk_type=chunk_type,
                    start_line=1,
                    end_line=len(lines),
                    file_path=file_path,
                    language=Language.LABVIEW,
                    name=lib_info.get('name', file_name),
                    metadata={
                        'component_type': component_type,
                        'members': lib_info.get('members', []),
                        'dependencies': lib_info.get('dependencies', []),
                        'file_type': file_ext
                    }
                ))
                
        except (ET.ParseError, Exception):
            chunks.extend(self._process_labview_binary(content, file_path, lines))
        
        return chunks
    
    def _process_labview_generic(self, content: str, file_path: str, lines: List[str]) -> List[CodeChunk]:
        """Process generic LabVIEW files"""
        chunks = []
        file_name = os.path.splitext(os.path.basename(file_path))[0]
        
        # Create a generic chunk for the file
        chunks.append(CodeChunk(
            text=content[:self.config.max_chunk_size],
            chunk_type=ChunkType.OTHER,
            start_line=1,
            end_line=len(lines),
            file_path=file_path,
            language=Language.LABVIEW,
            name=file_name,
            metadata={
                'file_type': os.path.splitext(file_path)[1].lower(),
                'labview_file': True
            }
        ))
        
        return chunks
    
    def _process_labview_binary(self, content: str, file_path: str, lines: List[str]) -> List[CodeChunk]:
        """Process binary LabVIEW files by extracting readable text"""
        chunks = []
        file_name = os.path.splitext(os.path.basename(file_path))[0]
        
        # Extract readable text from binary content
        readable_text = re.findall(r'[a-zA-Z0-9\s\.\-_]{4,}', content)
        text_content = ' '.join(readable_text[:50])  # Limit to first 50 readable strings
        
        chunks.append(CodeChunk(
            text=f"Binary LabVIEW File: {file_name}\nExtracted Text: {text_content}",
            chunk_type=ChunkType.OTHER,
            start_line=1,
            end_line=len(lines),
            file_path=file_path,
            language=Language.LABVIEW,
            name=file_name,
            metadata={
                'file_type': 'binary',
                'extracted_text_count': len(readable_text),
                'labview_file': True
            }
        ))
        
        return chunks
    
    def _extract_vi_info(self, root: ET.Element, file_path: str) -> Dict[str, Any]:
        """Extract information from VI XML"""
        info = {
            'name': os.path.splitext(os.path.basename(file_path))[0],
            'description': '',
            'version': '',
            'controls': [],
            'indicators': [],
            'functions': [],
            'subvis': []
        }
        
        # Try to extract various VI components (this is a simplified extraction)
        try:
            # Look for version info
            version_elem = root.find('.//Version')
            if version_elem is not None:
                info['version'] = version_elem.text or ''
            
            # Look for description
            desc_elem = root.find('.//Description')
            if desc_elem is not None:
                info['description'] = desc_elem.text or ''
            
            # Look for controls and indicators (simplified)
            for elem in root.iter():
                if 'Control' in elem.tag:
                    info['controls'].append({
                        'name': elem.get('name', f'Control_{len(info["controls"])}'),
                        'type': elem.get('type', 'Unknown')
                    })
                elif 'Indicator' in elem.tag:
                    info['indicators'].append({
                        'name': elem.get('name', f'Indicator_{len(info["indicators"])}'),
                        'type': elem.get('type', 'Unknown')
                    })
                elif 'SubVI' in elem.tag or 'VI' in elem.tag:
                    vi_name = elem.get('name', elem.text)
                    if vi_name and vi_name not in info['subvis']:
                        info['subvis'].append(vi_name)
        
        except Exception:
            pass  # If extraction fails, return basic info
        
        return info
    
    def _extract_project_info(self, root: ET.Element, file_path: str) -> Dict[str, Any]:
        """Extract information from LabVIEW Project XML"""
        info = {
            'name': os.path.splitext(os.path.basename(file_path))[0],
            'version': '',
            'vis': [],
            'libraries': [],
            'dependencies': []
        }
        
        try:
            # Look for project name
            name_elem = root.find('.//Name')
            if name_elem is not None:
                info['name'] = name_elem.text or info['name']
            
            # Look for VIs and libraries
            for elem in root.iter():
                if elem.tag.endswith('.vi'):
                    info['vis'].append(elem.text or elem.get('Include', ''))
                elif elem.tag.endswith('.lvlib'):
                    info['libraries'].append(elem.text or elem.get('Include', ''))
                elif 'Dependency' in elem.tag:
                    dep = elem.text or elem.get('Name', '')
                    if dep:
                        info['dependencies'].append(dep)
        
        except Exception:
            pass
        
        return info
    
    def _extract_library_info(self, root: ET.Element, file_path: str) -> Dict[str, Any]:
        """Extract information from LabVIEW Library/Class XML"""
        info = {
            'name': os.path.splitext(os.path.basename(file_path))[0],
            'members': [],
            'dependencies': []
        }
        
        try:
            # Look for library name
            name_elem = root.find('.//Name')
            if name_elem is not None:
                info['name'] = name_elem.text or info['name']
            
            # Look for members and dependencies
            for elem in root.iter():
                if 'Member' in elem.tag or 'Item' in elem.tag:
                    member = elem.text or elem.get('Name', '')
                    if member:
                        info['members'].append(member)
                elif 'Dependency' in elem.tag:
                    dep = elem.text or elem.get('Name', '')
                    if dep:
                        info['dependencies'].append(dep)
        
        except Exception:
            pass
        
        return info 