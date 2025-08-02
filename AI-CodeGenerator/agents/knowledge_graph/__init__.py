"""
Simple Vector-Based Knowledge Graph Agent Module
Provides code analysis and semantic search for cloned repositories.
"""

from .knowledge_graph_agent import KnowledgeGraphAgent, ChunkType, Language, CodeChunk, SearchResult, detect_language

__all__ = [
    'KnowledgeGraphAgent',
    'ChunkType',
    'Language',
    'CodeChunk',
    'SearchResult',
    'detect_language'
]

__version__ = "3.0.0"
__description__ = "Simplified Chroma-based code analysis agent" 