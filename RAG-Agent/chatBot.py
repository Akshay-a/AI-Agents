import logging
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableParallel
from langchain_ollama import OllamaLLM
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
#from .main import db, embedding_model  # Import from main.py in the same package

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

embedding_model = HuggingFaceEmbeddings(model_name="dunzhang/stella_en_1.5B_v5")

# Initialize database globally
db = Chroma(collection_name="cp_database", embedding_function=embedding_model, persist_directory='./db_knowledge_base')

# Reused function from main.py
def format_docs(docs):
    context = "\n\n".join(doc.page_content for doc in docs)
    print("Retrieved Context:", context)
    return context

PROMPT_TEMPLATE = """
Based on the following context:
{context}

Answer the question: {question}
"""

class ChatBot:
    def __init__(self, collection_name="cp_database", persist_directory='./db_knowledge_base'):
        """Initialize the chatbot with a connection to the Chroma DB."""
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        
        # Reuse the global db and embedding_model from main.py
        self.db = db
        self.embedding_model = embedding_model
        
        # Initialize the RAG chain
        self.retriever = self.db.as_retriever(search_kwargs={"k": 5})
        self.prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
        self.chat_model = OllamaLLM(model="qwen2.5:7b", base_url="http://localhost:11434", temperature=0.6)
        self.output_parser = StrOutputParser()
        
        self.chain = (
            {"context": self.retriever | format_docs, "question": RunnablePassthrough()}
            | self.prompt_template
            | self.chat_model
            | self.output_parser
        )
        
        # Stateful chat history
        self.chat_history = []

    def ask(self, query):
        """Process a user query and return the response."""
        try:
            response = self.chain.invoke(query)
            # Store the query and response in chat history
            self.chat_history.append({"query": query, "response": response})
            return response
        except Exception as e:
            logger.error(f"Error processing query '{query}': {str(e)}")
            return "Sorry, I encountered an error. Please try again."

    def get_chat_history(self):
        """Return the full chat history."""
        return self.chat_history

    def run_chat_session(self):
        """Run an interactive chat session in the console."""
        print("Welcome to the ChatBot! Ask me anything about the knowledge base.")
        print("Type 'exit' to end the session or 'history' to see past interactions.")
        
        while True:
            query = input("You: ").strip()
            
            if query.lower() == "exit":
                print("Goodbye!")
                break
            elif query.lower() == "history":
                if not self.chat_history:
                    print("No chat history yet.")
                else:
                    print("\nChat History:")
                    for i, entry in enumerate(self.chat_history, 1):
                        print(f"{i}. You: {entry['query']}")
                        print(f"   Bot: {entry['response']}\n")
            elif query:
                response = self.ask(query)
                print(f"Bot: {response}")
            else:
                print("Please enter a question.")

# Example usage (can be imported or run standalone)
if __name__ == "__main__":
    chatbot = ChatBot()
    chatbot.run_chat_session()