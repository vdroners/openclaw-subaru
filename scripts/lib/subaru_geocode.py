"""Offline-safe reverse geocoding for Talk location replies.

Turns ``lat, lon`` into a short place label (e.g. "Beaverton, OR"). Strictly
opt-in: network lookups only happen when ``SUBARU_GEOCODE=1`` AND a previous
result is not already cached. Results are cached on disk keyed by rounded
coordinates so repeated locates never re-hit the network, and every failure
falls back to ``None`` so the caller can show raw coordinates instead.

The default provider is OpenStreetMap Nominatim; per its usage policy a
descriptive User-Agent is sent and results are cached aggressively. Tests and
dry-run gates pass ``enabled=False`` (or a pre-seeded cache) so no network call
is ever made under CI.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable


def is_enabled(env: dict[str, str] | None = None) -> bool:
    import os

    env = env if env is not None else os.environ
    return (env.get("SUBARU_GEOCODE") or "").strip() == "1"


def cache_key(lat: float, lon: float, precision: int = 3) -> str:
    return f"{round(float(lat), precision)},{round(float(lon), precision)}"


def load_cache(path: str | Path) -> dict[str, str]:
    p = Path(path)
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError, OSError):
        return {}
    if isinstance(data, dict):
        return {str(k): str(v) for k, v in data.items()}
    return {}


def save_cache(path: str | Path, cache: dict[str, str]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cache, indent=0) + "\n", encoding="utf-8")


def _nominatim_fetcher(timeout: float, user_agent: str) -> Callable[[float, float], str | None]:
    def fetch(lat: float, lon: float) -> str | None:
        import urllib.parse
        import urllib.request

        params = urllib.parse.urlencode(
            {"lat": lat, "lon": lon, "format": "jsonv2", "zoom": "14"}
        )
        url = f"https://nominatim.openstreetmap.org/reverse?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": user_agent})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return _short_label(data.get("address") or {})

    return fetch


def _short_label(address: dict[str, Any]) -> str | None:
    """Compose a compact 'City, ST' style label from a Nominatim address dict."""
    city = (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("hamlet")
        or address.get("suburb")
        or address.get("neighbourhood")
    )
    state = address.get("state_code") or address.get("state")
    parts = [p for p in (city, state) if p]
    return ", ".join(parts) if parts else None


def reverse_geocode(
    lat: Any,
    lon: Any,
    *,
    cache_path: str | Path | None = None,
    enabled: bool | None = None,
    fetcher: Callable[[float, float], str | None] | None = None,
    timeout: float = 4.0,
    user_agent: str = "openclaw-subaru/1.0 (reverse-geocode)",
) -> str | None:
    """Return a place label for the coordinates, or None.

    Never raises and never blocks beyond ``timeout``. When disabled or on any
    error, returns None so the caller can fall back to raw coordinates.
    """
    if enabled is None:
        enabled = is_enabled()
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return None

    cache: dict[str, str] = {}
    key = cache_key(lat_f, lon_f)
    if cache_path is not None:
        cache = load_cache(cache_path)
        if key in cache:
            return cache[key] or None

    if not enabled:
        return None

    try:
        fn = fetcher or _nominatim_fetcher(timeout, user_agent)
        label = fn(lat_f, lon_f)
    except Exception:
        return None

    if label and cache_path is not None:
        cache[key] = label
        try:
            save_cache(cache_path, cache)
        except OSError:
            pass
    return label
