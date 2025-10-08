from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from sora2 import SoraClient, get_config


def parse_int(value: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Expected integer, received '{value}'") from exc


def parse_float(value: str) -> float:
    try:
        return float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Expected float, received '{value}'") from exc


def parse_json(value: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"metadata must be valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError("metadata JSON must decode to an object.")
    return parsed


def variant_to_extension(variant: str) -> str:
    return {
        "thumbnail": "webp",
        "spritesheet": "jpg",
    }.get(variant, "mp4")


def parse_seconds(value: str) -> str:
    allowed = {"4", "8", "12"}
    if value not in allowed:
        raise argparse.ArgumentTypeError("seconds must be one of 4, 8, or 12.")
    return value


def output(data: Any) -> None:
    json.dump(data, sys.stdout, indent=2)
    sys.stdout.write("\n")


def handle_error(error: Exception) -> None:
    message = getattr(error, "message", None) or str(error)
    print(message, file=sys.stderr)
    sys.exit(1)


def handle_create(args: argparse.Namespace) -> None:
    client = SoraClient()

    try:
        job = client.create_video(
            prompt=resolve_prompt(args),
            model=args.model,
            seconds=args.seconds,
            size=args.size,
            aspect_ratio=args.aspect_ratio,
            input_reference_path=args.input_reference,
            remix_video_id=args.remix_video_id,
            seed=args.seed,
            metadata=args.metadata,
            webhook=_build_webhook(args),
        )
        output(job)

        if not args.wait:
            return

        print("Waiting for completion...", file=sys.stderr)

        def on_update(update: Dict[str, Any]) -> None:
            timestamp = datetime.utcnow().isoformat() + "Z"
            progress = update.get("progress")
            suffix = f" ({progress}%)" if progress is not None else ""
            print(f"[{timestamp}] {update.get('status')}{suffix}", file=sys.stderr)

        final = client.wait_for_completion(
            job["id"],
            interval_seconds=args.poll_interval,
            timeout_seconds=args.timeout,
            on_update=on_update,
        )
        output(final)

        if args.download:
            resolved = resolve_output_path(args.download, final["id"], args.variant)
            client.download_video(final["id"], variant=args.variant, output_path=resolved)
            print(f"Saved {args.variant} to {resolved}", file=sys.stderr)

    except Exception as exc:
        handle_error(exc)


def resolve_prompt(args: argparse.Namespace) -> str:
    if args.prompt:
        return args.prompt
    if args.prompt_file:
        path = Path(args.prompt_file).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Prompt file not found: {path}")

        content = path.read_text(encoding="utf-8")

        if path.suffix.lower() == ".json":
            try:
                parsed = json.loads(content)
                if isinstance(parsed, str):
                    return parsed
                return json.dumps(parsed, ensure_ascii=False)
            except json.JSONDecodeError:
                pass  # fall back to raw text

        return content

    raise ValueError("Either --prompt or --prompt-file must be provided.")


def resolve_output_path(value: str, video_id: str, variant: str) -> str:
    if value.lower() != "auto":
        return str(Path(value).expanduser().resolve())

    filename = f"{video_id}.{variant_to_extension(variant)}"
    return str(Path.cwd() / "downloads" / filename)


def _build_webhook(args: argparse.Namespace) -> Dict[str, Any] | None:
    if not args.webhook_url:
        return None
    hook = {"url": args.webhook_url}
    if args.webhook_secret:
        hook["secret"] = args.webhook_secret
    return hook


def handle_status(args: argparse.Namespace) -> None:
    client = SoraClient()
    try:
        video = client.get_video(args.video_id)
        output(video)
    except Exception as exc:
        handle_error(exc)


def handle_download(args: argparse.Namespace) -> None:
    client = SoraClient()
    try:
        path = resolve_output_path(args.output or "auto", args.video_id, args.variant)
        client.download_video(args.video_id, variant=args.variant, output_path=path)
        print(f"Downloaded {args.variant} asset to {path}", file=sys.stderr)
    except Exception as exc:
        handle_error(exc)


def handle_list(args: argparse.Namespace) -> None:
    client = SoraClient()
    try:
        data = client.list_videos(limit=args.limit, after=args.after, order=args.order)
        output(data)
    except Exception as exc:
        handle_error(exc)


def handle_delete(args: argparse.Namespace) -> None:
    client = SoraClient()
    try:
        data = client.delete_video(args.video_id)
        output(data)
    except Exception as exc:
        handle_error(exc)


def handle_remix(args: argparse.Namespace) -> None:
    client = SoraClient()
    try:
        data = client.remix_video(args.video_id, prompt=args.prompt)
        output(data)
    except Exception as exc:
        handle_error(exc)


def handle_config(_: argparse.Namespace) -> None:
    try:
        config = get_config()
        output({"base_url": config.base_url, "api_key_present": bool(config.api_key)})
    except Exception as exc:
        handle_error(exc)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sora2", description="Sora 2 Pro video API CLI (Python).")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create
    create = subparsers.add_parser("create", help="Create a new render job.")
    prompt_group = create.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--prompt", help="Natural-language prompt describing the video.")
    prompt_group.add_argument(
        "--prompt-file",
        dest="prompt_file",
        help="Load prompt text from file (JSON files will be stringified).",
    )
    create.add_argument("--model", default="sora-2-pro", help="Model identifier to use.")
    create.add_argument(
        "--seconds",
        type=parse_seconds,
        default="8",
        help="Length of the clip in seconds (allowed: 4, 8, 12).",
    )
    create.add_argument("--size", default="1280x720", help="Resolution, e.g. 1280x720.")
    create.add_argument("--aspect-ratio", dest="aspect_ratio", help="Aspect ratio override (e.g. 16:9).")
    create.add_argument("--input-reference", dest="input_reference", help="Path to an image to guide generation.")
    create.add_argument("--remix-video-id", dest="remix_video_id", help="Previously completed video id to remix.")
    create.add_argument("--seed", type=parse_int, help="Deterministic seed value.")
    create.add_argument("--metadata", type=parse_json, help="JSON object with metadata to attach.")
    create.add_argument("--webhook-url", dest="webhook_url", help="Webhook URL for completion events.")
    create.add_argument("--webhook-secret", dest="webhook_secret", help="Optional secret for webhook verification.")
    create.add_argument("--wait", action="store_true", help="Poll until the job completes.")
    create.add_argument(
        "--poll-interval",
        type=parse_float,
        default=10.0,
        help="Polling interval in seconds while waiting.",
    )
    create.add_argument(
        "--timeout",
        type=parse_float,
        default=900.0,
        help="Timeout in seconds to wait for completion.",
    )
    create.add_argument(
        "--download",
        help="Download asset after completion. Use 'auto' to save under ./downloads/<id>.<ext>.",
    )
    create.add_argument(
        "--variant",
        default="video",
        help="Asset variant to download (video|thumbnail|spritesheet).",
    )
    create.set_defaults(func=handle_create)

    # status
    status = subparsers.add_parser("status", help="Get the status of a render job.")
    status.add_argument("video_id")
    status.set_defaults(func=handle_status)

    # download
    download = subparsers.add_parser("download", help="Download a completed asset.")
    download.add_argument("video_id")
    download.add_argument("--variant", default="video", help="video|thumbnail|spritesheet")
    download.add_argument("--output", help="Output path, defaults to auto under ./downloads/.")
    download.set_defaults(func=handle_download)

    # list
    list_cmd = subparsers.add_parser("list", help="List recent videos.")
    list_cmd.add_argument("--limit", type=parse_int, help="Number of records to fetch.")
    list_cmd.add_argument("--after", help="Pagination cursor.")
    list_cmd.add_argument("--order", choices=("asc", "desc"), help="Sort order.")
    list_cmd.set_defaults(func=handle_list)

    # delete
    delete = subparsers.add_parser("delete", help="Delete a video from OpenAI storage.")
    delete.add_argument("video_id")
    delete.set_defaults(func=handle_delete)

    # remix
    remix = subparsers.add_parser("remix", help="Create a remix job from a completed video.")
    remix.add_argument("video_id")
    remix.add_argument("--prompt", required=True, help="Prompt describing the change.")
    remix.set_defaults(func=handle_remix)

    # config
    config_cmd = subparsers.add_parser("config", help="Show currently loaded configuration (sanitized).")
    config_cmd.set_defaults(func=handle_config)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
