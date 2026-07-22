"""Shared OpenClaw gateway hooks dispatch for Nextcloud Talk (relay + shim)."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request


def resolve_hooks_token() -> str:
    token = (os.environ.get("OPENCLAW_HOOKS_TOKEN") or "").strip()
    if token:
        return token
    try:
        with open(os.path.expanduser("~/.openclaw/hooks-token.txt"), encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return ""


def resolve_family_hub_room() -> str:
    return (os.environ.get("SKYLIGHT_FAMILY_TALK_ROOM") or "").strip()


def agent_id_for_room(room_token: str, family_hub_room: str | None = None) -> str:
    fam = family_hub_room if family_hub_room is not None else resolve_family_hub_room()
    return "family" if room_token == fam else "main"


def strip_agent_mention(text: str, agent_name: str) -> str:
    cleaned = re.sub(rf"(?i)(^|\s)@{re.escape(agent_name)}[:\s]?", " ", text or "").strip()
    return cleaned or (text or "").strip()


def dispatch_talk_to_gateway(
    *,
    room_token: str,
    message: str,
    actor_id: str = "",
    origin: str = "talk-hooks-dispatch",
    family_hub_room: str | None = None,
    agent_name: str | None = None,
    strip_mention: bool = False,
    gateway_url: str | None = None,
    hooks_token: str | None = None,
    timeout_seconds: int = 240,
    http_timeout: float = 8.0,
    log_prefix: str = "[talk-hooks]",
) -> bool:
    """Wake OpenClaw via POST /hooks/agent. Returns True if wake accepted."""
    token = hooks_token if hooks_token is not None else resolve_hooks_token()
    if not token:
        print(f"{log_prefix} ERROR: no hooks token configured; cannot dispatch", flush=True)
        return False

    cleaned = (message or "").strip()
    if not cleaned:
        return False

    if strip_mention:
        name = (agent_name or os.environ.get("OPENCLAW_AGENT_MENTION", "@openclaw").lstrip("@") or "openclaw")
        cleaned = strip_agent_mention(cleaned, name)
        if not cleaned:
            return False

    fam_room = family_hub_room if family_hub_room is not None else resolve_family_hub_room()
    agent = agent_id_for_room(room_token, fam_room)
    session_key = f"agent:{agent}:nextcloud-talk:group:{room_token}"
    gateway = (gateway_url or os.environ.get("GATEWAY_URL") or "http://127.0.0.1:18789").rstrip("/")

    body = {
        "name": "talk-mention",
        "message": cleaned,
        "agentId": agent,
        "wakeMode": "now",
        "deliver": True,
        "sessionKey": session_key,
        "timeoutSeconds": timeout_seconds,
    }
    req = urllib.request.Request(
        f"{gateway}/hooks/agent",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "X-OpenClaw-Origin": origin,
            "X-OpenClaw-Actor": actor_id or "unknown",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=http_timeout) as resp:
            status = resp.status
            print(
                f"{log_prefix} dispatched room={room_token} agent={agent} actor={actor_id} "
                f"({len(cleaned)} chars) -> HTTP {status}",
                flush=True,
            )
            return 200 <= status < 300
    except TimeoutError:
        print(
            f"{log_prefix} dispatched room={room_token} agent={agent} actor={actor_id} "
            f"({len(cleaned)} chars) -> HTTP timeout (wake likely started)",
            flush=True,
        )
        return True
    except urllib.error.HTTPError as exc:
        print(
            f"{log_prefix} dispatch HTTPError room={room_token} status={exc.code} "
            f"body={exc.read()[:200]!r}",
            flush=True,
        )
        return False
    except Exception as exc:
        print(f"{log_prefix} dispatch EXCEPTION room={room_token}: {exc}", flush=True)
        return False
