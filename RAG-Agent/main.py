import os
import logging
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableParallel
from langchain_ollama import OllamaLLM

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

embedding_model = HuggingFaceEmbeddings(model_name="dunzhang/stella_en_1.5B_v5")
db = Chroma(collection_name="cp_database", embedding_function=embedding_model, persist_directory='./db_knowledge_base')
"""
The RecursiveCharacterTextSplitter:
Takes the full text and checks if it’s <= chunk_size (1500). If not, it proceeds.
Looks for the first separator (\n \n) to split the text into segments.
If a segment is still > chunk_size, it moves to the next separator (\n), then ., then " ".
Applies chunk_overlap to ensure continuity, pulling back 200 characters from the previous chunk.
Repeats recursively until all chunks are <= chunk_size.
"""
PROMPT_TEMPLATE = """
Based on the following context:
{context}

Answer the question: {question}
"""

def format_docs(docs):
    context = "\n\n".join(doc.page_content for doc in docs)
    print("Retrieved Context:", context)
    return context

def main():
    try:
        # Load PDF
        loader = PyPDFLoader('./RAG-Agent/temp/SOP.pdf', extract_images=False)
        data = loader.load()
        doc_content = [data[i].page_content for i in range(len(data))]
        doc_metadata = [data[i].metadata for i in range(len(data))]
        #print("Raw Document Content:", doc_content)

        # Split into chunks
        st_text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1500,
            chunk_overlap=200,
            separators=["\n \n", "\n", ".", " "]
        )
        st_chunks = st_text_splitter.create_documents(doc_content, doc_metadata)
        print("Chunks:", [chunk.page_content for chunk in st_chunks])

        # Reset and populate database
        db = Chroma(collection_name="cp_database", embedding_function=embedding_model, persist_directory='./db_knowledge_base')
        db.add_documents(st_chunks)
        print("Processed and added to the database!")

        # Query
        query = "tell me about Goutham Kumar"
        retriever = db.as_retriever(search_kwargs={'k': 5})

        # Get query embedding
        query_embedding = embedding_model.embed_query(query)
        #print("Query Embedding (first 10):", query_embedding[:10])

        # Retrieve documents
        docs_with_scores = db.similarity_search_with_score(query, k=5)
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