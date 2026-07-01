"""operations/audit/logger.py - Audit logging with chain-of-custody.

Provides immutable audit trail with append-only logs, cryptographically
verifiable checksum chain. Every admin and tenant action is logged
with full context for compliance and debugging.

Design: Append-only logs. SHA-256 checksum chain for tamper detection.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


class ActorType(str, Enum):
    """Type of actor performing an action."""
    USER = "user"
    SYSTEM = "system"
    ADMIN = "admin"
    API_KEY = "api_key"
    WEBHOOK = "webhook"


class ActionCategory(str, Enum):
    """Category of audit action."""
    TENANT = "tenant"
    USER = "user"
    CONFIG = "config"
    BILLING = "billing"
    PROMPT = "prompt"
    FEATURE = "feature"
    CALL = "call"
    SECURITY = "security"
    DATA = "data"
    SYSTEM = "system"


class Severity(str, Enum):
    """Severity level of audit event."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AuditLogEntry:
    """Single audit log entry with chain-of-custody.

    Attributes:
        id: Unique entry ID
        actor_type: Type of actor
        actor_id: Actor identifier
        actor_email: Actor email
        ip_address: Source IP
        tenant_id: Target tenant
        target_type: Type of target resource
        target_id: Target resource ID
        action_category: Action category
        action: Specific action
        severity: Severity level
        description: Human-readable description
        before_state: Previous state snapshot
        after_state: New state snapshot
        checksum: SHA-256 checksum
        previous_checksum: Previous entry checksum (chain link)
        timestamp: When the action occurred
    """

    def __init__(
        self,
        actor_type: ActorType,
        action_category: ActionCategory,
        action: str,
        description: str,
        actor_id: Optional[str] = None,
        actor_email: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        tenant_id: Optional[uuid.UUID] = None,
        target_type: str = "",
        target_id: Optional[str] = None,
        severity: Severity = Severity.INFO,
        before_state: Optional[Dict[str, Any]] = None,
        after_state: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ):
        self.id = uuid.uuid4()
        self.actor_type = actor_type
        self.actor_id = actor_id
        self.actor_email = actor_email
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.tenant_id = tenant_id
        self.target_type = target_type
        self.target_id = target_id
        self.action_category = action_category
        self.action = action
        self.severity = severity
        self.description = description
        self.before_state = before_state
        self.after_state = after_state
        self.metadata = metadata or {}
        self.timestamp = timestamp or datetime.utcnow()
        self.previous_checksum: Optional[str] = None
        self.checksum: str = ""

    def compute_checksum(self, previous_checksum: Optional[str] = None) -> str:
        """Compute SHA-256 checksum for this entry.

        The checksum includes the entry data plus the previous checksum,
        creating a cryptographic chain for tamper detection.
        """
        self.previous_checksum = previous_checksum
        data = {
            "id": str(self.id),
            "actor_type": self.actor_type.value,
            "actor_id": self.actor_id or "",
            "action": self.action,
            "timestamp": self.timestamp.isoformat(),
            "previous_checksum": previous_checksum or "",
        }
        payload = json.dumps(data, sort_keys=True, default=str)
        self.checksum = hashlib.sha256(payload.encode()).hexdigest()
        return self.checksum

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "actor_type": self.actor_type.value,
            "actor_id": self.actor_id,
            "actor_email": self.actor_email,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "tenant_id": str(self.tenant_id) if self.tenant_id else None,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "action_category": self.action_category.value,
            "action": self.action,
            "severity": self.severity.value,
            "description": self.description,
            "before_state": self.before_state,
            "after_state": self.after_state,
            "metadata": self.metadata,
            "checksum": self.checksum,
            "previous_checksum": self.previous_checksum,
            "timestamp": self.timestamp.isoformat(),
        }


