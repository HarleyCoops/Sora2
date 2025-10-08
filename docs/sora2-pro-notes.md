## October 2025 Sora 2 Pro API Notes (from https://platform.openai.com/docs/models/sora-2-pro)

- **Model id**: `sora-2-pro`
- **Modalities**: accepts text/image input, returns video with synced audio
- **Resolutions**:
  - Portrait `720x1280` / Landscape `1280x720` ($0.30 per rendered second)
  - Portrait `1024x1792` / Landscape `1792x1024` ($0.50 per rendered second)
- **Endpoints leveraged** (Video API):
  - `POST /v1/videos` – start render job (async response with `id`, `status`, `seconds`, `size`)
  - `GET /v1/videos/{video_id}` – poll job status (`queued`, `in_progress`, `completed`, `failed`)
  - `GET /v1/videos/{video_id}/content` – download MP4 (`variant=video`), thumbnail (`variant=thumbnail`), spritesheet (`variant=spritesheet`)
  - `GET /v1/videos` – list videos (supports `limit`, `after`, `order`)
  - `DELETE /v1/videos/{video_id}` – remove video asset from OpenAI storage
- **Rate limits** (RPM): Tier 1 → 1, Tier 2 → 2, Tier 3 → 5, Tier 4 → 10, Tier 5 → 20
- **Guardrails**: rejects R-rated content, copyrighted characters or music, real people faces; input images with faces not allowed.
- **Workflow overview**:
  1. `POST /videos` with `model`, creative `prompt`, and control params like `size`, `seconds`, optional `input_reference`, optional `remix_video_id`.
  2. Poll `GET /videos/{video_id}` or subscribe to webhooks until `status === "completed"`.
  3. Download deliverables via `GET /videos/{video_id}/content`.
- **Prompting tips**: describe shot type, subject, action, setting, lighting; refined prompting guide available at cookbook link.
