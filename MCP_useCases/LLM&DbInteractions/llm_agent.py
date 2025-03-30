# llm_agent.py
import google.generativeai as genai
import os
import json
import requests # To make HTTP requests to the MCP server
from dotenv import load_dotenv
from google.generativeai.types import GenerationConfig, FunctionDeclaration, Tool
from pydantic import ValidationError # For validating tool arguments

# Load environment variables (API Key, Server URL)
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8000") # Default if not set

if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in .env file")
if not MCP_SERVER_URL:
    raise ValueError("MCP_SERVER_URL not found in .env file")

genai.configure(api_key=GOOGLE_API_KEY)

# --- Define Functions (Tools) for the LLM ---
# Todo to make sure These descriptions accurately reflect the FastAPI endpoints

# Tool for getting user by ID
get_user_by_id_func = FunctionDeclaration(
    name="get_user_by_id",
    description="Get information about a specific user based on their unique ID.",
    parameters={
        "type": "object",
        "properties": {
            "user_id": {
                "type": "integer",
                "description": "The unique identifier of the user."
            }
        },
        "required": ["user_id"]
    }
)

# Tool for listing all users
list_users_func = FunctionDeclaration(
    name="get_users",
    description="Retrieve a list of all registered users. Can specify offset (skip) and limit for pagination.",
     parameters={
        "type": "object",
        "properties": {
            "skip": {
                "type": "integer",
                "description": "Number of users to skip from the beginning (for pagination). Default is 0."
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of users to return. Default is 10."
            }
        },
        # No required fields, defaults will be used
    }
)

# Tool for adding a new user
add_user_func = FunctionDeclaration(
    name="create_user",
    description="Create or add a new user to the system. Requires the user's name and email address.",
    parameters={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "The full name of the user."
            },
            "email": {
                "type": "string",
                "description": "The unique email address of the user."
            }
        },
        "required": ["name", "email"]
    }
)

# Tool for searching users
search_users_func = FunctionDeclaration(
    name="search_users",
    description="Search for users by matching a query string against their name or email (case-insensitive).",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search term to look for in user names or emails."
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of search results to return. Default is 10."
            }
        },
        "required": ["query"]
    }
)


# --- Tool Configuration for Gemini ---
# Encapsulate the FunctionDeclarations within a Tool object
mcp_tool = Tool(
    function_declarations=[
        get_user_by_id_func,
        list_users_func,
        add_user_func,
        search_users_func,
    ]
)
""""
Below is how each tool is mapped for each endpoint (mapping happens when check is called on tool_name)
tool_name == "get_user_by_id" -> Calls GET /users/{user_id} 

tool_name == "list_users" -> Calls GET /users/  

tool_name == "add_user" -> Calls POST /users/ 

tool_name == "search_users" -> Calls GET /users/search/ 
"""

