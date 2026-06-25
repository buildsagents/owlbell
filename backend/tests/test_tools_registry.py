"""
Tests for Tool Registry.

Covers tool registration, OpenAI schema generation, tool execution,
result formatting, parsing, and built-in tools.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from backend.ai.tools.registry import (
    CalendarTool,
    EndCallTool,
    FAQTool,
    HoursTool,
    MessageTool,
    SMSTool,
    Tool,
    ToolCall,
    ToolParameter,
    ToolRegistry,
    ToolResult,
    TransferTool,
    get_tool_registry,
)


# ---------------------------------------------------------------------------
#  ToolParameter tests
# ---------------------------------------------------------------------------


class TestToolParameter:
    """Tests for ToolParameter dataclass."""

    def test_basic_creation(self) -> None:
        """Test creating a parameter."""
        param = ToolParameter(
            name="date",
            type="string",
            description="The date",
            required=True,
        )
        assert param.name == "date"
        assert param.required

    def test_optional_parameter(self) -> None:
        """Test optional parameter."""
        param = ToolParameter(
            name="reason",
            type="string",
            description="Optional reason",
            required=False,
            default="general",
        )
        assert not param.required
        assert param.default == "general"

    def test_parameter_with_enum(self) -> None:
        """Test parameter with enum values."""
        param = ToolParameter(
            name="urgency",
            type="string",
            description="Urgency level",
            enum=["low", "normal", "high"],
        )
        assert param.enum == ["low", "normal", "high"]


# ---------------------------------------------------------------------------
#  Tool tests
# ---------------------------------------------------------------------------


class TestTool:
    """Tests for Tool dataclass."""

    def test_basic_creation(self) -> None:
        """Test creating a tool."""
        tool = Tool(
            name="test_tool",
            description="A test tool",
        )
        assert tool.name == "test_tool"
        assert tool.category == "general"
        assert not tool.requires_confirmation

    def test_to_openai_schema(self) -> None:
        """Test OpenAI schema conversion."""
        tool = Tool(
            name="check_calendar",
            description="Check availability",
            parameters=[
                ToolParameter(name="date", type="string", description="Date", required=True),
                ToolParameter(name="time", type="string", description="Time", required=False),
            ],
        )
        schema = tool.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "check_calendar"
        assert "parameters" in schema["function"]
        assert "date" in schema["function"]["parameters"]["properties"]
        assert "date" in schema["function"]["parameters"]["required"]
        assert "time" not in schema["function"]["parameters"]["required"]

    def test_to_openai_schema_no_params(self) -> None:
        """Test schema with no parameters."""
        tool = Tool(name="simple", description="Simple tool")
        schema = tool.to_openai_schema()
        assert schema["function"]["parameters"]["properties"] == {}
        assert schema["function"]["parameters"]["required"] == []


# ---------------------------------------------------------------------------
#  ToolResult tests
# ---------------------------------------------------------------------------


class TestToolResult:
    """Tests for ToolResult dataclass."""

    def test_success_result(self) -> None:
        """Test successful result."""
        result = ToolResult(
            tool_name="check_calendar",
            success=True,
            data={"slots": ["10:00", "11:00"]},
        )
        assert result.success
        assert result.data["slots"] == ["10:00", "11:00"]

    def test_error_result(self) -> None:
        """Test error result."""
        result = ToolResult(
            tool_name="test",
            success=False,
            error_message="Something went wrong",
        )
        assert not result.success
        assert "failed" in result.to_llm_text().lower()

    def test_to_llm_text_success(self) -> None:
        """Test formatting success for LLM."""
        result = ToolResult(
            tool_name="test",
            success=True,
            data={"key": "value"},
        )
        text = result.to_llm_text()
        assert "test" in text.lower()
        assert "key" in text

    def test_to_llm_text_empty(self) -> None:
        """Test formatting empty result."""
        result = ToolResult(tool_name="test", success=True)
        text = result.to_llm_text()
        assert "successfully" in text.lower()


# ---------------------------------------------------------------------------
#  ToolRegistry tests
# ---------------------------------------------------------------------------


class TestToolRegistry:
    """Tests for ToolRegistry."""

    @pytest.fixture
    def registry(self) -> ToolRegistry:
        return ToolRegistry(auto_register_builtin=True)

    def test_builtin_tools_registered(self, registry: ToolRegistry) -> None:
        """Test that all built-in tools are registered."""
        tools = registry.list_tools()
        assert "check_calendar" in tools
        assert "book_appointment" in tools
        assert "send_sms" in tools
        assert "transfer_call" in tools
        assert "lookup_faq" in tools
        assert "get_business_hours" in tools
        assert "take_message" in tools
        assert "end_call" in tools
        assert len(tools) == 8

    def test_get_tool(self, registry: ToolRegistry) -> None:
        """Test getting a tool by name."""
        tool = registry.get_tool("check_calendar")
        assert tool is not None
        assert tool.name == "check_calendar"
        assert tool.handler is not None

    def test_get_nonexistent_tool(self, registry: ToolRegistry) -> None:
        """Test getting a tool that doesn't exist."""
        tool = registry.get_tool("nonexistent")
        assert tool is None

    def test_get_tool_descriptions(self, registry: ToolRegistry) -> None:
        """Test getting tool descriptions."""
        descriptions = registry.get_tool_descriptions()
        assert len(descriptions) == 8
        for desc in descriptions:
            assert desc["type"] == "function"
            assert "function" in desc

    def test_register_duplicate(self, registry: ToolRegistry) -> None:
        """Test registering duplicate tool raises error."""
        with pytest.raises(ValueError):
            registry.register(
                Tool(name="check_calendar", description="Duplicate")
            )

    def test_unregister(self, registry: ToolRegistry) -> None:
        """Test unregistering a tool."""
        registry.unregister("end_call")
        assert "end_call" not in registry.list_tools()

    def test_register_custom_tool(self, registry: ToolRegistry) -> None:
        """Test registering a custom tool."""
        custom = Tool(
            name="custom_tool",
            description="A custom tool",
            parameters=[
                ToolParameter(name="input", type="string", description="Input", required=True)
            ],
            category="custom",
        )
        registry.register(custom)
        assert "custom_tool" in registry.list_tools()

    @pytest.mark.asyncio
    async def test_execute_tool(self, registry: ToolRegistry) -> None:
        """Test executing a tool."""
        result = await registry.execute(
            "get_business_hours",
            {"day": "monday"},
        )
        assert isinstance(result, ToolResult)
        assert result.success
        assert "day" in result.data

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self, registry: ToolRegistry) -> None:
        """Test executing unknown tool."""
        result = await registry.execute("nonexistent", {})
        assert not result.success
        assert "not found" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_execute_tool_with_error(self, registry: ToolRegistry) -> None:
        """Test executing tool that raises exception."""
        # Register a tool with a failing handler
        failing_tool = Tool(
            name="failing_tool",
            description="Always fails",
            handler=AsyncMock(side_effect=Exception("Boom")),
        )
        # Use a fresh registry
        fresh_registry = ToolRegistry(auto_register_builtin=False)
        fresh_registry.register(failing_tool)
        result = await fresh_registry.execute("failing_tool", {})
        assert not result.success
        assert "Boom" in result.error_message

    def test_parse_tool_call_xml(self, registry: ToolRegistry) -> None:
        """Test parsing XML-style tool call."""
        parsed = registry.parse_tool_call(
            '<tool_call name="check_calendar">{"date": "2025-01-15"}</tool_call>'
        )
        assert parsed is not None
        assert parsed.tool_name == "check_calendar"
        assert parsed.parameters["date"] == "2025-01-15"

    def test_parse_tool_call_invalid(self, registry: ToolRegistry) -> None:
        """Test parsing invalid tool call."""
        parsed = registry.parse_tool_call("not a valid tool call")
        assert parsed is None

    def test_format_result_for_llm(self, registry: ToolRegistry) -> None:
        """Test formatting result for LLM."""
        result = ToolResult(
            tool_name="test",
            success=True,
            data={"status": "ok"},
        )
        text = registry.format_result_for_llm(result)
        assert "test" in text

    def test_stats(self, registry: ToolRegistry) -> None:
        """Test statistics."""
        stats = registry.get_stats()
        assert stats["registered_tools"] == 8
        assert stats["total_executions"] == 0

    def test_reset_stats(self, registry: ToolRegistry) -> None:
        """Test resetting stats."""
        registry._execution_count = 5
        registry.reset_stats()
        assert registry.get_stats()["total_executions"] == 0

    @pytest.mark.asyncio
    async def test_execution_counts_stats(self, registry: ToolRegistry) -> None:
        """Test execution counts in stats."""
        await registry.execute("get_business_hours", {"day": "today"})
        stats = registry.get_stats()
        assert stats["total_executions"] == 1
        assert stats["successful"] == 1


