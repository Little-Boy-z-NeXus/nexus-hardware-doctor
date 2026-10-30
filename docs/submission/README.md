# NeXus submission pack

This folder is the single handoff point for the final hackathon submission. It separates files
that are ready to paste from checks that still require a person, a real rig, or an external
account.

| File | Use |
| --- | --- |
| [`devpost-submission.md`](devpost-submission.md) | English project story and form copy |
| [`video-script-en.md`](video-script-en.md) | Shot-by-shot demo plan under three minutes |
| [`subtitles-en.srt`](subtitles-en.srt) | English captions matching the video plan |
| [`release-checklist.md`](release-checklist.md) | Final automated and human go/no-go gates |
| [`nebius-feedback.md`](nebius-feedback.md) | Honest feedback form; confirm live observations before pasting |
| [`significant-updates.md`](significant-updates.md) | Changes built during the hackathon period |

Run `nexus-run-submission-gate.cmd` before recording and once more before submitting. Never add an
API key, raw provider response, private video, or raw device log to this folder.

The architecture images in this folder document the earlier INA226 physical vertical slice.
The active three-wheel DevKitC adapter uses INA219; use its versioned profile and current README
for wiring and setup.
