"""Data models for Multi-Agent Shared Working State and Lease Management."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class AgentSession:
    """An active AI coding agent registered in the repository workspace."""

    agent_id: str
    name: str
    task_description: str
    registered_at: float
    last_heartbeat: float
    status: str = "ACTIVE"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FileLease:
    """A lease on a file or module held by an AI agent."""

    file_path: str
    agent_id: str
    lease_type: str  # EXCLUSIVE_WRITE | SHARED_READ
    granted_at: float
    expires_at: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SemanticConflict:
    """A detected or predicted conflict between multiple concurrent agents."""

    file_path: str
    conflicting_agents: tuple[str, ...]
    conflict_type: str  # WRITE_WRITE | DOWNSTREAM_CONTRACT_BREAK
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "conflicting_agents": list(self.conflicting_agents),
            "conflict_type": self.conflict_type,
            "reason": self.reason,
        }


@dataclass
class MultiAgentStatusReport:
    """Consolidated workspace report of active agents, leases, and conflicts."""

    workspace: str
    total_agents: int
    active_leases_count: int
    conflicts_count: int
    agents: list[AgentSession] = field(default_factory=list)
    leases: list[FileLease] = field(default_factory=list)
    conflicts: list[SemanticConflict] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "workspace": self.workspace,
            "total_agents": self.total_agents,
            "active_leases_count": self.active_leases_count,
            "conflicts_count": self.conflicts_count,
            "agents": [a.as_dict() for a in self.agents],
            "leases": [lease.as_dict() for lease in self.leases],
            "conflicts": [c.as_dict() for c in self.conflicts],
        }
