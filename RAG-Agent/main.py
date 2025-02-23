import os
import logging
from langchain_community.document_loaders import PyPDFLoader, WebBaseLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableParallel
from langchain_ollama import OllamaLLM
import bs4

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set USER_AGENT to avoid warning
os.environ["USER_AGENT"] = "MyRAGAgent/1.0"

# Initialize embedding model globally
embedding_model = HuggingFaceEmbeddings(model_name="dunzhang/stella_en_1.5B_v5")

# Initialize database globally
db = Chroma(collection_name="cp_database", embedding_function=embedding_model, persist_directory='./db_knowledge_base')

PROMPT_TEMPLATE = """
Based on the following context:
{context}

Answer the question: {question}
"""

def format_docs(docs):
    context = "\n\n".join(doc.page_content for doc in docs)
    print("Retrieved Context:", context)
    return context

def load_document_data(isWeb, path, doc_type, source_id):
    if isWeb:
        loader = WebBaseLoader(
            web_paths=(path,),
            bs_kwargs=dict(
                parse_only=bs4.SoupStrainer(
                    class_=("post-content", "post-title", "post-header")
                )
            ),
        )
    else:
        loader = PyPDFLoader(path, extract_images=False)
    
    try:
        data = loader.load()
        doc_content = [data[i].page_content for i in range(len(data))]
        doc_metadata = [data[i].metadata for i in range(len(data))]
        
        # Add custom metadata
        for meta in doc_metadata:
            meta["doc_type"] = doc_type
            meta["source_id"] = source_id
        
        return doc_content, doc_metadata
    except Exception as e:
        logger.error(f"Failed to load {path}: {str(e)}")
        raise

def reset_and_initialize_db():
    """Reset and reinitialize the Chroma database."""
    global db
    db.delete_collection()  # Delete the existing collection
    # Reinitialize the Chroma instance
    db = Chroma(
        collection_name="cp_database",
        embedding_function=embedding_model,
        persist_directory='./db_knowledge_base'
    )
    logger.info("Database reset and reinitialized.")

def main():
    try:
        # Reset and reinitialize the database
        reset_and_initialize_db()

        # Load the blog
        doc_content, doc_metadata = load_document_data(
            isWeb=True,
            path="https://lilianweng.github.io/posts/2023-06-23-agent/",
            doc_type="blog",
            source_id="agent_blog_2023"
        )
        
        # Split into chunks
        st_text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=3000,
            chunk_overlap=500,
            separators=["\n \n", "\n", ".", " "]
        )
        st_chunks = st_text_splitter.create_documents(doc_content, doc_metadata)
        print("Chunks:", [chunk.page_content for chunk in st_chunks])
        print("Chunk Metadata:", [chunk.metadata for chunk in st_chunks])

        # Add to database
        db.add_documents(st_chunks)
        print("Processed and added to the database!")

        # Query to just test the insertion of the embedings to the vector db , Dry Run
        # created seperate chatbot.py class to test the db in a full  fledged manner
        query = "what is chain of thought?"
        retriever = db.as_retriever()

        # Retrieve documents with scores
        docs_with_scores = db.similarity_search_with_score(
            query,
            k=5
        )
        print("\nRetrieved Documents and Scores:")
        for i, (doc, score) in enumerate(docs_with_scores):
            print(f"Doc {i+1}: {doc.page_content} (Score: {score})")

        # Run RAG chain
        prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
        chat_model = OllamaLLM(model="qwen2.5:7b", base_url="http://localhost:11434", temperature=0.6)
        output_parser = StrOutputParser()
        op = RunnableParallel(
            {"context": retriever | format_docs, "question": RunnablePassthrough()}
        ) | prompt_template | chat_model | output_parser
        response = op.invoke(query)
        print(f"Response from LLM: {response}")

    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        raise

if __name__ == "__main__":
    main()