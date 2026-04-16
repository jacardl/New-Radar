"""
ForumEngine - Multi-Agent Collaboration Scheduler and Discussion Forum.

This engine acts as a "forum moderator" that:
1. Decomposes complex analysis requests
2. Orchestrates Query/Insight/Media agents for collaborative discussion
3. Synthesizes debate results into final analysis

Supports both blocking (orchestrate) and streaming (stream_orchestrate) modes.
"""

from .agent import ForumAgent, create_forum_agent
from .monitor import LogMonitor
from .llm_host import ForumHost, get_forum_host, generate_host_speech

__all__ = [
    'ForumAgent',
    'create_forum_agent',
    'LogMonitor',
    'ForumHost',
    'get_forum_host',
    'generate_host_speech',
]
