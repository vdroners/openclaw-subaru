# Nextcloud Talk webhook shim — Subaru fast-path (operator-local)

Family Hub messages hit the Talk bot webhook on **:8788** only. The relay on :8789
does not receive NC talk events unless `webhook_listeners` is wired separately.
This shim sits on :8788 and forwards everything else to OpenClaw on :8787.

## Install

1. `bash scripts/install-to-openclaw.sh --force` from openclaw-subaru
2. Set OpenClaw plugin port to **8787** in `~/.openclaw/openclaw.json`:
   ```json
   "webhookPort": 8787
   ```
3. Copy shim + unit:
   ```bash
   cp ~/openclaw-subaru/scripts/talk-webhook-shim.py ~/.openclaw/
   cp ~/openclaw-subaru/docs/templates/talk-webhook-shim.service \
     ~/.config/systemd/user/talk-webhook-shim.service
   ```
4. Restart:
   ```bash
   systemctl --user daemon-reload
   systemctl --user restart openclaw-gateway talk-webhook-shim
   ```

Point the Nextcloud Talk bot URL at `http://<your-host>:8788/nextcloud-talk-webhook`.

Set `OPENCLAW_AGENT_MENTION` in `~/.openclaw/.env` to match your agent alias (default `@openclaw`).

## Phrases (no `@` required when using NC mention chips)

- `@openclaw subaru status`
- `@openclaw subaru summary`
- `@openclaw subaru locate`
- `{mention-user1} subaru status` (Nextcloud @-mention chip + command)

Handled by `subaru-talk-fast-path.sh` → MySubaru API → formatted Talk reply. **No LLM.**

## Self-echo drop

Inbound messages from the OpenClaw NC user (`actor.id` matching your bot user) are dropped at the shim
so error replies do not re-trigger the agent.

Structured tool JSON payloads (`{"message":…,"parameters":[]}`) are also dropped — they are not operator commands.

## Relay snippet (secondary path)

If you later wire NC `webhook_listeners` to :8789, use the broadened pattern in
`nc-webhook-relay-subaru-snippet.md` (`@?openclaw subaru`).
