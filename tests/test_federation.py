"""Tests for cross-repository microservice federation."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from codegraph.federation import (
    discover_federated_repos,
    federate_workspace,
)
from codegraph.indexing.indexer import Indexer


@pytest.fixture
def multi_repo_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "microservices_workspace"
    workspace.mkdir()

    # Repo 1: users-service
    users_repo = workspace / "users-service"
    users_repo.mkdir()
    (users_repo / ".git").mkdir()
    src1 = users_repo / "src"
    src1.mkdir()
    (src1 / "api.py").write_text(
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n\n"
        "@app.get('/api/v1/users')\n"
        "def list_users():\n"
        "    return [{'id': 1, 'name': 'Alice'}]\n"
    )
    idx1 = Indexer(users_repo)
    idx1.index()

    # Repo 2: frontend-service
    fe_repo = workspace / "frontend-service"
    fe_repo.mkdir()
    (fe_repo / ".git").mkdir()
    src2 = fe_repo / "src"
    src2.mkdir()
    (src2 / "client.py").write_text(
        "import requests\n\n"
        "def fetch_remote_users():\n"
        "    return requests.get('http://users-service/api/v1/users').json()\n"
    )
    idx2 = Indexer(fe_repo)
    idx2.index()

    return workspace


def test_discover_federated_repos(multi_repo_workspace: Path) -> None:
    repos = discover_federated_repos(multi_repo_workspace)
    repo_names = [r.name for r in repos]
    assert "users-service" in repo_names
    assert "frontend-service" in repo_names


def test_discover_with_workspace_manifest(multi_repo_workspace: Path) -> None:
    manifest = multi_repo_workspace / "codegraph.workspace.json"
    manifest.write_text(
        json.dumps({
            "repositories": ["users-service", "frontend-service"]
        })
    )
    repos = discover_federated_repos(multi_repo_workspace)
    assert len(repos) == 2


def test_federate_workspace_routes(multi_repo_workspace: Path) -> None:
    report = federate_workspace(multi_repo_workspace)
    assert len(report.repos) == 2
    assert report.total_repos == 2

    # Check cross-repo link
    assert len(report.cross_repo_links) >= 1
    link = report.cross_repo_links[0]
    assert link.source_repo == "frontend-service"
    assert link.target_repo == "users-service"
    assert link.route_path == "/api/v1/users"
    assert link.target_handler == "list_users"
    assert link.confidence == "STATIC_VERIFIED"
