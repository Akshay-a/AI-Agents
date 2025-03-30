# database.py
import os
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

# Import Base from the new central base file
from .base import Base  


from . import models 

# Define DB Path consistently
DB_FILE_PATH = "./mcp_database.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_FILE_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}, # Needed only for SQLite
    # echo=True # Uncomment for debugging SQL
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# No need to define Base here anymore, it's imported

def init_db():
    """Initializes the database and creates tables if they don't exist."""
    print("Initializing database schema (checking tables)...")
    # Base.metadata should now contain table definitions from the imported 'models' module
    try:
        Base.metadata.create_all(bind=engine)
        print("Database schema ready.")
    except Exception as e:
        print(f"Error during table creation: {e}")
        raise # Re-raise the exception to halt if creation fails

@contextmanager
def get_db():
    """Provides a transactional scope around a series of operations."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def check_if_table_empty(db_session, table_model):
    """Checks if a specific table is empty within the given session."""
    return db_session.query(table_model).first() is None

def add_initial_data():
    """Adds initial data ONLY if the users table is empty."""
    # 1. Ensure the schema/tables exist first. init_db() will now work correctly
    #    because the 'models' module was imported at the top level.
    try:
        init_db()
    except Exception as e:
        print(f"Halting due to error during init_db: {e}")
        return # Stop if table creation failed

    # 2. Use a session to check and populate
    print("Checking if initial data population is needed...")
    try:
        with get_db() as db:
            # Use the imported models directly (e.g., models.User)
            target_model = models.User
            table_name = target_model.__tablename__

            # Check if the table exists using inspector (belt-and-suspenders check)
            inspector = inspect(engine)
            if not inspector.has_table(table_name):
                 # This *shouldn't* happen now if init_db succeeded, but good to check
                 print(f"Error: Table '{table_name}' still not found after successful init_db().")
                 return

            # Check if the table is empty
            if check_if_table_empty(db, target_model):
                print(f"Table '{table_name}' is empty. Populating initial data...")
                # Import crud/schemas only when needed
                from .crud import create_user
                from .schemas import UserCreate

                initial_users = [
                    {"name": "Alice Wonderland", "email": "alice@example.com"},
                    {"name": "Bob The Builder", "email": "bob@example.com"},
                    {"name": "Charlie Chaplin", "email": "charlie@example.com"},
                ]

                for user_data in initial_users:
                    user_schema = UserCreate(**user_data)
                    create_user(db=db, user=user_schema)

                print("Initial data added successfully.")
            else:
                print(f"Table '{table_name}' already contains data. Skipping population.")

    except Exception as e:
        print(f"An error occurred during initial data check/population: {e}")
        # Optionally re-raise the exception
        # raise

if __name__ == "__main__":
    print(f"Running database script directly: {__file__}")
    # No extra imports needed here now
    add_initial_data()
    print("Database script finished.")