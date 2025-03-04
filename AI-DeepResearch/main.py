import faiss
from langchain_ollama import OllamaLLM
from sentence_transformers import SentenceTransformer
from collections import deque
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Configuration
LLM_MODEL_NAME = "qwen2.5:7b"  
LLM_TEMPERATURE = 0.6
dimension = 384  

# Initialize LLM
llm = OllamaLLM(
    model=LLM_MODEL_NAME,
    base_url="http://localhost:11434",
    temperature=LLM_TEMPERATURE,
    top_p=0.9,
    num_ctx=4096
)


embedder = SentenceTransformer('all-MiniLM-L6-v2')
index = faiss.IndexFlatL2(dimension)  

class DeepResearchSimulator:
    def __init__(self):
        self.context_vectors = []  
        self.context_data = []  # Store (query, response) pairs
        self.query_queue = deque()  # Queue of sub-queries
        self.visited_queries = set()  # Track explored queries
        self.initial_prompt_embedding = None
        self.max_depth = 7  # Limit exploration depth
        self.relevance_threshold = 0.39  # Minimum relevance score ---> needs to be fine tuned based on use case, this is just a starting point and can vary based on monitoring each use case of the app
        #todo: the above relevance score threshold might not always be valid, and this needs to be fine tuned as it might eliminate some relevant data and we might miss this in research

    def embed_text(self, text):     
        """Generate embedding for text."""
        return embedder.encode(text, convert_to_tensor=False)

    def initialize_exploration(self, initial_prompt):
        """Start with the initial prompt."""
        self.initial_prompt_embedding = self.embed_text(initial_prompt)
        initial_queries = self.generate_sub_queries(initial_prompt, "")
        for query in initial_queries:
            logger.info(f"Exploring: {query}")
            self.query_queue.append((query, 0))  # (query, depth)

    def generate_sub_queries(self, prompt, context):
        """Generate sub-queries using the LLM."""
        if context:
            query_prompt = f"Based on '{context}', generate 5 follow-up questions to explore '{prompt}' deeper."
        else:
            query_prompt = f"Generate 3 sub-questions to explore '{prompt}'."
        response = llm(query_prompt)
        logger.info(f"Generated sub-queries for query{prompt}: {response}")
        return [q.strip() for q in response.strip().split("\n") if q.strip()]

    def generate_response(self, query):
        """Generate a response using the LLM."""
        return llm(query).strip()

    def evaluate_response(self, response_embedding):
        """Evaluate relevance using cosine similarity."""
        similarity = cosine_similarity(
            self.initial_prompt_embedding.reshape(1, -1),
            response_embedding.reshape(1, -1)
        )[0][0]
        return similarity

    def add_to_context(self, query, response):
        """Store query-response pair in the vector database."""
        combined_text = f"{query}: {response}"
        embedding = self.embed_text(combined_text)
        self.context_vectors.append(embedding)
        self.context_data.append((query, response))
        index.add(np.array([embedding], dtype='float32'))

    def search_context(self, query_embedding, k=3):
        """Retrieve top-k relevant context entries."""
        distances, indices = index.search(np.array([query_embedding], dtype='float32'), k)
        return [self.context_data[i] for i in indices[0] if i < len(self.context_data)]

    def explore_query(self, query, depth):
        """Process a query and update context if relevant."""
        if query in self.visited_queries or depth >= self.max_depth:
            return
        
        response = self.generate_response(query)
        logger.info(f"Response for query '{query}': {response}")
        response_embedding = self.embed_text(response)
        relevance_score = self.evaluate_response(response_embedding)
        
        logger.info(f"Relevance score for '{query}': {relevance_score}")

        if relevance_score > self.relevance_threshold:
            
            self.add_to_context(query, response)
            self.visited_queries.add(query)
            new_queries = self.generate_sub_queries(query, response)
            for new_query in new_queries:
                if new_query not in self.visited_queries:
                    self.query_queue.append((new_query, depth + 1))

    def synthesize_answer(self):
        """Synthesize a final answer from relevant context."""
        if not self.context_data:
            return "No relevant information gathered."
        
        top_indices = index.search(np.array([self.initial_prompt_embedding], dtype='float32'), 5)[1][0]
        top_context = [self.context_data[i] for i in top_indices if i < len(self.context_data)]
        context_text = "\n".join([f"Q: {q}\nA: {a}" for q, a in top_context])
        synthesis_prompt = f"Summarize this into a comprehensive Research answer:\n\n{context_text}"
        return llm(synthesis_prompt).strip()

    def deep_research(self, initial_prompt):
        """Execute the deep research process."""
        self.initialize_exploration(initial_prompt)
        while self.query_queue and len(self.visited_queries) < self.max_depth:
            query, depth = self.query_queue.popleft()
            logger.info(f"Exploring query: {query}, Depth: {depth}")
            self.explore_query(query, depth)
        return self.synthesize_answer()

# Usage
simulator = DeepResearchSimulator()
initial_prompt = "Explain about Bitcoin and how it revolutionises payment?"
logger.info(f"STARTING DEEP RESEARCH FOR: {initial_prompt}")
final_answer = simulator.deep_research(initial_prompt)
print("Final Answer:\n", final_answer)