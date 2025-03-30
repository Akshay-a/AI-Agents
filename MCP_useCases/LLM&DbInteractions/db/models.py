# models.py
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
# Import Base from the new central base file to fix circular import problem and create tables on the fly
from .base import Base 

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    signup_date = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<User(id={self.id}, name='{self.name}', email='{self.email}')>"

# Add any other models here, inheriting from base.Base