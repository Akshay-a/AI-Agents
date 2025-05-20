"""
Main agent processing logic module that handles conversation flow.
This module integrates with Groq for LLM processing using the Agno framework.
"""

import logging
import typer
from typing import Dict, List, Optional, Any
import os
from agno.agent import Agent
from agno.models.groq import Groq
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.reasoning import ReasoningTools
from agno.memory.v2.db.sqlite import SqliteMemoryDb
from agno.memory.v2.memory import Memory
from rich.pretty import pprint

GROQ_API_KEY=os.getenv("GROQ_API_KEY")

# Set up logger
logger = logging.getLogger(__name__)

class AgnoAgent:
    """
    Agent class that handles the core AI conversation logic using the Agno framework.
    This serves as the central reasoning component for the Voice AI application.
    """
    
    def __init__(self, api_key=None, conversation_id=None):
        """
        Initialize the agent with necessary configuration.
        
        Args:
            api_key (str, optional): API key for the Groq LLM service. Defaults to None.
            conversation_id (str, optional): ID for tracking conversation state. Defaults to None.
        """
        self.api_key = api_key or GROQ_API_KEY
        self.conversation_id = conversation_id
        self.conversation_history = []
        memory_db = SqliteMemoryDb(table_name="memory", db_file="tmp/memory.db")

# No need to set the model, it gets set by the agent to the agent's model
        memory = Memory(db=memory_db)
        print("Akshay's memories:")
        pprint(memory.memories)
        # Initialize the Agno agent with Groq LLM
        self.agent = Agent(
            model=Groq(
                id="meta-llama/llama-4-maverick-17b-128e-instruct",
                api_key=self.api_key
            ),
            description="""You are a helpful voice assistant who is engaging in a conversation with a user.
            Your responses should be:
            1. Conversational and natural - as if speaking, not writing
            2. Concise and to the point - users are speaking with you through voice
            3. Helpful and informative - provide valuable information when requested
            4. Polite and friendly - maintain a positive, supportive tone
            
            Since you are operating in a voice conversation:
            - Keep responses brief (1-3 sentences where possible)
            - Avoid complex formatted output (like code blocks or tables)
            - Be clear about what actions you're taking
            - When you don't know something, clearly say so
            """,
            tools=[
                DuckDuckGoTools(),  # Web search capability
                ReasoningTools(add_instructions=True),  # Enhanced reasoning capability
            ],
            show_tool_calls=False,  # Hide tool calls in the response for cleaner voice output
            markdown=False,  # Avoid markdown for voice responses
            session_id=self.conversation_id,  # Track conversation state
            memory=memory,
            enable_user_memories=True,
        )
        
        logger.info("Agno Agent initialized")

        self.agent.cli_app(markdown=True)
        

if __name__ == "__main__":
    typer.run(AgnoAgent)