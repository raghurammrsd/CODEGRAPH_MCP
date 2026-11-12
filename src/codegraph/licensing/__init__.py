from __future__ import annotations

from codegraph.licensing.engine import (
    MAX_TRIAL_SEATS,
    TRIAL_DURATION_DAYS,
    TrialManager,
    check_license,
    detect_usage_profile,
    generate_license_key,
    get_machine_fingerprint,
    save_license_key,
    verify_license_key,
)
from codegraph.licensing.models import (
    LicenseStatus,
    LicenseTier,
    LicenseToken,
    UsageProfile,
)

__all__ = [
    "MAX_TRIAL_SEATS",
    "TRIAL_DURATION_DAYS",
    "LicenseStatus",
    "LicenseTier",
    "LicenseToken",
    "TrialManager",
    "UsageProfile",
    "check_license",
    "detect_usage_profile",
    "generate_license_key",
    "get_machine_fingerprint",
    "save_license_key",
    "verify_license_key",
]
