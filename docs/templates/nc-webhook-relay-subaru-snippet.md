# Nextcloud Talk relay — Subaru fast-path snippet

Add to operator-local `~/.openclaw/nc-webhook-relay.py` **before** `_room_open_no_relay_llm` (same slot as `_household_proposal_fast_path`):

```python
_SUBARU_MENTION_RE = re.compile(
    rf"(?i)@{re.escape(AGENT_NAME)}\s+subaru\b"
)

def _subaru_fast_path(text: str, room_token: str, actor_display: str) -> bool:
    if not _SUBARU_MENTION_RE.search(text or ""):
        return False
    import subprocess
    dispatch = os.path.expanduser("~/.openclaw/scripts/subaru-dispatch-exec.sh")
    formatter = os.path.expanduser("~/.openclaw/scripts/subaru-format-talk-reply.sh")
    talk_post = os.path.expanduser("~/.openclaw/scripts/talk-post.sh")
    if not os.path.isfile(talk_post):
        talk_post = os.path.expanduser("~/openclaw-skylight/scripts/talk-post.sh")
    try:
        result = subprocess.run(
            ["bash", dispatch, text],
            capture_output=True,
            text=True,
            timeout=120,
        )
        fmt = subprocess.run(
            ["bash", formatter],
            input=result.stdout or result.stderr or "{}",
            capture_output=True,
            text=True,
            timeout=30,
        )
        summary = (fmt.stdout or "Subaru command failed").strip()[:500]
        post = subprocess.run(
            ["bash", talk_post, summary, room_token],
            capture_output=True,
            text=True,
            timeout=30,
        )
        print(
            f"[mention] subaru fast-path room={room_token} actor={actor_display} "
            f"dispatch_rc={result.returncode} post_rc={post.returncode} "
            f"summary={summary[:120]!r}"
        )
        return post.returncode == 0
    except Exception as e:
        print(f"[mention] subaru fast-path EXCEPTION: {e}", file=sys.stderr)
        return False

# Inside mention handler, after household fast-path:
if _subaru_fast_path(text, room_token, actor_display):
    self._respond(200, {"status": "dispatched", "via": "subaru-fast-path", "room": room_token})
    return
```

## Supported phrases

- `@openclaw subaru status` (match `OPENCLAW_AGENT_MENTION` if customized)
- `@openclaw subaru summary`
- `@openclaw subaru health`
- `@openclaw subaru locate`
- `@openclaw subaru start Winter` (Tier 3 — blocked unless actuation enabled)

Tier 3 actuation (`unlock`, `start`) requires `SUBARU_ACTUATION_ENABLED=1` or `SUBARU_FASTPATH_ACTUATION=1` (discouraged).

## Operator wiring

1. `bash scripts/install-to-openclaw.sh --force` from your openclaw-subaru clone
2. Unlock MySubaru → write password + PIN to `~/.openclaw/.env.d/`
3. **One** 2FA registration: `bash ~/.openclaw/scripts/subaru-device-register.sh --request`
4. Patch relay as above; restart relay service
5. Test in Family Hub: `@openclaw subaru status` (match your agent mention alias)
