# AI match stats from a phone camera

Assistive only: the AI suggests events; a referee or appointed stats operator confirms them. **Cards and score never auto-apply.**

## Architecture

1. **Record match** (Capacitor camera, landscape, tripod overlay, 720p/1080p). Upload in 30–60s chunks to S3-compatible storage (`STORAGE_*` env vars). Do not write video to Render disks.
2. **Worker** (`fairmeasure-v2-ai-worker` on Render Frankfurt) polls `MatchRecording` rows and runs `apps.ai_camera.services.process_recording`.
3. **VisionProvider** (`apps/ai_camera/providers.py`): stub for tests; `HttpVisionProvider` for Modal / Replicate / RunPod / AWS GPU hosts via `AI_VISION_PROVIDER` + `AI_VISION_ENDPOINT` + `AI_API_KEY`.
4. Output: `AiEventSuggestion` (pending → accepted/rejected/edited). Accept creates a `ScoreEvent` with `source=ai_camera`.
5. Scouting stats should show verification badges: Referee verified / AI + reviewed / Self-reported (filter verified-only).

## Local stub demo (no camera)

On a match **Setup** tab (owner/admin), use **Run stub demo**. That hits `POST /api/fixtures/<id>/ai/demo-stub`, turns on `settings_json.ai_camera_enabled`, runs `StubVisionProvider`, and lists suggestions to **Accept** / **Reject**. Dev defaults: `AI_CAMERA_ENABLED=true`, `AI_VISION_PROVIDER=stub`.

## Feature flags & cost

- Global: `AI_CAMERA_ENABLED=false` by default (true in local `dev` settings).
- Per competition: `settings_json.ai_camera_enabled`.
- Free tier: limit upload duration/size; show processing time and quota in the UI (to wire).
- Raw video retention: `RAW_VIDEO_RETENTION_DAYS` (default 30).

## Privacy (POPIA / GDPR)

- Organiser recording policy + player/guardian consent (`match_recording`, `match_clips` consent sections; `CONSENT_VERSION` bumped).
- Minors: guardian consent required; otherwise blur/exclude — no facial recognition (shirt number + lineup only).
- See Privacy on the legal page.

## External GPU options

Render has no GPUs. Point `AI_VISION_ENDPOINT` at:

| Host | Notes |
| --- | --- |
| Modal | Fast Python functions with GPU |
| Replicate | Hosted YOLO / custom models |
| RunPod | Persistent or serverless GPU pods |
| AWS (af-south-1 preferred for SA data) | SageMaker / ECS GPU |

Pipeline design allows swapping to a commercial sports-tracking API later behind the same interface.
