"""Explicit device binding for serial telemetry and its durable receipt evidence."""

from __future__ import annotations

import re
import sqlite3
from copy import deepcopy

from nexus_backend.store import SQLiteStore, StoreConflict, StoreNotFound
from nexus_backend.tool_adapter import ToolExecutionError
from nexus_backend.validation import validate_contract


class SerialHistory:
    def __init__(self, store: SQLiteStore, device_id: str) -> None:
        if (not isinstance(device_id, str) or len(device_id) > 128
                or not re.fullmatch(r"nexus-[a-z0-9-]+", device_id)):
            raise ValueError("Serial binding must be a canonical nexus- device identifier")
        self.store = store
        self.device_id = device_id
        self.status = "waiting_for_registered_device"

    def persist(self, record: dict) -> dict:
        """Never auto-register, rename a device, change its source, or replace history."""
        try:
            sample = validate_contract("telemetry", record["sample"])
            if sample["device_id"] != self.device_id or sample["quality"]["source"] != "device":
                raise StoreConflict("Serial binding mismatch")
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
