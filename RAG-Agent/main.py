import os
import logging


from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters.sentence_transformers import SentenceTransformersTokenTextSplitter
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough,RunnableParallel
from langchain_ollama import OllamaLLM
from langchain_huggingface import HuggingFaceEmbeddings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_rag_chain():
    logger.info("Running RAG chain...")
    retriever = db.as_retriever(search_type="similarity", search_kwargs={'k': 5})
    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    chat_model = OllamaLLM(model="qwen2.5:7b", base_url="http://localhost:11434", temperature=0.6)
    logger.info("Chat model initialized.")
    output_parser = StrOutputParser()
    logger.info("Output parser initialized.")
    return {"context": retriever | format_docs, "question": RunnablePassthrough()} | prompt_template | chat_model | output_parser


PROMPT_TEMPLATE = """
        You are a highly knowledgeable assistant specializing in computer science. 
        Answer the question based only on the following context:
        {context}

        Answer the question based on the above context:
        {question}

        Use the provided context to answer the user's question accurately and concisely.
        Don't justify your answers.
        Don't give information not mentioned in the CONTEXT INFORMATION.
        Do not say "according to the context" or "mentioned in the context" or similar.
        """

# Initialize embedding model
embedding_model = HuggingFaceEmbeddings(model_name="dunzhang/stella_en_1.5B_v5")
# Initialize KB database
db = Chroma(collection_name="cp_database", embedding_function=embedding_model, persist_directory='./db_knowledge_base')

def format_docs(docs) -> list:
    return "\n\n".join(doc.page_content for doc in docs)

def run_rag_chain(query):
    try:
        rag_chain = load_rag_chain()
        logger.info("RAG chain created.")
        response = rag_chain.invoke(query)
        logger.info(f"Query processed successfully.response: {response}")
        return response
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        return None

def main():
    try:

        loader = PyPDFLoader('./RAG-Agent/temp/SOP.pdf', extract_images=False)
        data = loader.load()

        doc_metadata = [data[i].metadata for i in range(len(data))]
        doc_content = [data[i].page_content for i in range(len(data))]
        print("doc content is ")
        print(doc_content)
        st_text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=100,
            separators=["\n \n", "\n", ".", " "])
        st_chunks = st_text_splitter.create_documents(doc_content, doc_metadata)
        
        print(st_chunks)
        db.add_documents(st_chunks)
        print("Processed and added to the database!")
        #ask the query below now to get the response
        query="tell me about Goutham kumar"
        retriever=db.as_retriever(k=5)
        prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
        chat_model = OllamaLLM(model="qwen2.5:7b", base_url="http://localhost:11434", temperature=0.6)
        logger.info("Chat model initialized.")
        output_parser = StrOutputParser()
        logger.info("Output parser initialized.")
        

    #  Get the query embedding
        query_embedding = embedding_model.embed_query(query)
        print("Query Embedding (first 10 values):", query_embedding[:10])  # Long vector, showing first 10 for brevity
        print("Query Embedding Length:", len(query_embedding))

        # Use Chroma's similarity search with scores to get documents and metadata
        docs_with_scores = db.similarity_search_with_score(query, k=5)

        # Inspect retrieved documents and fetch their embeddings
        print("\nRetrieved Documents and Embeddings:")
        print(docs_with_scores)


        op = RunnableParallel({"context": retriever | format_docs, "question": RunnablePassthrough()}) | prompt_template | chat_model | output_parser
        print(f'response fetched from LLM and result is {op.invoke(query)}')
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()