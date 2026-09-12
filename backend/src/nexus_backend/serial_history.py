"""Profile-verified serial telemetry discovery and durable receipt evidence."""

from __future__ import annotations

import re
import sqlite3
from copy import deepcopy
from typing import Any

from nexus_backend.hardware_profile import profile_to_hardware_model
from nexus_backend.store import SQLiteStore, StoreConflict, StoreNotFound
from nexus_backend.tool_adapter import ToolExecutionError
from nexus_backend.validation import validate_contract


class SerialHistory:
    def __init__(
        self,
        store: SQLiteStore,
        device_id: str | None = None,
        *,
        hardware_profile: dict[str, Any] | None = None,
    ) -> None:
        if device_id is not None and (
            not isinstance(device_id, str)
            or len(device_id) > 128
            or not re.fullmatch(r"nexus-[a-z0-9-]+", device_id)
        ):
            raise ValueError("Serial binding must be a canonical nexus- device identifier")
        self.store = store
        self.expected_device_id = device_id
        self.device_id = device_id
        self.hardware_profile = deepcopy(hardware_profile)
        self.status = (
            "waiting_for_registered_device" if device_id and hardware_profile is None
            else "waiting_for_device"
        )

    def persist(self, record: dict) -> dict:
        """Persist a verified device sample without replacing an existing identity.

        A blank binding enables discovery from firmware telemetry, but registration
        is still derived exclusively from the already validated Hardware-as-Code
        profile. Explicit bindings retain the legacy require-pre-registration rule.
        """
        try:
            sample = validate_contract("telemetry", record["sample"])
            if (
                (self.expected_device_id is not None
                 and sample["device_id"] != self.expected_device_id)
                or sample["quality"]["source"] != "device"
            ):
                raise StoreConflict("Serial binding mismatch")
            if self.hardware_profile is not None and self.expected_device_id is None:
                hardware_model = profile_to_hardware_model(
                    self.hardware_profile, sample["device_id"]
                )
                self.store.register_device(
                    hardware_model,
                    self.hardware_profile["name"],
                    "device",
                )
                self.device_id = sample["device_id"]
            provenance = record["provenance"]
            if (not isinstance(provenance, dict)
                    or provenance.keys() != {"transport", "connection_id", "device_sample_id",
                                              "received_at"}
                    or provenance["transport"] != "serial"):
                raise ValueError("Invalid serial provenance")
            self.store.append_telemetry(sample, provenance=deepcopy(provenance))
        except (ValueError, KeyError, TypeError, StoreConflict, StoreNotFound, sqlite3.Error):
            self.status = "serial_history_rejected"
            raise ToolExecutionError("Serial measurement could not be saved for the bound device") from None
        self.status = "receiving"
        return sample

    def ingest(self, record: dict) -> None:
        try:
            self.persist(record)
        except ToolExecutionError:
            # A registration/source mismatch must not stop the USB reader or rewrite
            # existing data. Status is exposed separately for setup troubleshooting.
            pass
