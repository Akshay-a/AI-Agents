# mcp_server.py
import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

import db.crud as crud
import db.models as models
import db.schemas as schemas
from db.database import SessionLocal, engine, add_initial_data, init_db

# Initialize DB and add initial data if needed when server starts
# init_db() # Ensure tables are created---> # add_initial_data() # Add sample data if DB was just created

app = FastAPI(
    title="MCP Database Access Server",
    description="Provides API endpoints (tools) for interacting with the user database.",
    version="1.0.0"  #todo- to learn more about versioning
)

# to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- API Endpoints AKA (Tools) which MCP server si gonna expose---

@app.post("/users/", response_model=schemas.User, tags=["Users"], summary="Add a new user")
def api_create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    Creates a new user in the database.
    Requires name and email.
    Returns the created user details including ID and signup date.
    """
    db_user = crud.get_user_by_email(db, email=user.email)      
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db=db, user=user)

@app.get("/users/{user_id}", response_model=schemas.User, tags=["Users"], summary="Get user by ID")
def api_read_user(user_id: int, db: Session = Depends(get_db)):
    """
    Retrieves a specific user by their unique ID.
    Returns user details or a 404 error if not found.
    """
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

@app.get("/users/", response_model=List[schemas.User], tags=["Users"], summary="List all users")
def api_read_users(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    """
    Retrieves a list of users. Supports pagination using 'skip' and 'limit' query parameters.
    Default limit is 10.
    """
    users = crud.get_users(db, skip=skip, limit=limit)
    return users

@app.get("/users/search/", response_model=List[schemas.User], tags=["Users"], summary="Search users")
def api_search_users(
    query: str = Query(..., min_length=1, description="Search term for name or email"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results to return"),
    db: Session = Depends(get_db)
):
    """
    Searches for users whose name or email contains the query string (case-insensitive).
    Returns a list of matching users.
    """
    users = crud.search_users(db, query=query, limit=limit)
    if not users:
         # Return empty list, maybe LLM can handle it. Or raise 404? Let's return empty list.
         # raise HTTPException(status_code=404, detail=f"No users found matching '{query}'")
         pass
    return users

@app.get("/tools", tags=["Meta"], summary="List available tools")
async def list_tools():
    """
    Provides a list of available API endpoints (tools) that the LLM can use.
    This is useful for introspection or potentially dynamically feeding tools to the LLM.
    """
    tool_list = []
    for route in app.routes:
        if hasattr(route, "summary") and route.summary: # Check if it's an endpoint with a summary
             tool_list.append({
                 "path": route.path,
                 "name": route.name,
                 "methods": list(route.methods) if hasattr(route, "methods") else [],
                 "summary": route.summary,
                 "description": route.description or route.summary, # Use description if available
             })
    return {"available_tools": tool_list}


if __name__ == "__main__":
    # Run this only when executing `python mcp_server.py`
    # Ensure DB is ready before starting the server
    print("Checking database...")
    add_initial_data() # This function includes init_db()
    print("Starting MCP server...")
    # Use 0.0.0.0 to make it accessible from other containers/machines if needed
    uvicorn.run(app, host="127.0.0.1", port=8000)