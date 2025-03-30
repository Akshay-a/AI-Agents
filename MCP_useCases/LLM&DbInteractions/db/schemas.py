# schemas.py
from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional
from datetime import datetime

# Base schema for User properties
class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None

# Schema for creating a user (inherits from UserBase)
# Used when receiving data via API POST request
class UserCreate(UserBase):
    pass # No extra fields needed for creation beyond UserBase as we only have email & name at the moment

# Schema for reading user data (inherits from UserBase)
# Used when returning data via API GET requests
class User(UserBase):
    id: int
    signup_date: datetime

    model_config = ConfigDict(from_attributes=True) # Pydantic V2 way for ORM mode

# Schema specifically for the add_user tool's arguments and to add validation layer before hitting to server
# Ensures LLM provides data in the correct format
class AddUserToolArgs(BaseModel):
    name: str
    email: EmailStr

# Schema specifically for the get_user_by_id tool's arguments 
class GetUserByIdToolArgs(BaseModel):
    user_id: int

# Schema specifically for the search_users tool's arguments
class SearchUsersToolArgs(BaseModel):
    query: str