# server_state.py
# Tracks per-guild bot state: whether automatic posting and command listening
# are active. Persisted to GCS so state survives restarts.

from gcs_utils import read_json, write_json

STATE_FILE = "server_state.json"
_cache: dict | None = None


def _load() -> dict:
    global _cache
    if _cache is None:
        _cache = read_json(STATE_FILE, default={})
    return _cache


def _save(data: dict) -> None:
    global _cache
    _cache = data
    write_json(STATE_FILE, data)


def get_state(guild_id) -> dict:
    """Return {posting, listening} for a guild. Both default to True."""
    return _load().get(str(guild_id), {"posting": True, "listening": True})


def is_posting(guild_id) -> bool:
    """True if the bot should send automatic posts (tasks) to this guild."""
    return get_state(guild_id).get("posting", True)


def is_listening(guild_id) -> bool:
    """True if the bot should respond to commands from this guild."""
    return get_state(guild_id).get("listening", True)


def set_state(guild_id, *, posting: bool, listening: bool) -> None:
    data = _load()
    data[str(guild_id)] = {"posting": posting, "listening": listening}
    _save(data)
