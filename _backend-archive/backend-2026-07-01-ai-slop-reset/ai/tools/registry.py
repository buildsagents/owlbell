"""
Tool calling registry for the LLM engine.

Provides a registry of callable tools that the LLM can invoke.
Includes built-in tools for calendar, SMS, call transfer, FAQ lookup,
business hours, message taking, and call ending.

Usage:
    registry = ToolRegistry()
    registry.register(my_tool)
    descriptions = registry.get_tool_descriptions()
    result = await registry.execute("check_calendar", {"date": "2025-01-15"})
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    List,
    Optional,
    Protocol,
    TypeVar,
    runtime_checkable,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Data models
# ---------------------------------------------------------------------------


@dataclass
class ToolParameter:
    """Parameter definition for a tool.

    Attributes:
        name: Parameter name.
        type: JSON schema type.
        description: Human-readable description.
        required: Whether parameter is required.
        enum: Optional list of allowed values.
        default: Default value if optional.
    """

    name: str
    type: str
    description: str
    required: bool = True
    enum: Optional[List[str]] = None
    default: Any = None


@dataclass
class Tool:
    """Tool definition for LLM function calling.

    Attributes:
        name: Tool identifier (used in LLM calls).
        description: Human-readable description for LLM.
        parameters: Parameter definitions.
        handler: Async function that executes the tool.
        requires_confirmation: Whether tool needs user confirmation.
        category: Tool category for organization.
    """

    name: str
    description: str
    parameters: List[ToolParameter] = field(default_factory=list)
    handler: Optional[Callable[..., Coroutine[Any, Any, Any]]] = None
    requires_confirmation: bool = False
    category: str = "general"

    def to_openai_schema(self) -> Dict[str, Any]:
        """Convert to OpenAI function schema format.

        Returns:
            Dict in OpenAI function calling format.
        """
        properties: Dict[str, Any] = {}
        required: List[str] = []

        for param in self.parameters:
            prop: Dict[str, Any] = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum
            if param.default is not None:
                prop["default"] = param.default

            properties[param.name] = prop
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


@dataclass
class ToolCall:
    """Parsed tool call from LLM response.

    Attributes:
        tool_name: Name of tool to call.
        parameters: Tool arguments.
        call_id: Optional unique call identifier.
    """

    tool_name: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    call_id: Optional[str] = None


@dataclass
class ToolResult:
    """Result of tool execution.

    Attributes:
        tool_name: Name of tool that was called.
        success: Whether execution succeeded.
        data: Result data.
        error_message: Error description if failed.
        latency_ms: Execution time in milliseconds.
    """

    tool_name: str
    success: bool = True
    data: Dict[str, Any] = field(default_factory=dict)
    error_message: str = ""
    latency_ms: int = 0

    def to_llm_text(self) -> str:
        """Format result for LLM consumption.

        Returns:
            Human-readable result string.
        """
        if not self.success:
            return (
                f"Tool '{self.tool_name}' failed: {self.error_message}"
            )
        if not self.data:
            return f"Tool '{self.tool_name}' executed successfully."

        parts = [f"Tool '{self.tool_name}' result:"]
        for key, value in self.data.items():
            parts.append(f"  {key}: {value}")
        return "\n".join(parts)


# ---------------------------------------------------------------------------
#  Built-in tool implementations
# ---------------------------------------------------------------------------


class CalendarTool:
    """Calendar tool for checking availability and booking appointments."""

    @staticmethod
    async def check_calendar(
        date: str = "",
        time: str = "",
        duration_minutes: int = 30,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Check calendar availability.

        Args:
            date: Date to check (YYYY-MM-DD).
            time: Preferred time (HH:MM).
            duration_minutes: Appointment duration.

        Returns:
            Availability info dict.
        """
        logger.info(f"Checking calendar for {date} at {time}")

        # Simulated calendar check - replace with real calendar integration
        now = datetime.now()
        if not date:
            date = now.strftime("%Y-%m-%d")

        # Generate mock availability
        available_slots = []
        for hour in range(9, 17):
            for minute in (0, 30):
                slot_time = f"{hour:02d}:{minute:02d}"
                # Randomly mark some slots as available
                if hash(f"{date}:{slot_time}") % 3 != 0:
                    available_slots.append(slot_time)

        return {
            "date": date,
            "requested_time": time,
            "available_slots": available_slots[:6],
            "is_available": time in available_slots if time else True,
            "next_available": available_slots[0] if available_slots else None,
        }

    @staticmethod
    async def book_appointment(
        date: str = "",
        time: str = "",
        name: str = "",
        phone: str = "",
        reason: str = "",
        duration_minutes: int = 30,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Book an appointment.

        Args:
            date: Appointment date (YYYY-MM-DD).
            time: Appointment time (HH:MM).
            name: Caller name.
            phone: Caller phone number.
            reason: Reason for appointment.
            duration_minutes: Appointment duration.

        Returns:
            Booking confirmation dict.
        """
        logger.info(f"Booking appointment for {name} on {date} at {time}")

        if not date or not time:
            return {
                "success": False,
                "error": "Date and time are required to book an appointment.",
                "appointment_id": None,
            }

        # Simulated booking - replace with real calendar integration
        appointment_id = f"appt_{abs(hash(f'{date}:{time}:{phone}')) % 100000:05d}"

        return {
            "success": True,
            "appointment_id": appointment_id,
            "date": date,
            "time": time,
            "duration_minutes": duration_minutes,
            "name": name,
            "phone": phone,
            "reason": reason,
            "status": "confirmed",
            "message": (
                f"Appointment confirmed for {name} on {date} at {time}. "
                f"Your appointment ID is {appointment_id}."
            ),
        }


class SMSTool:
    """SMS notification tool."""

    @staticmethod
    async def send_sms(
        phone_number: str = "",
        message: str = "",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Send an SMS notification via Twilio (config-guarded).

        Args:
            phone_number: Destination phone number.
            message: SMS message body.

        kwargs may carry call context (``tenant_id``, ``call_id``) injected by
        the orchestrator; when present, the send is logged to
        ``notification_logs``.

        Returns:
            Send result dict.
        """
        logger.info(f"Sending SMS to {phone_number}")

        if not phone_number or not message:
            return {
                "success": False,
                "error": "Phone number and message are required.",
                "message_id": None,
            }

        from backend.integrations.twilio import send_sms as twilio_send_sms

        tenant_id, call_id, session_maker = _call_context(kwargs)
        result = await twilio_send_sms(
            phone_number,
            message,
            tenant_id=tenant_id,
            session_maker=session_maker,
            event_type="sms.tool",
            entity_id=call_id,
        )

        return {
            "success": result.get("success", False),
            "message_id": result.get("provider_message_id"),
            "phone_number": phone_number,
            "message_preview": message[:50] + "..." if len(message) > 50 else message,
            "status": result.get("status", "failed"),
            "error": result.get("error"),
        }


def _call_context(kwargs: Dict[str, Any]) -> tuple[Any, Any, Any]:
    """Extract (tenant_id, call_id, session_maker) from tool kwargs.

    The orchestrator may inject ``tenant_id`` / ``call_id`` (as UUIDs or
    strings) into tool calls. Returns ``(None, None, None)`` gracefully when
    context or the DB is unavailable (e.g. unit tests).
    """
    import uuid as _uuid

    def _as_uuid(val: Any) -> Any:
        if val is None:
            return None
        if isinstance(val, _uuid.UUID):
            return val
        try:
            return _uuid.UUID(str(val))
        except (ValueError, TypeError):
            return None

    tenant_id = _as_uuid(kwargs.get("tenant_id"))
    call_id = _as_uuid(kwargs.get("call_id"))
    session_maker = None
    if tenant_id is not None:
        from backend.db.session import require_session_maker

        session_maker = require_session_maker()
    return tenant_id, call_id, session_maker


class TransferTool:
    """Call transfer tool."""

    @staticmethod
    async def transfer_call(
        destination: str = "",
        reason: str = "",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Transfer a call to a human agent or extension.

        Args:
            destination: Extension or department to transfer to.
            reason: Reason for transfer.

        On an ``emergency`` transfer, also fires a config-guarded emergency
        SMS alert to the tenant's emergency contact (no-op without Twilio
        credentials or tenant context).

        Returns:
            Transfer result dict.
        """
        logger.info(f"Transferring call to {destination}: {reason}")

        # Valid destinations
        destinations = {
            "reception": "100",
            "support": "200",
            "sales": "300",
            "billing": "400",
            "emergency": "911",
            "human": "100",
            "operator": "0",
        }

        extension = destinations.get(destination.lower(), destination)

        alert: Optional[Dict[str, Any]] = None
        if destination.lower() == "emergency":
            tenant_id, call_id, session_maker = _call_context(kwargs)
            if tenant_id is not None:
                try:
                    from backend.integrations.twilio import send_emergency_alert

                    alert = await send_emergency_alert(
                        tenant_id,
                        session_maker=session_maker,
                        to_number=kwargs.get("emergency_number"),
                        caller_number=kwargs.get("caller_number", ""),
                        reason=reason,
                        business_name=kwargs.get("business_name", ""),
                        call_id=call_id,
                    )
                except Exception as exc:
                    logger.error("transfer.emergency_alert_failed", error=str(exc))

        result = {
            "success": True,
            "destination": destination,
            "extension": extension,
            "reason": reason,
            "transfer_id": f"xfer_{abs(hash(destination)) % 10000:04d}",
            "message": f"Transferring you to {destination}. Please hold.",
        }
        if alert is not None:
            result["emergency_alert"] = alert
        return result


class FAQTool:
    """FAQ lookup tool."""

    # Built-in FAQ knowledge base
    FAQ_DATABASE: Dict[str, str] = {
        "hours": "Our business hours are Monday through Friday, 9 AM to 5 PM. "
        "We're closed on weekends and major holidays.",
        "location": "We're located at the main business district. "
        "Please check our website for the exact address and directions.",
        "services": "We offer a variety of professional services. "
        "Please let us know what you need help with so we can assist you better.",
        "insurance": "We accept most major insurance providers. "
        "Please call our billing department for specific questions about your coverage.",
        "payment": "We accept cash, credit cards, and most insurance plans. "
        "Payment is due at the time of service unless other arrangements have been made.",
        "cancellation": "We require at least 24 hours notice for appointment cancellations. "
        "Late cancellations may be subject to a fee.",
        "parking": "Free parking is available in the lot behind our building.",
        "wifi": "Yes, complimentary WiFi is available in our waiting area.",
        "appointment": "You can schedule an appointment by phone or through our website. "
        "Same-day appointments may be available depending on our schedule.",
        "new patient": "Welcome! New patients should arrive 15 minutes early to complete "
        "paperwork. Please bring your ID, insurance card, and a list of any current medications.",
    }

    @classmethod
    async def lookup_faq(
        cls,
        question: str = "",
        topic: str = "",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Look up an answer in the FAQ database.

        Args:
            question: User's question.
            topic: Specific topic to look up.

        Returns:
            FAQ result dict.
        """
        query = (topic or question).lower()

        # Try keyword matching
        for keyword, answer in cls.FAQ_DATABASE.items():
            if keyword in query:
                return {
                    "found": True,
                    "topic": keyword,
                    "question": question,
                    "answer": answer,
                    "confidence": "high",
                }

        # Partial keyword matching
        for keyword, answer in cls.FAQ_DATABASE.items():
            words = keyword.split()
            if any(word in query for word in words if len(word) > 3):
                return {
                    "found": True,
                    "topic": keyword,
                    "question": question,
                    "answer": answer,
                    "confidence": "medium",
                }

        return {
            "found": False,
            "topic": topic or question,
            "question": question,
            "answer": (
                "I'm sorry, I don't have a specific answer for that question. "
                "I'd be happy to take a message and have someone get back to you."
            ),
            "confidence": "none",
        }


class HoursTool:
    """Business hours tool."""

    @staticmethod
    async def get_business_hours(
        day: str = "",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Get business hours for a specific day.

        Args:
            day: Day of week (or 'today', 'tomorrow').

        Returns:
            Hours info dict.
        """
        now = datetime.now()

        if day.lower() == "today":
            day = now.strftime("%A")
        elif day.lower() == "tomorrow":
            day = (now + timedelta(days=1)).strftime("%A")

        day_name = day.capitalize() if day else now.strftime("%A")

        # Standard business hours
        hours_map = {
            "Monday": {"open": "9:00 AM", "close": "5:00 PM", "is_open": True},
            "Tuesday": {"open": "9:00 AM", "close": "5:00 PM", "is_open": True},
            "Wednesday": {"open": "9:00 AM", "close": "5:00 PM", "is_open": True},
            "Thursday": {"open": "9:00 AM", "close": "5:00 PM", "is_open": True},
            "Friday": {"open": "9:00 AM", "close": "5:00 PM", "is_open": True},
            "Saturday": {"open": None, "close": None, "is_open": False},
            "Sunday": {"open": None, "close": None, "is_open": False},
        }

        today_hours = hours_map.get(day_name, hours_map["Monday"])

        return {
            "day": day_name,
            "is_open": today_hours["is_open"],
            "open_time": today_hours["open"],
            "close_time": today_hours["close"],
            "regular_hours": "Monday through Friday, 9 AM to 5 PM",
        }


class MessageTool:
    """Message taking tool."""

    @staticmethod
    async def take_message(
        caller_name: str = "",
        caller_phone: str = "",
        message: str = "",
        urgency: str = "normal",
        callback_number: str = "",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Take a message from the caller.

        Args:
            caller_name: Name of caller.
            caller_phone: Caller's phone number.
            message: Message content.
            urgency: Message urgency (low/normal/high/urgent).
            callback_number: Number to call back.

        Returns:
            Message receipt dict.
        """
        message_id = f"msg_{abs(hash(caller_phone + message)) % 100000:05d}"

        return {
            "success": True,
            "message_id": message_id,
            "caller_name": caller_name,
            "caller_phone": caller_phone,
            "message": message,
            "urgency": urgency,
            "callback_number": callback_number or caller_phone,
            "timestamp": datetime.now().isoformat(),
            "status": "recorded",
            "confirmation": (
                f"Thank you, {caller_name}. I've recorded your message "
                f"and will make sure it gets to the right person."
            ),
        }


class EndCallTool:
    """End call tool."""

    @staticmethod
    async def end_call(
        reason: str = "goodbye",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """End the current call.

        Args:
            reason: Reason for ending the call.

        Returns:
            End call result dict.
        """
        return {
            "success": True,
            "reason": reason,
            "message": "Goodbye! Have a wonderful day.",
            "action": "end_call",
        }


# ---------------------------------------------------------------------------
#  Tool registry
# ---------------------------------------------------------------------------


class ToolRegistry:
    """Registry of callable tools for the LLM engine.

    Manages tool registration, description generation, execution,
and result formatting.

    Args:
        auto_register_builtin: Whether to register built-in tools on init.
    """

    def __init__(self, auto_register_builtin: bool = True) -> None:
        self._tools: Dict[str, Tool] = {}
        self._execution_count: int = 0
        self._success_count: int = 0
        self._error_count: int = 0

        if auto_register_builtin:
            self._register_builtin_tools()

    def _register_builtin_tools(self) -> None:
        """Register all built-in tools."""
        # Calendar tools
        self.register(
            Tool(
                name="check_calendar",
                description=(
                    "Check calendar availability for a specific date and time. "
                    "Returns available time slots for booking appointments."
                ),
                parameters=[
                    ToolParameter(
                        name="date",
                        type="string",
                        description="Date to check in YYYY-MM-DD format",
                        required=False,
                    ),
                    ToolParameter(
                        name="time",
                        type="string",
                        description="Preferred time in HH:MM format",
                        required=False,
                    ),
                    ToolParameter(
                        name="duration_minutes",
                        type="integer",
                        description="Appointment duration in minutes",
                        required=False,
                        default=30,
                    ),
                ],
                handler=CalendarTool.check_calendar,
                category="calendar",
            )
        )

        self.register(
            Tool(
                name="book_appointment",
                description=(
                    "Book an appointment for the caller. Requires date, time, "
                    "and caller information. Always confirm details before booking."
                ),
                parameters=[
                    ToolParameter(
                        name="date",
                        type="string",
                        description="Appointment date in YYYY-MM-DD format",
                        required=True,
                    ),
                    ToolParameter(
                        name="time",
                        type="string",
                        description="Appointment time in HH:MM format",
                        required=True,
                    ),
                    ToolParameter(
                        name="name",
                        type="string",
                        description="Caller's full name",
                        required=True,
                    ),
                    ToolParameter(
                        name="phone",
                        type="string",
                        description="Caller's phone number",
                        required=True,
                    ),
                    ToolParameter(
                        name="reason",
                        type="string",
                        description="Reason for appointment",
                        required=False,
                    ),
                    ToolParameter(
                        name="duration_minutes",
                        type="integer",
                        description="Appointment duration",
                        required=False,
                        default=30,
                    ),
                ],
                handler=CalendarTool.book_appointment,
                requires_confirmation=True,
                category="calendar",
            )
        )

        # SMS tool
        self.register(
            Tool(
                name="send_sms",
                description=(
                    "Send an SMS notification to a phone number. "
                    "Useful for sending confirmations, reminders, or updates."
                ),
                parameters=[
                    ToolParameter(
                        name="phone_number",
                        type="string",
                        description="Destination phone number",
                        required=True,
                    ),
                    ToolParameter(
                        name="message",
                        type="string",
                        description="SMS message content (max 160 chars)",
                        required=True,
                    ),
                ],
                handler=SMSTool.send_sms,
                category="communication",
            )
        )

        # Transfer tool
        self.register(
            Tool(
                name="transfer_call",
                description=(
                    "Transfer the current call to a human agent or department. "
                    "Use when the caller explicitly asks for a human, or when "
                    "the request requires human assistance."
                ),
                parameters=[
                    ToolParameter(
                        name="destination",
                        type="string",
                        description="Department or extension to transfer to",
                        required=False,
                        enum=[
                            "reception",
                            "support",
                            "sales",
                            "billing",
                            "human",
                            "operator",
                        ],
                    ),
                    ToolParameter(
                        name="reason",
                        type="string",
                        description="Reason for transfer",
                        required=False,
                    ),
                ],
                handler=TransferTool.transfer_call,
                requires_confirmation=False,
                category="call",
            )
        )

        # FAQ tool
        self.register(
            Tool(
                name="lookup_faq",
                description=(
                    "Look up answers to frequently asked questions. "
                    "Use for general questions about the business."
                ),
                parameters=[
                    ToolParameter(
                        name="question",
                        type="string",
                        description="The caller's question",
                        required=False,
                    ),
                    ToolParameter(
                        name="topic",
                        type="string",
                        description="Specific topic to look up",
                        required=False,
                        enum=[
                            "hours",
                            "location",
                            "services",
                            "insurance",
                            "payment",
                            "cancellation",
                            "parking",
                            "wifi",
                            "appointment",
                            "new patient",
                        ],
                    ),
                ],
                handler=FAQTool.lookup_faq,
                category="information",
            )
        )

        # Business hours tool
        self.register(
            Tool(
                name="get_business_hours",
                description=(
                    "Get business hours for a specific day. "
                    "Returns open/close times and whether the business is open."
                ),
                parameters=[
                    ToolParameter(
                        name="day",
                        type="string",
                        description="Day to check (e.g., 'Monday', 'today', 'tomorrow')",
                        required=False,
                    ),
                ],
                handler=HoursTool.get_business_hours,
                category="information",
            )
        )

        # Message tool
        self.register(
            Tool(
                name="take_message",
                description=(
                    "Take a message from the caller when no one is available "
                    "or the caller prefers to leave a message."
                ),
                parameters=[
                    ToolParameter(
                        name="caller_name",
                        type="string",
                        description="Name of the caller",
                        required=True,
                    ),
                    ToolParameter(
                        name="caller_phone",
                        type="string",
                        description="Caller's phone number",
                        required=True,
                    ),
                    ToolParameter(
                        name="message",
                        type="string",
                        description="Message content",
                        required=True,
                    ),
                    ToolParameter(
                        name="urgency",
                        type="string",
                        description="Message urgency level",
                        required=False,
                        enum=["low", "normal", "high", "urgent"],
                        default="normal",
                    ),
                    ToolParameter(
                        name="callback_number",
                        type="string",
                        description="Number to call back",
                        required=False,
                    ),
                ],
                handler=MessageTool.take_message,
                category="communication",
            )
        )

        # End call tool
        self.register(
            Tool(
                name="end_call",
                description=(
                    "End the current call gracefully. "
                    "Use when the conversation is complete or the caller wants to hang up."
                ),
                parameters=[
                    ToolParameter(
                        name="reason",
                        type="string",
                        description="Reason for ending the call",
                        required=False,
                        enum=["goodbye", "complete", "transfer", "error"],
                        default="goodbye",
                    ),
                ],
                handler=EndCallTool.end_call,
                category="call",
            )
        )

    def register(self, tool: Tool) -> None:
        """Register a tool.

        Args:
            tool: Tool definition.

        Raises:
            ValueError: If tool with same name already exists.
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")

        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")

    def unregister(self, tool_name: str) -> None:
        """Unregister a tool.

        Args:
            tool_name: Name of tool to remove.
        """
        self._tools.pop(tool_name, None)
        logger.debug(f"Unregistered tool: {tool_name}")

    def get_tool(self, tool_name: str) -> Optional[Tool]:
        """Get a tool by name.

        Args:
            tool_name: Tool name.

        Returns:
            Tool or None if not found.
        """
        return self._tools.get(tool_name)

    def get_tool_descriptions(self) -> List[Dict[str, Any]]:
        """Get all tool descriptions in OpenAI schema format.

        Returns:
            List of tool schema dicts.
        """
        return [tool.to_openai_schema() for tool in self._tools.values()]

    def list_tools(self) -> List[str]:
        """List all registered tool names.

        Returns:
            List of tool names.
        """
        return list(self._tools.keys())

    # ------------------------------------------------------------------ #
    #  Tool execution
    # ------------------------------------------------------------------ #

    async def execute(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        tenant_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> ToolResult:
        """Execute a tool by name.

        Args:
            tool_name: Name of tool to execute.
            parameters: Tool arguments.
            tenant_id: Optional tenant ID.
            session_id: Optional session ID.

        Returns:
            ToolResult with execution outcome.
        """
        import time as time_module

        start_time = time_module.perf_counter()
        self._execution_count += 1

        tool = self._tools.get(tool_name)
        if not tool:
            self._error_count += 1
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error_message=f"Tool '{tool_name}' not found",
                latency_ms=int((time_module.perf_counter() - start_time) * 1000),
            )

        if not tool.handler:
            self._error_count += 1
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error_message=f"Tool '{tool_name}' has no handler",
                latency_ms=int((time_module.perf_counter() - start_time) * 1000),
            )

        try:
            # Inject tenant/session context
            exec_params = dict(parameters)
            if tenant_id:
                exec_params["_tenant_id"] = tenant_id
            if session_id:
                exec_params["_session_id"] = session_id

            result = await tool.handler(**exec_params)

            self._success_count += 1

            return ToolResult(
                tool_name=tool_name,
                success=result.get("success", True),
                data=result,
                error_message=result.get("error", ""),
                latency_ms=int(
                    (time_module.perf_counter() - start_time) * 1000
                ),
            )

        except Exception as exc:
            logger.exception(f"Tool execution error: {tool_name}")
            self._error_count += 1
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error_message=str(exc),
                latency_ms=int(
                    (time_module.perf_counter() - start_time) * 1000
                ),
            )

    def parse_tool_call(self, raw: str) -> Optional[ToolCall]:
        """Parse a raw tool call string from LLM output.

        Supports XML-style and JSON-style tool calls.

        Args:
            raw: Raw tool call string.

        Returns:
            Parsed ToolCall or None.
        """
        # Try XML-style: <tool_call name="xxx">{params}</tool_call>
        import re

        xml_match = re.search(
            r'<tool_call\s+name="([^"]+)">\s*(\{[^}]*\})?\s*</tool_call>',
            raw,
            re.DOTALL,
        )
        if xml_match:
            name = xml_match.group(1)
            params_str = xml_match.group(2) or "{}"
            try:
                params = json.loads(params_str)
                return ToolCall(tool_name=name, parameters=params, call_id=None)
            except json.JSONDecodeError:
                pass

        # Try JSON-style
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                if "tool" in data or "name" in data:
                    name = data.get("tool") or data.get("name", "")
                    params = data.get("parameters") or data.get("args", {})
                    return ToolCall(
                        tool_name=name, parameters=params, call_id=None
                    )
        except json.JSONDecodeError:
            pass

        return None

    def format_result_for_llm(self, result: ToolResult) -> str:
        """Format tool result for LLM consumption.

        Args:
            result: Tool execution result.

        Returns:
            Formatted result string.
        """
        return result.to_llm_text()

    def get_stats(self) -> Dict[str, Any]:
        """Get tool execution statistics.

        Returns:
            Dict with execution metrics.
        """
        return {
            "total_executions": self._execution_count,
            "successful": self._success_count,
            "failed": self._error_count,
            "success_rate": (
                self._success_count / self._execution_count
                if self._execution_count > 0
                else 0.0
            ),
            "registered_tools": len(self._tools),
            "tool_names": self.list_tools(),
        }

    def reset_stats(self) -> None:
        """Reset execution statistics."""
        self._execution_count = 0
        self._success_count = 0
        self._error_count = 0


# ---------------------------------------------------------------------------
#  Factory functions
# ---------------------------------------------------------------------------

_tool_registry_instance: Optional[ToolRegistry] = None


async def get_tool_registry() -> ToolRegistry:
    """Get or create singleton ToolRegistry instance.

    Returns:
        Configured ToolRegistry with built-in tools.
    """
    global _tool_registry_instance
    if _tool_registry_instance is None:
        _tool_registry_instance = ToolRegistry(auto_register_builtin=True)
    return _tool_registry_instance


async def close_tool_registry() -> None:
    """Close singleton instance."""
    global _tool_registry_instance
    _tool_registry_instance = None
