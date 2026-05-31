# Nextcloud Talk relay — Subaru fast-path snippet

Add to operator-local `~/.openclaw/nc-webhook-relay.py` **before** `_room_open_no_relay_llm` (same slot as `_household_proposal_fast_path`).

Prefer importing shared helpers from `scripts/lib/subaru_talk_match.py`:

```python
from subaru_talk_match import extract_user_message, is_subaru_command, is_tool_json_payload

def _subaru_fast_path(text: str, room_token: str, actor_display: str) -> bool:
    if is_tool_json_payload(text) or not is_subaru_command(text, AGENT_NAME):
        return False
    import subprocess
    norm = extract_user_message(text)
    fast_path = os.path.expanduser("~/.openclaw/scripts/subaru-talk-fast-path.sh")
    ...
```

Run **before** the mention gate (Subaru is self-describing — no separate `@` required when the phrase includes `subaru`).

## Supported phrases

- `@openclaw subaru status`
- `@openclaw subaru summary`
- `@openclaw subaru health`
- `@openclaw subaru locate`
- `{mention-user1} subaru status` (NC mention chip)
- `@openclaw subaru start Winter` (Tier 3 — blocked unless actuation enabled)

Tier 3 actuation (`unlock`, `start`) requires `SUBARU_ACTUATION_ENABLED=1` or `SUBARU_FASTPATH_ACTUATION=1` (discouraged).

## Operator wiring

1. `bash scripts/install-to-openclaw.sh --force` from your openclaw-subaru clone
2. Unlock MySubaru → write password + PIN to `~/.openclaw/.env.d/` (see `.env.example` for filenames)
3. **One** 2FA registration: `bash ~/.openclaw/scripts/subaru-device-register.sh --request`
4. Patch relay as above; restart relay service
5. Test in Talk: `@openclaw subaru status` (match your `OPENCLAW_AGENT_MENTION`)
