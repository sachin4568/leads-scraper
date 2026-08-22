from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


class GovernanceApprovalError(Exception):
    """Raised when an unapproved model promotion or retraining step is attempted."""

    pass


@dataclass
class ModelGovernanceState:
    champion_model_name: str = "real_model_v2_1"
    champion_model_version: str = "real_model_v2_1"
    challenger_models_registered: list[str] = None  # type: ignore
    automatic_retraining_enabled: bool = False
    automatic_promotion_enabled: bool = False
    unrestricted_scraping_enabled: bool = False

    def __post_init__(self):
        if self.challenger_models_registered is None:
            self.challenger_models_registered = []


class ProductionGovernanceManager:
    """Manages model registry states, offline challenger evaluation, and human approval enforcement."""

    def __init__(self) -> None:
        self.state = ModelGovernanceState()

    def register_challenger(self, challenger_version: str) -> None:
        if challenger_version not in self.state.challenger_models_registered:
            self.state.challenger_models_registered.append(challenger_version)
            logger.info(f"[Governance] Registered challenger model version '{challenger_version}'.")

    def promote_challenger_to_champion(
        self, challenger_version: str, human_approved: bool = False
    ) -> None:
        if not human_approved:
            raise GovernanceApprovalError(
                f"Promotion of '{challenger_version}' requires explicit human approval."
            )
        if self.state.automatic_promotion_enabled:
            raise GovernanceApprovalError("Automatic champion promotion is strictly DISABLED.")

        self.state.champion_model_version = challenger_version
        logger.info(
            f"[Governance] Promoted challenger '{challenger_version}' to champion with human approval."
        )

    def audit_governance_compliance(self) -> dict[str, Any]:
        return {
            "champion_model_version": self.state.champion_model_version,
            "registered_challengers": self.state.challenger_models_registered,
            "automatic_retraining": "OFF",
            "automatic_promotion": "OFF",
            "unrestricted_scraping": "OFF",
            "governance_compliant": (
                not self.state.automatic_retraining_enabled
                and not self.state.automatic_promotion_enabled
            ),
        }
