#!/usr/bin/env python3
"""Shared Subaru Talk fast-path detection + NC message normalization."""

from __future__ import annotations

import json
import re

MENTION_CHIP_RE = re.compile(r"\{mention-user\d+\}", re.IGNORECASE)
ROOM_TOKEN_RE = re.compile(r"/(?:call|chat)/([a-z0-9]+)(?:/|$)", re.IGNORECASE)
_SUBARU_VERB_RE = re.compile(
    r"(?i)\b(status|summary|locate|location|where|parked|maps|maps-link|condition|"
    r"capabilities|fetch|presets|lock(?:ed)?|unlock(?:ed)?|stop|horn|lights|charge|"
    r"start|health-report|health|fuel|gas|range|doors?|tires?|tpms)\b"
)


def normalize_talk_text(text: str) -> str:
    cleaned = MENTION_CHIP_RE.sub(" ", text or "")
    return re.sub(r"\s+", " ", cleaned).strip()


def extract_user_message(text: str) -> str:
    """Plain Talk text for dispatch — never pass raw tool JSON to bash grep."""
    raw = (text or "").strip()
    if raw.startswith("{") and '"message"' in raw:
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                msg = obj.get("message")
                if isinstance(msg, str) and msg.strip():
                    return normalize_talk_text(msg)
        except json.JSONDecodeError:
            pass
    return normalize_talk_text(raw)


def _is_rich_object_map(params: object) -> bool:
    """Talk rich-object parameters, e.g. {"mention-user1": {"type": "user", ...}}."""
    return (
        isinstance(params, dict)
        and bool(params)
        and all(isinstance(v, dict) and isinstance(v.get("type"), str) for v in params.values())
    )


def is_talk_message_envelope(text: str) -> bool:
    """Nextcloud Talk human input wrapper: {"message":"...","parameters":[]}.

    A message with an @-mention or attachment carries rich-object parameters
    instead of ``[]``; that is still human input, not a tool-call echo.
    """
    raw = (text or "").strip()
    if not raw.startswith("{"):
        return False
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return False
    if not isinstance(obj, dict):
        return False
    msg = obj.get("message")
    params = obj.get("parameters")
    return isinstance(msg, str) and bool(msg.strip()) and (params == [] or _is_rich_object_map(params))


def is_tool_json_payload(text: str) -> bool:
    """OpenClaw bot echo of a structured tool invocation — not NC human envelopes."""
    raw = (text or "").strip()
    if not raw.startswith("{"):
        return False
    if is_talk_message_envelope(text):
        return False
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return False
    return isinstance(obj, dict) and "parameters" in obj


def extract_room_token(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    match = ROOM_TOKEN_RE.search(raw)
    if match:
        return match.group(1)
    if "/" in raw:
        return raw.rstrip("/").split("/")[-1]
    return raw


def is_subaru_command(text: str, agent_name: str = "openclaw") -> bool:
    """True when text should take the Subaru Talk fast-path.

    Accepts:
    - ``@openclaw subaru status`` (canonical)
    - mention-chip + subaru (``{mention-user1} subaru unlock``)
    - ``@openclaw … subaru …`` when a known verb is present (``is subaru locked``)
    - bare ``subaru status`` / ``subaru unlock`` (Family Hub open-room style)
    """
    norm = extract_user_message(text)
    if not norm:
        return False
    agent = agent_name.lstrip("@")
    agent_re = re.compile(rf"(?i)\b@?{re.escape(agent)}\s+subaru\b")
    if agent_re.search(norm):
        return True
    if MENTION_CHIP_RE.search(text or "") and re.search(r"(?i)\bsubaru\b", norm):
        return True
    # @openclaw … subaru … <verb>  (verb not required immediately after "subaru")
    if re.search(rf"(?i)\b@?{re.escape(agent)}\b", norm) and re.search(
        r"(?i)\bsubaru\b", norm
    ) and _SUBARU_VERB_RE.search(norm):
        return True
    # Family Hub often omits @: "subaru status", "subaru unlock confirm"
    if re.match(r"(?i)^subaru\b", norm) and (
        _SUBARU_VERB_RE.search(norm) or len(norm.split()) == 1
    ):
        return True
    return False


def is_overflow_echo(text: str) -> bool:
    lower = (text or "").lower()
    return "context overflow" in lower or "subaru_err" in lower


def is_noise_echo(text: str) -> bool:
    """Bot/LLM junk that must not re-trigger OpenClaw or fast-path."""
    if is_overflow_echo(text):
        return True
    if is_tool_json_payload(text):
        return True
    norm = extract_user_message(text)
    if norm.startswith("{") and norm.endswith("}"):
        return True
    return False
