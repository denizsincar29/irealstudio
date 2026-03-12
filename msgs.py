"""msgs.py - Telegram Bot message fetcher with local history caching.

Fetches updates from the Telegram Bot API using long polling and persists
every received message to a local ``history/`` directory as JSON.  A small
offset file keeps track of the last processed update so that subsequent
calls only return *new* messages - no Redis required.

Environment variables
---------------------
TELEGRAM_BOT_TOKEN
    Your bot token obtained from @BotFather.  Required.

Typical usage
-------------
>>> import msgs
>>> new_messages = msgs.get_updates()       # fetch & cache new messages
>>> history      = msgs.get_chat_history(chat_id)  # read cached history
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

HISTORY_DIR = Path("history")
_OFFSET_FILE = HISTORY_DIR / "offset.json"
_TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/{method}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_token() -> str:
    """Return the bot token from the environment, raising if missing."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN environment variable is not set. "
            "Get your token from @BotFather and export it before running."
        )
    return token


def _api_url(method: str) -> str:
    return _TELEGRAM_API_BASE.format(token=_get_token(), method=method)


def _ensure_history_dir() -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Offset persistence (tracks which updates have already been processed)
# ---------------------------------------------------------------------------


def _load_offset() -> int:
    """Return the next update offset to request from Telegram."""
    _ensure_history_dir()
    if _OFFSET_FILE.exists():
        try:
            data = json.loads(_OFFSET_FILE.read_text(encoding="utf-8"))
            return int(data.get("offset", 0))
        except (json.JSONDecodeError, ValueError):
            pass
    return 0


def _save_offset(offset: int) -> None:
    """Persist the next update offset to disk."""
    _ensure_history_dir()
    _OFFSET_FILE.write_text(
        json.dumps({"offset": offset}, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Per-chat history persistence
# ---------------------------------------------------------------------------


def _chat_history_file(chat_id: int | str) -> Path:
    _ensure_history_dir()
    return HISTORY_DIR / f"chat_{chat_id}.json"


def _load_chat_history(chat_id: int | str) -> list[dict[str, Any]]:
    path = _chat_history_file(chat_id)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
    return []


def _save_chat_history(
    chat_id: int | str, messages: list[dict[str, Any]]
) -> None:
    path = _chat_history_file(chat_id)
    path.write_text(
        json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _append_to_history(message: dict[str, Any]) -> None:
    """Append *message* to the appropriate per-chat history file.

    Duplicate messages (same ``message_id`` in the same chat) are silently
    ignored so that edited-message updates don't create duplicate entries.
    """
    chat_id: int | str = message.get("chat", {}).get("id", "unknown")
    history = _load_chat_history(chat_id)
    seen_ids = {m.get("message_id") for m in history}
    if message.get("message_id") not in seen_ids:
        history.append(message)
        _save_chat_history(chat_id, history)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_updates(timeout: int = 30) -> list[dict[str, Any]]:
    """Fetch new updates from Telegram using long polling.

    Parameters
    ----------
    timeout:
        Long-poll timeout in seconds passed to Telegram (default 30).
        The HTTP request timeout is set to ``timeout + 5`` seconds.

    Returns
    -------
    list[dict]
        A list of message objects for every new update.  All messages are
        also appended to the matching ``history/chat_<id>.json`` file so
        they are available offline via :func:`get_chat_history`.

    Notes
    -----
    The offset returned by the last processed update is stored in
    ``history/offset.json``.  Only updates with a higher update_id are
    requested on the next call, which means every message is delivered
    exactly once.
    """
    offset = _load_offset()
    params: dict[str, Any] = {
        "timeout": timeout,
        "allowed_updates": json.dumps(
            ["message", "edited_message", "channel_post", "edited_channel_post"]
        ),
    }
    if offset:
        params["offset"] = offset

    response = requests.get(
        _api_url("getUpdates"),
        params=params,
        timeout=timeout + 5,
    )
    response.raise_for_status()
    data: dict[str, Any] = response.json()

    if not data.get("ok"):
        raise RuntimeError(
            f"Telegram API error: {data.get('description', 'unknown error')}"
        )

    updates: list[dict[str, Any]] = data.get("result", [])
    messages: list[dict[str, Any]] = []
    new_offset = offset

    for update in updates:
        update_id: int = update["update_id"]

        # Extract the message payload regardless of update type.
        msg: dict[str, Any] | None = (
            update.get("message")
            or update.get("edited_message")
            or update.get("channel_post")
            or update.get("edited_channel_post")
        )

        if msg:
            _append_to_history(msg)
            messages.append(msg)

        # Telegram requires offset = last_update_id + 1 to acknowledge.
        if update_id >= new_offset:
            new_offset = update_id + 1

    if new_offset != offset:
        _save_offset(new_offset)

    return messages


def get_chat_history(chat_id: int | str) -> list[dict[str, Any]]:
    """Return all locally cached messages for *chat_id*.

    This reads directly from the ``history/chat_<chat_id>.json`` file and
    never makes a network request.
    """
    return _load_chat_history(chat_id)


def get_known_chat_ids() -> list[int | str]:
    """Return a list of chat IDs for which a local history file exists."""
    _ensure_history_dir()
    chats: list[int | str] = []
    for path in sorted(HISTORY_DIR.glob("chat_*.json")):
        raw = path.stem[len("chat_"):]  # strip leading "chat_"
        chats.append(int(raw) if raw.removeprefix("-").isdigit() else raw)
    return chats
