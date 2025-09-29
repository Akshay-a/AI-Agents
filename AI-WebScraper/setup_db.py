#!/usr/bin/env python3
"""
Database setup script for Scraper Agent.
Creates SQLite database with necessary tables and indexes.
"""

import sqlite3
import os
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configuration
DB_NAME = "scraper_agent.db"
DB_PATH = str(Path(__file__).parent / DB_NAME)

# SQL statements for table creation
SQL_CREATE_TABLES = """
-- Processed URLs table
CREATE TABLE IF NOT EXISTS processed_urls (
    url_hash TEXT PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT  -- Optional: store additional info
);

-- Chat sessions table
CREATE TABLE IF NOT EXISTS chat_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    chat_type TEXT NOT NULL,  -- 'broad' or 'url'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    urls TEXT,  -- JSON array of URLs for URL analysis sessions
    summary TEXT  -- Brief summary of the chat session
);

-- Messages table
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    role TEXT NOT NULL,  -- 'user' or 'assistant' or 'system'
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT,  -- JSON field for additional metadata
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
);
"""

# Index creation SQL
SQL_CREATE_INDEXES = """
-- Indexes for processed_urls
CREATE INDEX IF NOT EXISTS idx_processed_urls_url ON processed_urls(url);
CREATE INDEX IF NOT EXISTS idx_processed_urls_processed_at ON processed_urls(processed_at);

-- Indexes for chat_sessions
CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated_at ON chat_sessions(updated_at);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_created_at ON chat_sessions(created_at);

-- Indexes for messages
CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role);
"""

def setup_database():
    """Set up the SQLite database with required tables and indexes."""
    try:
        # Remove existing database if it exists
        if os.path.exists(DB_PATH):
            logger.warning(f"Database already exists at {DB_PATH}. It will be removed and recreated.")
            os.remove(DB_PATH)
        
        logger.info(f"Creating new database at {DB_PATH}")
        
        # Connect to SQLite (creates the database file if it doesn't exist)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys = ON;")
        
        # Create tables
        logger.info("Creating tables...")
        cursor.executescript(SQL_CREATE_TABLES)
        
        # Create indexes
        logger.info("Creating indexes...")
        cursor.executescript(SQL_CREATE_INDEXES)
        
        # Verify the tables were created
        cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' 
        ORDER BY name;
        """)
        
        tables = cursor.fetchall()
        logger.info("Tables created successfully:")
        for table in tables:
            logger.info(f"- {table[0]}")
        
        # Verify indexes
        cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='index' 
        AND name LIKE 'idx_%';
        """)
        
        indexes = cursor.fetchall()
        logger.info("\nIndexes created successfully:")
        for idx in indexes:
            logger.info(f"- {idx[0]}")
        
        # Commit changes and close connection
        conn.commit()
        conn.close()
        
        logger.info("\nDatabase setup completed successfully!")
        logger.info(f"Database file: {os.path.abspath(DB_PATH)}")
        
    except Exception as e:
        logger.error(f"Error setting up database: {e}", exc_info=True)
        if 'conn' in locals():
            conn.rollback()
        raise

if __name__ == "__main__":
    print("=" * 60)
    print("Scraper Agent Database Setup")
    print("=" * 60)
    print(f"This will create a new SQLite database at: {os.path.abspath(DB_PATH)}")
    print("The following tables will be created:")
    print("- processed_urls: Tracks processed URLs to avoid reprocessing")
    print("- chat_sessions: Stores chat session metadata")
    print("- messages: Stores individual chat messages")
    print("\nIndexes will also be created for better performance.")
    print("-" * 60)
    
    confirm = input("Do you want to continue? (y/n): ").strip().lower()
    if confirm == 'y':
        setup_database()
    else:
        print("Database setup cancelled.")
