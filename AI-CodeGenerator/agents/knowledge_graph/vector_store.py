"""
Simple Vector Store for Code Embeddings
Handles embedding generation and similarity search for code chunks.
"""

import numpy as np
from typing import List, Dict, Any, Optional, Tuple
import logging
from collections import defaultdict

from .schema import CodeChunk, SearchResult


class VectorStore:
    """Simple in-memory vector store for code embeddings"""
    
    def __init__(self, embedding_model: str = "all-MiniLM-L6-v2"):
        self.embedding_model_name = embedding_model
        self.embedder = None
        self.chunks: List[CodeChunk] = []
        self.embeddings: Optional[np.ndarray] = None
        self.logger = logging.getLogger(__name__)
        
        # Initialize embedder
        self._init_embedder()
    
    def _init_embedder(self):
        """Initialize the embedding model"""
        try:
            from sentence_transformers import SentenceTransformer
            self.embedder = SentenceTransformer(self.embedding_model_name)
            self.embedder_type = "sentence_transformer"
            self.logger.info(f"Initialized SentenceTransformer: {self.embedding_model_name}")
        except ImportError:
            self.logger.warning("sentence-transformers not available, using TF-IDF fallback")
            from sklearn.feature_extraction.text import TfidfVectorizer
            self.embedder = TfidfVectorizer(
                max_features=500,
                stop_words='english',
                ngram_range=(1, 2),
                lowercase=True
            )
            self.embedder_type = "tfidf"
    
    def add_chunks(self, chunks: List[CodeChunk]) -> None:
        """Add code chunks and generate embeddings"""
        self.logger.info(f"Adding {len(chunks)} chunks to vector store")
        
        self.chunks = chunks
        
        # Extract text for embedding
        texts = []
        for chunk in chunks:
            # Combine different text fields for better embedding
            text_parts = [chunk.text]
            
            if chunk.name:
                text_parts.append(f"name: {chunk.name}")
            if chunk.signature:
                text_parts.append(f"signature: {chunk.signature}")
            if chunk.docstring:
                text_parts.append(f"doc: {chunk.docstring}")
            
            combined_text = "\n".join(text_parts)
            texts.append(combined_text)
        
        # Generate embeddings
        if self.embedder_type == "sentence_transformer":
            self.embeddings = self.embedder.encode(texts, show_progress_bar=True)
        else:
            # TF-IDF
            self.embeddings = self.embedder.fit_transform(texts).toarray()
        
        # Store embeddings in chunks for serialization
        for i, chunk in enumerate(self.chunks):
            chunk.embedding = self.embeddings[i].tolist()
        
        self.logger.info(f"Generated embeddings with shape: {self.embeddings.shape}")
    
    def search(self, query: str, top_k: int = 10, filters: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        """Search for similar code chunks"""
        if self.embeddings is None or len(self.chunks) == 0:
            return []
        
        # Generate query embedding
        if self.embedder_type == "sentence_transformer":
            query_embedding = self.embedder.encode([query])[0]
        else:
            query_embedding = self.embedder.transform([query]).toarray()[0]
        
        # Calculate similarities
        similarities = self._cosine_similarity_batch(query_embedding, self.embeddings)
        
        # Apply filters if provided
        valid_indices = self._apply_filters(filters) if filters else range(len(self.chunks))
        
        # Get top-k results from valid indices
        filtered_similarities = [(similarities[i], i) for i in valid_indices]
        filtered_similarities.sort(reverse=True)
        
        results = []
        for similarity, idx in filtered_similarities[:top_k]:
            chunk = self.chunks[idx]
            snippet = self._create_relevance_snippet(chunk, query)
            
            result = SearchResult(
                chunk=chunk,
                similarity=float(similarity),
                relevance_snippet=snippet
            )
            results.append(result)
        
        return results
    
    def search_by_similarity(self, reference_chunk: CodeChunk, top_k: int = 10, 
                           exclude_same_file: bool = True) -> List[SearchResult]:
        """Find chunks similar to a reference chunk"""
        if reference_chunk not in self.chunks:
            return []
        
        ref_idx = self.chunks.index(reference_chunk)
        ref_embedding = self.embeddings[ref_idx]
        
        # Calculate similarities
        similarities = self._cosine_similarity_batch(ref_embedding, self.embeddings)
        
        # Create results excluding the reference chunk itself
        results = []
        for i, similarity in enumerate(similarities):
            if i == ref_idx:
                continue
            
            chunk = self.chunks[i]
            
            # Optionally exclude chunks from the same file
            if exclude_same_file and chunk.file_path == reference_chunk.file_path:
                continue
            
            snippet = self._create_relevance_snippet(chunk, reference_chunk.name or "")
            
            result = SearchResult(
                chunk=chunk,
                similarity=float(similarity),
                relevance_snippet=snippet
            )
            results.append(result)
        
        # Sort by similarity and return top-k
        results.sort(key=lambda x: x.similarity, reverse=True)
        return results[:top_k]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the vector store"""
        if not self.chunks:
            return {"total_chunks": 0}
        
        # Language distribution
        language_counts = defaultdict(int)
        chunk_type_counts = defaultdict(int)
        file_counts = defaultdict(int)
        
        for chunk in self.chunks:
            language_counts[chunk.language.value] += 1
            chunk_type_counts[chunk.chunk_type.value] += 1
            file_counts[chunk.file_path] += 1
        
        return {
            "total_chunks": len(self.chunks),
            "total_files": len(file_counts),
            "embedding_dimension": self.embeddings.shape[1] if self.embeddings is not None else 0,
            "embedder_type": self.embedder_type,
            "language_distribution": dict(language_counts),
            "chunk_type_distribution": dict(chunk_type_counts),
            "avg_chunks_per_file": len(self.chunks) / len(file_counts) if file_counts else 0
        }
    
    def _cosine_similarity_batch(self, query_embedding: np.ndarray, embeddings: np.ndarray) -> np.ndarray:
        """Calculate cosine similarity between query and all embeddings"""
        query_norm = np.linalg.norm(query_embedding)
        embeddings_norm = np.linalg.norm(embeddings, axis=1)
        
        # Avoid division by zero
        query_norm = max(query_norm, 1e-8)
        embeddings_norm = np.maximum(embeddings_norm, 1e-8)
        
        # Calculate cosine similarity
        dot_products = np.dot(embeddings, query_embedding)
        similarities = dot_products / (embeddings_norm * query_norm)
        
        return similarities
    
    def _apply_filters(self, filters: Dict[str, Any]) -> List[int]:
        """Apply filters to find valid chunk indices"""
        valid_indices = []
        
        for i, chunk in enumerate(self.chunks):
            is_valid = True
            
            # Language filter
            if 'language' in filters:
                if chunk.language.value != filters['language']:
                    is_valid = False
            
            # Chunk type filter
            if 'chunk_type' in filters:
                if chunk.chunk_type.value != filters['chunk_type']:
                    is_valid = False
            
            # File path filter (partial match)
            if 'file_path' in filters:
                if filters['file_path'] not in chunk.file_path:
                    is_valid = False
            
            # Name filter (partial match)
            if 'name' in filters and chunk.name:
                if filters['name'].lower() not in chunk.name.lower():
                    is_valid = False
            
            # Minimum similarity threshold
            if 'min_similarity' in filters:
                # This would be applied during search, not here
                pass
            
            if is_valid:
                valid_indices.append(i)
        
        return valid_indices
    
    def _create_relevance_snippet(self, chunk: CodeChunk, query: str) -> str:
        """Create a relevance snippet showing why this chunk matches"""
        text = chunk.text
        max_snippet_length = 200
        
        # Try to find the query terms in the text
        query_terms = query.lower().split()
        text_lower = text.lower()
        
        # Find the best position to show
        best_position = 0
        best_score = 0
        
        # Look for positions where multiple query terms appear
        words = text.split()
        for i in range(len(words)):
            window = ' '.join(words[i:i+20]).lower()  # 20-word window
            score = sum(1 for term in query_terms if term in window)
            if score > best_score:
                best_score = score
                best_position = i
        
        # Extract snippet around the best position
        start_word = max(0, best_position - 10)
        end_word = min(len(words), best_position + 10)
        snippet = ' '.join(words[start_word:end_word])
        
        # Truncate if too long
        if len(snippet) > max_snippet_length:
            snippet = snippet[:max_snippet_length] + "..."
        
        # Add prefix if we're not at the beginning
        if start_word > 0:
            snippet = "..." + snippet
        
        return snippet
    
    def clear(self) -> None:
        """Clear all chunks and embeddings"""
        self.chunks = []
        self.embeddings = None
        self.logger.info("Cleared vector store")
    
    def save_to_file(self, file_path: str) -> None:
        """Save vector store to file (simple pickle serialization)"""
        import pickle
        
        data = {
            'chunks': self.chunks,
            'embeddings': self.embeddings.tolist() if self.embeddings is not None else None,
            'embedder_type': self.embedder_type,
            'embedding_model_name': self.embedding_model_name
        }
        
        with open(file_path, 'wb') as f:
            pickle.dump(data, f)
        
        self.logger.info(f"Saved vector store to {file_path}")
    
    def load_from_file(self, file_path: str) -> None:
        """Load vector store from file"""
        import pickle
        
        with open(file_path, 'rb') as f:
            data = pickle.load(f)
        
        self.chunks = data['chunks']
        self.embeddings = np.array(data['embeddings']) if data['embeddings'] else None
        self.embedder_type = data.get('embedder_type', 'unknown')
        self.embedding_model_name = data.get('embedding_model_name', 'unknown')
        
        self.logger.info(f"Loaded vector store from {file_path}")


class SessionVectorStore:
    """Manages vector stores per session"""
    
    def __init__(self):
        self.stores: Dict[str, VectorStore] = {}
        self.logger = logging.getLogger(__name__)
    
    def get_store(self, session_id: str) -> VectorStore:
        """Get or create a vector store for a session"""
        if session_id not in self.stores:
            self.stores[session_id] = VectorStore()
            self.logger.info(f"Created new vector store for session: {session_id}")
        
        return self.stores[session_id]
    
    def remove_store(self, session_id: str) -> bool:
        """Remove a vector store for a session"""
        if session_id in self.stores:
            del self.stores[session_id]
            self.logger.info(f"Removed vector store for session: {session_id}")
            return True
        return False
    
    def list_sessions(self) -> List[str]:
        """List all active sessions"""
        return list(self.stores.keys())
    
    def get_session_stats(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a specific session"""
        if session_id in self.stores:
            return self.stores[session_id].get_statistics()
        return None 