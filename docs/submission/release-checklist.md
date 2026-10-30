# Final release checklist

Do not mark the project submitted until every **human gate** is checked by a named owner. The
automated gate writes `artifacts/submission/readiness.json`; that report does not claim a physical
test, public-repository state, account registration, video quality, or successful Devpost submission.

## Automated gate

- [ ] `nexus-run-submission-gate.cmd` exits with PASS on the exact commit to submit.
- [ ] Repository structure and all four v1 contracts validate.
- [ ] Backend lint and full pytest suite pass.
- [ ] Frontend lint, unit tests, TypeScript, and production build pass.
- [ ] Three-wheel PS2 firmware builds for `nexus-goouuu-esp32-s3-3wheel-ps2`.
- [ ] Five consecutive offline Prevent, Manual Diagnose, and Auto Heal paths pass.
- [ ] Tracked-file secret scan passes; `.env`, raw logs, and private evidence remain ignored.

## Live integration gate

- [ ] API key was entered only through `nexus-configure-nebius.cmd`; no key appears in Git or video.
- [ ] `nexus-run-u07-vertical-slice.cmd` passes 3/3 with `source=device` on the final wiring/profile.
- [ ] Live result shows the intended NVIDIA model through Nebius and at least one read-only tool call.
- [ ] Dashboard, Hardware Graph, AI Doctor, timeline, retry, and evidence export work after reload.
- [ ] Latest firmware profile ID/hash and backend profile ID/hash match.

## Physical safety and quality gate

- [ ] Fuse, relay isolation, ON/OFF, E-stop, common ground, capacitors, and strain relief are present.
- [ ] Wheels are raised for motor tests; an operator stays next to the main disconnect.
- [ ] Three encoders report plausible RPM; no wheel starts before explicit arm/control input.
- [ ] Thirty-minute baseline and N08 recovery drill evidence correspond to the final hardware revision.
- [ ] No P0/P1 issue remains open; any limitation is stated honestly in the submission.

## Devpost human gate

- [ ] All four people joined the same Devpost team and accepted invitations.
- [ ] Nebius Builder Program/credits and submission-account requirements are complete.
- [ ] Repository is public, MIT license is visible at root, and anonymous clone works.
- [ ] README quick start works on a clean machine and contains no private/local-only link.
- [ ] Video is public, below 03:00, includes at least 01:00 of real hardware, and captions are enabled.
- [ ] English submission copy, NVIDIA model, Nebius usage, open-source link, and honest feedback are filled.
- [ ] Final form preview was reviewed by Hiếu; a screenshot of successful submission was saved.
