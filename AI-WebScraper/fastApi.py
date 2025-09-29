
import asyncio
from typing import List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from app import SearchAgent
from database_repository import DatabaseRepository, ChatSession, Message, ChatType

# --- FastAPI App Initialization ---
app = FastAPI(
    title="AI Web Scraper API",
    description="An API for scraping web content, storing it in a vector DB, and chatting about it.",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Global Instances ---
# These are instantiated once and reused across requests.
search_agent = SearchAgent()
db_repo = DatabaseRepository()

# --- Pydantic Models (for Request/Response validation) ---

class UrlList(BaseModel):
    """Model for a list of URLs."""
    urls: List[str] = Field(..., example=["https://www.example.com/article1", "https://www.example.com/article2"])

class UserMessage(BaseModel):
    """Model for a user's chat message."""
    content: str = Field(..., example="What is the main topic of the articles?")

class SessionResponse(BaseModel):
    """Model for a new session response."""
    id: int
    title: str
    chat_type: str
    urls: List[str] = []

class SessionUpdate(BaseModel):
    """Model for updating a session."""
    title: Optional[str] = None
    urls: Optional[List[str]] = None

class MessageResponse(BaseModel):
    """Model for a message response."""
    id: int
    session_id: int
    role: str
    content: str
    created_at: str

# --- Background Task Function ---

async def process_urls_task(session_id: int, urls: List[str]):
    """
    Asynchronous task to process and index URLs for a given session.
    This runs in the background to not block the API response.
    """
    print(f"Starting background task to process {len(urls)} URLs for session {session_id}...")
    try:
        # The 'context' here is crucial for filtering RAG results later.
        context = f"session_{session_id}"
        result = await search_agent.run_batch_urls(urls=urls, context=context)
        print(f"Background task for session {session_id} completed. Result: {result}")
    except Exception as e:
        print(f"Error in background task for session {session_id}: {e}")

# --- API Endpoints ---

@app.post("/sessions", response_model=SessionResponse, status_code=201)
async def create_session():
    """
    Creates a new chat session.
    
    This endpoint initializes a new conversation, providing a unique session ID
    that is used to associate URLs and messages.
    """
    try:
        session = db_repo.create_chat_session(
            title="New Session",
            chat_type=ChatType.URL
        )
        return SessionResponse(id=session.id, title=session.title, chat_type=session.chat_type.value, urls=session.urls)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create session: {e}")

@app.get("/sessions", response_model=List[SessionResponse])
async def list_sessions():
    """
    Lists all previously created chat sessions.

    Useful for a UI that allows users to resume past conversations.
    """
    try:
        sessions = db_repo.list_chat_sessions(limit=100) # Increased limit
        return [SessionResponse(id=s.id, title=s.title, chat_type=s.chat_type.value, urls=s.urls) for s in sessions]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {e}")

@app.put("/sessions/{session_id}")
async def update_session(
    session_id: int = Path(..., description="The ID of the session to update."),
    session_update: SessionUpdate = None
):
    """
    Updates a chat session's title or other properties.

    Useful for updating session metadata like titles based on conversation content.
    """
    if not session_update:
        raise HTTPException(status_code=400, detail="No update data provided.")

    # Get the current session
    session = db_repo.get_chat_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session with ID {session_id} not found.")

    # Update only the provided fields
    if session_update.title is not None:
        session.title = session_update.title

    if session_update.urls is not None:
        session.urls = session_update.urls

    try:
        success = db_repo.update_chat_session(session)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update session.")

        return {"message": "Session updated successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update session: {e}")

@app.post("/sessions/{session_id}/urls")
async def add_urls_to_session(
    background_tasks: BackgroundTasks,
    session_id: int = Path(..., description="The ID of the session to add URLs to."),
    url_list: UrlList = None
):
    """
    Adds and processes a list of URLs for a specific session.
    
    This endpoint accepts a list of URLs, validates the session, and then
    triggers a background task to scrape and index the content. It returns
    an immediate response to keep the UI responsive.
    """
    if not url_list or not url_list.urls:
        raise HTTPException(status_code=400, detail="URL list cannot be empty.")

    # Verify the session exists before starting a background task
    if not db_repo.get_chat_session(session_id):
        raise HTTPException(status_code=404, detail=f"Session with ID {session_id} not found.")
    
    # Update session URLs immediately
    success = db_repo.add_urls_to_session(session_id, url_list.urls)
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to update session {session_id} with URLs.")

    # Add the processing task to run in the background
    background_tasks.add_task(process_urls_task, session_id, url_list.urls)

    return {"message": f"URL processing started for session {session_id} in the background."}

@app.get("/sessions/{session_id}/messages", response_model=List[MessageResponse])
async def get_session_messages(
    session_id: int = Path(..., description="The ID of the session to retrieve messages for.")
):
    """
    Retrieves all messages for a specific chat session.
    
    This is used to load the chat history when a user selects a past conversation.
    """
    if not db_repo.get_chat_session(session_id):
        raise HTTPException(status_code=404, detail=f"Session with ID {session_id} not found.")
    
    try:
        messages = db_repo.get_messages(session_id=session_id, limit=500)
        return [
            MessageResponse(
                id=m.id,
                session_id=m.session_id,
                role=m.role,
                content=m.content,
                created_at=m.created_at.isoformat()
            ) for m in messages
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve messages: {e}")

@app.post("/sessions/{session_id}/messages", response_model=MessageResponse)
async def post_message(
    session_id: int = Path(..., description="The ID of the session to post a message to."),
    message: UserMessage = None
):
    """
    Posts a message to a session and gets an AI-generated response.
    
    This is the core chat endpoint. It saves the user's message, performs a
    RAG search filtered by the session's content, gets a response from the LLM,
    saves the assistant's response, and returns it.
    """
    if not message or not message.content:
        raise HTTPException(status_code=400, detail="Message content cannot be empty.")

    if not db_repo.get_chat_session(session_id):
        raise HTTPException(status_code=404, detail=f"Session with ID {session_id} not found.")

    try:
        # 1. Save the user's message
        db_repo.add_message(session_id=session_id, role='user', content=message.content)
        
        # 2. Perform RAG search, filtering by the session context
        context_identifier = f"session_{session_id}"
        search_results = await search_agent.search_rag(
            query=message.content,
            question=context_identifier,
            n_results=5,
            filter_by_question=True
        )
        
        # 3. Prepare context for the LLM
        if search_results:
            combined_context = "\n\n---\n\n".join(
                f"Source: {res.get('metadata', {}).get('url', 'N/A')}\n"
                f"Content: {res.get('text', 'No content')}"
                for res in search_results
            )
        else:
            combined_context = "No relevant information found in the provided URLs for this session."

        # 4. Get LLM response
        llm_response = await search_agent.get_llm_response(
            question=message.content,
            context=combined_context
        )
        
        if not llm_response:
            llm_response = "I could not generate a response based on the available information."

        # 5. Save the assistant's message
        assistant_message = db_repo.add_message(
            session_id=session_id,
            role='assistant',
            content=llm_response
        )
        
        return MessageResponse(
            id=assistant_message.id,
            session_id=assistant_message.session_id,
            role=assistant_message.role,
            content=assistant_message.content,
            created_at=assistant_message.created_at.isoformat()
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process message: {e}")

# To run this app:
# uvicorn fastApi:app --reload