class LLMAgent:
    def __init__(self, model_name="gemini-2.5-pro-exp-03-25"):
        self.model = genai.GenerativeModel(
            model_name=model_name,
            # Pass the tool configuration to the model
            tools=[mcp_tool],
            # Optional: Force function calling if needed, or let the model decide
            # tool_config={'function_calling_config': "AUTO"} #  "ANY" to force a function call
            generation_config=GenerationConfig(temperature=0.25) # LLM needs to do exactly what's its being told to 
        )
        self.chat = self.model.start_chat(enable_automatic_function_calling=False) # handle calls manually
        self.mcp_server_url = MCP_SERVER_URL
        print(f"LLM Agent initialized. Using MCP Server at: {self.mcp_server_url}")
        print(f"Available tools: {[func.name for func in mcp_tool.function_declarations]}")


    def _call_mcp_api(self, tool_name: str, args: dict):
        """Internal method to call the corresponding MCP Server API endpoint."""
        print(f"[Agent] Executing tool: {tool_name} with args: {args}")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        api_result = None
        error_message = None

        try:
            if tool_name == "get_user_by_id":
                # Validate args using Pydantic schema before calling API
                from db.schemas import GetUserByIdToolArgs
                validated_args = GetUserByIdToolArgs(**args)
                user_id = validated_args.user_id
                response = requests.get(f"{self.mcp_server_url}/users/{user_id}", headers=headers)
            elif tool_name == "get_users":
                # Args are optional (skip, limit), pass them as query params
                response = requests.get(f"{self.mcp_server_url}/users/", params=args, headers=headers)
            elif tool_name == "create_user":
                # Validate args using Pydantic schema before calling API
                from db.schemas import AddUserToolArgs
                validated_args = AddUserToolArgs(**args)
                response = requests.post(f"{self.mcp_server_url}/users/", json=validated_args.model_dump(), headers=headers) # Use model_dump() for Pydantic V2
            elif tool_name == "search_users":
                 # Validate args using Pydantic schema before calling API
                from db.schemas import SearchUsersToolArgs
                validated_args = SearchUsersToolArgs(**args)
                # Search args go in query parameters
                response = requests.get(f"{self.mcp_server_url}/users/search/", params=validated_args.model_dump(), headers=headers)
            else:
                error_message = f"Unknown tool: {tool_name}"
                print(f"[Agent] Error: {error_message}")
                return {"error": error_message} # Return error info back to LLM

            # Check response status and parse JSON
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            api_result = response.json()
            print(f"[Agent] Tool '{tool_name}' executed successfully. Result: {api_result}")

        except ValidationError as e:
             error_message = f"Input validation error for tool '{tool_name}': {e}"
             print(f"[Agent] Error: {error_message}")
             api_result = {"error": error_message}
        except requests.exceptions.RequestException as e:
            error_message = f"API call failed for tool '{tool_name}': {e}"
            print(f"[Agent] Error: {error_message}")
            # Try to get error detail from response if available
            try:
                error_detail = e.response.json().get("detail", str(e))
                api_result = {"error": f"API Error: {error_detail}"}
            except:
                 api_result = {"error": error_message} # Fallback error message
        except Exception as e:
            error_message = f"An unexpected error occurred while executing tool '{tool_name}': {e}"
            print(f"[Agent] Error: {error_message}")
            api_result = {"error": error_message}

        # Return the result (or error) in the format expected by Gemini's function response
        return {
            "tool_result": {
                "tool_name": tool_name,
                "result": api_result # This can be the success JSON or the error dict
            }
        }


    def run(self, user_query: str):
        """Sends user query to LLM, handles function calls, returns final response."""
        print(f"\n[User] Query: {user_query}")

        try:
            # Send message to the model
            response = self.chat.send_message(user_query)

            # Check if the model wants to call a function
            if response.candidates[0].content.parts[0].function_call:
                function_call = response.candidates[0].content.parts[0].function_call
                tool_name = function_call.name
                tool_args = {key: value for key, value in function_call.args.items()} # Convert FunctionCall args

                # Call the appropriate MCP API endpoint
                api_response_dict = self._call_mcp_api(tool_name, tool_args)

                

                #function response structure based on docs:
                # It should contain the *result* of the function call directly under 'response' key.
                function_response_part = genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=tool_name,
                        response={"content": json.dumps(api_response_dict['tool_result']['result'])} # Gemini expects the result *content* often as a JSON string
                    )
                )

                print(f"[Agent] Sending function response to LLM: {function_response_part}")

                # Send the function response back to the model
                response = self.chat.send_message(function_response_part)

                # Get the model's final response after processing the function result
                final_response = response.candidates[0].content.parts[0].text
                print(f"[LLM] Final Response: {final_response}")
                return final_response

            else:
                # No function call, just return the text response
                text_response = response.candidates[0].content.parts[0].text
                print(f"[LLM] Direct Response: {text_response}")
                return text_response

        except Exception as e:
            print(f"[Agent] Error during LLM interaction: {e}")
            # Check for specific Gemini errors if needed (e.g., blocked content)
            if hasattr(e, 'response') and e.response.prompt_feedback:
                 print(f"[Agent] Prompt Feedback: {e.response.prompt_feedback}")
            return "Sorry, I encountered an error while processing your request."