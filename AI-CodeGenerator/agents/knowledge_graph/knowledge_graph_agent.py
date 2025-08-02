import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import chromadb
from chromadb.utils import embedding_functions
from transformers import AutoTokenizer, AutoModel
import torch

from agents.base.agent_interface import BaseAgent, AgentInput, AgentOutput, AgentStatus


class ChunkType:
    FILE = "file"
    BLOCK = "block"

class Language:
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    # Add other languages as needed
    UNKNOWN = "unknown"

class CodeChunk:
    def __init__(self, text: str, file_path: str, chunk_type: str, language: str, start_line: int = None, end_line: int = None, name: Optional[str] = None):
        self.text = text
        self.file_path = file_path
        self.chunk_type = chunk_type
        self.language = language
        self.start_line = start_line
        self.end_line = end_line
        self.name = name

    def to_dict(self):
        return {
            "text": self.text,
            "file_path": self.file_path,
            "chunk_type": self.chunk_type,
            "language": self.language,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "name": self.name
        }

class SearchResult:
    def __init__(self, chunk: CodeChunk, similarity: float):
        self.chunk = chunk
        self.similarity = similarity

    def to_dict(self):
        return {
            "chunk": self.chunk.to_dict(),
            "similarity": self.similarity
        }

def detect_language(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.py':
        return Language.PYTHON
    elif ext in ['.js', '.ts']:
        return Language.JAVASCRIPT
    return Language.UNKNOWN

class KnowledgeGraphAgent(BaseAgent):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(agent_id="knowledge_graph_agent", config=config)
        self.logger = logging.getLogger(__name__)
        self.chroma_client = chromadb.Client()
        
        # Set up enhanced logging
        self.logger.setLevel(logging.DEBUG)
        
        # Initialize Jina embedding model
        self._initialize_embedding_model()
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
    
    def _initialize_embedding_model(self):
        """Initialize Jina embedding model as requested"""
        try:
            # Using Jina embedding model as originally requested
            self.embedding_model_name = "jinaai/jina-embeddings-v2-base-code"
            self.tokenizer = AutoTokenizer.from_pretrained(self.embedding_model_name)
            self.model = AutoModel.from_pretrained(self.embedding_model_name)
            self.logger.info(f"Successfully loaded Jina embedding model: {self.embedding_model_name}")
        except Exception as e:
            self.logger.error(f"Failed to initialize Jina embedding model: {e}")
            # Fallback to CodeBERT if Jina fails
            try:
                self.embedding_model_name = "microsoft/codebert-base"
                self.tokenizer = AutoTokenizer.from_pretrained(self.embedding_model_name)
                self.model = AutoModel.from_pretrained(self.embedding_model_name)
                self.logger.info(f"Fallback: Successfully loaded CodeBERT model: {self.embedding_model_name}")
            except Exception as fallback_e:
                self.logger.error(f"Failed to initialize fallback model: {fallback_e}")
                raise RuntimeError(f"Failed to initialize any embedding model. Jina error: {e}, Fallback error: {fallback_e}")
    def validate_input(self, agent_input: AgentInput) -> bool:
        return True
    def embed_text(self, text: str) -> List[float]:
        """Generate embeddings for text using Jina model with proper error handling"""
        try:
            if not hasattr(self, 'tokenizer') or not hasattr(self, 'model'):
                raise RuntimeError("Embedding model not properly initialized")
            
            # Use transformers with Jina model
            inputs = self.tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=8192)
            with torch.no_grad():
                outputs = self.model(**inputs)
            embedding = outputs.last_hidden_state.mean(dim=1).squeeze().tolist()
            
            self.logger.debug(f"Generated embedding of dimension: {len(embedding)}")
            return embedding
                
        except Exception as e:
            self.logger.error(f"Error generating embedding for text (length {len(text)}): {e}")
            raise RuntimeError(f"Failed to generate embedding: {e}")
    def chunk_file(self, file_path: str, rel_path: str) -> List[CodeChunk]:
        """Enhanced chunking with comprehensive debug logging"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            self.logger.error(f"Failed to read file {file_path}: {e}")
            return []
            
        lines = content.split('\n')
        file_size_bytes = len(content.encode('utf-8'))
        
        self.logger.info(f"Processing file: {rel_path}")
        self.logger.info(f"  - Lines: {len(lines)}")
        self.logger.info(f"  - Size: {file_size_bytes:,} bytes ({file_size_bytes/1024:.1f} KB)")
        self.logger.info(f"  - Language: {detect_language(file_path)}")
        
        if len(lines) > 5000:
            self.logger.warning(f"File {rel_path} has {len(lines)} lines (>5000), creating TODO chunk")
            return [CodeChunk(
                text=f"# TODO: File too large - {len(lines)} lines\n# File: {rel_path}\n# Consider implementing large file chunking strategy", 
                file_path=rel_path, 
                chunk_type=ChunkType.FILE, 
                language=detect_language(file_path), 
                name=os.path.basename(rel_path)
            )]
            
        chunks = []
        # Improved chunking strategy
        chunk_size = 150  # Smaller chunks for better granularity
        overlap = 30      # Larger overlap for better context
        
        self.logger.debug(f"Chunking strategy: chunk_size={chunk_size}, overlap={overlap}")
        
        for i in range(0, len(lines), chunk_size - overlap):
            end = min(i + chunk_size, len(lines))
            chunk_lines = lines[i:end]
            chunk_text = '\n'.join(chunk_lines)
            
            # Skip very small chunks (less than 10 lines) unless it's the last chunk
            if len(chunk_lines) < 10 and i + chunk_size < len(lines):
                self.logger.debug(f"Skipping small chunk at lines {i+1}-{end} ({len(chunk_lines)} lines)")
                continue
                
            chunk = CodeChunk(
                text=chunk_text,
                file_path=rel_path,
                chunk_type=ChunkType.BLOCK,
                language=detect_language(file_path),
                start_line=i + 1,
                end_line=end
            )
            chunks.append(chunk)
            
            self.logger.debug(f"Created chunk {len(chunks)}: lines {i+1}-{end} ({len(chunk_lines)} lines, {len(chunk_text)} chars)")
        
        self.logger.info(f"  - Generated {len(chunks)} chunks for {rel_path}")
        return chunks

    def analyze_repository(self, data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Analyze repository with comprehensive debug logging and improved file discovery"""
        try:
            repo_path = data['repository_path']
            
            if not os.path.exists(repo_path):
                raise ValueError(f"Repository path does not exist: {repo_path}")
            
            self.logger.info(f"=== REPOSITORY ANALYSIS START ===")
            self.logger.info(f"Repository path: {repo_path}")
            self.logger.info(f"Session ID: {session_id}")
            
            # Enhanced file discovery with debug logging
            code_files = []
            all_files = []
            supported_extensions = ('.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.go', '.rs', '.rb', '.php')
            
            for root, dirs, files in os.walk(repo_path):
                # Skip .git directories
                dirs[:] = [d for d in dirs if d != '.git']
                
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, repo_path)
                    all_files.append((file_path, rel_path))
                    
                    if file.endswith(supported_extensions):
                        file_size = os.path.getsize(file_path)
                        code_files.append((file_path, rel_path, file_size))
                        self.logger.debug(f"Found code file: {rel_path} ({file_size:,} bytes)")
            
            self.logger.info(f"Repository scan complete:")
            self.logger.info(f"  - Total files: {len(all_files)}")
            self.logger.info(f"  - Code files: {len(code_files)}")
            self.logger.info(f"  - Supported extensions: {supported_extensions}")
            
            if not code_files:
                self.logger.warning("No supported code files found!")
                self.logger.info("Files found in repository:")
                for file_path, rel_path in all_files[:10]:  # Show first 10 files
                    self.logger.info(f"  - {rel_path}")
                return {"error": "No supported code files found in repository", "total_files": len(all_files)}
            
            # Create collection
            try:
                collection = self.chroma_client.get_or_create_collection(name=session_id)
                self.logger.info(f"Created/accessed ChromaDB collection: {session_id}")
            except Exception as e:
                raise RuntimeError(f"Failed to create collection: {e}")
            
            total_chunks = 0
            failed_files = []
            file_chunk_counts = {}
            
            self.logger.info(f"=== PROCESSING {len(code_files)} CODE FILES ===")
            
            for file_path, rel_path, file_size in code_files:
                try:
                    self.logger.info(f"\n--- Processing file {total_chunks + 1}/{len(code_files)}: {rel_path} ---")
                    
                    chunks = self.chunk_file(file_path, rel_path)
                    file_chunk_counts[rel_path] = len(chunks)
                    
                    successful_chunks = 0
                    for idx, chunk in enumerate(chunks):
                        try:
                            self.logger.debug(f"Generating embedding for chunk {idx+1}/{len(chunks)} in {rel_path}")
                            embedding = self.embed_text(chunk.text)
                            
                            metadata_dict = {k: v for k, v in chunk.to_dict().items() if k != "text" and v is not None}
                            
                            chunk_id = f"{rel_path}_{idx}"
                            collection.add(
                                ids=[chunk_id],
                                embeddings=[embedding],
                                metadatas=[metadata_dict],
                                documents=[chunk.text]
                            )
                            successful_chunks += 1
                            
                        except Exception as e:
                            self.logger.error(f"Failed to process chunk {idx} in {rel_path}: {e}")
                            continue
                    
                    total_chunks += successful_chunks
                    self.logger.info(f"Successfully processed {successful_chunks}/{len(chunks)} chunks from {rel_path}")
                    
                except Exception as e:
                    self.logger.error(f"Failed to process file {file_path}: {e}")
                    failed_files.append(rel_path)
                    continue
            
            self.logger.info(f"\n=== REPOSITORY ANALYSIS COMPLETE ===")
            self.logger.info(f"Total chunks created: {total_chunks}")
            self.logger.info(f"Files processed successfully: {len(code_files) - len(failed_files)}/{len(code_files)}")
            
            if file_chunk_counts:
                self.logger.info(f"Chunk distribution by file:")
                for file, chunk_count in file_chunk_counts.items():
                    self.logger.info(f"  - {file}: {chunk_count} chunks")
            
            result = {
                "total_chunks": total_chunks, 
                "session_id": session_id,
                "files_processed": len(code_files) - len(failed_files),
                "total_files_found": len(code_files),
                "chunk_distribution": file_chunk_counts
            }
            
            if failed_files:
                result["warnings"] = f"Failed to process {len(failed_files)} files"
                result["failed_files"] = failed_files
                self.logger.warning(f"Failed to process files: {failed_files}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Repository analysis failed: {e}")
            import traceback
            self.logger.error(f"Full traceback: {traceback.format_exc()}")
            return {"error": f"Repository analysis failed: {str(e)}"}

    def search_code(self, data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Search code with proper error handling"""
        try:
            query = data['query']
            max_results = data.get('max_results', 10)
            
            if not query or not query.strip():
                return {"error": "Query cannot be empty"}
            
            try:
                collection = self.chroma_client.get_collection(name=session_id)
            except Exception as e:
                return {"error": f"Session not found or invalid: {session_id}"}
            
            try:
                query_embedding = self.embed_text(query)
            except Exception as e:
                return {"error": f"Failed to generate query embedding: {e}"}
            
            try:
                results = collection.query(query_embeddings=[query_embedding], n_results=max_results)
            except Exception as e:
                return {"error": f"Failed to search collection: {e}"}
            
            search_results = []
            for i in range(len(results['ids'][0])):
                try:
                    metadata = results['metadatas'][0][i]
                    text = results['documents'][0][i]
                    distance = results['distances'][0][i]
                    
                    # Create chunk dict with text included
                    chunk_dict = {
                        "text": text,
                        "file_path": metadata.get("file_path"),
                        "chunk_type": metadata.get("chunk_type"),
                        "language": metadata.get("language"),
                        "start_line": metadata.get("start_line"),
                        "end_line": metadata.get("end_line"),
                        "name": metadata.get("name")
                    }
                    
                    similarity = max(0, 1 - distance)  # Convert distance to similarity, ensure non-negative
                    search_results.append({"chunk": chunk_dict, "similarity": similarity})
                except Exception as e:
                    self.logger.warning(f"Failed to process search result {i}: {e}")
                    continue
            
            return {"results": search_results}
            
        except Exception as e:
            self.logger.error(f"Code search failed: {e}")
            return {"error": f"Code search failed: {str(e)}"}
    #Finds a reference match for the query, then searches for code similar to that reference.
    def find_similar(self, data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        query = data['query']
        max_results = data.get('max_results', 10)
        collection = self.chroma_client.get_collection(name=session_id)
        query_embedding = self.embed_text(query)
        results = collection.query(query_embeddings=[query_embedding], n_results=max_results)
        # For similarity, perhaps find top match and then query similar to its embedding
        if results['ids'][0]:
            ref_id = results['ids'][0][0]
            ref_embedding = collection.get(ids=[ref_id], include=['embeddings'])['embeddings'][0]
            sim_results = collection.query(query_embeddings=[ref_embedding], n_results=max_results)
            search_results = [self._result_to_dict(sim_results, i) for i in range(len(sim_results['ids'][0]))]
            return {"results": search_results}
        return {"results": []}

    def find_functions(self, data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        query = data['query']
        max_results = data.get('max_results', 10)
        collection = self.chroma_client.get_collection(name=session_id)
        query_embedding = self.embed_text(query)
        results = collection.query(query_embeddings=[query_embedding], n_results=max_results, where={"chunk_type": "function"})  # Assuming we add chunk_type metadata
        search_results = [self._result_to_dict(results, i) for i in range(len(results['ids'][0]))]
        return {"results": search_results}

    def find_classes(self, data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        query = data['query']
        max_results = data.get('max_results', 10)
        collection = self.chroma_client.get_collection(name=session_id)
        query_embedding = self.embed_text(query)
        results = collection.query(query_embeddings=[query_embedding], n_results=max_results, where={"chunk_type": "class"})
        search_results = [self._result_to_dict(results, i) for i in range(len(results['ids'][0]))]
        return {"results": search_results}
    #TODO - to improve this more
    def find_patterns(self, data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        query = data['query']
        max_results = data.get('max_results', 10)
        collection = self.chroma_client.get_collection(name=session_id)
        query_embedding = self.embed_text(query)
        results = collection.query(query_embeddings=[query_embedding], n_results=max_results)
        search_results = [self._result_to_dict(results, i) for i in range(len(results['ids'][0]))]
        return {"results": search_results}
    #TODO - to define what more to need apart from total chunks in the RAG
    def get_statistics(self, session_id: str) -> Dict[str, Any]:
        try:
            collection = self.chroma_client.get_collection(name=session_id)
            return {"total_chunks": collection.count()}
        except:
            return {"error": "Session not found"}

    def cleanup_session(self, session_id: str) -> Dict[str, Any]:
        self.chroma_client.delete_collection(name=session_id)
        return {"message": "Session cleaned"}

    def _result_to_dict(self, results, i):
        metadata = results['metadatas'][0][i]
        text = results['documents'][0][i]
        similarity = 1 - results['distances'][0][i]
        chunk_dict = {
            "text": text,
            "file_path": metadata.get("file_path"),
            "chunk_type": metadata.get("chunk_type"),
            "language": metadata.get("language"),
            "start_line": metadata.get("start_line"),
            "end_line": metadata.get("end_line"),
            "name": metadata.get("name")
        }
        return {"chunk": chunk_dict, "similarity": similarity}

    def process(self, agent_input: AgentInput) -> AgentOutput:
        start_time = datetime.now()
        operation = agent_input.data.get('operation')
        session_id = agent_input.session_id
        
        try:
            if operation == 'analyze_repository':
                result = self.analyze_repository(agent_input.data, session_id)
                status = AgentStatus.ERROR if 'error' in result else AgentStatus.SUCCESS
            elif operation == 'search_code':
                result = self.search_code(agent_input.data, session_id)
                status = AgentStatus.ERROR if 'error' in result else AgentStatus.SUCCESS
            elif operation == 'find_similar':
                result = self.find_similar(agent_input.data, session_id)
                status = AgentStatus.ERROR if 'error' in result else AgentStatus.SUCCESS
            elif operation == 'find_functions':
                result = self.find_functions(agent_input.data, session_id)
                status = AgentStatus.ERROR if 'error' in result else AgentStatus.SUCCESS
            elif operation == 'find_classes':
                result = self.find_classes(agent_input.data, session_id)
                status = AgentStatus.ERROR if 'error' in result else AgentStatus.SUCCESS
            elif operation == 'find_patterns':
                result = self.find_patterns(agent_input.data, session_id)
                status = AgentStatus.ERROR if 'error' in result else AgentStatus.SUCCESS
            elif operation == 'get_statistics':
                result = self.get_statistics(session_id)
                status = AgentStatus.ERROR if 'error' in result else AgentStatus.SUCCESS
            elif operation == 'cleanup_session':
                result = self.cleanup_session(session_id)
                status = AgentStatus.SUCCESS
            else:
                result = {"error": f"Unsupported operation: {operation}"}
                status = AgentStatus.ERROR
                
        except Exception as e:
            self.logger.error(f"Unexpected error in operation '{operation}': {e}")
            result = {"error": f"Unexpected error: {str(e)}"}
            status = AgentStatus.ERROR
        
        execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        return self._create_output(status, result, execution_time_ms)

    def _create_output(self, status: AgentStatus, data: Dict[str, Any], execution_time_ms: int) -> AgentOutput:
        return AgentOutput(
            session_id="",
            agent_id=self.agent_id,
            status=status,
            data=data,
            execution_time_ms=execution_time_ms,
            timestamp=datetime.now()
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


"""
def demo_repository_analysis(repo_path: str = ".") -> None:
    Demo function to show repository analysis
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

"""
  # Add at the very end of the file
if __name__ == "__main__":
    print("Running KnowledgeGraphAgent module directly - initializing test instance...")
    agent = KnowledgeGraphAgent()  # Or add simple test code here