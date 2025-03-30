# main.py
from llm_agent import LLMAgent
import sys

def main():
    # Ensure MCP server is running before starting the agent interaction

    
    print("Connecting to LLM and MCP Server...")
    try:
        agent = LLMAgent() # Initializes connection to Gemini and defines tools
    except Exception as e:
        print(f"Failed to initialize LLM Agent: {e}", file=sys.stderr)
        print("ensure the MCP server (mcp_server.py) is running and api keys are correct", file=sys.stderr)
        sys.exit(1)

    print("\nAgent ready. Type 'quit' or 'exit' to stop.")
    print("Examples:")
    print(" - 'Who is user 1?'")
    print(" - 'List the users'")
    print(" - 'Add a user named Test User with email test@example.com'")
    print(" - 'Find users matching 'bob''")
    print("-" * 20)

    while True:
        try:
            user_input = input("You: ")
            if user_input.lower() in ["quit", "exit"]:
                print("LLM Agent shutting down. Goodbye!")
                break

            if not user_input:
                continue

            # Send query to agent and get response
            response = agent.run(user_input)
            print(f"Agent: {response}")

        except KeyboardInterrupt:
            print("\nLLM Agent shutting down. Goodbye!")
            break
        except Exception as e:
            print(f"\nAn unexpected error occurred: {e}")
            # Optionally, re-initialize the agent or just continue
            # break # Uncomment to stop on any error

if __name__ == "__main__":
    main()