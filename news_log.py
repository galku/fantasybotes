# news_log.py
# Rolling log of bootstrap change entries (player news + price changes).
# Stored via GCS when available, local file otherwise.
# Used by !nyheter and !skade commands.

import time
from gcs_utils import read_json, write_json

NEWS_LOG_FILE = "news_log.json"
MAX_ENTRIES = 300  # keep the last 300 entries in the log


def append_entries(entries: list[dict]) -> None:
    """Append entries to the rolling log. Each entry: {type, text, ts}"""
    existing = read_json(NEWS_LOG_FILE, default=[])
    if not isinstance(existing, list):
        existing = []
    combined = (existing + entries)[-MAX_ENTRIES:]
    write_json(NEWS_LOG_FILE, combined)


def get_recent(n: int, entry_type: str = None) -> list[dict]:
    """Return up to n recent entries, newest first. Filter by type if given."""
    data = read_json(NEWS_LOG_FILE, default=[])
    if not isinstance(data, list):
        return []
    if entry_type:
        data = [e for e in data if e.get("type") == entry_type]
    return list(reversed(data[-n:]))
