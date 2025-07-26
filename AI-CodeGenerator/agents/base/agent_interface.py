"""
Base Agent Interface
Provides common structure and functionality for all agents in the multi-agent system.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
import json
import logging
import uuid
from enum import Enum


class AgentStatus(Enum):
    """Agent execution status"""
    IDLE = "idle"
    PROCESSING = "processing"
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class AgentInput:
    """Base input structure for all agents"""
    session_id: str
    agent_id: str
    timestamp: datetime
    data: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None

    def validate(self) -> bool:
        """Validate input data structure"""
        required_fields = ['session_id', 'agent_id', 'data']
        return all(hasattr(self, field) and getattr(self, field) is not None for field in required_fields)


@dataclass
class AgentOutput:
    """Base output structure for all agents"""
    session_id: str
    agent_id: str
    status: AgentStatus
    data: Dict[str, Any]
    execution_time_ms: int
    timestamp: datetime
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert output to dictionary for JSON serialization"""
        return {
            'session_id': self.session_id,
            'agent_id': self.agent_id,
            'status': self.status.value,
            'data': self.data,
            'execution_time_ms': self.execution_time_ms,
            'timestamp': self.timestamp.isoformat(),
            'error_message': self.error_message,
            'metadata': self.metadata or {}
        }


class BaseAgent(ABC):
    """
    Base class for all agents in the multi-agent system.
    Provides common functionality and enforces consistent interface.
    """

    def __init__(self, agent_id: str, config: Optional[Dict[str, Any]] = None):
        self.agent_id = agent_id
        self.config = config or {}
        self.status = AgentStatus.IDLE
        self.logger = self._setup_logger()
        
    def _setup_logger(self) -> logging.Logger:
        """Setup agent-specific logger"""
        logger = logging.getLogger(f"agent.{self.agent_id}")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                f'%(asctime)s - {self.agent_id} - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    @abstractmethod
    def process(self, agent_input: AgentInput) -> AgentOutput:
        """
        Main processing method that each agent must implement.
        Should contain the core business logic of the agent.
        """
        pass

    @abstractmethod
    def validate_input(self, agent_input: AgentInput) -> bool:
        """
        Validate agent-specific input requirements.
        Should check for required fields and data types.
        """
        pass

    def execute(self, input_data: Dict[str, Any], session_id: Optional[str] = None) -> AgentOutput:
        """
        Execute the agent with proper error handling and timing.
        This is the main entry point for external calls.
        """
        start_time = datetime.now()
        session_id = session_id or str(uuid.uuid4())
        
        try:
            # Create agent input
            agent_input = AgentInput(
                session_id=session_id,
                agent_id=self.agent_id,
                timestamp=start_time,
                data=input_data
            )

            # Validate input
            if not agent_input.validate() or not self.validate_input(agent_input):
                return self._create_error_output(
                    session_id, start_time, "Invalid input data"
                )

            self.status = AgentStatus.PROCESSING
            self.logger.info(f"Starting processing for session {session_id}")

            # Process the request
            result = self.process(agent_input)
            
            self.status = AgentStatus.SUCCESS
            self.logger.info(f"Successfully completed processing for session {session_id}")
            
            return result

        except Exception as e:
            self.status = AgentStatus.ERROR
            error_msg = f"Agent execution failed: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            
            return self._create_error_output(session_id, start_time, error_msg)

    def _create_error_output(self, session_id: str, start_time: datetime, error_message: str) -> AgentOutput:
        """Create standardized error output"""
        execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        return AgentOutput(
            session_id=session_id,
            agent_id=self.agent_id,
            status=AgentStatus.ERROR,
            data={},
            execution_time_ms=execution_time,
            timestamp=datetime.now(),
            error_message=error_message
        )

    def _create_success_output(self, session_id: str, start_time: datetime, data: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> AgentOutput:
        """Create standardized success output"""
        execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        return AgentOutput(
            session_id=session_id,
            agent_id=self.agent_id,
            status=AgentStatus.SUCCESS,
            data=data,
            execution_time_ms=execution_time,
            timestamp=datetime.now(),
            metadata=metadata
        )

    def get_status(self) -> AgentStatus:
        """Get current agent status"""
        return self.status

    def get_config(self) -> Dict[str, Any]:
        """Get agent configuration"""
        return self.config.copy()

    def update_config(self, new_config: Dict[str, Any]) -> None:
        """Update agent configuration"""
        self.config.update(new_config)
        self.logger.info("Agent configuration updated")


class AgentRegistry:
    """
    Registry to manage and coordinate multiple agents.
    Provides agent discovery and lifecycle management.
    """
    
    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}
        self.logger = logging.getLogger("agent.registry")

    def register_agent(self, agent: BaseAgent) -> None:
        """Register a new agent"""
        self._agents[agent.agent_id] = agent
        self.logger.info(f"Registered agent: {agent.agent_id}")

    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """Get agent by ID"""
        return self._agents.get(agent_id)

    def list_agents(self) -> List[str]:
        """List all registered agent IDs"""
        return list(self._agents.keys())

    def execute_agent(self, agent_id: str, input_data: Dict[str, Any], session_id: Optional[str] = None) -> AgentOutput:
        """Execute specific agent by ID"""
        agent = self.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent not found: {agent_id}")
        
        return agent.execute(input_data, session_id)

    def get_agent_status(self, agent_id: str) -> Optional[AgentStatus]:
        """Get status of specific agent"""
        agent = self.get_agent(agent_id)
        return agent.get_status() if agent else None


# Global agent registry instance
agent_registry = AgentRegistry() 