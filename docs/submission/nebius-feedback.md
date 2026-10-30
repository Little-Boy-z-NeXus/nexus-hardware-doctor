# Nebius feedback — verify before pasting

Use this as a factual structure, not as an automatic testimonial. Replace bracketed lines only after
the final live rehearsal and do not claim latency, uptime, credit behavior, or model quality that was
not observed.

## What worked well

- The OpenAI-compatible chat-completions surface let the backend keep a small provider boundary.
- Structured output plus schema validation made Nemotron usable inside a deterministic orchestrator.
- Provider/model metadata could be recorded in redacted acceptance evidence without storing the key
  or raw chain-of-thought.
- `[CONFIRM AFTER FINAL RUN: model name, successful run count, read-only tool path, and approximate
  observed latency range.]`

## What could improve

- Clearer examples for structured JSON recovery, reasoning controls, token accounting, retryable
  error categories, and rate-limit headers would reduce integration time.
- A first-party health/model-capabilities endpoint would make preflight checks easier than spending a
  generation request to discover configuration problems.
- Hardware teams benefit from concise guidance on key rotation, credit exhaustion, request tracing,
  and how to retain audit metadata without persisting sensitive prompts.
- `[ADD ONLY A REAL ISSUE SEEN IN THE FINAL RUN; otherwise remove this bullet.]`

## Product impact

Nebius provided the hosted NVIDIA-model layer while NeXus kept physical authority in local,
deterministic safety policy. This separation allowed us to use model reasoning for ranked hardware
hypotheses without treating a generated answer as permission to actuate a motor.
