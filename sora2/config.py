from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

_loaded = False
_cached: Optional["Config"] = None

DEFAULT_BASE_URL = "https://api.openai.com/v1"


@dataclass(frozen=True)
class Config:
    api_key: str
    base_url: str = DEFAULT_BASE_URL


def _ensure_loaded() -> None:
    global _loaded, _cached
    if not _loaded:
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL", DEFAULT_BASE_URL)

        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Copy .env.example to .env and add your Sora key."
            )

        _cached = Config(api_key=api_key, base_url=base_url)
        _loaded = True


def get_config() -> Config:
    _ensure_loaded()
    assert _cached is not None
    return _cached


def override_config(**kwargs: str) -> Config:
    global _cached
    _ensure_loaded()
    assert _cached is not None
    data = _cached.__dict__ | kwargs
    _cached = Config(**data)
    return _cached
