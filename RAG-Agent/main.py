import os
import streamlit as st

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters.sentence_transformers import SentenceTransformersTokenTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_ollama import OllamaLLM
from sentence_transformers import SentenceTransformer
from langchain_huggingface import HuggingFaceEmbeddings

# Initialize embedding model
#embedding_model = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
embedding_model = HuggingFaceEmbeddings(model_name="dunzhang/stella_en_1.5B_v5")
#SentenceTransformer('all-MiniLM-L6-v2')
# Initialize KB database
db = Chroma(collection_name="cp_database",
            embedding_function=embedding_model,
            persist_directory='./db_knowledge_base')

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

def add_to_db(uploaded_files):
    # Check if files are uploaded
    if not uploaded_files:
        st.error("No files uploaded!")
        return

    for uploaded_file in uploaded_files:
        # Save the uploaded file to a temporary path
        temp_file_path = os.path.join("./temp", uploaded_file.name)
        os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)

        with open(temp_file_path, "wb") as temp_file:
            temp_file.write(uploaded_file.getbuffer())

        # Load the file using PyPDFLoader
        loader = PyPDFLoader(temp_file_path,extract_images = False)
        data = loader.load()

        # Store metadata and content
        doc_metadata = [data[i].metadata for i in range(len(data))]
        doc_content = [data[i].page_content for i in range(len(data))]

        # Split documents into smaller chunks
        st_text_splitter = SentenceTransformersTokenTextSplitter(
            model_name="sentence-transformers/all-mpnet-base-v2",
            chunk_size=100,
            chunk_overlap=50
        )
        st_chunks = st_text_splitter.create_documents(doc_content, doc_metadata)

        # Add chunks to database
        #db.add_documents(st_chunks)
        db.add_documents(data)

        # Remove the temporary file after processing
        os.remove(temp_file_path)

def run_rag_chain(query):
    # Create a Retriever Object and apply Similarity Search
    retriever = db.as_retriever(search_type="similarity", search_kwargs={'k': 5})

    # Initialize a Chat Prompt Template
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

    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)

    # Initialize a Generator (i.e. Chat Model)
    chat_model = OllamaLLM(
        model="qwen2.5:7b",
        base_url="http://localhost:11434",  # Assuming Ollama is running locally on this port
        temperature=1
    )

    # Initialize a Output Parser
    output_parser = StrOutputParser()

    # RAG Chain
    rag_chain = {"context": retriever | format_docs, "question": RunnablePassthrough()} | prompt_template | chat_model | output_parser

    # Invoke the Chain
    response = rag_chain.invoke(query)

    return response


def main():
    st.set_page_config(page_title="Query", page_icon=":microscope:")
    st.header("KB Retrieval System")

    query = st.text_area(
        ":bulb: Enter your query about the document:",
        placeholder="e.g., What is the info on document?"
    )

    if st.button("Submit"):
        if not query:
            st.warning("Please ask a question")
        
        else:
            with st.spinner("Thinking..."):
                result = run_rag_chain(query=query)
                st.write(result)

    
    with st.sidebar:
        st.markdown("---")
        pdf_docs = st.file_uploader("Upload PDF to the knowledge base",
                                    type=["pdf"],
                                    accept_multiple_files=True
        )
        
        if st.button("Submit & Process"):
            if not pdf_docs:
                st.warning("Please upload the file")

            else:
                with st.spinner("Processing your documents..."):
                    add_to_db(pdf_docs)
                    st.success(":file_folder: Documents successfully added to the database!")

    # Sidebar Footer
    st.sidebar.write("Just a Side Project!!")
             
if __name__ == "__main__":
    main()