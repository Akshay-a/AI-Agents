# crud.py
from sqlalchemy.orm import Session
from sqlalchemy import or_
from . import models
from . import schemas

# --- User CRUD Operations ---

def get_user(db: Session, user_id: int) -> models.User | None:
    """Fetches a single user by their ID."""
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_email(db: Session, email: str) -> models.User | None:
    """Fetches a single user by their email."""
    return db.query(models.User).filter(models.User.email == email).first()

def get_users(db: Session, skip: int = 0, limit: int = 100) -> list[models.User]:
    """Fetches a list of users with pagination."""
    return db.query(models.User).offset(skip).limit(limit).all()

def search_users(db: Session, query: str, limit: int = 10) -> list[models.User]:
    """Searches for users by name or email containing the query string."""
    search = f"%{query}%"
    return db.query(models.User).filter(
        or_(
            models.User.name.ilike(search), # Case-insensitive like
            models.User.email.ilike(search)
        )
    ).limit(limit).all()


def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    """Creates a new user in the database."""
    db_user = models.User(name=user.name, email=user.email)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# Todo to Add more CRUD functions here as needed (e.g., update_user, delete_user)