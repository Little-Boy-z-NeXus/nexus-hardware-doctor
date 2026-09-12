# N07 — Automation, telemetry replay, and soak evidence

N07 lets backend/frontend development continue without the physical rig and collects the
quality evidence needed for the frozen MVP. Replay is visibly labelled `replay`; it must never
be presented as a fresh device measurement or physical proof.

## One-click replay

Double-click `nexus-start-replay-demo.cmd`. It stops any NeXus server that owns port 8000,
starts a local replay backend, starts the frontend, and opens `/hardware`. The replay backend
publishes the sanitized fixture through `/api/v1/live`, `/api/v1/logs`, and
`/api/v1/live/ws`, which are the same read-only realtime endpoints used with the ESP32.

For a local U05 evidence file, start the replay server directly with
`python -m nexus_backend.replay_server --input artifacts/U05/<file>.ndjson`. The loader accepts
both direct telemetry NDJSON and U05 records whose `kind` is `serial`. Original device/session
IDs and timestamps are replaced, and `quality.source` becomes `replay`.

## Acceptance evidence

| Gate | Evidence |
| --- | --- |
| Telemetry soak | N02 physical run: 2,652 seconds (44m12s), 2,644 samples, 0.997 Hz, maximum gap 2 seconds, 12.096–12.105 V; exceeds the N07 30-minute threshold |
| Reconnect | SerialBridge and WebSocket tests cover disconnect/reconnect, reset identity, current snapshot on reconnect, and no stale command replay |
| Timeout | Serial channel tests prove bounded timeout/cancellation and removal of pending commands |
| Duplicate command | N03 physical acceptance and unit tests prove identical request IDs return cached results without applying the action twice |
| Tool/API smoke | Backend suite plus k6 MVP smoke run in CI; replay loader/sanitizer/live snapshot are unit tested |

Raw physical telemetry remains under ignored `artifacts/`; only this redacted summary and the
synthetic replay fixture are committed.
