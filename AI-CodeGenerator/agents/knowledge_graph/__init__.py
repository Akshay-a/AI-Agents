"""
Simple Vector-Based Knowledge Graph Agent Module
Provides code analysis and semantic search for cloned repositories.
"""

from .knowledge_graph_agent import KnowledgeGraphAgent
from .schema import (
    CodeChunk, ChunkType, Language, ChunkingResult, SearchResult, 
    ChunkingConfig, detect_language
)
from .chunker import CodeChunker
from .vector_store import VectorStore, SessionVectorStore
from .query_engine import QueryEngine, BatchQueryEngine

__all__ = [
    # Main agent
    'KnowledgeGraphAgent',
    
    # Core schema components
    'CodeChunk',
    'ChunkType', 
    'Language',
    'ChunkingResult',
    'SearchResult',
    'ChunkingConfig',
    'detect_language',
    
    # Processing components  
    'CodeChunker',
    'VectorStore',
    'SessionVectorStore',
    'QueryEngine',
    'BatchQueryEngine'
]

# Version info
__version__ = "2.0.0"
__description__ = "Simple vector-based code analysis for AI agents" 