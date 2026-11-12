from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class LicenseTier(StrEnum):
    COMMUNITY_FREE = "COMMUNITY_FREE"  # Single developer on laptop with local SQLite (Free forever)
    TEAM_TRIAL = "TEAM_TRIAL"          # 14-day free trial for teams up to 10 users & Cloud DB
    TEAM_PRO = "TEAM_PRO"              # Paid commercial license for teams & enterprise
    EXPIRED_TRIAL = "EXPIRED_TRIAL"    # Trial elapsed without renewal (prompts upgrade, falls back to local)


class UsageProfile(BaseModel):
    is_cloud_db: bool = False
    database_type: str = "sqlite"  # "sqlite" | "postgresql"
    is_ci: bool = False
    contributor_count_30d: int = 1
    contributors: list[str] = Field(default_factory=list)
    machine_fingerprint: str = ""
    is_team: bool = False


class LicenseToken(BaseModel):
    team_id: str
    team_name: str = "Team"
    tier: LicenseTier = LicenseTier.TEAM_PRO
    seats_licensed: int = 10
    issued_at: int
    expires_at: int  # Unix timestamp
    allowed_domains: list[str] = Field(default_factory=list)
    features: list[str] = Field(default_factory=lambda: ["team_collaboration", "cloud_db", "pr_gates", "token_optimizer"])


class LicenseStatus(BaseModel):
    tier: LicenseTier
    is_valid: bool
    is_free_single_developer: bool
    is_cloud_db: bool
    active_seats: int
    max_seats: int
    days_remaining: int | None = None
    message: str = ""
    checkout_url: str = "https://codegraph.dev/pricing"
    raw_token: dict[str, Any] | None = None
