# Security rules

- Store Nebius keys, Wi-Fi credentials, broker credentials, and device tokens only in local environment variables or the chosen secret store.
- Keep `.env`, raw logs, and captured prompts out of Git.
- Redact authorization headers, tokens, network addresses, and personal data from demo evidence.
- Validate every model response against a strict schema before using it.
- Run every proposed device action through the deterministic allowlist and range checks.
- Keep the firmware PWM ceiling independent of backend and model behavior.
- Never expose an unrestricted voltage, flash, shell, or arbitrary GPIO tool in the MVP.
