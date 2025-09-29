"""
Db Repository for Scraper Agent
"""

import sqlite3
import json
import hashlib
from typing import List, Dict, Any, Optional, Tuple, Union
from pathlib import Path
import logging
from datetime import datetime
from dataclasses import dataclass, asdict, field
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ChatType(str, Enum):
    """Types of chat sessions."""
    BROAD = 'broad'
    URL = 'url'

@dataclass
class ChatSession:
    """Represents a chat session."""
    id: Optional[int] = None
    title: str = "Untitled"
    chat_type: ChatType = ChatType.BROAD
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    urls: List[str] = field(default_factory=list)
    summary: Optional[str] = None

@dataclass
class Message:
    """Represents a chat message."""
    id: Optional[int] = None
    session_id: Optional[int] = None
    role: str = "user"  # 'user', 'assistant', or 'system'
    content: str = ""
    created_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class DatabaseRepository:
    """Handles all database operations for the Scraper Agent."""
    
    def __init__(self, db_path: str = "scraper_agent.db"):
        """Initialize the database repository.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = str(Path(db_path).resolve())
        self._ensure_connection()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with the right settings."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dictionary-style access
        conn.execute("PRAGMA foreign_keys = ON;")  # Enable foreign key constraints
        return conn
    
    def _ensure_connection(self):
        """Ensure the database and tables exist."""
        try:
            with self._get_connection() as conn:
                # This will create the database file if it doesn't exist
                pass
            logger.info(f"Database connection established: {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    # ===== URL Operations =====
    
    def is_url_processed(self, url: str) -> bool:
        """Check if a URL has already been processed."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM processed_urls WHERE url = ? LIMIT 1",
                (url,)
            )
            return cursor.fetchone() is not None
    
    def mark_url_processed(self, url: str, metadata: Optional[Dict] = None) -> bool:
        """Mark a URL as processed."""
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
        metadata_str = json.dumps(metadata) if metadata else None
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT OR IGNORE INTO processed_urls (url_hash, url, metadata)
                VALUES (?, ?, ?)
                """, (url_hash, url, metadata_str))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.IntegrityError:
            logger.warning(f"URL already processed: {url}")
            return False
        except Exception as e:
            logger.error(f"Error marking URL as processed: {e}")
            raise
    
    def get_processed_urls(self, limit: int = 100) -> List[Dict]:
        """Get a list of processed URLs."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT url, processed_at, metadata 
                FROM processed_urls 
                ORDER BY processed_at DESC 
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    # ===== Chat Session Operations =====
    
    def create_chat_session(self, title: str, chat_type: Union[ChatType, str], 
                          urls: Optional[List[str]] = None) -> ChatSession:
        """Create a new chat session."""
        if isinstance(chat_type, str):
            chat_type = ChatType(chat_type.lower())
            
        session = ChatSession(
            title=title,
            chat_type=chat_type,
            urls=urls or [],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO chat_sessions (title, chat_type, urls, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                session.title,
                session.chat_type.value,
                json.dumps(session.urls) if session.urls else None,
                session.created_at.isoformat(),
                session.updated_at.isoformat()
            ))
            session.id = cursor.lastrowid
            conn.commit()
        
        return session

    def add_urls_to_session(self, session_id: int, urls: List[str]) -> bool:
        """Add URLs to an existing chat session."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Get current session
                session = self.get_chat_session(session_id)
                if not session:
                    return False

                # Add new URLs to existing URLs
                current_urls = set(session.urls)
                new_urls = [url for url in urls if url not in current_urls]
                updated_urls = list(current_urls.union(set(new_urls)))

                # Update session
                session.urls = updated_urls
                session.updated_at = datetime.utcnow()

                cursor.execute("""
                    UPDATE chat_sessions
                    SET urls = ?, updated_at = ?
                    WHERE id = ?
                """, (
                    json.dumps(updated_urls) if updated_urls else None,
                    session.updated_at.isoformat(),
                    session_id
                ))

                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to add URLs to session {session_id}: {e}")
            return False

    def get_chat_session(self, session_id: int) -> Optional[ChatSession]:
        """Retrieve a chat session by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM chat_sessions WHERE id = ?
            """, (session_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
                
            return self._row_to_chat_session(dict(row))
    
    def update_chat_session(self, session: ChatSession) -> bool:
        """Update an existing chat session."""
        if not session.id:
            raise ValueError("Cannot update a session without an ID")
            
        session.updated_at = datetime.utcnow()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE chat_sessions 
                SET title = ?, chat_type = ?, urls = ?, summary = ?, updated_at = ?
                WHERE id = ?
            """, (
                session.title,
                session.chat_type.value,
                json.dumps(session.urls) if session.urls else None,
                session.summary,
                session.updated_at.isoformat(),
                session.id
            ))
            conn.commit()
            return cursor.rowcount > 0
    
    def list_chat_sessions(self, limit: int = 20, offset: int = 0) -> List[ChatSession]:
        """List chat sessions with pagination."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM chat_sessions 
                ORDER BY updated_at DESC 
                LIMIT ? OFFSET ?
            """, (limit, offset))
            
            return [self._row_to_chat_session(dict(row)) for row in cursor.fetchall()]
    
    def delete_chat_session(self, session_id: int) -> bool:
        """Delete a chat session and all its messages."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Delete messages first due to foreign key constraint
            cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    # ===== Message Operations =====
    
    def add_message(self, session_id: int, role: str, content: str, 
                   metadata: Optional[Dict] = None) -> Message:
        """Add a message to a chat session."""
        message = Message(
            session_id=session_id,
            role=role,
            content=content,
            metadata=metadata or {},
            created_at=datetime.utcnow()
        )
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO messages (session_id, role, content, metadata, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                message.session_id,
                message.role,
                message.content,
                json.dumps(message.metadata) if message.metadata else None,
                message.created_at.isoformat()
            ))
            message.id = cursor.lastrowid
            
            # Update session's updated_at timestamp
            cursor.execute("""
                UPDATE chat_sessions 
                SET updated_at = ?
                WHERE id = ?
            """, (message.created_at.isoformat(), session_id))
            
            conn.commit()
        
        return message
    
    def get_messages(self, session_id: int, limit: int = 100, 
                    offset: int = 0) -> List[Message]:
        """Get messages for a chat session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM messages 
                WHERE session_id = ? 
                ORDER BY created_at ASC
                LIMIT ? OFFSET ?
            """, (session_id, limit, offset))
            
            return [self._row_to_message(dict(row)) for row in cursor.fetchall()]
    
    def get_message(self, message_id: int) -> Optional[Message]:
        """Get a specific message by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM messages WHERE id = ?", (message_id,))
            row = cursor.fetchone()
            return self._row_to_message(dict(row)) if row else None
    
    def delete_message(self, message_id: int) -> bool:
        """Delete a message."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages WHERE id = ?", (message_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    # ===== Helper Methods =====
    
    @staticmethod
    def _row_to_chat_session(row: Dict) -> ChatSession:
        """Convert a database row to a ChatSession object."""
        try:
            urls = json.loads(row['urls']) if row.get('urls') else []
        except (json.JSONDecodeError, TypeError):
            urls = []
            
        return ChatSession(
            id=row['id'],
            title=row['title'],
            chat_type=ChatType(row['chat_type']),
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']),
            urls=urls,
            summary=row.get('summary')
        )
    
    @staticmethod
    def _row_to_message(row: Dict) -> Message:
        """Convert a database row to a Message object."""
        try:
            metadata = json.loads(row['metadata']) if row.get('metadata') else {}
        except (json.JSONDecodeError, TypeError):
            metadata = {}
            
        return Message(
            id=row['id'],
            session_id=row['session_id'],
            role=row['role'],
            content=row['content'],
            created_at=datetime.fromisoformat(row['created_at']),
            metadata=metadata
        )
    
    def __enter__(self):
        """Support for context manager protocol."""
        self.conn = self._get_connection()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up resources when exiting context."""
        if hasattr(self, 'conn'):
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.conn.close()


# Example usage
if __name__ == "__main__":
    # Initialize the repository
    repo = DatabaseRepository()
    
    # Create a new chat session
    session = repo.create_chat_session(
        title="Test Session",
        chat_type=ChatType.URL,
        urls=["https://example.com"]
    )
    print(f"Created session: {session.id}")
    
    # Add some messages
    repo.add_message(session.id, "user", "Hello, world!")
    repo.add_message(session.id, "assistant", "Hi there! How can I help you?")
    
    # Retrieve messages
    messages = repo.get_messages(session.id)
    for msg in messages:
        print(f"{msg.role}: {msg.content}")
    
    # List all sessions
    sessions = repo.list_chat_sessions()
    print(f"Total sessions: {len(sessions)}")