# ---------------------------------------------------------------------------
#  Built-in tool tests
# ---------------------------------------------------------------------------


class TestCalendarTool:
    """Tests for calendar tools."""

    @pytest.mark.asyncio
    async def test_check_calendar(self) -> None:
        """Test calendar check."""
        result = await CalendarTool.check_calendar(date="2025-01-15")
        assert result["date"] == "2025-01-15"
        assert "available_slots" in result
        assert isinstance(result["available_slots"], list)

    @pytest.mark.asyncio
    async def test_check_calendar_no_date(self) -> None:
        """Test calendar check without date."""
        result = await CalendarTool.check_calendar()
        assert "date" in result
        assert "available_slots" in result

    @pytest.mark.asyncio
    async def test_book_appointment(self) -> None:
        """Test booking appointment."""
        result = await CalendarTool.book_appointment(
            date="2025-01-15",
            time="10:00",
            name="John",
            phone="555-1234",
        )
        assert result["success"]
        assert "appointment_id" in result
        assert result["name"] == "John"

    @pytest.mark.asyncio
    async def test_book_appointment_no_date(self) -> None:
        """Test booking without date fails."""
        result = await CalendarTool.book_appointment()
        assert not result["success"]


class TestSMSTool:
    """Tests for SMS tool."""

    @pytest.mark.asyncio
    async def test_send_sms(self) -> None:
        """Test sending SMS."""
        result = await SMSTool.send_sms(
            phone_number="555-1234",
            message="Your appointment is confirmed",
        )
        assert result["success"]
        assert "message_id" in result

    @pytest.mark.asyncio
    async def test_send_sms_missing_fields(self) -> None:
        """Test SMS without required fields."""
        result = await SMSTool.send_sms()
        assert not result["success"]


