import chainlit as cl
import PyPDF2
import docx
import chromadb
from transformers import BertTokenizer, BertModel
import torch
import uuid
from typing import List, Dict

# Initialize Chroma client with persistent storage
chroma_client = chromadb.PersistentClient(path="chroma_storage")

# Create or load a collection
collection = chroma_client.get_or_create_collection(name="knowledge_base")

# Load pre-trained BERT model and tokenizer
tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
model = BertModel.from_pretrained('bert-base-uncased')

def extract_text_from_pdf(file):
    reader = PyPDF2.PdfFileReader(file)
    text = ''
    for page_num in range(reader.numPages):
        text += reader.getPage(page_num).extract_text()
    return text

def extract_text_from_docx(file):
    doc = docx.Document(file)
    text = '\n'.join([para.text for para in doc.paragraphs])
    return text

def chunk_text(text: str) -> List[str]:
        """Split text into overlapping chunks for better context preservation"""
        words = text.split()
        chunks = []
        
        for i in range(0, len(words),128):
            chunk = ' '.join(words[i:i + 128])
            chunks.append(chunk)
        
        return chunks

def generate_embeddings(text):
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True, max_length=128)
    with torch.no_grad():
        outputs = model(**inputs)
    print("created outputs for the file")
    # Use [CLS] token embedding as the sequence embedding
    embedding = outputs.last_hidden_state[:, 0, :].numpy()
    return embedding.squeeze()

@cl.on_chat_start
async def start():
    await cl.Message(content="Welcome! You can upload a document (PDF or Word) or ask a question.").send()

@cl.on_message
async def main(message: cl.Message):
    print("Message elements:", message.elements)
    
    # File upload handling
    if message.elements:
        for element in message.elements:
            if element.type == "file":
                file = element
                print("File details:", file.name, file.path)
                
                # Extract text based on file type
                if file.name.endswith('.pdf'):
                    text = extract_text_from_pdf(file.path)
                elif file.name.endswith('.docx'):
                    text = extract_text_from_docx(file.path)
                else:
                    await cl.Message(content="Unsupported file format. Please upload a PDF or Word document.").send()
                    return

                chunks = chunk_text(text)
               # Generate embeddings and store chunks
                embeddings = []
                ids = []
                metadatas = []
                
                for i, chunk in enumerate(chunks):
                    embedding = generate_embeddings(chunk)
                    chunk_id = f"{str(uuid.uuid4())}_{i}"
                    
                    embeddings.append(embedding.tolist())
                    ids.append(chunk_id)
                    metadatas.append({
                        "filename": file.name,
                        "chunk_index": i,
                        "text": chunk
                    })

                # Store in Chroma
                collection.add(
                    embeddings=embeddings,
                    ids=ids,
                    metadatas=metadatas
                )
            
                
                

                await cl.Message(content=f"Document '{file.name}' added successfully!").send()
        return  # Exit after handling files

    # Question handling
    question = message.content
    print("Question:", question)
    question_embedding = generate_embeddings(question)
    print("created Embeddings & now searching!")
    # Search in Chroma
    try:
        results = collection.query(
            query_embeddings=[question_embedding.tolist()],
            n_results=3,
               include=["metadatas", "distances"]  # Return the top 3 result
        )
        print("Results:", results)
        formatted_results = []
        if results['documents'] and len(results['documents'][0]) > 0:
            distance = results['distances'][0][0]  # Get the distance of the first result
            if distance < 0.5:  # Adjust threshold as needed
                document_text = results['documents'][0][0]
                file_name = results['metadatas'][0][0]['filename']
                await cl.Message(content=f"Found in {file_name}:\n\n{document_text}").send()
            else:
                await cl.Message(content="No sufficiently similar content found in the knowledge base.").send()
        else:
            await cl.Message(content="No matching content found in the knowledge base.").send()
            
        
        """"                
        if results and results['distances'] and results['distances'][0] and results['distances'][0][0] < 0.5:
            # Retrieve metadata or document content if available
            metadata = results['metadatas'][0][0]
            await cl.Message(content=f"Answer found in document '{metadata['filename']}'. (Details can be added here)").send()
        else:
            await cl.Message(content="I can't find the answer in the knowledge base.").send()
        """
    except Exception as e:
        print("Error querying Chroma:", e)
        await cl.Message(content="An error occurred while searching the knowledge base.").send()



if __name__ == "__main__":
    main()