"""Exercise simulator identity, bounded publishing and failure behavior."""

import json
from datetime import UTC, datetime

import httpx
import pytest

from nexus_backend import mock_device
from nexus_backend.contracts import TelemetrySample


def test_publishes_bounded_identified_simulator_samples(monkeypatch):
    model, template = mock_device.load_fixtures()
    model["device_id"] = "nexus-test-simulator"
    requests = []
    sleeps = []

    def receive(request):
        requests.append((request.url.path, json.loads(request.content)))
        return httpx.Response(201, json={"ok": True})

    monkeypatch.setattr(mock_device.time, "sleep", sleeps.append)
    before = datetime.now(UTC)
    with httpx.Client(base_url="http://testserver", transport=httpx.MockTransport(receive)) as client:
        assert mock_device.run_simulator(client, model, template, count=3, interval=0.5) == 3
    after = datetime.now(UTC)

    registration = requests[0][1]
    assert registration["hardware_model"]["device_id"] == "nexus-test-simulator"
    assert registration["source"] == "simulator"
    assert sleeps == [0.5, 0.5]
    samples = [body for _, body in requests[1:]]
    assert [sample["sequence"] for sample in samples] == [0, 1, 2]
    assert len({sample["sample_id"] for sample in samples}) == 3
    for endpoint, sample in requests[1:]:
        assert endpoint == "/api/devices/nexus-test-simulator/telemetry"
        assert sample["device_id"] == "nexus-test-simulator"
        assert sample["hardware_model_id"] == model["hardware_model_id"]
        assert sample["quality"]["source"] == "simulator"
        assert sample["measurements"]["motor_rpm"] is None
        timestamp = datetime.fromisoformat(sample["recorded_at"])
        assert before <= timestamp <= after
        TelemetrySample.model_validate(sample)
    assert template["quality"]["source"] == "device"
    assert samples[0]["measurements"]["bus_voltage_v"] != samples[1]["measurements"]["bus_voltage_v"]


def test_new_runs_have_distinct_sample_ids(monkeypatch):
    model, template = mock_device.load_fixtures()
    samples = []

    def receive(request):
        if request.url.path.endswith("/telemetry"):
            samples.append(json.loads(request.content))
        return httpx.Response(200)

    monkeypatch.setattr(mock_device.time, "sleep", lambda _: None)
    with httpx.Client(base_url="http://testserver", transport=httpx.MockTransport(receive)) as client:
        for _ in range(2):
            mock_device.run_simulator(client, model, template, count=1, interval=1)
    assert samples[0]["sample_id"] != samples[1]["sample_id"]
    assert samples[0]["measurements"] == samples[1]["measurements"]


@pytest.mark.parametrize("failure_path", ["/api/devices", "/telemetry"])
def test_rejected_api_request_stops_publishing(failure_path):
    model, template = mock_device.load_fixtures()
    paths = []

    def receive(request):
        paths.append(request.url.path)
        return httpx.Response(422 if request.url.path.endswith(failure_path) else 201)

    with (
        httpx.Client(base_url="http://testserver", transport=httpx.MockTransport(receive)) as client,
        pytest.raises(httpx.HTTPStatusError),
    ):
        mock_device.run_simulator(client, model, template, count=3, interval=1)
    assert len(paths) == (1 if failure_path == "/api/devices" else 2)


@pytest.mark.parametrize(
    "args",
    [
        ["--count", "0"], ["--count", "10001"], ["--interval", "nan"],
        ["--interval", "0"], ["--interval", "61"], ["--device-id", "../bad"],
        ["--device-id", "nexus-BAD"], ["--device-id", "nexus_bad"],
        ["--base-url", "http://user:secret@localhost"],
        ["--base-url", "http://localhost?token=secret"],
        ["--base-url", "http://localhost/api"],
    ],
)
def test_cli_rejects_invalid_options_before_network(args):
    with pytest.raises(SystemExit) as error:
        mock_device.main(args)
    assert error.value.code == 2


def test_cli_reports_connection_failure_without_traceback(monkeypatch, capsys):
    def fail(*args, **kwargs):
        raise httpx.ConnectError("private connection diagnostics")

    monkeypatch.setattr(mock_device, "run_simulator", fail)
    assert mock_device.main(["--count", "1", "--device-id", "nexus-other"]) == 1
    output = capsys.readouterr()
    assert "nexus-other" in output.out
    assert "cannot reach the API" in output.err
    assert "private connection diagnostics" not in output.err


def test_cli_reports_http_failure_without_response_body(monkeypatch, capsys):
    def fail(*args, **kwargs):
        request = httpx.Request("POST", "http://testserver/api/devices")
        response = httpx.Response(409, request=request, text="private response details")
        response.raise_for_status()

    monkeypatch.setattr(mock_device, "run_simulator", fail)
    assert mock_device.main(["--count", "1"]) == 1
    output = capsys.readouterr()
    assert "HTTP 409 for POST /api/devices" in output.err
    assert "private response details" not in output.err
