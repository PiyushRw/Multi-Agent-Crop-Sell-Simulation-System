"""
Base Agent class and communication framework.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import uuid
import logging

from .models import AgentMessage, CropType, Country, MarketRegion

logger = logging.getLogger(__name__)


@dataclass
class AgentState:
    """Internal state of an agent."""
    agent_id: str
    agent_type: str
    context: Dict[str, Any] = field(default_factory=dict)
    message_history: List[AgentMessage] = field(default_factory=list)
    last_active: datetime = field(default_factory=datetime.now)


class BaseAgent(ABC):
    """Base class for all agents in the simulation."""

    def __init__(self, agent_id: str, agent_type: str, config: Optional[Dict[str, Any]] = None):
        self.state = AgentState(agent_id=agent_id, agent_type=agent_type)
        self.config = config or {}
        self.peers: Dict[str, 'BaseAgent'] = {}

    def register_peer(self, agent: 'BaseAgent'):
        """Register another agent as a communication peer."""
        self.peers[agent.state.agent_id] = agent
        logger.debug(f"{self.state.agent_id} registered peer {agent.state.agent_id}")

    def send_message(self, recipient_id: str, message_type: str, payload: Dict[str, Any]) -> Optional[AgentMessage]:
        """Send a message to another agent and get response."""
        if recipient_id not in self.peers:
            logger.warning(f"{self.state.agent_id}: Peer {recipient_id} not found")
            return None

        message = AgentMessage(
            sender=self.state.agent_id,
            recipient=recipient_id,
            message_type=message_type,
            payload=payload
        )
        self.state.message_history.append(message)
        
        recipient = self.peers[recipient_id]
        response = recipient.receive_message(message)
        
        if response:
            self.state.message_history.append(response)
        
        return response

    def receive_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Receive and process a message from another agent."""
        self.state.message_history.append(message)
        self.state.last_active = datetime.now()
        return self.process_message(message)

    @abstractmethod
    def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Process an incoming message and return a response."""
        pass

    @abstractmethod
    def act(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Perform the agent's primary action given a context."""
        pass

    def get_context(self) -> Dict[str, Any]:
        """Get the agent's current context."""
        return self.state.context.copy()

    def update_context(self, key: str, value: Any):
        """Update the agent's context."""
        self.state.context[key] = value
        self.state.last_active = datetime.now()


class AgentCoordinator:
    """Coordinates communication between multiple agents."""

    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.message_log: List[AgentMessage] = []

    def register(self, agent: BaseAgent):
        """Register an agent with the coordinator."""
        self.agents[agent.state.agent_id] = agent
        # Register all agents as peers of each other
        for other_agent in self.agents.values():
            if other_agent != agent:
                agent.register_peer(other_agent)
                other_agent.register_peer(agent)

    def broadcast(self, sender_id: str, message_type: str, payload: Dict[str, Any]) -> Dict[str, AgentMessage]:
        """Broadcast a message from sender to all other agents."""
        responses = {}
        sender = self.agents.get(sender_id)
        if not sender:
            return responses
        
        for agent_id, agent in self.agents.items():
            if agent_id != sender_id:
                response = sender.send_message(agent_id, message_type, payload)
                if response:
                    responses[agent_id] = response
                    self.message_log.append(response)
        
        return responses

    def run_negotiation(self, 
                        initiator_id: str, 
                        topic: str, 
                        initial_proposal: Dict[str, Any],
                        max_rounds: int = 5) -> Dict[str, Any]:
        """Run a multi-round negotiation between agents."""
        # This is a simplified negotiation - in practice would be more sophisticated
        context = {"topic": topic, "proposal": initial_proposal, "round": 0}
        
        # Broadcast initial proposal
        responses = self.broadcast(initiator_id, "proposal", context)
        
        # Simple consensus building
        for round_num in range(1, max_rounds + 1):
            context["round"] = round_num
            context["responses"] = {k: v.payload for k, v in responses.items()}
            
            # Check for consensus
            if self._check_consensus(responses):
                context["consensus"] = True
                break
                
            # Request revised proposals
            responses = self.broadcast(initiator_id, "counter_proposal", context)
        
        context["consensus"] = self._check_consensus(responses)
        return context

    def _check_consensus(self, responses: Dict[str, AgentMessage]) -> bool:
        """Check if all agents agree (simplified)."""
        if not responses:
            return False
        # In a real implementation, this would compare specific fields
        return True

    def get_message_log(self) -> List[AgentMessage]:
        """Get the full message log."""
        return self.message_log.copy()