class TestTransferTool:
    """Tests for transfer tool."""

    @pytest.mark.asyncio
    async def test_transfer_to_department(self) -> None:
        """Test transfer to a department."""
        result = await TransferTool.transfer_call(destination="billing")
        assert result["success"]
        assert "extension" in result

    @pytest.mark.asyncio
    async def test_transfer_message(self) -> None:
        """Test transfer result has message."""
        result = await TransferTool.transfer_call(
            destination="human", reason="Customer request"
        )
        assert "message" in result


class TestFAQTool:
    """Tests for FAQ tool."""

    @pytest.mark.asyncio
    async def test_lookup_hours(self) -> None:
        """Test hours FAQ lookup."""
        result = await FAQTool.lookup_faq(topic="hours")
        assert result["found"]
        assert "answer" in result

    @pytest.mark.asyncio
    async def test_lookup_unknown(self) -> None:
        """Test unknown FAQ."""
        result = await FAQTool.lookup_faq(question="xyz unknown topic")
        assert not result["found"]
        assert "answer" in result  # Fallback answer

    @pytest.mark.asyncio
    async def test_lookup_by_question(self) -> None:
        """Test FAQ by question text."""
        result = await FAQTool.lookup_faq(question="Where are you located?")
        assert result["found"]


class TestHoursTool:
    """Tests for hours tool."""

    @pytest.mark.asyncio
    async def test_get_hours_today(self) -> None:
        """Test getting hours for today."""
        result = await HoursTool.get_business_hours(day="today")
        assert "is_open" in result
        assert "day" in result

    @pytest.mark.asyncio
    async def test_get_hours_specific_day(self) -> None:
        """Test getting hours for a specific day."""
        result = await HoursTool.get_business_hours(day="Monday")
        assert result["day"] == "Monday"
        assert result["is_open"]  # Monday is typically open

    @pytest.mark.asyncio
    async def test_get_hours_weekend(self) -> None:
        """Test getting hours for weekend."""
        result = await HoursTool.get_business_hours(day="Saturday")
        assert not result["is_open"]  # Saturday typically closed


class TestMessageTool:
    """Tests for message tool."""

    @pytest.mark.asyncio
    async def test_take_message(self) -> None:
        """Test taking a message."""
        result = await MessageTool.take_message(
            caller_name="Jane",
            caller_phone="555-5678",
            message="Call me back please",
        )
        assert result["success"]
        assert "message_id" in result
        assert result["caller_name"] == "Jane"

    @pytest.mark.asyncio
    async def test_take_message_with_urgency(self) -> None:
        """Test message with urgency."""
        result = await MessageTool.take_message(
            caller_name="Bob",
            caller_phone="555-9999",
            message="Urgent matter",
            urgency="high",
        )
        assert result["urgency"] == "high"


class TestEndCallTool:
    """Tests for end call tool."""

    @pytest.mark.asyncio
    async def test_end_call(self) -> None:
        """Test ending call."""
        result = await EndCallTool.end_call()
        assert result["success"]
        assert result["action"] == "end_call"
        assert "Goodbye" in result["message"]


# ---------------------------------------------------------------------------
#  ToolCall dataclass tests
# ---------------------------------------------------------------------------


class TestToolCall:
    """Tests for ToolCall dataclass."""

    def test_basic_creation(self) -> None:
        """Test creating a tool call."""
        call = ToolCall(tool_name="check_calendar", parameters={"date": "2025-01-15"})
        assert call.tool_name == "check_calendar"
        assert call.parameters["date"] == "2025-01-15"

    def test_defaults(self) -> None:
        """Test default values."""
        call = ToolCall(tool_name="test")
        assert call.parameters == {}
        assert call.call_id is None


# ---------------------------------------------------------------------------
#  Factory tests
# ---------------------------------------------------------------------------


class TestFactory:
    """Tests for factory function."""

    @pytest.mark.asyncio
    async def test_get_tool_registry(self) -> None:
        """Test getting registry instance."""
        registry = await get_tool_registry()
        assert isinstance(registry, ToolRegistry)
        assert len(registry.list_tools()) == 8

    @pytest.mark.asyncio
    async def test_singleton(self) -> None:
        """Test singleton behavior."""
        r1 = await get_tool_registry()
        r2 = await get_tool_registry()
        assert r1 is r2
