from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class LeakageError(Exception):
    """Raised when a forbidden leakage column or target-derived attribute is passed as an input feature."""

    pass


# Strict Forbidden Denylist (Must NEVER be used as input features for Genuineness Model)
FORBIDDEN_LEAKAGE_COLUMNS: set[str] = {
    "lead score",
    "status",
    "ground truth genuine",
    "contactability",
    "service opportunity",
    "prediction",
    "confidence",
    "decision",
}

# Explicit Allowed Input Feature Columns
ALLOWED_FEATURE_COLUMNS: set[str] = {
    "industry",
    "location",
    "state",
    "google rating",
    "review count",
    "has website",
    "website status",
    "ssl valid",
    "has email",
    "email valid",
    "email mx",
    "has phone",
    "phone valid",
}


class LeakageGuard:
    """Enforces strict separation between input features and target-derived leakage columns."""

    @staticmethod
    def check_for_leakage(column_names: list[str]) -> list[str]:
        """Validates input feature columns against forbidden leakage denylist."""
        detected_leakage: list[str] = []
        for col in column_names:
            col_clean = str(col).strip().lower()
            if col_clean in FORBIDDEN_LEAKAGE_COLUMNS:
                detected_leakage.append(col)

        if detected_leakage:
            raise LeakageError(
                f"Target leakage detected! Forbidden columns passed as input features: {detected_leakage}"
            )
        return [col for col in column_names if col.strip().lower() in ALLOWED_FEATURE_COLUMNS]

    @staticmethod
    def get_feature_allowlist() -> list[str]:
        return sorted(list(ALLOWED_FEATURE_COLUMNS))

    @staticmethod
    def get_feature_denylist() -> list[str]:
        return sorted(list(FORBIDDEN_LEAKAGE_COLUMNS))
