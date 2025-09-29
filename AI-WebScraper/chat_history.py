import sqlite3
from datetime import datetime
import json
from typing import List, Dict, Any, Optional
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ChatHistoryManager:
    def __init__(self, db_path: str = "./chat_history.db"):
        """Initialize the ChatHistoryManager.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._init_db()
        
    def _init_db(self):
        """Initialize the SQLite database with necessary tables."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create chat_sessions table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    chat_type TEXT NOT NULL,  -- 'broad' or 'url'
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    urls TEXT,  -- JSON array of URLs for URL analysis sessions
                    summary TEXT  -- Brief summary of the chat session
                )
                """)
                
                # Create messages table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    role TEXT NOT NULL,  -- 'user' or 'assistant'
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT,  -- JSON field for additional metadata
                    FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
                )
                """)
                
                conn.commit()
                logger.info("Database initialized successfully")
                
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
            
    def create_session(self, title: str, chat_type: str, urls: Optional[List[str]] = None) -> int:
        """Create a new chat session.
        
        Args:
            title: Title of the chat session
            chat_type: Type of chat ('broad' or 'url')
            urls: List of URLs for URL analysis sessions
            
        Returns:
            ID of the created session
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                INSERT INTO chat_sessions (title, chat_type, urls)
                VALUES (?, ?, ?)
                """, (title, chat_type, json.dumps(urls) if urls else None))
                
                session_id = cursor.lastrowid
                conn.commit()
                
                logger.info(f"Created new chat session with ID: {session_id}")
                return session_id
                
        except Exception as e:
            logger.error(f"Error creating chat session: {e}")
            raise
            
    def add_message(self, session_id: int, role: str, content: str, metadata: Optional[Dict] = None):
        """Add a message to a chat session.
        
        Args:
            session_id: ID of the chat session
            role: Role of the message sender ('user' or 'assistant')
            content: Content of the message
            metadata: Additional metadata for the message
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                INSERT INTO messages (session_id, role, content, metadata)
                VALUES (?, ?, ?, ?)
                """, (session_id, role, content, json.dumps(metadata) if metadata else None))
                
                # Update session's updated_at timestamp
                cursor.execute("""
                UPDATE chat_sessions 
                SET updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """, (session_id,))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error adding message: {e}")
            raise
            
    def get_session_history(self, session_id: int) -> List[Dict[str, Any]]:
        """Get all messages from a chat session.
        
        Args:
            session_id: ID of the chat session
            
        Returns:
            List of message dictionaries
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                SELECT role, content, created_at, metadata
                FROM messages
                WHERE session_id = ?
                ORDER BY created_at ASC
                """, (session_id,))
                
                messages = []
                for row in cursor.fetchall():
                    message = dict(row)
                    if message['metadata']:
                        message['metadata'] = json.loads(message['metadata'])
                    messages.append(message)
                    
                return messages
                
        except Exception as e:
            logger.error(f"Error retrieving session history: {e}")
            raise
            
    def get_recent_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recently updated chat sessions.
        
        Args:
            limit: Maximum number of sessions to return
            
        Returns:
            List of session dictionaries
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                SELECT id, title, chat_type, created_at, updated_at, urls, summary
                FROM chat_sessions
                ORDER BY updated_at DESC
                LIMIT ?
                """, (limit,))
                
                sessions = []
                for row in cursor.fetchall():
                    session = dict(row)
                    if session['urls']:
                        session['urls'] = json.loads(session['urls'])
                    sessions.append(session)
                    
                return sessions
                
        except Exception as e:
            logger.error(f"Error retrieving recent sessions: {e}")
            raise
            
    def update_session_summary(self, session_id: int, summary: str):
        """Update the summary of a chat session.
        
        Args:
            session_id: ID of the chat session
            summary: New summary text
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                UPDATE chat_sessions
                SET summary = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """, (summary, session_id))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error updating session summary: {e}")
            raise

# Example usage
if __name__ == "__main__":
    # Initialize manager
    chat_mgr = ChatHistoryManager()
    
    # Create a new chat session
    session_id = chat_mgr.create_session(
        title="Test Chat Session",
        chat_type="broad"
    )
    
    # Add some messages
    chat_mgr.add_message(
        session_id=session_id,
        role="user",
        content="What is the latest news about the Fed rate cut?",
        metadata={"timestamp": datetime.now().isoformat()}
    )
    
    chat_mgr.add_message(
        session_id=session_id,
        role="assistant",
        content="According to recent reports...",
        metadata={
            "timestamp": datetime.now().isoformat(),
            "sources": ["source1.com", "source2.com"]
        }
    )
    
    # Get session history
    messages = chat_mgr.get_session_history(session_id)
    print("\nChat History:")
    for msg in messages:
        print(f"{msg['role']}: {msg['content']}")
        
    # Get recent sessions
    sessions = chat_mgr.get_recent_sessions(limit=5)
    print("\nRecent Sessions:")
    for session in sessions:
        print(f"{session['title']} ({session['chat_type']}) - Last updated: {session['updated_at']}")
