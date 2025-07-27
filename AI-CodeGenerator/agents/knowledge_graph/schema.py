"""
Simple Schema for Vector-Based Code Analysis
Focuses on code chunks rather than complex graph relationships.
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from enum import Enum


class ChunkType(Enum):
    """Types of code chunks"""
    FILE = "file"           # Entire small file
    CLASS = "class"         # Class definition
    FUNCTION = "function"   # Function/method definition
    BLOCK = "block"         # Logical code block
    LINES = "lines"         # Line-based chunk


class Language(Enum):
    """Supported programming languages"""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    CPP = "cpp"
    C = "c"
    CSHARP = "csharp"
    GO = "go"
    RUST = "rust"
    PHP = "php"
    RUBY = "ruby"
    LABVIEW = "labview"
    UNKNOWN = "unknown"


@dataclass
class CodeChunk:
    """A chunk of code with metadata and embedding"""
    
    # Core content
    text: str                           # The actual code content
    file_path: str                      # Relative path from repository root
    chunk_type: ChunkType              # Type of chunk
    language: Language                 # Programming language
    
    # Position metadata
    start_line: Optional[int] = None    # Starting line number
    end_line: Optional[int] = None      # Ending line number
    
    # Code metadata
    name: Optional[str] = None          # Function/class name if applicable
    signature: Optional[str] = None     # Function signature or class declaration
    docstring: Optional[str] = None     # Documentation string
    
    # Vector data
    embedding: Optional[List[float]] = None  # Vector embedding
    
    # Additional metadata
    metadata: Dict[str, Any] = None     # Additional language-specific metadata
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ChunkingResult:
    """Result of chunking a repository"""
    
    chunks: List[CodeChunk]             # All extracted chunks
    total_files: int                    # Number of files processed
    total_lines: int                    # Total lines of code
    language_stats: Dict[Language, int] # Files per language
    chunk_stats: Dict[ChunkType, int]   # Chunks per type
    
    def summary(self) -> str:
        """Generate a summary string"""
        return (
            f"Processed {self.total_files} files, {self.total_lines} lines, "
            f"created {len(self.chunks)} chunks"
        )


@dataclass
class SearchResult:
    """Result of a vector search"""
    
    chunk: CodeChunk                    # The matching chunk
    similarity: float                   # Similarity score (0-1)
    relevance_snippet: str             # Highlighted relevant part
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'file_path': self.chunk.file_path,
            'chunk_type': self.chunk.chunk_type.value,
            'language': self.chunk.language.value,
            'name': self.chunk.name,
            'signature': self.chunk.signature,
            'similarity': self.similarity,
            'snippet': self.relevance_snippet,
            'start_line': self.chunk.start_line,
            'end_line': self.chunk.end_line,
            'metadata': self.chunk.metadata
        }


class ChunkingConfig:
    """Configuration for chunking strategy"""
    
    def __init__(self):
        # File size thresholds
        self.small_file_threshold = 2000      # Treat as single chunk
        self.max_chunk_size = 500           # Maximum chunk size in characters
        self.min_chunk_size = 50           # Minimum chunk size
        
        # Chunking strategy
        self.overlap_lines = 10               # Lines of overlap between chunks
        self.prefer_function_chunks = True   # Prefer function-level chunks
        self.include_docstrings = True       # Include docstrings in chunks
        
        # Language-specific settings
        self.language_settings = {
            Language.PYTHON: {
                'function_patterns': [r'def\s+\w+', r'class\s+\w+'],
                'comment_patterns': [r'#.*', r'""".*?"""', r"'''.*?'''"],
            },
            Language.JAVASCRIPT: {
                'function_patterns': [r'function\s+\w+', r'class\s+\w+', r'const\s+\w+\s*='],
                'comment_patterns': [r'//.*', r'/\*.*?\*/'],
            },
            Language.JAVA: {
                'function_patterns': [r'public\s+\w+', r'private\s+\w+', r'class\s+\w+'],
                'comment_patterns': [r'//.*', r'/\*.*?\*/'],
            }
        }
        
        # File filtering
        self.exclude_patterns = [
            'node_modules', '__pycache__', '.git', 'venv', 'env',
            'build', 'dist', 'target', '.idea', '.vscode',
            '*.pyc', '*.class', '*.o', '*.so', '*.dll'
        ]
        
        self.include_extensions = [
            '.py', '.js', '.ts', '.java', '.cpp', '.c', '.cs',
            '.go', '.rs', '.php', '.rb', '.scala', '.kt',
            # LabVIEW file extensions
            '.vi', '.lvproj', '.ctl', '.lvlib', '.lvclass', 
            '.xctl', '.vit', '.lvsc'
        ]


def detect_language(file_path: str) -> Language:
    """Detect programming language from file extension"""
    
    extension_map = {
        '.py': Language.PYTHON,
        '.js': Language.JAVASCRIPT,
        '.ts': Language.TYPESCRIPT,
        '.tsx': Language.TYPESCRIPT,
        '.jsx': Language.JAVASCRIPT,
        '.java': Language.JAVA,
        '.cpp': Language.CPP,
        '.cc': Language.CPP,
        '.cxx': Language.CPP,
        '.c': Language.C,
        '.cs': Language.CSHARP,
        '.go': Language.GO,
        '.rs': Language.RUST,
        '.php': Language.PHP,
        '.rb': Language.RUBY,
        '.scala': Language.UNKNOWN,  # Can be added later
        '.kt': Language.UNKNOWN,     # Kotlin
        # LabVIEW file extensions
        '.vi': Language.LABVIEW,      # Virtual Instrument
        '.lvproj': Language.LABVIEW,  # LabVIEW Project
        '.ctl': Language.LABVIEW,     # Control
        '.lvlib': Language.LABVIEW,   # LabVIEW Library
        '.lvclass': Language.LABVIEW, # LabVIEW Class
        '.xctl': Language.LABVIEW,    # XControl
        '.vit': Language.LABVIEW,     # VI Template
        '.lvsc': Language.LABVIEW,    # LabVIEW Source Control
    }
    
    import os
    ext = os.path.splitext(file_path)[1].lower()
    return extension_map.get(ext, Language.UNKNOWN) 