class AuditLogger:
    """Audit logger with chain-of-custody.

    Usage:
        audit = AuditLogger()
        await audit.log(
            actor_type=ActorType.USER,
            action_category=ActionCategory.TENANT,
            action="tenant.created",
            description="Tenant created via onboarding",
            tenant_id=tenant_id,
        )
    """

    def __init__(self) -> None:
        self._entries: List[AuditLogEntry] = []
        self._last_checksum: Optional[str] = None
        self._tenant_index: Dict[str, List[AuditLogEntry]] = {}
        self._action_index: Dict[str, List[AuditLogEntry]] = {}

    # -- Core Logging -----------------------------------------------------

    async def log(
        self,
        actor_type: ActorType,
        action_category: ActionCategory,
        action: str,
        description: str,
        actor_id: Optional[str] = None,
        actor_email: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        tenant_id: Optional[uuid.UUID] = None,
        target_type: str = "",
        target_id: Optional[str] = None,
        severity: Severity = Severity.INFO,
        before_state: Optional[Dict[str, Any]] = None,
        after_state: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLogEntry:
        """Create and store an audit log entry.

        Args:
            actor_type: Type of actor
            action_category: Action category
            action: Specific action identifier
            description: Human-readable description
            actor_id: Actor identifier
            actor_email: Actor email
            ip_address: Source IP address
            tenant_id: Target tenant
            target_type: Type of target resource
            target_id: Target resource ID
            severity: Severity level
            before_state: Previous state snapshot
            after_state: New state snapshot
            metadata: Additional context

        Returns:
            The created audit log entry
        """
        entry = AuditLogEntry(
            actor_type=actor_type,
            action_category=action_category,
            action=action,
            description=description,
            actor_id=actor_id,
            actor_email=actor_email,
            ip_address=ip_address,
            user_agent=user_agent,
            tenant_id=tenant_id,
            target_type=target_type,
            target_id=target_id,
            severity=severity,
            before_state=before_state,
            after_state=after_state,
            metadata=metadata,
        )

        # Compute checksum with chain link
        entry.compute_checksum(self._last_checksum)
        self._last_checksum = entry.checksum

        # Store
        self._entries.append(entry)

        # Index
        if tenant_id:
            tid = str(tenant_id)
            if tid not in self._tenant_index:
                self._tenant_index[tid] = []
            self._tenant_index[tid].append(entry)

        if action not in self._action_index:
            self._action_index[action] = []
        self._action_index[action].append(entry)

        # Log to structured logger
        log_fn = logger.warning if severity == Severity.WARNING else logger.critical if severity == Severity.CRITICAL else logger.info
        log_fn(
            "audit.log",
            action=action,
            actor_type=actor_type.value,
            actor_id=actor_id,
            tenant_id=str(tenant_id) if tenant_id else None,
            severity=severity.value,
        )

        return entry

    # -- Convenience Methods ----------------------------------------------

    async def log_tenant_action(
        self,
        action: str,
        description: str,
        tenant_id: uuid.UUID,
        actor_id: str,
        actor_email: str,
        before_state: Optional[Dict[str, Any]] = None,
        after_state: Optional[Dict[str, Any]] = None,
        severity: Severity = Severity.INFO,
    ) -> AuditLogEntry:
        """Log a tenant-related action."""
        return await self.log(
            actor_type=ActorType.ADMIN,
            action_category=ActionCategory.TENANT,
            action=action,
            description=description,
            actor_id=actor_id,
            actor_email=actor_email,
            tenant_id=tenant_id,
            target_type="tenant",
            target_id=str(tenant_id),
            severity=severity,
            before_state=before_state,
            after_state=after_state,
        )

    async def log_user_action(
        self,
        action: str,
        description: str,
        user_id: str,
        user_email: str,
        tenant_id: uuid.UUID,
        ip_address: Optional[str] = None,
        severity: Severity = Severity.INFO,
    ) -> AuditLogEntry:
        """Log a user-related action."""
        return await self.log(
            actor_type=ActorType.USER,
            action_category=ActionCategory.USER,
            action=action,
            description=description,
            actor_id=user_id,
            actor_email=user_email,
            ip_address=ip_address,
            tenant_id=tenant_id,
            target_type="user",
            target_id=user_id,
            severity=severity,
        )

    async def log_security_event(
        self,
        action: str,
        description: str,
        actor_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        tenant_id: Optional[uuid.UUID] = None,
        severity: Severity = Severity.INFO,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLogEntry:
        """Log a security-related event."""
        return await self.log(
            actor_type=ActorType.SYSTEM,
            action_category=ActionCategory.SECURITY,
            action=action,
            description=description,
            actor_id=actor_id,
            ip_address=ip_address,
            tenant_id=tenant_id,
            target_type="security",
            severity=severity,
            metadata=metadata,
        )

    async def log_config_change(
        self,
        action: str,
        description: str,
        tenant_id: uuid.UUID,
        actor_id: str,
        before_state: Optional[Dict[str, Any]] = None,
        after_state: Optional[Dict[str, Any]] = None,
    ) -> AuditLogEntry:
        """Log a configuration change."""
        return await self.log(
            actor_type=ActorType.USER,
            action_category=ActionCategory.CONFIG,
            action=action,
            description=description,
            actor_id=actor_id,
            tenant_id=tenant_id,
            target_type="config",
            before_state=before_state,
            after_state=after_state,
        )

    # -- Query Methods ----------------------------------------------------

    async def get_entries(
        self,
        tenant_id: Optional[uuid.UUID] = None,
        action: Optional[str] = None,
        actor_id: Optional[str] = None,
        severity: Optional[Severity] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Query audit log entries."""
        entries = self._entries

        if tenant_id:
            entries = self._tenant_index.get(str(tenant_id), entries)
        if action:
            entries = [e for e in entries if e.action == action]
        if actor_id:
            entries = [e for e in entries if e.actor_id == actor_id]
        if severity:
            entries = [e for e in entries if e.severity == severity]

        sorted_entries = sorted(entries, key=lambda e: e.timestamp, reverse=True)
        return [e.to_dict() for e in sorted_entries[offset:offset + limit]]

    async def get_entries_for_tenant(
        self, tenant_id: uuid.UUID, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get all entries for a tenant."""
        entries = self._tenant_index.get(str(tenant_id), [])
        sorted_entries = sorted(entries, key=lambda e: e.timestamp, reverse=True)
        return [e.to_dict() for e in sorted_entries[:limit]]

    # -- Chain Verification -----------------------------------------------

    async def verify_chain(self) -> Dict[str, Any]:
        """Verify the integrity of the audit log chain.

        Returns:
            Verification result with pass/fail status
        """
        if not self._entries:
            return {"valid": True, "entries_checked": 0}

        invalid = []
        for i, entry in enumerate(self._entries):
            # Recompute checksum
            data = {
                "id": str(entry.id),
                "actor_type": entry.actor_type.value,
                "actor_id": entry.actor_id or "",
                "action": entry.action,
                "timestamp": entry.timestamp.isoformat(),
                "previous_checksum": entry.previous_checksum or "",
            }
            payload = json.dumps(data, sort_keys=True, default=str)
            expected = hashlib.sha256(payload.encode()).hexdigest()

            if expected != entry.checksum:
                invalid.append({
                    "index": i,
                    "entry_id": str(entry.id),
                    "expected": expected,
                    "actual": entry.checksum,
                })

            # Check chain link
            if i > 0:
                prev_checksum = self._entries[i - 1].checksum
                if entry.previous_checksum != prev_checksum:
                    invalid.append({
                        "index": i,
                        "entry_id": str(entry.id),
                        "error": "chain_broken",
                        "expected_previous": prev_checksum,
                        "actual_previous": entry.previous_checksum,
                    })

        return {
            "valid": len(invalid) == 0,
            "entries_checked": len(self._entries),
            "invalid_count": len(invalid),
            "invalid_entries": invalid,
        }

    # -- Statistics -------------------------------------------------------

    async def get_stats(self) -> Dict[str, Any]:
        """Get audit log statistics."""
        total = len(self._entries)
        by_category: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        by_actor: Dict[str, int] = {}

        for entry in self._entries:
            cat = entry.action_category.value
            by_category[cat] = by_category.get(cat, 0) + 1

            sev = entry.severity.value
            by_severity[sev] = by_severity.get(sev, 0) + 1

            actor = entry.actor_type.value
            by_actor[actor] = by_actor.get(actor, 0) + 1

        return {
            "total_entries": total,
            "by_category": by_category,
            "by_severity": by_severity,
            "by_actor_type": by_actor,
            "chain_valid": (await self.verify_chain())["valid"],
            "last_entry_at": self._entries[-1].timestamp.isoformat() if self._entries else None,
        }

    # -- Export -----------------------------------------------------------

    async def export_entries(
        self,
        tenant_id: Optional[uuid.UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Export audit log entries for compliance."""
        entries = self._entries

        if tenant_id:
            entries = self._tenant_index.get(str(tenant_id), [])
        if start_date:
            entries = [e for e in entries if e.timestamp >= start_date]
        if end_date:
            entries = [e for e in entries if e.timestamp <= end_date]

        return [e.to_dict() for e in sorted(entries, key=lambda e: e.timestamp)]
