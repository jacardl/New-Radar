# -*- coding: utf-8 -*-
"""
Mock hermes_agent module for compatibility.
Provides stub implementations when hermes_agent is not available.
"""
from typing import Any, Dict, List, Optional, Callable
import logging

logger = logging.getLogger(__name__)


class MockAIAgent:
    """Mock AIAgent that provides basic functionality without Hermes."""

    def __init__(
        self,
        name: str,
        role_instruction: str,
        session_id: Optional[str] = None,
        tools: Optional[List[Any]] = None,
        **kwargs
    ):
        self.name = name
        self.role_instruction = role_instruction
        self.session_id = session_id or f"mock_session_{id(self)}"
        self.tools = tools or []
        logger.info(f"MockAIAgent initialized: {name}")

    async def chat(self, message: str, **kwargs) -> Dict[str, Any]:
        """Mock chat that just echoes the message."""
        return {
            "content": f"[Mock] Received: {message}",
            "session_id": self.session_id
        }

    def add_tool(self, tool: Any) -> None:
        """Add a tool to the agent."""
        self.tools.append(tool)


class Tool:
    """Mock Tool base class."""

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        func: Optional[Callable] = None
    ):
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.func = func

    def __call__(self, **kwargs) -> Any:
        if self.func:
            return self.func(**kwargs)
        return {"status": "ok"}


# Alias
AIAgent = MockAIAgent

__all__ = ['AIAgent', 'Tool', 'MockAIAgent']