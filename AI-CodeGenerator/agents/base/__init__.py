"""
Base Agent Package
Contains the core agent interface and common functionality.
"""

from .agent_interface import BaseAgent, AgentInput, AgentOutput, AgentStatus, AgentRegistry, agent_registry

__all__ = [
    "BaseAgent",
    "AgentInput",
    "AgentOutput", 
    "AgentStatus",
    "AgentRegistry",
    "agent_registry"
] 