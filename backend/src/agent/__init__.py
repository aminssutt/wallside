"""Tool-calling agent for the Wallside vehicle assistant.

The public surface is deliberately small: external code (``guide_chatbot``
and the Flask API) should only call ``run_agent`` (sync) or ``stream_agent``
(SSE generator). Internals — planner, tools, responder — stay private to
this package.
"""
from .bridge import stream_agent_legacy_events
from .orchestrator import AgentAnswer, run_agent, stream_agent
from .safety import SafetyVerdict, assess_input_safety
from .tools import Citation, ToolCall, ToolResult

__all__ = [
    "AgentAnswer",
    "Citation",
    "SafetyVerdict",
    "ToolCall",
    "ToolResult",
    "assess_input_safety",
    "run_agent",
    "stream_agent",
    "stream_agent_legacy_events",
]
