import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path

import pytest

from nexus_backend.contracts import LifecycleEvent
from nexus_backend.store import SQLiteStore, StoreConflict, StoreNotFound

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "nexus-contracts" / "v1" / "fixtures"


@pytest.fixture
def hardware_model() -> dict:
    return json.loads((FIXTURE_ROOT / "hardware-model.example.json").read_text())


@pytest.fixture
def telemetry() -> dict:
    return json.loads((FIXTURE_ROOT / "telemetry.example.json").read_text())


@pytest.fixture
def store(hardware_model: dict, telemetry: dict):
    database = SQLiteStore(":memory:")
    database.register_device(hardware_model, "Motor rig", telemetry["quality"]["source"])
    yield database
    database.close()


def test_restart_preserves_device_configuration_telemetry_session_and_audit(
    tmp_path: Path, hardware_model: dict, telemetry: dict
) -> None:
    path = tmp_path / "nested" / "state" / "nexus.sqlite3"
    initial = SQLiteStore(path)
    device = initial.register_device(hardware_model, "Motor rig", telemetry["quality"]["source"])
    sample, event, inserted = initial.append_telemetry(telemetry)
    session = initial.create_session(device["device_id"], "Motor does not turn")
    initial.close()

    restored = SQLiteStore(path)
    try:
        assert inserted is True
        assert restored.get_device(device["device_id"]) == device
        assert restored.get_hardware_model(device["device_id"]) == hardware_model
        assert restored.latest_telemetry(device["device_id"]) == sample
        assert restored.list_events(device["device_id"]) == [event]
        assert restored.get_session(device["device_id"], session["session_id"]) == session
        assert restored.append_telemetry(telemetry) == (sample, event, False)
    finally:
        restored.close()


def test_registration_retries_are_idempotent_and_conflicts_preserve_configuration(
    store: SQLiteStore, hardware_model: dict, telemetry: dict
) -> None:
    device = store.get_device(hardware_model["device_id"])
    assert store.register_device(
        dict(reversed(list(hardware_model.items()))), "Motor rig", telemetry["quality"]["source"]
    ) == device
    changed = deepcopy(hardware_model)
    changed["safety_limits"]["max_pwm_percent"] = 60
    with pytest.raises(StoreConflict):
        store.register_device(changed, "Motor rig", telemetry["quality"]["source"])
    with pytest.raises(StoreConflict):
        store.register_device(hardware_model, "Different rig", telemetry["quality"]["source"])
    with pytest.raises(StoreConflict):
        store.register_device(hardware_model, "Motor rig", "different-source")
    assert store.list_devices() == [device]
    assert store.get_hardware_model(device["device_id"]) == hardware_model


def test_telemetry_retry_returns_original_audit_event_and_rejects_conflicting_body(
    store: SQLiteStore, telemetry: dict
) -> None:
    sample, event, inserted = store.append_telemetry(telemetry)
    assert inserted is True
    assert LifecycleEvent.model_validate(event).event_type == "telemetry.received"
    assert event["payload"] == {
        "sample_id": telemetry["sample_id"], "source": telemetry["quality"]["source"]
    }
    assert store.append_telemetry(deepcopy(telemetry)) == (sample, event, False)
    changed = deepcopy(telemetry)
    changed["sequence"] += 1
    with pytest.raises(StoreConflict):
        store.append_telemetry(changed)
    assert store.telemetry_history(telemetry["device_id"]) == [sample]
    assert store.list_events(telemetry["device_id"]) == [event]


@pytest.mark.parametrize("field", ["device_id", "hardware_model_id", "source"])
def test_telemetry_cannot_impersonate_device_model_or_registered_source(
    store: SQLiteStore, telemetry: dict, field: str
) -> None:
    changed = deepcopy(telemetry)
    if field == "source":
        changed["quality"]["source"] = "different-source"
    else:
        changed[field] = "nexus-unknown"
    expected = StoreNotFound if field == "device_id" else StoreConflict
    with pytest.raises(expected):
        store.append_telemetry(changed)
    assert store.latest_telemetry(telemetry["device_id"]) is None
    assert store.list_events(telemetry["device_id"]) == []


def test_two_devices_keep_samples_sessions_and_audit_separate(
    store: SQLiteStore, hardware_model: dict, telemetry: dict
) -> None:
    other_model = deepcopy(hardware_model)
    other_model["device_id"] = "nexus-other-device"
    store.register_device(other_model, "Second rig", telemetry["quality"]["source"])
    other_sample = deepcopy(telemetry)
    other_sample["device_id"] = other_model["device_id"]
    first = store.append_telemetry(telemetry)
    second = store.append_telemetry(other_sample)
    session = store.create_session(telemetry["device_id"], "No motion")

    assert store.telemetry_history(telemetry["device_id"]) == [first[0]]
    assert store.telemetry_history(other_sample["device_id"]) == [second[0]]
    assert store.list_events(telemetry["device_id"]) == [first[1]]
    assert store.list_events(other_sample["device_id"]) == [second[1]]
    assert store.list_sessions(telemetry["device_id"]) == [session]
    assert store.list_sessions(other_sample["device_id"]) == []
    with pytest.raises(StoreNotFound):
        store.get_session(other_sample["device_id"], session["session_id"])
    with pytest.raises(StoreNotFound):
        store.get_session("' OR 1=1 --", session["session_id"])
    assert store.session(telemetry["device_id"], session["session_id"]) == session


