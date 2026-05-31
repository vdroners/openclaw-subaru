# Nextcloud Talk relay — Subaru fast-path snippet

Add to operator-local `~/.openclaw/nc-webhook-relay.py`:

```python
_SUBARU_RE = re.compile(
    rf"(?i)@{re.escape(AGENT_NAME)}\s+subaru\s+(\S+)(?:\s+(\S+))?"
)

# Inside mention handler, before LLM fallback:
m = _SUBARU_RE.search(message_text or "")
if m:
    sub, arg = m.group(1), m.group(2)
    cmd = ["bash", os.path.expanduser("~/.openclaw/scripts/subaru-vehicle.sh"), sub]
    if sub.lower() == "start" and arg:
        cmd.extend(["--preset", arg])
    if sub.lower() == "maps":
        cmd[-1] = "maps-link"
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    summary = result.stdout.strip().split("\n")[-1] if result.stdout else "Subaru command failed"
    post_talk_reply(room, summary[:500])
    return {"handled": True}
```

## Supported phrases

- `@openclaw subaru status`
- `@openclaw subaru health`
- `@openclaw subaru locate`
- `@openclaw subaru start Winter`
- `@openclaw subaru lock|unlock|stop|horn|lights`

Tier 3 actuation (`unlock`, `start`) should require chat confirmation unless `SUBARU_FASTPATH_ACTUATION=1` (discouraged).
