"""
esl_connection.py — FreeSWITCH Event Socket Library (ESL) async client.

Manages the persistent ESL connection to FreeSWITCH:
- Connects via TCP to FreeSWITCH's event socket (default :8021)
- Authenticates with ESL password
- Subscribes to relevant events (CHANNEL_CREATE, ANSWER, HANGUP, DTMF, etc.)
- Dispatches events to registered handlers
- Sends commands (bgapi, api, sendmsg) to control calls
- Auto-reconnects with exponential backoff

Integration Points:
- OUT: FreeSWITCH (TCP ESL)
- IN: CallHandler (event subscriptions)
- IN: main.py SubsystemManager (lifecycle)
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Set

import structlog

logger = structlog.get_logger(__name__)


class ESLEvent:
    """Parsed FreeSWITCH ESL event."""

    def __init__(self, headers: Dict[str, str], body: bytes = b""):
        self.headers = headers
        self.body = body

    @property
    def name(self) -> str:
        return self.headers.get("Event-Name", "UNKNOWN")

    @property
    def call_id(self) -> Optional[str]:
        """Unique-ID / Channel-Call-UUID."""
        return self.headers.get("Unique-ID") or self.headers.get("Channel-Call-UUID")

    @property
    def caller_number(self) -> Optional[str]:
        return self.headers.get("Caller-Caller-ID-Number") or self.headers.get("Caller-Caller-ID")

    @property
    def caller_name(self) -> Optional[str]:
        return self.headers.get("Caller-Caller-ID-Name")

    @property
    def destination_number(self) -> Optional[str]:
        return self.headers.get("Caller-Destination-Number") or self.headers.get("Channel-Destination-Number")

    @property
    def channel_state(self) -> Optional[str]:
        return self.headers.get("Channel-State")

    @property
    def answer_state(self) -> Optional[str]:
        return self.headers.get("Answer-State")

    @property
    def hangup_cause(self) -> Optional[str]:
        return self.headers.get("Hangup-Cause")

    @property
    def variable_tenant_id(self) -> Optional[str]:
        return self.headers.get("Variable_Tenant_ID") or self.headers.get("Variable_tenant_id")

    def get(self, key: str, default: str = "") -> str:
        return self.headers.get(key, default)

    def __repr__(self) -> str:
        return f"ESLEvent(name={self.name}, call_id={self.call_id}, state={self.channel_state})"


class ESLConnection:
    """Async FreeSWITCH ESL client with auto-reconnect.

    Usage:
        esl = ESLConnection(host="localhost", port=8021, password="ClueCon")
        esl.on("CHANNEL_CREATE", handle_inbound)
        esl.on("CHANNEL_HANGUP", handle_hangup)
        await esl.connect()
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8021,
        password: str = "ClueCon",
        reconnect_interval: float = 1.0,
        max_reconnect_interval: float = 30.0,
        reconnect_backoff: float = 1.5,
    ):
        self.host = host
        self.port = port
        self.password = password
        self.reconnect_interval = reconnect_interval
        self.max_reconnect_interval = max_reconnect_interval
        self.reconnect_backoff = reconnect_backoff

        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected = False
        self._authenticated = False
        self._should_reconnect = True
        self._receive_task: Optional[asyncio.Task] = None

        # Event handlers: event_name -> list of callbacks
        self._handlers: Dict[str, List[Callable]] = {}
        # Wildcard handlers (receive all events)
        self._wildcard_handlers: List[Callable] = []

        # Command response futures (for api/bgapi commands)
        self._pending_responses: Dict[str, asyncio.Future] = {}
        self._command_counter = 0

    # ------------------------------------------------------------------ #
    # Properties
    # ------------------------------------------------------------------ #

    @property
    def connected(self) -> bool:
        return self._connected and self._authenticated

    # ------------------------------------------------------------------ #
    # Event subscription
    # ------------------------------------------------------------------ #

    def on(self, event_name: str, handler: Callable) -> None:
        """Register a handler for a specific event type.

        Use "ALL" to receive all events.
        """
        if event_name.upper() == "ALL":
            self._wildcard_handlers.append(handler)
        else:
            self._handlers.setdefault(event_name.upper(), []).append(handler)

    def off(self, event_name: str, handler: Optional[Callable] = None) -> None:
        """Remove handler(s) for an event type."""
        if event_name.upper() == "ALL":
            if handler is None:
                self._wildcard_handlers.clear()
            elif handler in self._wildcard_handlers:
                self._wildcard_handlers.remove(handler)
        else:
            if handler is None:
                self._handlers.pop(event_name.upper(), None)
            elif event_name.upper() in self._handlers:
                try:
                    self._handlers[event_name.upper()].remove(handler)
                except ValueError:
                    pass

    # ------------------------------------------------------------------ #
    # Connection lifecycle
    # ------------------------------------------------------------------ #

    async def connect(self) -> None:
        """Connect to FreeSWITCH ESL and start the event receive loop."""
        await self._connect_with_retry()

    async def disconnect(self) -> None:
        """Gracefully disconnect from FreeSWITCH."""
        self._should_reconnect = False
        self._connected = False
        self._authenticated = False

        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
        self._reader = None

        logger.info("esl.disconnected", host=self.host, port=self.port)

    async def _connect_with_retry(self) -> None:
        """Connect with exponential backoff."""
        interval = self.reconnect_interval

        while self._should_reconnect:
            try:
                logger.info("esl.connecting", host=self.host, port=self.port)
                self._reader, self._writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port),
                    timeout=10.0,
                )
                self._connected = True

                # Wait for auth request
                await self._authenticate()

                # Subscribe to events
                await self._subscribe_events()

                # Start receive loop
                self._receive_task = asyncio.create_task(self._receive_loop())

                logger.info("esl.connected", host=self.host, port=self.port)
                return

            except Exception as exc:
                self._connected = False
                self._authenticated = False
                logger.warning(
                    "esl.connect_failed",
                    host=self.host,
                    error=str(exc),
                    retry_in=f"{interval:.1f}s",
                )

                if not self._should_reconnect:
                    return

                await asyncio.sleep(interval)
                interval = min(
                    interval * self.reconnect_backoff,
                    self.max_reconnect_interval,
                )

    async def _authenticate(self) -> None:
        """Read auth request and send password."""
        # FreeSWITCH sends "Content-Type: auth/request" on connect
        headers, body = await self._read_message()

        if headers.get("Content-Type") != "auth/request":
            raise ConnectionError(f"Expected auth request, got: {headers.get('Content-Type')}")

        # Send auth
        self._send_raw(f"auth {self.password}\n\n")

        # Wait for auth reply
        headers, body = await self._read_message()

        if headers.get("Reply-Text", "").startswith("+OK"):
            self._authenticated = True
            logger.info("esl.authenticated")
        else:
            raise ConnectionError(f"Authentication failed: {headers.get('Reply-Text')}")

    async def _subscribe_events(self) -> None:
        """Subscribe to all events."""
        # Subscribe to all events — filtering happens in Python
        self._send_raw("event plain ALL\n\n")
        headers, _ = await self._read_message()
        if not headers.get("Reply-Text", "").startswith("+OK"):
            logger.warning("esl.subscribe_failed", reply=headers.get("Reply-Text"))

    # ------------------------------------------------------------------ #
    # Receiving events
    # ------------------------------------------------------------------ #

    async def _receive_loop(self) -> None:
        """Main event receive loop."""
        while self._connected and self._should_reconnect:
            try:
                headers, body = await self._read_message()

                content_type = headers.get("Content-Type", "")

                if content_type == "text/event-plain":
                    event = self._parse_event(body)
                    if event:
                        await self._dispatch_event(event)

                elif content_type == "api/response" or content_type == "command/reply":
                    # Response to a command we sent
                    future = self._pop_pending_command()
                    if future and not future.done():
                        future.set_result((headers, body))

                elif content_type == "disconnect":
                    logger.warning("esl.disconnect_message_received")
                    break

            except asyncio.TimeoutError:
                continue
            except ConnectionError:
                logger.warning("esl.connection_lost")
                break
            except Exception as exc:
                logger.error("esl.receive_error", error=str(exc))
                break

        # Attempt reconnection if unexpectedly disconnected
        if self._should_reconnect:
            self._connected = False
            self._authenticated = False
            logger.info("esl.attempting_reconnect")
            asyncio.create_task(self._connect_with_retry())

    async def _read_message(self) -> tuple[Dict[str, str], bytes]:
        """Read a complete ESL message (headers + optional body)."""
        headers: Dict[str, str] = {}
        body = b""

        # Read headers until blank line
        while True:
            line = await asyncio.wait_for(self._reader.readline(), timeout=30.0)

            if line in (b"\n", b"\r\n"):
                break

            try:
                decoded = line.decode("utf-8", errors="replace").strip()
                if ": " in decoded:
                    key, value = decoded.split(": ", 1)
                    headers[key.strip()] = value.strip()
            except Exception:
                continue

        # Check for Content-Length (body follows)
        content_length_str = headers.get("Content-Length")
        if content_length_str:
            try:
                length = int(content_length_str)
                if length > 0:
                    body = await self._reader.readexactly(length)
            except (ValueError, asyncio.IncompleteReadError):
                pass

        return headers, body

    def _parse_event(self, body: bytes) -> Optional[ESLEvent]:
        """Parse a plain ESL event body into ESLEvent."""
        headers: Dict[str, str] = {}

        try:
            text = body.decode("utf-8", errors="replace")
            for line in text.split("\n"):
                line = line.strip()
                if not line:
                    continue
                if ": " in line:
                    key, value = line.split(": ", 1)
                    headers[key.strip()] = value.strip()
        except Exception as exc:
            logger.error("esl.parse_error", error=str(exc))
            return None

        return ESLEvent(headers=headers, body=body)

    async def _dispatch_event(self, event: ESLEvent) -> None:
        """Dispatch an event to registered handlers."""
        event_name = event.name

        # Specific handlers
        handlers = self._handlers.get(event_name, [])
        for handler in handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                logger.error(
                    "esl.handler_error",
                    event=event_name,
                    error=str(exc),
                )

        # Wildcard handlers
        for handler in self._wildcard_handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                logger.error(
                    "esl.wildcard_handler_error",
                    event=event_name,
                    error=str(exc),
                )

    # ------------------------------------------------------------------ #
    # Sending commands
    # ------------------------------------------------------------------ #

    def _send_raw(self, data: str) -> None:
        """Send raw data to FreeSWITCH."""
        if not self._writer:
            raise ConnectionError("ESL not connected")
        self._writer.write(data.encode("utf-8"))
        try:
            self._writer.flush()  # type: ignore
        except Exception:
            pass

    async def send_api(self, command: str, args: str = "") -> str:
        """Send an api command and return the response text.

        Args:
            command: The API command (e.g., "uuid_answer")
            args: Command arguments

        Returns:
            Response text from FreeSWITCH
        """
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._command_counter += 1
        cmd_id = str(self._command_counter)
        self._pending_responses[cmd_id] = future

        self._send_raw(f"api {command} {args}\n\n")

        try:
            headers, body = await asyncio.wait_for(future, timeout=10.0)
            text = body.decode("utf-8", errors="replace").strip()
            return text
        except asyncio.TimeoutError:
            self._pending_responses.pop(cmd_id, None)
            raise TimeoutError(f"API command timed out: {command} {args}")

    async def send_bgapi(self, command: str, args: str = "") -> str:
        """Send a background API command (non-blocking).

        Returns:
            Job UUID for tracking
        """
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._command_counter += 1
        cmd_id = str(self._command_counter)
        self._pending_responses[cmd_id] = future

        self._send_raw(f"bgapi {command} {args}\n\n")

        try:
            headers, body = await asyncio.wait_for(future, timeout=10.0)
            text = body.decode("utf-8", errors="replace").strip()
            return text
        except asyncio.TimeoutError:
            self._pending_responses.pop(cmd_id, None)
            raise TimeoutError(f"bgapi command timed out: {command} {args}")

    async def send_msg(self, call_uuid: str, command: str, args: Dict[str, str] = None) -> None:
        """Send a sendmsg command to control a specific channel.

        Args:
            call_uuid: The channel's Unique-ID
            command: The command (e.g., "answer", "hangup", "playback")
            args: Additional arguments (e.g., {"call-command": "execute", "execute-app-arg": "..."})
        """
        msg_lines = [
            f"sendmsg {call_uuid}",
            f"call-command: execute",
            f"execute-app-name: {command}",
        ]

        if args:
            for key, value in args.items():
                msg_lines.append(f"{key}: {value}")

        msg_lines.append("")  # blank line to terminate
        self._send_raw("\n".join(msg_lines) + "\n")

    async def answer(self, call_uuid: str) -> str:
        """Answer an inbound call."""
        return await self.send_api("uuid_answer", call_uuid)

    async def hangup(self, call_uuid: str, cause: str = "normal_clearing") -> str:
        """Hangup a call."""
        return await self.send_api("uuid_kill", f"{call_uuid} {cause}")

    async def playback(self, call_uuid: str, audio_file: str) -> str:
        """Play an audio file to the caller."""
        return await self.send_api(
            "uuid_broadcast",
            f"{call_uuid} play::{audio_file} aleg"
        )

    async def bridge(self, call_uuid: str, dest_url: str) -> str:
        """Bridge a call to a destination."""
        return await self.send_api(
            "uuid_bridge",
            f"{call_uuid} {dest_url}"
        )

    async def record(self, call_uuid: str, file_path: str, max_len: int = 300) -> str:
        """Start recording a call."""
        return await self.send_api(
            "uuid_record",
            f"{call_uuid} start {file_path} {max_len}"
        )

    async def set_var(self, call_uuid: str, var_name: str, var_value: str) -> str:
        """Set a channel variable."""
        return await self.send_api(
            "uuid_setvar",
            f"{call_uuid} {var_name} {var_value}"
        )

    async def get_var(self, call_uuid: str, var_name: str) -> str:
        """Get a channel variable."""
        return await self.send_api(
            "uuid_getvar",
            f"{call_uuid} {var_name}"
        )

    def _pop_pending_command(self) -> Optional[asyncio.Future]:
        """Pop the oldest pending command future."""
        if self._pending_responses:
            cmd_id = next(iter(self._pending_responses))
            return self._pending_responses.pop(cmd_id, None)
        return None