def test_latest_and_history_follow_receive_order_after_device_counter_resets(
    store: SQLiteStore, telemetry: dict
) -> None:
    samples = []
    for index, sequence in enumerate([200, 201, 0]):
        sample = deepcopy(telemetry)
        sample.update(sample_id=f"sample-{index}", sequence=sequence)
        sample["recorded_at"] = None if index == 2 else sample["recorded_at"]
        samples.append(store.append_telemetry(sample)[0])
    device_id = telemetry["device_id"]
    assert store.latest_telemetry(device_id) == samples[-1]
    assert store.telemetry_history(device_id, limit=2) == samples[-2:]
    assert [event["payload"]["sample_id"] for event in store.list_events(device_id, limit=2)] == [
        "sample-1", "sample-2"
    ]
    # Retrying an older sample does not change receive ordering.
    assert store.append_telemetry(samples[0])[2] is False
    assert store.latest_telemetry(device_id) == samples[-1]


def test_failed_audit_insert_rolls_back_telemetry(
    tmp_path: Path, hardware_model: dict, telemetry: dict
) -> None:
    path = tmp_path / "audit.sqlite3"
    database = SQLiteStore(path)
    try:
        database.register_device(hardware_model, "Motor rig", telemetry["quality"]["source"])
        with sqlite3.connect(path) as connection:
            connection.execute(
                """CREATE TRIGGER reject_audit BEFORE INSERT ON events
                   BEGIN SELECT RAISE(ABORT, 'audit unavailable'); END"""
            )
        with pytest.raises(sqlite3.IntegrityError, match="audit unavailable"):
            database.append_telemetry(telemetry)
        assert database.latest_telemetry(telemetry["device_id"]) is None
        assert database.list_events(telemetry["device_id"]) == []
        with sqlite3.connect(path) as connection:
            connection.execute("DROP TRIGGER reject_audit")
        assert database.append_telemetry(telemetry)[2] is True
    finally:
        database.close()


def test_concurrent_duplicate_requests_create_only_one_sample_and_event(
    store: SQLiteStore, telemetry: dict
) -> None:
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: store.append_telemetry(telemetry), range(16)))
    assert sum(result[2] for result in results) == 1
    assert len({result[1]["event_id"] for result in results}) == 1
    assert len(store.telemetry_history(telemetry["device_id"])) == 1
    assert len(store.list_events(telemetry["device_id"])) == 1


def test_durable_receive_cursors_paginate_new_samples_and_keep_devices_isolated(
    tmp_path: Path, hardware_model: dict, telemetry: dict
) -> None:
    path = tmp_path / "cursors.sqlite3"
    database = SQLiteStore(path)
    device_id = hardware_model["device_id"]
    database.register_device(hardware_model, "Motor rig", telemetry["quality"]["source"])
    assert database.latest_telemetry_record(device_id) is None
    database.append_telemetry(telemetry)
    first_cursor, first = database.latest_telemetry_record(device_id)
    other_model = deepcopy(hardware_model)
    other_model["device_id"] = "nexus-other-device"
    database.register_device(other_model, "Other rig", telemetry["quality"]["source"])
    other_sample = deepcopy(telemetry)
    other_sample["device_id"] = other_model["device_id"]
    database.append_telemetry(other_sample)
    samples = []
    for index in range(3):
        sample = deepcopy(telemetry)
        sample.update(sample_id=f"after-reboot-{index}", sequence=index)
        samples.append(database.append_telemetry(sample)[0])
    database.close()

    restored = SQLiteStore(path)
    try:
        assert first == telemetry
        batch = restored.telemetry_after(device_id, first_cursor, limit=2)
        assert [sample for _, sample in batch] == samples[:2]
        assert first_cursor < batch[0][0] < batch[1][0]
        final = restored.telemetry_after(device_id, batch[-1][0], limit=2)
        assert [sample for _, sample in final] == samples[-1:]
        assert restored.latest_telemetry_record(device_id) == final[-1]
        assert restored.telemetry_after(device_id, final[-1][0]) == []
        # An idempotent retry never creates a new cursor or repeats a streamed record.
        restored.append_telemetry(telemetry)
        assert restored.telemetry_after(device_id, final[-1][0]) == []
    finally:
        restored.close()


@pytest.mark.parametrize("limit", [0, -1, 1001, True, 1.5])
def test_collection_queries_reject_unbounded_or_invalid_limits(
    store: SQLiteStore, telemetry: dict, limit
) -> None:
    for read in (store.telemetry_history, store.list_events, store.list_sessions):
        with pytest.raises(ValueError, match="limit"):
            read(telemetry["device_id"], limit=limit)


@pytest.mark.parametrize("cursor", [-1, True, 1.5, "1"])
def test_stream_cursor_must_be_a_nonnegative_integer(
    store: SQLiteStore, telemetry: dict, cursor
) -> None:
    with pytest.raises(ValueError, match="after_cursor"):
        store.telemetry_after(telemetry["device_id"], cursor)
