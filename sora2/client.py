from __future__ import annotations

import mimetypes
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

import requests
from openai import OpenAI

from .config import get_config

DEFAULT_MODEL = "sora-2-pro"
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


class SoraClient:
    def __init__(self, *, api_key: Optional[str] = None, base_url: Optional[str] = None) -> None:
        config = get_config()
        self.api_key = api_key or config.api_key
        self.base_url = (base_url or config.base_url).rstrip("/")
        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def create_video(
        self,
        *,
        prompt: str,
        model: str = DEFAULT_MODEL,
        seconds: int = 8,
        size: str = "1280x720",
        aspect_ratio: Optional[str] = None,
        input_reference_path: Optional[str] = None,
        remix_video_id: Optional[str] = None,
        seed: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        webhook: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not prompt:
            raise ValueError("Prompt must be a non-empty string.")

        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "seconds": str(seconds),
            "size": size,
        }

        if aspect_ratio:
            payload["aspect_ratio"] = aspect_ratio
        if remix_video_id:
            payload["remix_video_id"] = remix_video_id
        if seed is not None:
            payload["seed"] = seed
        if metadata:
            payload["metadata"] = metadata
        if webhook:
            payload["webhook"] = webhook

        if input_reference_path:
            file_payload = self._prepare_file_payload(input_reference_path)
            return self._post_with_files("/videos", payload, file_payload)

        if hasattr(self._client, "videos"):
            return self._client.videos.create(**payload)  # type: ignore[arg-type]

        return self._request_json("POST", "/videos", json=payload)

    def get_video(self, video_id: str) -> Dict[str, Any]:
        self._assert_id(video_id, "get_video")

        if hasattr(self._client, "videos"):
            return self._client.videos.retrieve(video_id)  # type: ignore[arg-type]

        return self._request_json("GET", f"/videos/{video_id}")

    def wait_for_completion(
        self,
        video_id: str,
        *,
        interval_seconds: float = 10.0,
        timeout_seconds: float = 900.0,
        on_update: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        start = time.monotonic()
        last_status: Optional[str] = None

        while True:
            if time.monotonic() - start > timeout_seconds:
                raise TimeoutError(f"Timed out waiting for video {video_id}.")

            video = self.get_video(video_id)
            status = video.get("status")
            if on_update and status and status != last_status:
                on_update(video)
                last_status = status

            if status in TERMINAL_STATUSES:
                return video

            time.sleep(interval_seconds)

    def list_videos(
        self,
        *,
        limit: Optional[int] = None,
        after: Optional[str] = None,
        order: Optional[str] = None,
    ) -> Dict[str, Any]:
        params = {
            k: v
            for k, v in (("limit", limit), ("after", after), ("order", order))
            if v is not None
        }

        if hasattr(self._client, "videos"):
            return self._client.videos.list(**params)  # type: ignore[arg-type]

        return self._request_json("GET", "/videos", params=params)

    def delete_video(self, video_id: str) -> Dict[str, Any]:
        self._assert_id(video_id, "delete_video")

        if hasattr(self._client, "videos"):
            return self._client.videos.delete(video_id)  # type: ignore[arg-type]

        return self._request_json("DELETE", f"/videos/{video_id}")

    def download_video(
        self,
        video_id: str,
        *,
        variant: str = "video",
        output_path: Optional[str] = None,
    ) -> bytes | str:
        self._assert_id(video_id, "download_video")

        params = {}
        if variant:
            params["variant"] = variant

        response = self._request_raw("GET", f"/videos/{video_id}/content", params=params, stream=True)

        if output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("wb") as out_file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        out_file.write(chunk)
            return str(path)

        return response.content

    def remix_video(self, video_id: str, *, prompt: str) -> Dict[str, Any]:
        self._assert_id(video_id, "remix_video")
        if not prompt:
            raise ValueError("Prompt is required for remix operations.")

        if hasattr(self._client, "videos"):
            return self._client.videos.remix(video_id, prompt=prompt)  # type: ignore[arg-type]

        return self._request_json(
            "POST",
            f"/videos/{video_id}/remix",
            json={"prompt": prompt},
        )

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------
    def _prepare_file_payload(self, file_path: str) -> Dict[str, Any]:
        path = Path(file_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Input reference not found: {path}")

        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return {"input_reference": (path.name, path.open("rb"), mime)}

    def _post_with_files(
        self,
        endpoint: str,
        fields: Dict[str, Any],
        files: Dict[str, Any],
    ) -> Dict[str, Any]:
        url = self._url(endpoint)
        response = requests.post(
            url,
            data={key: self._stringify(value) for key, value in fields.items()},
            files=files,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        return self._decode_json(response, url, "POST")

    def _request_json(
        self,
        method: str,
        endpoint: str,
        *,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        response = requests.request(
            method,
            self._url(endpoint),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=json,
            params=params,
        )
        return self._decode_json(response, self._url(endpoint), method)

    def _request_raw(
        self,
        method: str,
        endpoint: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        stream: bool = False,
    ) -> requests.Response:
        url = self._url(endpoint)
        response = requests.request(
            method,
            url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            params=params,
            stream=stream,
        )
        if not response.ok:
            raise RuntimeError(f"Request {method} {url} failed: {response.status_code} {response.text}")
        return response

    def _decode_json(self, response: requests.Response, url: str, method: str) -> Dict[str, Any]:
        if not response.ok:
            raise RuntimeError(f"Request {method} {url} failed: {response.status_code} {response.text}")
        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError(f"Unexpected JSON response from {url}: {exc}") from exc

    def _url(self, endpoint: str) -> str:
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"
        return f"{self.base_url}{endpoint}"

    @staticmethod
    def _assert_id(value: str, method: str) -> None:
        if not value or not isinstance(value, str):
            raise ValueError(f"{method} requires a non-empty video id.")

    @staticmethod
    def _stringify(value: Any) -> str:
        if isinstance(value, (dict, list, tuple)):
            import json

            return json.dumps(value)
        return str(value)
