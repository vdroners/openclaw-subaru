"""Subaru Talk mention-chip detection tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

from subaru_dispatch_parse import parse_dispatch  # noqa: E402
from subaru_talk_match import (  # noqa: E402
    extract_room_token,
    extract_user_message,
    is_noise_echo,
    is_overflow_echo,
    is_subaru_command,
    is_talk_message_envelope,
    is_tool_json_payload,
    normalize_talk_text,
)


def test_normalize_strips_mention_chip():
    assert normalize_talk_text("{mention-user1} Openclaw subaru status") == "Openclaw subaru status"


def test_extract_user_message_from_talk_envelope():
    raw = '{"message":"@openclaw subaru status","parameters":[]}'
    assert extract_user_message(raw) == "@openclaw subaru status"
    assert is_talk_message_envelope(raw)
    assert not is_tool_json_payload(raw)
    assert not is_noise_echo(raw)


def test_is_subaru_from_talk_envelope():
    raw = '{"message":"@openclaw subaru status","parameters":[]}'
    assert is_subaru_command(raw, "openclaw")


def test_human_calendar_envelope_not_noise():
    raw = (
        '{"message":"OpenClaw can you change the concert start time to 615pm please",'
        '"parameters":[]}'
    )
    assert is_talk_message_envelope(raw)
    assert not is_noise_echo(raw)


def test_is_subaru_with_mention_chip_only():
    assert is_subaru_command("{mention-user1} subaru status", "openclaw")


def test_is_subaru_with_mention_chip_and_agent_name():
    assert is_subaru_command("{mention-user1} Openclaw subaru status", "openclaw")


def test_is_not_subaru_random_chat():
    assert not is_subaru_command("what's for dinner?", "openclaw")


def test_extract_room_token_from_url():
    url = "https://cloud.example.com/call/abcd1234"
    assert extract_room_token(url) == "abcd1234"


def test_overflow_echo_detection():
    assert is_overflow_echo("Context overflow: prompt too large for the model")
    assert is_noise_echo("SUBARU_ERR command failed")


def test_parse_dispatch_from_talk_envelope():
    parsed = parse_dispatch('{"message":"@openclaw subaru status","parameters":[]}', "openclaw")
    assert parsed == {"action": "status", "args": []}
    parsed = parse_dispatch("@openclaw subaru status", "openclaw")
    assert parsed == {"action": "status", "args": []}


def test_parse_dispatch_start():
    parsed = parse_dispatch("@openclaw subaru start Auto", "openclaw")
    assert parsed == {"action": "start", "args": ["--preset", "Auto"]}
