# Sora 2 Pro API Toolkit (Python)

Python utilities and CLI helpers for the October 2025 Sora 2 Pro video API.

## Prerequisites

- Python 3.10+
- An OpenAI API key with access to Sora 2 Pro models

## Setup

```bash
python -m venv .venv
. .venv/Scripts/activate  # PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set:

```
OPENAI_API_KEY=sk-your-sora-key
# Optional: OPENAI_BASE_URL=https://api.openai.com/v1
```

## CLI usage

```bash
python cli.py --help
```

### Create a render job

```bash
python cli.py create \
  --prompt "Wide shot of a neon-lit street market, slow camera push" \
  --model sora-2-pro \
  --seconds 8 \
  --size 1280x720 \
  --wait \
  --download auto
```

Allowed durations for `--seconds` are `4`, `8`, or `12`.

Key flags:

- `--input-reference path/to/image.png` supplies a first-frame guide.
- `--remix-video-id video_123` spins a remix job with the new prompt.
- `--metadata '{"shot":"opening"}'` stores custom JSON.
- `--variant thumbnail` downloads the thumbnail instead of the MP4.
- `--prompt-file prompts/hateful_eight_homage.json` reads prompt text from a file (JSON auto-stringified).

#### Structured prompts from JSON

Store rich prompt payloads under `prompts/` and call:

```bash
python cli.py create \
  --prompt-file prompts/hateful_eight_homage.json \
  --seconds 8 \
  --size 1280x720
```

If the JSON decodes to an object, the CLI automatically stringifies it before sending, preserving nested guidance and metadata. Plain-text files are passed through unchanged.

### Check status

```bash
python cli.py status video_abc123
```

### Download assets

```bash
python cli.py download video_abc123 --variant spritesheet --output ./sprites/video.jpg
```

### List jobs

```bash
python cli.py list --limit 5
```

### Delete a job

```bash
python cli.py delete video_abc123
```

### Remix an existing job

```bash
python cli.py remix video_abc123 --prompt "Shift the palette to teal and rust hues."
```

### Inspect configuration

```bash
python cli.py config
```

## Programmatic usage

```python
from sora2 import SoraClient

client = SoraClient()

job = client.create_video(
    prompt="Drone fly-through of a rainforest waterfall at sunrise",
    model="sora-2-pro",
    seconds=10,
)

final = client.wait_for_completion(
    job["id"],
    interval_seconds=15,
    on_update=lambda update: print(update["status"], update.get("progress")),
)

client.download_video(final["id"], output_path=f"./downloads/{final['id']}.mp4")
```

## References

- [Sora 2 Pro model notes](https://platform.openai.com/docs/models/sora-2-pro)
- [Video generation guide (October 2025)](https://platform.openai.com/docs/guides/video-generation)
