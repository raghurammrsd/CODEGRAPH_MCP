from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Any

from codegraph.licensing.models import (
    LicenseStatus,
    LicenseTier,
    LicenseToken,
    UsageProfile,
)

DEFAULT_SIGNING_SALT = "codegraph-enterprise-v3-license-salt-98124"
STRIPE_CHECKOUT_URL = "https://codegraph.dev/pricing"
TRIAL_DURATION_DAYS = 14
MAX_TRIAL_SEATS = 10


def get_machine_fingerprint() -> str:
    """Derive deterministic, privacy-preserving machine/seat hash."""
    user = os.getenv("USER") or os.getenv("USERNAME") or "user"
    host = platform.node() or "localhost"
    system_str = f"{user}@{host}::{platform.system()}"
    return hashlib.sha256(system_str.encode("utf-8")).hexdigest()[:16]


def detect_usage_profile(
    repo_path: Path | None = None,
    database_url: str | None = None,
    is_ci: bool | None = None,
) -> UsageProfile:
    """Determine whether current execution is single-developer local, team collaboration, or cloud DB."""
    db_url = database_url or os.getenv("CODEGRAPH_DATABASE_URL") or ""
    is_cloud_db = db_url.startswith("postgresql://") or db_url.startswith("postgres://")
    db_type = "postgresql" if is_cloud_db else "sqlite"

    if is_ci is None:
        ci_env_vars = ["CI", "GITHUB_ACTIONS", "GITLAB_CI", "CIRCLECI", "TRAVIS", "JENKINS_URL", "BUILDKITE"]
        is_ci_detected = any(os.getenv(var) for var in ci_env_vars)
    else:
        is_ci_detected = is_ci

    contributors: set[str] = set()
    repo = repo_path or Path.cwd()
    if (repo / ".git").exists():
        try:
            res = subprocess.run(
                ["git", "log", "--since=30 days ago", "--format=%ae"],
                cwd=repo,
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    email = line.strip().lower()
                    if email:
                        contributors.add(email)
        except Exception:
            pass

    # If git query found no committers, record current machine user
    if not contributors:
        contributors.add(f"{os.getenv('USER', 'developer')}@local")

    is_team = (len(contributors) > 1) or is_ci_detected

    return UsageProfile(
        is_cloud_db=is_cloud_db,
        database_type=db_type,
        is_ci=is_ci_detected,
        contributor_count_30d=len(contributors),
        contributors=sorted(list(contributors)),
        machine_fingerprint=get_machine_fingerprint(),
        is_team=is_team,
    )


class TrialManager:
    """Manages the 14-day free trial for teams (up to 10 users)."""

    def __init__(self, storage_dir: Path | None = None) -> None:
        self.storage_dir = storage_dir or (Path.home() / ".codegraph")
        self.trial_file = self.storage_dir / "trial.json"

    def _ensure_dir(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def load_trial_state(self) -> dict[str, Any]:
        if not self.trial_file.exists():
            return {}
        try:
            data = json.loads(self.trial_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def get_or_start_trial(self, team_name: str = "Local Team") -> dict[str, Any]:
        self._ensure_dir()
        state = self.load_trial_state()
        now = int(time.time())

        if not state or "started_at" not in state:
            state = {
                "team_name": team_name,
                "started_at": now,
                "expires_at": now + (TRIAL_DURATION_DAYS * 86400),
                "active_seats": [get_machine_fingerprint()],
            }
            self.trial_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
        else:
            # Register current machine seat
            fingerprint = get_machine_fingerprint()
            seats = set(state.get("active_seats", []))
            seats.add(fingerprint)
            state["active_seats"] = list(seats)
            self.trial_file.write_text(json.dumps(state, indent=2), encoding="utf-8")

        return state


def sign_payload(payload_bytes: bytes, secret: str = DEFAULT_SIGNING_SALT) -> str:
    return hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()


def generate_license_key(
    team_id: str,
    team_name: str = "Enterprise Team",
    seats: int = 10,
    valid_days: int = 365,
    tier: LicenseTier = LicenseTier.TEAM_PRO,
    secret: str = DEFAULT_SIGNING_SALT,
) -> str:
    """Mint a cryptographically signed license token for Stripe webhook dispatch."""
    now = int(time.time())
    payload = {
        "team_id": team_id,
        "team_name": team_name,
        "tier": tier.value,
        "seats_licensed": seats,
        "issued_at": now,
        "expires_at": now + (valid_days * 86400),
        "features": ["team_collaboration", "cloud_db", "pr_gates", "token_optimizer"],
    }
    raw = json.dumps(payload, sort_keys=True).encode("utf-8")
    sig = sign_payload(raw, secret)
    token = f"{base64.urlsafe_b64encode(raw).decode('utf-8')}.{sig}"
    return token


def verify_license_key(token_str: str, secret: str = DEFAULT_SIGNING_SALT) -> LicenseToken | None:
    """Verify cryptographic authenticity and temporal validity of a license token."""
    try:
        parts = token_str.strip().split(".")
        if len(parts) != 2:
            return None
        raw_b64, sig = parts[0], parts[1]
        raw_bytes = base64.urlsafe_b64decode(raw_b64.encode("utf-8"))
        expected_sig = sign_payload(raw_bytes, secret)
        if not hmac.compare_digest(sig, expected_sig):
            return None

        data = json.loads(raw_bytes.decode("utf-8"))
        token = LicenseToken(**data)
        if time.time() > token.expires_at:
            return None
        return token
    except Exception:
        return None


def get_stored_license_key(storage_dir: Path | None = None) -> str | None:
    env_key = os.getenv("CODEGRAPH_LICENSE_KEY")
    if env_key:
        return env_key.strip()
    target_dir = storage_dir or (Path.home() / ".codegraph")
    key_file = target_dir / "license.key"
    if key_file.exists():
        try:
            return key_file.read_text(encoding="utf-8").strip()
        except Exception:
            return None
    return None


def save_license_key(key_str: str, storage_dir: Path | None = None) -> None:
    target_dir = storage_dir or (Path.home() / ".codegraph")
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "license.key").write_text(key_str.strip(), encoding="utf-8")


def check_license(
    repo_path: Path | None = None,
    database_url: str | None = None,
    license_key: str | None = None,
    storage_dir: Path | None = None,
    is_ci: bool | None = None,
) -> LicenseStatus:
    """Core license gate evaluating usage profile against commercial tiers."""
    profile = detect_usage_profile(repo_path, database_url, is_ci=is_ci)

    # 1. Single developer on local machine with SQLite is 100% Free Forever
    if not profile.is_cloud_db and not profile.is_team:
        return LicenseStatus(
            tier=LicenseTier.COMMUNITY_FREE,
            is_valid=True,
            is_free_single_developer=True,
            is_cloud_db=False,
            active_seats=1,
            max_seats=1,
            message="Single developer on local SQLite — 100% Free Forever",
        )

    # 2. Check for active paid commercial license
    key = license_key or get_stored_license_key(storage_dir)
    if key:
        token = verify_license_key(key)
        if token:
            days_left = max(0, int((token.expires_at - time.time()) / 86400))
            active_seats = max(1, profile.contributor_count_30d)
            if active_seats <= token.seats_licensed:
                return LicenseStatus(
                    tier=token.tier,
                    is_valid=True,
                    is_free_single_developer=False,
                    is_cloud_db=profile.is_cloud_db,
                    active_seats=active_seats,
                    max_seats=token.seats_licensed,
                    days_remaining=days_left,
                    message=f"Team Pro License Active for '{token.team_name}' ({active_seats}/{token.seats_licensed} seats)",
                    raw_token=token.model_dump(),
                )
            else:
                return LicenseStatus(
                    tier=token.tier,
                    is_valid=False,
                    is_free_single_developer=False,
                    is_cloud_db=profile.is_cloud_db,
                    active_seats=active_seats,
                    max_seats=token.seats_licensed,
                    days_remaining=days_left,
                    message=f"Team seat limit exceeded ({active_seats}/{token.seats_licensed} active contributors). Upgrade your seat count.",
                    checkout_url=STRIPE_CHECKOUT_URL,
                )

    # 3. Team or Cloud DB usage without a paid key -> 14-day Free Trial (10 seats)
    tm = TrialManager(storage_dir)
    trial_state = tm.get_or_start_trial()
    now = time.time()
    expires_at = trial_state.get("expires_at", now)
    days_left = max(0, int((expires_at - now) / 86400))
    active_seats = max(len(trial_state.get("active_seats", [])), profile.contributor_count_30d)

    if now < expires_at:
        if active_seats <= MAX_TRIAL_SEATS:
            reason = "Cloud DB" if profile.is_cloud_db else "Team Collaboration"
            return LicenseStatus(
                tier=LicenseTier.TEAM_TRIAL,
                is_valid=True,
                is_free_single_developer=False,
                is_cloud_db=profile.is_cloud_db,
                active_seats=active_seats,
                max_seats=MAX_TRIAL_SEATS,
                days_remaining=days_left,
                message=f"14-Day Free Team Trial Active ({days_left} days remaining, {active_seats}/{MAX_TRIAL_SEATS} seats used) for {reason}",
                checkout_url=STRIPE_CHECKOUT_URL,
            )
        else:
            return LicenseStatus(
                tier=LicenseTier.TEAM_TRIAL,
                is_valid=False,
                is_free_single_developer=False,
                is_cloud_db=profile.is_cloud_db,
                active_seats=active_seats,
                max_seats=MAX_TRIAL_SEATS,
                days_remaining=days_left,
                message=f"Trial limit reached ({active_seats}/{MAX_TRIAL_SEATS} seats). Upgrade to Team Pro to add more seats.",
                checkout_url=STRIPE_CHECKOUT_URL,
            )

    # 4. Trial expired
    reason = "Cloud Database" if profile.is_cloud_db else f"Team Collaboration ({active_seats} contributors)"
    return LicenseStatus(
        tier=LicenseTier.EXPIRED_TRIAL,
        is_valid=False,
        is_free_single_developer=False,
        is_cloud_db=profile.is_cloud_db,
        active_seats=active_seats,
        max_seats=MAX_TRIAL_SEATS,
        days_remaining=0,
        message=f"14-Day Free Team Trial has expired for {reason}. Upgrade to Team Pro at {STRIPE_CHECKOUT_URL} or switch to local SQLite for single-developer free use.",
        checkout_url=STRIPE_CHECKOUT_URL,
    )
