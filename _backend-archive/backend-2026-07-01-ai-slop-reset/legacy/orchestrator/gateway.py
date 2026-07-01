"""
gateway.py -- WebSocket gateway and FastAPI router for orchestration.

Responsibilities:
- Accept WebSocket connections from FreeSWITCH (audio streaming)
- Route audio to appropriate AI worker
- Handle connection lifecycle (connect, message, disconnect, error)
- Bridge FreeSWITCH events to the event bus
- Provide REST endpoints for session/worker/queue management

Integration Points:
- IN: FreeSWITCH (mod_event_socket, mod_audio_stream)
- IN: React frontend (monitoring dashboard)
- OUT: SessionManager (session CRUD)
- OUT: WorkerPool (task dispatch)
- OUT: EventBus (event publishing)
- OUT: LoadBalancer (worker assignment)
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import JSONResponse, PlainTextResponse

from legacy.orchestrator.models import (
    ActiveSession,
    CallState,
    ControlMessage,
    ErrorMessage,
    EventType,
    StatusMessage,
    SystemEvent,
    TranscriptMessage,
    WorkerStatus,
)

logger = logging.getLogger(__name__)


class GatewayRouter:
    """FastAPI router factory for orchestration endpoints.

    Provides WebSocket endpoints for real-time audio streaming
    and REST endpoints for session/worker/queue management.
    """

    def __init__(
        self,
        session_manager: Any,
        worker_pool: Any,
        event_bus: Any,
        load_balancer: Any,
        health_monitor: Any,
        call_queue: Any,
    ):
        self.session_mgr = session_manager
        self.worker_pool = worker_pool
        self.event_bus = event_bus
        self.load_balancer = load_balancer
        self.health_monitor = health_monitor
        self.call_queue = call_queue

        # Track active WebSocket connections: call_id -> WebSocket
        self.active_connections: Dict[str, WebSocket] = {}
        # Track active tasks: call_id -> asyncio.Task
        self.active_tasks: Dict[str, asyncio.Task] = {}

    def get_router(self) -> APIRouter:
        """Create and configure the FastAPI router.

        Returns:
            Configured APIRouter with all endpoints
        """
        router = APIRouter(prefix="/api/v1/orchestrator", tags=["orchestration"])

        # ---- WebSocket Endpoints ----

        @router.websocket("/ws/call/{call_id}/audio")
        async def websocket_audio(websocket: WebSocket, call_id: str) -> None:
            """Primary audio streaming WebSocket.

            Connection Flow:
            1. Validate call_id exists in Redis
            2. Accept connection, transition state to CONNECTING
            3. Start audio processing loop
            4. On disconnect: cleanup, transition to ENDED, archive
            """
            await self._handle_audio_websocket(websocket, call_id)

        @router.websocket("/ws/events")
        async def websocket_events(
            websocket: WebSocket,
            event_types: Optional[str] = Query(None),
            tenant_id: Optional[str] = Query(None),
        ) -> None:
            """Event streaming WebSocket for monitoring dashboards."""
            await self._handle_events_websocket(websocket, event_types, tenant_id)

        # ---- Session Endpoints ----

        @router.get("/sessions")
        async def list_sessions(
            tenant_id: Optional[str] = Query(None),
            state: Optional[str] = Query(None),
            limit: int = Query(50, ge=1, le=200),
            offset: int = Query(0, ge=0),
        ) -> Dict[str, Any]:
            """List active sessions with optional filtering."""
            sessions = await self.session_mgr.list_sessions(
                tenant_id=tenant_id,
                state=state,
                limit=limit,
                offset=offset,
            )
            total = await self.session_mgr.count_sessions(
                tenant_id=tenant_id, state=state
            )
            return {
                "total": total,
                "limit": limit,
                "offset": offset,
                "sessions": [s.model_dump(mode="json") for s in sessions],
            }

        @router.get("/sessions/{call_id}")
        async def get_session(call_id: str) -> Dict[str, Any]:
            """Get detailed session information."""
            session = await self.session_mgr.get_session(call_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            return session.model_dump(mode="json")

        @router.patch("/sessions/{call_id}")
        async def update_session(call_id: str, update: Dict[str, Any]) -> Dict[str, Any]:
            """Update session state or trigger actions."""
            session = await self.session_mgr.get_session(call_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

            action = update.get("action")

            if action == "transfer":
                result = await self._transfer_call(call_id, update.get("target"))
                return {"action": "transfer", "status": "pending", "result": result}
            elif action == "hold":
                await self.session_mgr.update_session(
                    call_id, {"state": CallState.HOLDING}
                )
                return {"action": "hold", "status": "success"}
            elif action == "resume":
                await self.session_mgr.update_session(
                    call_id, {"state": CallState.ACTIVE}
                )
                return {"action": "resume", "status": "success"}
            elif action == "end":
                await self._end_call(call_id, update.get("reason", "operator_request"))
                return {"action": "end", "status": "success"}
            else:
                # Generic field update
                await self.session_mgr.update_session(call_id, update)
                return {"action": "update", "status": "success"}

        @router.delete("/sessions/{call_id}")
        async def force_end_session(call_id: str) -> Dict[str, str]:
            """Forcefully end a session (emergency use)."""
            await self._end_call(call_id, "force_terminated")
            return {"status": "terminated", "call_id": call_id}

        # ---- Worker Endpoints ----

        @router.get("/workers")
        async def list_workers() -> Dict[str, Any]:
            """List all worker nodes with their status."""
            workers = await self.worker_pool.list_workers()
            summary = {
                "total": len(workers),
                "idle": sum(1 for w in workers if w.status == WorkerStatus.IDLE),
                "busy": sum(1 for w in workers if w.status == WorkerStatus.BUSY),
                "starting": sum(
                    1 for w in workers if w.status == WorkerStatus.STARTING
                ),
                "draining": sum(
                    1 for w in workers if w.status == WorkerStatus.DRAINING
                ),
                "unhealthy": sum(
                    1 for w in workers if w.status == WorkerStatus.UNHEALTHY
                ),
                "offline": sum(
                    1 for w in workers if w.status == WorkerStatus.OFFLINE
                ),
                "total_available_slots": sum(
                    w.available_slots for w in workers
                ),
            }
            return {
                "workers": [w.model_dump(mode="json") for w in workers],
                "summary": summary,
            }

        @router.get("/workers/{worker_id}")
        async def get_worker(worker_id: str) -> Dict[str, Any]:
            """Get detailed worker information."""
            worker = await self.worker_pool.get_worker(worker_id)
            if not worker:
                raise HTTPException(status_code=404, detail="Worker not found")
            return worker.model_dump(mode="json")

        @router.post("/workers/{worker_id}/drain")
        async def drain_worker(worker_id: str) -> Dict[str, str]:
            """Drain worker: no new assignments, finish current calls."""
            result = await self.worker_pool.drain_worker(worker_id)
            if not result:
                raise HTTPException(status_code=404, detail="Worker not found")
            return {"status": "draining", "worker_id": worker_id}

        @router.post("/workers/{worker_id}/restart")
        async def restart_worker(worker_id: str) -> Dict[str, Any]:
            """Restart a worker container."""
            result = await self.worker_pool.restart_worker(worker_id)
            if result.get("error"):
                raise HTTPException(
                    status_code=500, detail=result["error"]
                )
            return {"status": "restarting", "worker_id": worker_id, **result}

        @router.get("/workers/stats")
        async def worker_stats() -> Dict[str, Any]:
            """Aggregate worker statistics."""
            return await self.health_monitor.get_aggregate_stats()

        # ---- Queue Endpoints ----

        @router.get("/queue")
        async def queue_status() -> Dict[str, Any]:
            """Get global queue status."""
            return await self.call_queue.get_global_status()

        @router.get("/queue/{tenant_id}")
        async def tenant_queue(tenant_id: str) -> Dict[str, Any]:
            """Get queue for specific tenant."""
            return await self.call_queue.get_tenant_queue(tenant_id)

        @router.post("/queue/{call_id}/priority")
        async def bump_priority(call_id: str, priority: int) -> Dict[str, Any]:
            """Manually adjust call priority."""
            result = await self.call_queue.update_priority(call_id, priority)
            if not result:
                raise HTTPException(status_code=404, detail="Call not in queue")
            return {"status": "updated", "call_id": call_id, "priority": priority}

        # ---- System Endpoints ----

        @router.get("/status")
        async def system_status() -> Dict[str, Any]:
            """Get overall system health status."""
            return await self.health_monitor.get_system_status()

        @router.get("/metrics")
        async def prometheus_metrics() -> PlainTextResponse:
            """Prometheus-compatible metrics endpoint."""
            metrics = await self.health_monitor.get_prometheus_metrics()
            return PlainTextResponse(content=metrics)

        @router.get("/events")
        async def recent_events(
            event_type: Optional[str] = Query(None),
            limit: int = Query(100, ge=1, le=1000),
        ) -> List[Dict[str, Any]]:
            """Get recent system events."""
            events = await self.event_bus.get_recent_events(event_type, limit)
            return [e.model_dump(mode="json") for e in events]

        @router.get("/events/stream")
        async def get_stream_events(
            start_id: str = Query("0"),
            count: int = Query(100, ge=1, le=1000),
        ) -> List[Dict[str, Any]]:
            """Get events from Redis Stream (for replay)."""
            return await self.event_bus.get_stream_events(start_id, count)

        # ---- Health Check Endpoint ----

        @router.get("/health")
        async def health_check() -> Dict[str, Any]:
            """Health check endpoint."""
            status_data = await self.health_monitor.get_system_status()
            http_status = (
                status.HTTP_200_OK
                if status_data["status"] == "healthy"
                else status.HTTP_503_SERVICE_UNAVAILABLE
            )
            return JSONResponse(
                content=status_data, status_code=http_status
            )

        return router

    # ---- WebSocket Handler Methods ----

    async def _handle_audio_websocket(self, websocket: WebSocket, call_id: str) -> None:
        """Handle audio streaming WebSocket lifecycle.

        Args:
            websocket: FastAPI WebSocket object
            call_id: Call identifier from URL path
        """
        # Validate session exists
        session = await self.session_mgr.get_session(call_id)
        if not session:
            await websocket.close(code=4004, reason="Unknown call_id")
            return

        await websocket.accept()
        self.active_connections[call_id] = websocket

        # Update session
        await self.session_mgr.update_session(
            call_id,
            {
                "state": CallState.CONNECTING,
                "ws_connected": True,
                "ws_client_ip": (
                    websocket.client.host if websocket.client else None
                ),
            },
        )

        self.event_bus.publish(
            SystemEvent(
                event_type=EventType.CALL_CONNECTED,
                call_id=call_id,
                tenant_id=session.tenant_id,
                payload={
                    "client_ip": (
                        websocket.client.host if websocket.client else None
                    )
                },
            )
        )

        try:
            # Transition to ACTIVE
            await self.session_mgr.update_session(
                call_id,
                {
                    "state": CallState.ACTIVE,
                    "answered_at": datetime.utcnow(),
                },
            )

            self.event_bus.publish(
                SystemEvent(
                    event_type=EventType.CALL_ACTIVE,
                    call_id=call_id,
                    tenant_id=session.tenant_id,
                )
            )

            # Main message loop
            await self._audio_message_loop(websocket, call_id, session)

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for call {call_id}")
        except Exception as e:
            logger.error(f"WebSocket error for call {call_id}: {e}")
            try:
                await self.session_mgr.update_session(
                    call_id,
                    {
                        "error_count": session.error_count + 1,
                        "last_error": str(e),
                    },
                )
            except Exception:
                pass
        finally:
            # Cleanup
            await self._cleanup_call(call_id, "websocket_closed")

    async def _audio_message_loop(
        self, websocket: WebSocket, call_id: str, session: ActiveSession
    ) -> None:
        """Process incoming audio messages and dispatch AI tasks.

        Args:
            websocket: FastAPI WebSocket
            call_id: Call identifier
            session: ActiveSession object
        """

        async def send_response(result: Dict[str, Any]) -> None:
            """Send TTS audio back to FreeSWITCH."""
            if result.get("response_audio_b64"):
                await websocket.send_json(
                    {
                        "type": "audio_output",
                        "timestamp": time.time(),
                        "data": result["response_audio_b64"],
                        "duration_ms": result.get("duration_ms", 0),
                        "sequence": session.audio_chunks_sent + 1,
                    }
                )
                await self.session_mgr.update_session(
                    call_id,
                    {
                        "audio_chunks_sent": session.audio_chunks_sent + 1
                    },
                )

            # Send transcript update
            if result.get("transcript"):
                await websocket.send_json(
                    {
                        "type": "transcript",
                        "speaker": "caller",
                        "text": result["transcript"],
                        "is_final": True,
                    }
                )

            # Send AI response transcript
            if result.get("response_text"):
                await websocket.send_json(
                    {
                        "type": "transcript",
                        "speaker": "agent",
                        "text": result["response_text"],
                        "is_final": True,
                    }
                )

        async def process_audio(audio_b64: str) -> Dict[str, Any]:
            """Dispatch AI pipeline task."""
            task = self.worker_pool.process_audio_chunk(call_id, audio_b64)

            if task is None:
                return {}

            # Wait for result (with timeout)
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: task.get(timeout=20)),
                timeout=25.0,
            )
            return result or {}

        while True:
            try:
                message = await websocket.receive_json()
            except WebSocketDisconnect:
                break

            msg_type = message.get("type")

            if msg_type == "audio_input":
                # Update metrics
                duration_ms = message.get("duration_ms", 0)
                try:
                    await self.session_mgr.update_session(
                        call_id,
                        {
                            "audio_chunks_received": (
                                session.audio_chunks_received + 1
                            ),
                            "total_audio_seconds": (
                                session.total_audio_seconds
                                + duration_ms / 1000
                            ),
                        },
                    )
                except Exception as e:
                    logger.debug(f"Session metric update failed: {e}")

                # Process audio
                try:
                    # Send "processing" status
                    await websocket.send_json(
                        {
                            "type": "status",
                            "state": "processing",
                            "detail": "stt",
                        }
                    )

                    result = await process_audio(message.get("data", ""))

                    if result:
                        await send_response(result)

                        # Log latency
                        latency_ms = result.get("total_latency_ms", 0)
                        if latency_ms > 2000:
                            logger.warning(
                                f"High latency for call {call_id}: {latency_ms}ms"
                            )

                except asyncio.TimeoutError:
                    logger.error(f"AI pipeline timeout for call {call_id}")
                    await websocket.send_json(
                        {
                            "type": "error",
                            "code": "PIPELINE_TIMEOUT",
                            "message": "Processing took too long",
                            "recoverable": True,
                        }
                    )
                except Exception as e:
                    logger.error(f"AI pipeline error for call {call_id}: {e}")
                    await websocket.send_json(
                        {
                            "type": "error",
                            "code": "PIPELINE_ERROR",
                            "message": str(e),
                            "recoverable": True,
                        }
                    )

            elif msg_type == "control":
                action = message.get("action")
                if action == "mute":
                    pass  # Handled by FreeSWITCH
                elif action == "unmute":
                    pass
                elif action == "hold":
                    await self.session_mgr.update_session(
                        call_id, {"state": CallState.HOLDING}
                    )
                elif action == "resume":
                    await self.session_mgr.update_session(
                        call_id, {"state": CallState.ACTIVE}
                    )
                elif action == "end_call":
                    break

            elif msg_type == "ping":
                await websocket.send_json(
                    {"type": "pong", "timestamp": time.time()}
                )

    async def _handle_events_websocket(
        self,
        websocket: WebSocket,
        event_types: Optional[str],
        tenant_id: Optional[str],
    ) -> None:
        """Handle event streaming WebSocket for monitoring.

        Args:
            websocket: FastAPI WebSocket
            event_types: Comma-separated event type filter
            tenant_id: Optional tenant filter
        """
        await websocket.accept()

        # Parse filter
        type_filter: Optional[Any] = None
        if event_types:
            type_filter = set(event_types.split(","))

        try:
            async for event in self.event_bus.subscribe(
                filter_types=type_filter, filter_tenant=tenant_id
            ):
                try:
                    await websocket.send_json(event.model_dump(mode="json"))
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.error(f"Error sending event to WebSocket: {e}")
                    break
        except Exception as e:
            logger.error(f"Events WebSocket error: {e}")
        finally:
            try:
                await websocket.close()
            except Exception:
                pass

    # ---- Call Control Methods ----

    async def _transfer_call(self, call_id: str, target: Optional[str]) -> Dict[str, Any]:
        """Transfer call to external number or extension.

        Args:
            call_id: Call identifier
            target: Transfer target

        Returns:
            Transfer result dict
        """
        session = await self.session_mgr.get_session(call_id)
        if not session:
            return {"error": "Session not found"}

        # Publish transfer event
        self.event_bus.publish(
            SystemEvent(
                event_type=EventType.CALL_TRANSFERRED,
                call_id=call_id,
                tenant_id=session.tenant_id,
                payload={"target": target},
            )
        )

        await self.session_mgr.update_session(
            call_id,
            {
                "state": CallState.ENDED,
                "ended_at": datetime.utcnow(),
            },
        )

        return {"target": target, "status": "transferred"}

    async def _end_call(self, call_id: str, reason: str) -> None:
        """End a call and cleanup resources.

        Args:
            call_id: Call identifier
            reason: Reason for ending
        """
        session = await self.session_mgr.get_session(call_id)
        if not session:
            return

        # Close WebSocket if still open
        ws = self.active_connections.pop(call_id, None)
        if ws:
            try:
                await ws.close()
            except Exception:
                pass

        # Cancel any pending tasks
        task = self.active_tasks.pop(call_id, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Update session
        try:
            await self.session_mgr.update_session(
                call_id,
                {
                    "state": CallState.ENDED,
                    "ended_at": datetime.utcnow(),
                },
            )
        except Exception as e:
            logger.error(f"Failed to update session to ENDED: {e}")

        # Release worker
        if session.worker_id:
            try:
                await self.worker_pool.release_worker(session.worker_id, call_id)
            except Exception as e:
                logger.error(f"Failed to release worker: {e}")

        # Publish event
        duration = self._get_call_duration(session)
        self.event_bus.publish(
            SystemEvent(
                event_type=EventType.CALL_ENDED,
                call_id=call_id,
                tenant_id=session.tenant_id,
                payload={"reason": reason, "duration_seconds": duration},
            )
        )

        # Trigger async archive via Celery
        try:
            self.worker_pool.handle_call_end(call_id)
        except Exception as e:
            logger.error(f"Failed to trigger call archive: {e}")

    async def _cleanup_call(self, call_id: str, reason: str) -> None:
        """Cleanup after call ends or disconnects.

        Args:
            call_id: Call identifier
            reason: Cleanup reason
        """
        self.active_connections.pop(call_id, None)
        task = self.active_tasks.pop(call_id, None)
        if task:
            task.cancel()

        session = await self.session_mgr.get_session(call_id)
        if session and session.state not in (CallState.ENDED, CallState.ARCHIVED):
            await self._end_call(call_id, reason)

    @staticmethod
    def _get_call_duration(session: ActiveSession) -> int:
        """Calculate call duration in seconds.

        Args:
            session: ActiveSession

        Returns:
            Duration in seconds
        """
        if session.ended_at and session.answered_at:
            return int((session.ended_at - session.answered_at).total_seconds())
        return 0


def create_orchestrator_router(
    session_manager: Any,
    worker_pool: Any,
    event_bus: Any,
    load_balancer: Any,
    health_monitor: Any,
    call_queue: Any,
) -> APIRouter:
    """Factory function to create the orchestrator router.

    Args:
        session_manager: SessionManager instance
        worker_pool: WorkerPool instance
        event_bus: EventBus instance
        load_balancer: LoadBalancer instance
        health_monitor: HealthMonitor instance
        call_queue: CallQueue instance

    Returns:
        Configured APIRouter
    """
    gateway = GatewayRouter(
        session_manager=session_manager,
        worker_pool=worker_pool,
        event_bus=event_bus,
        load_balancer=load_balancer,
        health_monitor=health_monitor,
        call_queue=call_queue,
    )
    return gateway.get_router()
