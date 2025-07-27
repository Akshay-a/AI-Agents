"""
Simple Query Engine for Vector-Based Code Search
Provides simple query interface for semantic code search.
"""

from typing import List, Dict, Any, Optional
import re
import logging

from .schema import SearchResult, CodeChunk, ChunkType, Language
from .vector_store import VectorStore


class QueryEngine:
    """Simple query engine for vector-based code search"""
    
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
        self.logger = logging.getLogger(__name__)
    
    def search(self, query: str, max_results: int = 10, 
               filters: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        """
        Main search method - performs semantic search
        
        Args:
            query: Natural language search query
            max_results: Maximum number of results to return
            filters: Optional filters (language, chunk_type, file_path, etc.)
        
        Returns:
            List of SearchResult objects ranked by relevance
        """
        self.logger.info(f"Searching for: '{query}' with filters: {filters}")
        
        # Enhance query for better semantic matching
        enhanced_query = self._enhance_query(query)
        
        # Perform vector search
        results = self.vector_store.search(
            query=enhanced_query,
            top_k=max_results,
            filters=filters
        )
        
        self.logger.info(f"Found {len(results)} results")
        return results
    
    def find_similar_code(self, reference_chunk: CodeChunk, max_results: int = 10,
                         exclude_same_file: bool = True) -> List[SearchResult]:
        """
        Find code chunks similar to a reference chunk
        
        Args:
            reference_chunk: The reference chunk to find similar code for
            max_results: Maximum number of results
            exclude_same_file: Whether to exclude chunks from the same file
        
        Returns:
            List of similar code chunks
        """
        self.logger.info(f"Finding code similar to: {reference_chunk.name}")
        
        results = self.vector_store.search_by_similarity(
            reference_chunk=reference_chunk,
            top_k=max_results,
            exclude_same_file=exclude_same_file
        )
        
        return results
    
    def search_by_type(self, query: str, chunk_type: ChunkType, 
                      max_results: int = 10) -> List[SearchResult]:
        """
        Search for specific types of code (functions, classes, etc.)
        
        Args:
            query: Search query
            chunk_type: Type of code chunk to search for
            max_results: Maximum results
        
        Returns:
            List of matching code chunks of the specified type
        """
        filters = {"chunk_type": chunk_type.value}
        return self.search(query, max_results, filters)
    
    def search_by_language(self, query: str, language: Language,
                          max_results: int = 10) -> List[SearchResult]:
        """
        Search within a specific programming language
        
        Args:
            query: Search query
            language: Programming language to search in
            max_results: Maximum results
        
        Returns:
            List of matching code chunks in the specified language
        """
        filters = {"language": language.value}
        return self.search(query, max_results, filters)
    
    def search_in_file(self, query: str, file_path: str,
                      max_results: int = 10) -> List[SearchResult]:
        """
        Search within a specific file
        
        Args:
            query: Search query
            file_path: Path to search within (partial match)
            max_results: Maximum results
        
        Returns:
            List of matching code chunks from the specified file
        """
        filters = {"file_path": file_path}
        return self.search(query, max_results, filters)
    
    def find_functions(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Find functions matching the query"""
        return self.search_by_type(query, ChunkType.FUNCTION, max_results)
    
    def find_classes(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Find classes matching the query"""
        return self.search_by_type(query, ChunkType.CLASS, max_results)
    
    def find_patterns(self, pattern_description: str, max_results: int = 10) -> List[SearchResult]:
        """
        Find code patterns based on description
        
        Args:
            pattern_description: Description of the pattern to find
            max_results: Maximum results
        
        Returns:
            List of code chunks matching the pattern
        """
        # Enhance the query with pattern-related keywords
        enhanced_query = f"pattern {pattern_description} implementation example"
        return self.search(enhanced_query, max_results)
    
    def find_by_name(self, name: str, max_results: int = 10) -> List[SearchResult]:
        """
        Find code by function/class name
        
        Args:
            name: Name to search for
            max_results: Maximum results
        
        Returns:
            List of code chunks with matching names
        """
        filters = {"name": name}
        return self.search(name, max_results, filters)
    
    def get_suggestions(self, partial_query: str, max_suggestions: int = 5) -> List[str]:
        """
        Get search suggestions based on partial query
        
        Args:
            partial_query: Partial search query
            max_suggestions: Maximum number of suggestions
        
        Returns:
            List of suggested queries
        """
        suggestions = []
        
        # Common code search patterns
        common_patterns = [
            "authentication", "database connection", "error handling",
            "logging", "configuration", "API endpoint", "validation",
            "serialization", "testing", "caching", "security"
        ]
        
        # Find matching patterns
        query_lower = partial_query.lower()
        for pattern in common_patterns:
            if query_lower in pattern or pattern.startswith(query_lower):
                suggestions.append(pattern)
        
        # Get suggestions from existing chunk names
        if self.vector_store.chunks:
            for chunk in self.vector_store.chunks:
                if chunk.name and query_lower in chunk.name.lower():
                    suggestions.append(chunk.name)
        
        # Remove duplicates and limit results
        suggestions = list(set(suggestions))[:max_suggestions]
        
        return suggestions
    
    def explain_results(self, results: List[SearchResult]) -> Dict[str, Any]:
        """
        Provide explanation of search results
        
        Args:
            results: List of search results
        
        Returns:
            Dictionary with analysis of the results
        """
        if not results:
            return {"total": 0, "message": "No results found"}
        
        # Analyze results
        language_dist = {}
        type_dist = {}
        file_dist = {}
        
        for result in results:
            chunk = result.chunk
            
            # Language distribution
            lang = chunk.language.value
            language_dist[lang] = language_dist.get(lang, 0) + 1
            
            # Type distribution
            chunk_type = chunk.chunk_type.value
            type_dist[chunk_type] = type_dist.get(chunk_type, 0) + 1
            
            # File distribution
            file_path = chunk.file_path
            file_dist[file_path] = file_dist.get(file_path, 0) + 1
        
        # Find best match
        best_match = results[0]
        
        return {
            "total": len(results),
            "best_match": {
                "file": best_match.chunk.file_path,
                "name": best_match.chunk.name,
                "type": best_match.chunk.chunk_type.value,
                "similarity": best_match.similarity
            },
            "language_distribution": language_dist,
            "type_distribution": type_dist,
            "files_found": list(file_dist.keys()),
            "avg_similarity": sum(r.similarity for r in results) / len(results)
        }
    
    def _enhance_query(self, query: str) -> str:
        """
        Enhance the query for better semantic matching
        
        Args:
            query: Original query
        
        Returns:
            Enhanced query string
        """
        # Add common programming terms based on query content
        enhancements = []
        
        query_lower = query.lower()
        
        # Authentication related
        if any(term in query_lower for term in ['auth', 'login', 'password', 'token']):
            enhancements.extend(['authentication', 'security', 'credentials'])
        
        # Database related
        if any(term in query_lower for term in ['db', 'database', 'sql', 'query']):
            enhancements.extend(['database', 'connection', 'orm'])
        
        # API related
        if any(term in query_lower for term in ['api', 'endpoint', 'request', 'response']):
            enhancements.extend(['api', 'http', 'rest'])
        
        # Error handling
        if any(term in query_lower for term in ['error', 'exception', 'try', 'catch']):
            enhancements.extend(['error handling', 'exception', 'validation'])
        
        # Configuration
        if any(term in query_lower for term in ['config', 'setting', 'env']):
            enhancements.extend(['configuration', 'settings', 'environment'])
        
        # Testing
        if any(term in query_lower for term in ['test', 'mock', 'assert']):
            enhancements.extend(['testing', 'unit test', 'assertion'])
        
        # Combine original query with enhancements
        if enhancements:
            return f"{query} {' '.join(enhancements)}"
        
        return query
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get query engine statistics"""
        return self.vector_store.get_statistics()


class BatchQueryEngine:
    """Handles batch queries for multiple searches"""
    
    def __init__(self, query_engine: QueryEngine):
        self.query_engine = query_engine
        self.logger = logging.getLogger(__name__)
    
    def batch_search(self, queries: List[str], max_results_per_query: int = 5) -> Dict[str, List[SearchResult]]:
        """
        Perform multiple searches in batch
        
        Args:
            queries: List of search queries
            max_results_per_query: Maximum results per query
        
        Returns:
            Dictionary mapping queries to their results
        """
        results = {}
        
        for query in queries:
            try:
                search_results = self.query_engine.search(query, max_results_per_query)
                results[query] = search_results
            except Exception as e:
                self.logger.error(f"Error searching for '{query}': {e}")
                results[query] = []
        
        return results
    
    def find_related_concepts(self, concept: str, max_concepts: int = 10) -> List[SearchResult]:
        """
        Find code related to a specific concept
        
        Args:
            concept: The concept to find related code for
            max_concepts: Maximum number of related concepts to find
        
        Returns:
            List of code chunks related to the concept
        """
        # Search for the main concept
        main_results = self.query_engine.search(concept, max_concepts)
        
        # If we have results, find similar code
        if main_results:
            related_results = []
            for result in main_results[:3]:  # Use top 3 results as seeds
                similar = self.query_engine.find_similar_code(
                    result.chunk, 
                    max_results=3, 
                    exclude_same_file=True
                )
                related_results.extend(similar)
            
            # Combine and deduplicate
            all_results = main_results + related_results
            seen_chunks = set()
            unique_results = []
            
            for result in all_results:
                chunk_id = f"{result.chunk.file_path}:{result.chunk.start_line}"
                if chunk_id not in seen_chunks:
                    seen_chunks.add(chunk_id)
                    unique_results.append(result)
            
            return unique_results[:max_concepts]
        
        return main_results 