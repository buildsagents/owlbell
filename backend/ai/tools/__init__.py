"""
Tool Calling module.

Provides tool/function calling support for the LLM engine.
Includes built-in tools for calendar, SMS, call transfer, FAQ lookup, etc.
"""

from backend.ai.tools.registry import (
    Tool,
    ToolCall,
    ToolRegistry,
    ToolResult,
    get_tool_registry,
    close_tool_registry,
)

__all__ = [
    "Tool",
    "ToolCall",
    "ToolRegistry",
    "ToolResult",
    "get_tool_registry",
    "close_tool_registry",
]
