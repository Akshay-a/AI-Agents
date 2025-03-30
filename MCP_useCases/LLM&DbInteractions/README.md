Below is the mermaid diagram
```mermaid

sequenceDiagram
    participant User
    participant Agent as LLM Agent
    participant LLM as LLM API (Gemini)
    participant MCP as MCP Server
    participant DB as Database

    Note over User,DB: Query Processing Flow
    
    User->>Agent: 1. Submit query: "Who is user 1?"
    
    Agent->>LLM: 2. Send query + available tool definitions 
    Note right of LLM: LLM analyzes if tools needed
    
    alt Tool needed
        LLM->>Agent: 3. Return function call (get_user_by_id, {id: 1})
        Agent->>Agent: 4. Validate function & arguments
        Agent->>MCP: 5. Call MCP API endpoint
        MCP->>DB: 6. Execute database query
        DB->>MCP: 7. Return user data
        MCP->>Agent: 8. Return API response (user details)
        Agent->>LLM: 9. Send function result
        LLM->>Agent: 10. Generate final response with data
    else No tool needed
        LLM->>Agent: 3a. Return direct text response
    end
    
    Agent->>User: 11. Display final response
