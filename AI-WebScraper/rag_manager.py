"""
RAG Manager for handling document storage and retrieval in a vector database.

This module provides functionality to store, chunk, and retrieve documents using ChromaDB
with sentence-transformers for embeddings.
"""

import os
import hashlib
from typing import List, Dict, Any, Optional, Tuple
import chromadb
from chromadb.utils import embedding_functions
from more_itertools import batched
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RAGManager:
    """
    A class to manage RAG (Retrieval-Augmented Generation) operations including
    document storage, chunking, and retrieval.
    """
    
    def __init__(
        self,
        persist_directory: str = "./chroma_db",
        collection_name: str = "web_documents",
        embedding_model: str = "all-MiniLM-L6-v2",
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ):
        """
        Initialize the RAG Manager.
        
        Args:
            persist_directory: Directory to store the ChromaDB data
            collection_name: Name of the collection to use in ChromaDB
            embedding_model: Name of the sentence-transformers model to use for embeddings
            chunk_size: Maximum size of each chunk in characters
            chunk_overlap: Number of characters to overlap between chunks
        """
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Initialize ChromaDB client and collection
        self.client = self._get_chroma_client()
        self.collection = self._get_or_create_collection()
    
    def _get_chroma_client(self) -> chromadb.PersistentClient:
        """Get a ChromaDB client with the specified persistence directory."""
        os.makedirs(self.persist_directory, exist_ok=True)
        return chromadb.PersistentClient(path=self.persist_directory)
    
    def _get_or_create_collection(self) -> chromadb.Collection:
        """Get an existing collection or create a new one if it doesn't exist."""
        # Create embedding function
        embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=self.embedding_model
        )
        
        try:
            # Try to get the collection if it exists
            collection = self.client.get_collection(
                name=self.collection_name,
                embedding_function=embedding_func
            )
            logger.info(f"Using existing collection: {self.collection_name}")
            return collection
        except Exception as e:
            # Create the collection if it doesn't exist
            logger.info(f"Collection {self.collection_name} not found, creating new one...")
            collection = self.client.create_collection(
                name=self.collection_name,
                embedding_function=embedding_func,
                metadata={"hnsw:space": "cosine"}  # Use cosine distance
            )
            logger.info(f"Created new collection: {self.collection_name}")
            return collection
    
    def _generate_document_id(self, url: str, chunk_index: int) -> str:
        """Generate a unique ID for a document chunk."""
        # Create a hash of the URL and chunk index
        hash_input = f"{url}_{chunk_index}".encode('utf-8')
        return hashlib.md5(hash_input).hexdigest()
    
    def chunk_content(self, content: str, is_markdown: bool = False) -> List[Dict[str, Any]]:
        """
        Split content into chunks with optional markdown-aware splitting.
        
        Args:
            content: The content to chunk
            is_markdown: Whether the content is markdown (enables markdown-aware splitting)
            
        Returns:
            List of chunk dictionaries with text and metadata
        """
        if not content:
            return []
            
        # If it's markdown and we have markdown-specific chunking
        if is_markdown and '\n# ' in content:
            return self._chunk_markdown(content)
        
        # Fall back to simple character-based chunking
        return self._chunk_text(content)
    
    def _chunk_markdown(self, content: str) -> List[Dict[str, Any]]:
        """
        Chunk markdown content by headers to preserve semantic structure.
        
        Args:
            content: Markdown content to chunk
            
        Returns:
            List of chunk dictionaries with text and metadata
        """
        import re
        from typing import List, Dict, Any
        
        # Split by headers (lines starting with #)
        header_pattern = r'(^#+ .+$\n(?:^[^#].*\n)*)'
        chunks = []
        
        # Find all header sections
        for match in re.finditer(header_pattern, content, re.MULTILINE):
            header_text = match.group(1).strip()
            if len(header_text) > self.chunk_size:
                # If the header section is too large, split it further
                sub_chunks = self._chunk_text(header_text)
                chunks.extend(sub_chunks)
            else:
                chunks.append({
                    'text': header_text,
                    'metadata': {
                        'chunk_type': 'header_section',
                        'header': header_text.split('\n', 1)[0] if '\n' in header_text else header_text
                    }
                })
        
        # If no headers found or content is empty, fall back to text chunking
        if not chunks:
            return self._chunk_text(content)
            
        return chunks
    
    def _chunk_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Split text into chunks of specified size with overlap.
        
        Args:
            text: Text to chunk
            
        Returns:
            List of chunk dictionaries with text and metadata
        """
        if not text:
            return []
            
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            end = min(start + self.chunk_size, text_length)
            
            # If we're not at the end of the text, try to find a good breaking point
            if end < text_length:
                # Look for the nearest sentence or paragraph end
                break_chars = {'. ', '\n\n', '\n', ' '}
                best_break = -1
                
                for bc in break_chars:
                    pos = text.rfind(bc, start, end)
                    if pos > start + (self.chunk_size // 2):  # Only break if we're past half the chunk size
                        best_break = pos + len(bc)
                        break
                
                if best_break > 0:
                    end = best_break
            
            chunk_text = text[start:end].strip()
            if chunk_text:  # Only add non-empty chunks
                chunks.append({
                    'text': chunk_text,
                    'metadata': {
                        'chunk_type': 'text_fragment',
                        'chunk_position': len(chunks)
                    }
                })
            
            # Move start position, accounting for overlap
            start = end - self.chunk_overlap if (end - self.chunk_overlap) > start else end
            
            # If we didn't make progress, force move to avoid infinite loop
            if start == end and start < text_length:
                start = end
                
        return chunks
    
    def _optimize_chunks(self, chunks: List[str], min_chunk_size: int = 100) -> List[str]:
        """Optimize chunks by combining small ones while preserving larger ones.
        
        Args:
            chunks: List of content chunks
            min_chunk_size: Minimum size for a chunk to be considered standalone
            
        Returns:
            List of optimized chunks
        """
        if not chunks:
            return []
            
        optimized = []
        current_chunk = []
        current_size = 0
        
        for chunk in chunks:
            chunk = str(chunk).strip()
            if not chunk:
                continue
                
            chunk_size = len(chunk)
            
            # If chunk is too small, combine with others
            if chunk_size < min_chunk_size:
                current_chunk.append(chunk)
                current_size += chunk_size
                
                # If combined chunks reach minimum size, add to optimized
                if current_size >= min_chunk_size:
                    optimized.append(' '.join(current_chunk))
                    current_chunk = []
                    current_size = 0
            else:
                # Flush any accumulated chunks
                if current_chunk:
                    optimized.append(' '.join(current_chunk))
                    current_chunk = []
                    current_size = 0
                # Add the current large chunk
                optimized.append(chunk)
        
        # Add any remaining chunks
        if current_chunk:
            optimized.append(' '.join(current_chunk))
            
        return optimized

    def store_document(
            self,
            content: List[str],
            url: str,
            question: str,
            title: str = "",
            source_type: str = "web",  # 'web' or 'pdf'
            metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Store a document in the vector database after chunking.
        
        Args:
            content: The document content to store (can be string or list of strings)
            url: Source URL of the document
            title: Title of the document
            source_type: Type of the source ('web' or 'pdf')
            metadata: Additional metadata to store with the document
            
        Returns:
            Number of chunks stored
        """
        from datetime import datetime
        
        if not content:
            logger.warning("No content or URL provided for storage")
            return 0
            
            
        # Clean and filter empty strings
        #content = [str(c).strip() for c in content if str(c).strip()]
        
        if not content:
            logger.warning(f"Empty content after processing for {url}")
            return 0
            
        # Optimize chunks before further processing, commenting below for now as getting some error
        optimized_chunks = self._optimize_chunks(content)
        #optimized_chunks=content
        # Prepare metadata
        doc_metadata = metadata or {}
        doc_metadata.update({
            'url': url,
            'title': title,
            'source': source_type,
            'question': question,
            'stored_at': datetime.now().isoformat()
        })
        
        # Prepare documents and metadata for storage
        documents = []
        metadatas = []
        ids = []
        
        for i, chunk in enumerate(optimized_chunks):
            if not chunk:
                continue
                
            doc_id = self._generate_document_id(url, i)
            chunk_metadata = doc_metadata.copy()
            
            # Add chunk-specific metadata if needed
            if i < len(optimized_chunks) - 1:
                chunk_metadata['chunk_position'] = i
                chunk_metadata['total_chunks'] = len(optimized_chunks)
            
            documents.append(chunk)
            metadatas.append(chunk_metadata)
            print(f"chunk metadata is {chunk_metadata}")
            ids.append(doc_id)
            
        if not documents:
            logger.warning(f"No valid chunks to store for {url}")
            return 0
            
        # Store in ChromaDB
        try:
            self.collection.upsert(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            logger.info(f"Stored {len(documents)} chunks for {url}")
            return len(documents)
            
        except Exception as e:
            logger.error(f"Error storing document {url}: {e}")
            if hasattr(e, 'details') and 'already exists' in str(e.details):
                logger.info("Document already exists in the collection")
                return len(documents)
            return 0
    
    def search(
        self,
        query: str,
        question: Optional[str] = None,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
        filter_by_question: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search the vector database for documents similar to the query.
        
        Args:
            query: The search query
            n_results: Number of results to return
            where: Filter conditions for metadata
            where_document: Filter conditions for document content
            
        Returns:
            List of search results with documents and metadata
        """
        try:
            # If we have a question and want to filter by it
            if question and filter_by_question:
                if where is None:
                    where = {}
                where['question'] = question
            
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where,
                where_document=where_document
            )
            
            # Format results into a more usable structure
            formatted_results = []
            
            # Check if we have any results
            if not results or 'documents' not in results or not results['documents']:
                return formatted_results
            
            # Process each document in the results
            for i in range(len(results['documents'][0])):
                doc_text = results['documents'][0][i]
                metadata = results['metadatas'][0][i] if results.get('metadatas') and i < len(results['metadatas'][0]) else {}
                distance = results['distances'][0][i] if results.get('distances') and i < len(results['distances'][0]) else None
                
                formatted_results.append({
                    'text': doc_text,
                    'metadata': metadata,
                    'distance': distance
                })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error searching the vector database: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the vector database.
        
        Returns:
            Dictionary containing statistics
        """
        try:
            count = self.collection.count()
            return {
                'collection_name': self.collection_name,
                'document_count': count,
                'embedding_model': self.embedding_model
            }
        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return {}


# Example usage
if __name__ == "__main__":
    # Initialize the RAG manager
    rag = RAGManager()
    
    # Example document
    sample_text = """
    # Sample Document
    
    This is a sample document that demonstrates the RAG manager's capabilities.
    
    ## Introduction
    
    The RAG manager can handle both plain text and markdown content, with smart chunking
    that preserves document structure.
    
    ## Features
    
    - Smart chunking of documents
    - Support for markdown and plain text
    - Vector similarity search
    - Metadata filtering
    """
    
    # Store the document
    url = "https://example.com/sample-doc"
    title = "Sample Document"
    rag.store_document(sample_text, url, title, source_type="web")
    
    # Search for similar content
    query = "What features does the RAG manager support?"
    results = rag.search(query, n_results=2)
    
    print(f"Search results for '{query}':")
    for i, result in enumerate(results, 1):
        print(f"\n--- Result {i} ---")
        print(f"Text: {result['text']}")
        print(f"Source: {result['metadata'].get('source', 'N/A')}")
        print(f"Similarity: {1 - result['distance']:.2f}")
