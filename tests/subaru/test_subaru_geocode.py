"""Tests for offline-safe reverse geocoding (subaru_geocode)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "lib"))

from subaru_geocode import (  # noqa: E402
    cache_key,
    reverse_geocode,
    _short_label,
    load_cache,
)


def test_disabled_returns_none_without_network():
    # No fetcher, disabled -> must never touch network.
    assert reverse_geocode(45.5231, -122.6765, enabled=False) is None


def test_cache_hit_returns_without_fetch(tmp_path):
    cache = tmp_path / "geo.json"
    key = cache_key(45.5231, -122.6765)
    cache.write_text(f'{{"{key}": "Portland, OR"}}', encoding="utf-8")

    def boom(lat, lon):  # pragma: no cover - must not be called
        raise AssertionError("network fetch must not happen on cache hit")

    assert reverse_geocode(45.5231, -122.6765, cache_path=cache, enabled=True, fetcher=boom) == "Portland, OR"


def test_enabled_fetch_writes_cache(tmp_path):
    cache = tmp_path / "geo.json"
    out = reverse_geocode(
        45.5231,
        -122.6765,
        cache_path=cache,
        enabled=True,
        fetcher=lambda lat, lon: "Beaverton, OR",
    )
    assert out == "Beaverton, OR"
    assert load_cache(cache)[cache_key(45.5231, -122.6765)] == "Beaverton, OR"


def test_fetcher_exception_falls_back_to_none(tmp_path):
    def boom(lat, lon):
        raise RuntimeError("nominatim down")

    assert reverse_geocode(1.0, 2.0, cache_path=tmp_path / "g.json", enabled=True, fetcher=boom) is None


def test_invalid_coords_none():
    assert reverse_geocode(None, None, enabled=True, fetcher=lambda a, b: "x") is None


def test_short_label_prefers_city_state():
    assert _short_label({"city": "Beaverton", "state_code": "OR"}) == "Beaverton, OR"
    assert _short_label({"town": "Hillsboro", "state": "Oregon"}) == "Hillsboro, Oregon"
    assert _short_label({}) is None
