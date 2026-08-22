from __future__ import annotations

import logging
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class RolloutMode(str, Enum):
    CONTROLLED_TEST = "CONTROLLED_TEST"
    LIMITED_PRODUCTION = "LIMITED_PRODUCTION"
    SCHEDULED_PRODUCTION = "SCHEDULED_PRODUCTION"
    CONTINUOUS_PRODUCTION = "CONTINUOUS_PRODUCTION"


class RolloutTransitionError(Exception):
    """Raised when an invalid rollout mode transition is attempted without approval."""

    pass


class EmergencyStopError(Exception):
    """Raised when a production component is triggered by a safety kill-switch."""

    pass


class ProductionKillSwitch:
    """Provides instant emergency stopping for batches, inference, or ingestion sources without data loss."""

    def __init__(self) -> None:
        self.inference_enabled: bool = True
        self.ingestion_enabled: bool = True
        self.disabled_sources: set[str] = set()
        self.stopped_batches: set[str] = set()
        self.current_rollout_mode: RolloutMode = RolloutMode.CONTROLLED_TEST

    def disable_inference(self, reason: str = "Emergency inference halt") -> None:
        self.inference_enabled = False
        logger.warning(f"[ProductionKillSwitch] Model inference DISABLED. Reason: {reason}")

    def enable_inference(self) -> None:
        self.inference_enabled = True
        logger.info("[ProductionKillSwitch] Model inference ENABLED.")

    def disable_source(self, source_name: str, reason: str = "Source failure") -> None:
        self.disabled_sources.add(source_name)
        logger.warning(
            f"[ProductionKillSwitch] Ingestion source '{source_name}' DISABLED. Reason: {reason}"
        )

    def enable_source(self, source_name: str) -> None:
        self.disabled_sources.discard(source_name)
        logger.info(f"[ProductionKillSwitch] Ingestion source '{source_name}' ENABLED.")

    def stop_batch(self, batch_id: str, reason: str = "Emergency batch stop") -> None:
        self.stopped_batches.add(batch_id)
        logger.warning(f"[ProductionKillSwitch] Batch '{batch_id}' STOPPED. Reason: {reason}")

    def validate_inference_allowed(self) -> bool:
        if not self.inference_enabled:
            raise EmergencyStopError("Inference is currently DISABLED by safety kill switch.")
        return True

    def validate_source_allowed(self, source_name: str) -> bool:
        if not self.ingestion_enabled or source_name in self.disabled_sources:
            raise EmergencyStopError(
                f"Ingestion source '{source_name}' is DISABLED by safety kill switch."
            )
        return True

    def validate_batch_allowed(self, batch_id: str) -> bool:
        if batch_id in self.stopped_batches:
            raise EmergencyStopError(f"Batch '{batch_id}' has been STOPPED by safety kill switch.")
        return True

    def transition_rollout_mode(
        self, target_mode: RolloutMode, human_approved: bool = False
    ) -> RolloutMode:
        if not human_approved:
            raise RolloutTransitionError(
                f"Transition to '{target_mode.value}' requires explicit human approval."
            )

        valid_transitions = {
            RolloutMode.CONTROLLED_TEST: [RolloutMode.LIMITED_PRODUCTION],
            RolloutMode.LIMITED_PRODUCTION: [RolloutMode.SCHEDULED_PRODUCTION],
            RolloutMode.SCHEDULED_PRODUCTION: [RolloutMode.CONTINUOUS_PRODUCTION],
            RolloutMode.CONTINUOUS_PRODUCTION: [],
        }

        allowed = valid_transitions.get(self.current_rollout_mode, [])
        if target_mode not in allowed:
            raise RolloutTransitionError(
                f"Invalid rollout transition from '{self.current_rollout_mode.value}' to '{target_mode.value}'."
            )

        self.current_rollout_mode = target_mode
        logger.info(f"[ProductionKillSwitch] Advanced rollout mode to '{target_mode.value}'.")
        return target_mode

    def get_safety_status(self) -> dict[str, Any]:
        return {
            "current_rollout_mode": self.current_rollout_mode.value,
            "inference_enabled": self.inference_enabled,
            "ingestion_enabled": self.ingestion_enabled,
            "disabled_sources_count": len(self.disabled_sources),
            "stopped_batches_count": len(self.stopped_batches),
        }
