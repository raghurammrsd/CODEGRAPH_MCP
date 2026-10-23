"""Tests for Multi-Agent Coordination and Semantic Lease Management."""
from __future__ import annotations

from pathlib import Path

from codegraph.multi_agent.coordinator import MultiAgentCoordinator


def test_agent_registration_and_heartbeat(tmp_path: Path) -> None:
    coord = MultiAgentCoordinator(tmp_path)
    sess = coord.register_session("agent-1", "BugFixer", "Fix auth token expiration")
    assert sess.agent_id == "agent-1"
    assert sess.name == "BugFixer"
    assert sess.status == "ACTIVE"

    assert coord.heartbeat("agent-1")
    report = coord.get_status_report()
    assert report.total_agents == 1
    assert report.agents[0].agent_id == "agent-1"


def test_file_lease_claim_and_conflict(tmp_path: Path) -> None:
    coord = MultiAgentCoordinator(tmp_path)
    coord.register_session("agent-1", "BackendWorker", "Refactor models")
    coord.register_session("agent-2", "FrontendWorker", "Update forms")

    # Agent 1 claims exclusive write lease
    ok, msg = coord.claim_lease("agent-1", "src/models.py", lease_type="EXCLUSIVE_WRITE", ttl_seconds=60)
    assert ok

    # Agent 2 attempts to claim write lease on same file -> conflict!
    ok2, msg2 = coord.claim_lease("agent-2", "src/models.py", lease_type="EXCLUSIVE_WRITE", ttl_seconds=60)
    assert not ok2
    assert "Conflict" in msg2

    # Agent 2 claims non-conflicting file
    ok3, msg3 = coord.claim_lease("agent-2", "src/views.py", lease_type="EXCLUSIVE_WRITE", ttl_seconds=60)
    assert ok3

    report = coord.get_status_report()
    assert report.active_leases_count == 2

    # Agent 1 releases lease
    released = coord.release_lease("agent-1", "src/models.py")
    assert released == 1

    # Now Agent 2 can claim
    ok4, msg4 = coord.claim_lease("agent-2", "src/models.py", lease_type="EXCLUSIVE_WRITE", ttl_seconds=60)
    assert ok4
