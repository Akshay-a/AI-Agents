"""
Simple Vector-Based Knowledge Graph Agent
Replaces complex graph analysis with efficient vector search for code understanding.
"""

import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from ..base.agent_interface import BaseAgent, AgentInput, AgentOutput, AgentStatus
from .chunker import CodeChunker, ChunkingConfig
from .vector_store import VectorStore, SessionVectorStore
from .query_engine import QueryEngine, BatchQueryEngine
from .schema import ChunkingResult, Language, ChunkType


class KnowledgeGraphAgent(BaseAgent):
    """
    Plain embedding of a file to generate semantic understanding of code
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(agent_id="knowledge_graph_agent", config=config)
        
        # Initialize components
        self.chunking_config = ChunkingConfig()
        self.chunker = CodeChunker(self.chunking_config)
        self.session_stores = SessionVectorStore()
        
        # Agent state
        self.supported_operations = [
            'analyze_repository',
            'search_code', 
            'find_similar',
            'find_functions',
            'find_classes',
            'find_patterns',
            'get_statistics',
            'cleanup_session'
        ]
        
        self.logger.info("Initialized Simple Vector-Based Knowledge Graph Agent")
    
    def validate_input(self, agent_input: AgentInput) -> bool:
        """Validate input for supported operations"""
        data = agent_input.data
        operation = data.get('operation')
        
        if operation not in self.supported_operations:
            self.logger.error(f"Unsupported operation: {operation}")
            return False
        
        # Operation-specific validation
        if operation == 'analyze_repository':
            if 'repository_path' not in data:
                self.logger.error("Missing repository_path for analyze_repository")
                return False
            
            repo_path = data['repository_path']
            if not os.path.exists(repo_path):
                self.logger.error(f"Repository path does not exist: {repo_path}")
                return False
        
        elif operation in ['search_code', 'find_similar', 'find_functions', 'find_classes', 'find_patterns']:
            if 'query' not in data:
                self.logger.error(f"Missing query for {operation}")
                return False
        
        return True
    
    def process(self, agent_input: AgentInput) -> AgentOutput:
        """Process the agent input and return results"""
        start_time = agent_input.timestamp
        operation = agent_input.data.get('operation')
        session_id = agent_input.session_id
        
        self.logger.info(f"Processing {operation} for session {session_id}")
        
        try:
            # Route to appropriate handler
            if operation == 'analyze_repository':
                result = self._analyze_repository(agent_input.data, session_id)
            elif operation == 'search_code':
                result = self._search_code(agent_input.data, session_id)
            elif operation == 'find_similar':
                result = self._find_similar(agent_input.data, session_id)
            elif operation == 'find_functions':
                result = self._find_functions(agent_input.data, session_id)
            elif operation == 'find_classes':
                result = self._find_classes(agent_input.data, session_id)
            elif operation == 'find_patterns':
                result = self._find_patterns(agent_input.data, session_id)
            elif operation == 'get_statistics':
                result = self._get_statistics(session_id)
            elif operation == 'cleanup_session':
                result = self._cleanup_session(session_id)
            else:
                raise ValueError(f"Unknown operation: {operation}")
            
            return self._create_success_output(session_id, start_time, result)
            
        except Exception as e:
            self.logger.error(f"Error processing {operation}: {str(e)}")
            return self._create_error_output(session_id, start_time, str(e))
    
    def _analyze_repository(self, data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Analyze a repository and create vector embeddings"""
        repository_path = data['repository_path']
        
        self.logger.info(f"Analyzing repository: {repository_path}")
        
        # Chunk the repository
        chunking_result = self.chunker.chunk_repository(repository_path)
        
        # Get or create vector store for this session
        vector_store = self.session_stores.get_store(session_id)
        
        # Generate embeddings
        vector_store.add_chunks(chunking_result.chunks)
        
        self.logger.info(f"Analysis complete: {chunking_result.summary()}")
        
        return {
            'repository_path': repository_path,
            'analysis_summary': chunking_result.summary(),
            'statistics': {
                'total_files': chunking_result.total_files,
                'total_lines': chunking_result.total_lines,
                'total_chunks': len(chunking_result.chunks),
                'language_distribution': {lang.value: count for lang, count in chunking_result.language_stats.items()},
                'chunk_type_distribution': {chunk_type.value: count for chunk_type, count in chunking_result.chunk_stats.items()},
            },
            'ready_for_search': True,
            'session_id': session_id
        }
    
    def _search_code(self, data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Perform semantic code search"""
        query = data['query']
        max_results = data.get('max_results', 10)
        filters = data.get('filters', {})
        
        # Get vector store and query engine
        vector_store = self.session_stores.get_store(session_id)
        query_engine = QueryEngine(vector_store)
        
        # Perform search
        results = query_engine.search(query, max_results, filters)
        
        # Convert results to serializable format
        search_results = [result.to_dict() for result in results]
        
        return {
            'query': query,
            'results': search_results,
            'total_results': len(search_results),
            'explanation': query_engine.explain_results(results)
        }
    
    def _find_similar(self, data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Find code similar to a reference"""
        query = data['query']
        max_results = data.get('max_results', 10)
        
        # Get vector store and query engine
        vector_store = self.session_stores.get_store(session_id)
        query_engine = QueryEngine(vector_store)
        
        # First, find the reference chunk by searching
        reference_results = query_engine.search(query, max_results=1)
        
        if not reference_results:
            return {
                'query': query,
                'error': 'No reference code found for similarity search',
                'results': []
            }
        
        reference_chunk = reference_results[0].chunk
        
        # Find similar chunks
        similar_results = query_engine.find_similar_code(
            reference_chunk, 
            max_results=max_results
        )
        
        search_results = [result.to_dict() for result in similar_results]
        
        return {
            'query': query,
            'reference': reference_results[0].to_dict(),
            'similar_results': search_results,
            'total_results': len(search_results)
        }
    
    def _find_functions(self, data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Find functions matching the query"""
        query = data['query']
        max_results = data.get('max_results', 10)
        
        # Get vector store and query engine
        vector_store = self.session_stores.get_store(session_id)
        query_engine = QueryEngine(vector_store)
        
        # Search for functions
        results = query_engine.find_functions(query, max_results)
        
        search_results = [result.to_dict() for result in results]
        
        return {
            'query': query,
            'search_type': 'functions',
            'results': search_results,
            'total_results': len(search_results)
        }
    
    def _find_classes(self, data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Find classes matching the query"""
        query = data['query']
        max_results = data.get('max_results', 10)
        
        # Get vector store and query engine
        vector_store = self.session_stores.get_store(session_id)
        query_engine = QueryEngine(vector_store)
        
        # Search for classes
        results = query_engine.find_classes(query, max_results)
        
        search_results = [result.to_dict() for result in results]
        
        return {
            'query': query,
            'search_type': 'classes',
            'results': search_results,
            'total_results': len(search_results)
        }
    
    def _find_patterns(self, data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Find code patterns matching the description"""
        query = data['query']
        max_results = data.get('max_results', 10)
        
        # Get vector store and query engine
        vector_store = self.session_stores.get_store(session_id)
        query_engine = QueryEngine(vector_store)
        
        # Search for patterns
        results = query_engine.find_patterns(query, max_results)
        
        search_results = [result.to_dict() for result in results]
        
        return {
            'query': query,
            'search_type': 'patterns',
            'results': search_results,
            'total_results': len(search_results)
        }
    
    def _get_statistics(self, session_id: str) -> Dict[str, Any]:
        """Get statistics for the current session"""
        stats = self.session_stores.get_session_stats(session_id)
        
        if stats is None:
            return {
                'session_id': session_id,
                'error': 'No data found for this session',
                'analyzed': False
            }
        
        return {
            'session_id': session_id,
            'statistics': stats,
            'analyzed': True
        }
    
    def _cleanup_session(self, session_id: str) -> Dict[str, Any]:
        """Clean up session data"""
        removed = self.session_stores.remove_store(session_id)
        
        return {
            'session_id': session_id,
            'cleaned': removed,
            'message': 'Session cleaned successfully' if removed else 'No session data to clean'
        }
    
    def _create_success_output(self, session_id: str, start_time: datetime, result: Dict[str, Any]) -> AgentOutput:
        """Create a successful agent output"""
        processing_time = (datetime.now() - start_time).total_seconds()
        return AgentOutput(
            agent_id=self.agent_id,
            session_id=session_id,
            status=AgentStatus.SUCCESS,
            data=result,
            execution_time_ms=int(processing_time * 1000),
            timestamp=datetime.now(),
            metadata={
                'processing_time': processing_time,
                'agent_type': 'vector_knowledge_graph'
            }
        )
    
    def _create_error_output(self, session_id: str, start_time: datetime, error_message: str) -> AgentOutput:
        """Create an error agent output"""
        processing_time = (datetime.now() - start_time).total_seconds()
        return AgentOutput(
            agent_id=self.agent_id,
            session_id=session_id,
            status=AgentStatus.ERROR,
            data={'error': error_message},
            execution_time_ms=int(processing_time * 1000),
            timestamp=datetime.now(),
            error_message=error_message,
            metadata={
                'processing_time': processing_time,
                'agent_type': 'vector_knowledge_graph'
            }
        )


# Example usage functions for testing
def create_sample_agent_input(operation: str, data: Dict[str, Any], session_id: str = "test_session") -> AgentInput:
    """Create a sample agent input for testing"""
    return AgentInput(
        agent_id="knowledge_graph_agent",
        session_id=session_id,
        timestamp=datetime.now(),
        data={"operation": operation, **data}
    )


def demo_repository_analysis(repo_path: str = ".") -> None:
    """Demo function to show repository analysis"""
    agent = KnowledgeGraphAgent()
    
    # Analyze repository
    analyze_input = create_sample_agent_input(
        "analyze_repository", 
        {"repository_path": repo_path}
    )
    
    analyze_output = agent.process(analyze_input)
    print("=== Repository Analysis ===")
    print(f"Success: {analyze_output.success}")
    if analyze_output.success:
        print(f"Summary: {analyze_output.data['analysis_summary']}")
        print(f"Statistics: {analyze_output.data['statistics']}")
    else:
        print(f"Error: {analyze_output.data.get('error')}")
    
    # Search for code
    if analyze_output.success:
        search_input = create_sample_agent_input(
            "search_code",
            {"query": "authentication", "max_results": 5}
        )
        
        search_output = agent.process(search_input)
        print("\n=== Code Search ===")
        print(f"Success: {search_output.success}")
        if search_output.success:
            results = search_output.data['results']
            print(f"Found {len(results)} results for 'authentication'")
            for i, result in enumerate(results[:3]):
                print(f"{i+1}. {result['file_path']} - {result['name']} (similarity: {result['similarity']:.3f})")
    
    # Cleanup
    cleanup_input = create_sample_agent_input("cleanup_session", {})
    agent.process(cleanup_input)
    print("\n=== Session cleaned up ===")


if __name__ == "__main__":
    # Run demo
    demo_repository_analysis() 