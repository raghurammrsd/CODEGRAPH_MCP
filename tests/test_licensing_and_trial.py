from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from codegraph.cli import app
from codegraph.licensing import (
    LicenseTier,
    TrialManager,
    check_license,
    generate_license_key,
    get_machine_fingerprint,
    verify_license_key,
)
from codegraph.licensing.telemetry import fetch_pypi_download_stats


def test_machine_fingerprint_deterministic() -> None:
    fp1 = get_machine_fingerprint()
    fp2 = get_machine_fingerprint()
    assert fp1 == fp2
    assert len(fp1) == 16


def test_single_developer_on_local_sqlite_free_forever(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A developer working on their laptop with local SQLite is 100% free."""
    for var in ["CI", "GITHUB_ACTIONS", "GITLAB_CI", "CIRCLECI", "TRAVIS", "JENKINS_URL", "BUILDKITE"]:
        monkeypatch.delenv(var, raising=False)
    status = check_license(repo_path=tmp_path, database_url=None, storage_dir=tmp_path / ".cg", is_ci=False)
    assert status.tier == LicenseTier.COMMUNITY_FREE
    assert status.is_valid is True
    assert status.is_free_single_developer is True
    assert status.is_cloud_db is False
    assert status.active_seats == 1
    assert "Free Forever" in status.message


def test_ci_environment_detected_as_team(tmp_path: Path) -> None:
    """In CI environments, CodeGraph detects team usage and activates trial/team tier."""
    status = check_license(repo_path=tmp_path, database_url=None, storage_dir=tmp_path / ".cg_ci", is_ci=True)
    assert status.tier in {LicenseTier.TEAM_TRIAL, LicenseTier.TEAM_PRO}
    assert status.is_free_single_developer is False


def test_cloud_db_initiates_14_day_free_trial(tmp_path: Path) -> None:
    """Connecting to a PostgreSQL cloud DB triggers the 14-day team trial."""
    storage = tmp_path / ".cg_storage"
    cloud_db = "postgresql://user:secret@db.cloud.provider/codegraph"

    status = check_license(repo_path=tmp_path, database_url=cloud_db, storage_dir=storage)
    assert status.tier == LicenseTier.TEAM_TRIAL
    assert status.is_valid is True
    assert status.is_cloud_db is True
    assert status.max_seats == 10
    assert status.days_remaining is not None and status.days_remaining >= 13
    assert "14-Day Free Team Trial" in status.message


def test_trial_manager_seat_tracking_and_expiry(tmp_path: Path) -> None:
    """Test TrialManager state persistence, seat accumulation, and expiration."""
    storage = tmp_path / ".cg_trial"
    tm = TrialManager(storage_dir=storage)

    # 1. Start trial
    state = tm.get_or_start_trial("Engineering Team")
    assert state["team_name"] == "Engineering Team"
    assert len(state["active_seats"]) >= 1

    # 2. Simulate expired trial by modifying trial.json timestamp
    state["expires_at"] = int(time.time()) - 3600
    (storage / "trial.json").write_text(json.dumps(state), encoding="utf-8")

    cloud_db = "postgresql://user:secret@db.cloud.provider/codegraph"
    status = check_license(repo_path=tmp_path, database_url=cloud_db, storage_dir=storage)
    assert status.tier == LicenseTier.EXPIRED_TRIAL
    assert status.is_valid is False
    assert status.days_remaining == 0
    assert "expired" in status.message.lower()


def test_cryptographic_license_minting_and_anti_tamper(tmp_path: Path) -> None:
    """Mint authentic tokens and ensure tampered or expired tokens fail."""
    # 1. Valid token
    token_str = generate_license_key(
        team_id="team_acme_corp",
        team_name="Acme Corp",
        seats=15,
        valid_days=30,
        tier=LicenseTier.TEAM_PRO,
    )
    token = verify_license_key(token_str)
    assert token is not None
    assert token.team_name == "Acme Corp"
    assert token.seats_licensed == 15
    assert token.tier == LicenseTier.TEAM_PRO

    # 2. Tampered payload
    parts = token_str.split(".")
    tampered = "eyJ0ZWFtX2lkIjogImhhY2tlZCJ9." + parts[1]
    assert verify_license_key(tampered) is None

    # 3. Tampered signature
    assert verify_license_key(token_str[:-4] + "dead") is None

    # 4. Expired token
    expired_token_str = generate_license_key(
        team_id="team_old",
        team_name="Old Team",
        seats=5,
        valid_days=-1,  # Expired yesterday
    )
    assert verify_license_key(expired_token_str) is None


def test_cli_auth_status_and_trial_commands(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test CLI commands: `codegraph auth status` and `codegraph auth trial`."""
    for var in ["CI", "GITHUB_ACTIONS", "GITLAB_CI", "CIRCLECI", "TRAVIS", "JENKINS_URL", "BUILDKITE"]:
        monkeypatch.delenv(var, raising=False)
    runner = CliRunner()

    # 1. Auth status
    res_status = runner.invoke(app, ["auth", "status", "--repo", str(tmp_path), "--json"])
    assert res_status.exit_code == 0
    parsed_status = json.loads(res_status.stdout)
    assert parsed_status["tier"] == "COMMUNITY_FREE"
    assert parsed_status["is_valid"] is True

    # 2. Auth trial
    res_trial = runner.invoke(app, ["auth", "trial", "--team", "TestTeam", "--json"])
    assert res_trial.exit_code == 0
    parsed_trial = json.loads(res_trial.stdout)
    assert parsed_trial["team_name"] == "TestTeam"
    assert parsed_trial["max_seats"] == 10

    # 3. Auth buy
    res_buy = runner.invoke(app, ["auth", "buy"])
    assert res_buy.exit_code == 0
    assert "https://codegraph.dev/pricing" in res_buy.stdout


def test_cli_auth_activate_valid_and_invalid_keys(tmp_path: Path) -> None:
    """Test activating valid and invalid keys via CLI."""
    runner = CliRunner()

    # 1. Invalid key fails
    res_invalid = runner.invoke(app, ["auth", "activate", "--key", "invalid.key.string"])
    assert res_invalid.exit_code != 0

    # 2. Valid key succeeds
    valid_key = generate_license_key("team_test", "Active Team", seats=20)
    res_valid = runner.invoke(app, ["auth", "activate", "--key", valid_key, "--json"])
    assert res_valid.exit_code == 0
    parsed_valid = json.loads(res_valid.stdout)
    assert parsed_valid["status"] == "ok"
    assert parsed_valid["seats_licensed"] == 20


def test_pypi_download_telemetry_fetch() -> None:
    """Verify official PyPI download telemetry fetching."""
    stats = fetch_pypi_download_stats("codegraph-engine")
    assert stats["package"] == "codegraph-engine"
    # Should either successfully query API or handle timeout gracefully
    assert stats["status"] in {"ok", "error"}

    # Also test CLI `codegraph metrics`
    runner = CliRunner()
    res_metrics = runner.invoke(app, ["metrics", "--json"])
    assert res_metrics.exit_code == 0
    parsed_metrics = json.loads(res_metrics.stdout)
    assert parsed_metrics["package"] == "codegraph-engine"
