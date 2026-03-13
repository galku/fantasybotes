# posted_tracker.py
# Tracks which automated Discord posts have been sent, keyed by namespaced string.
# Loaded from GCS once at startup and kept in memory; GCS is only written on change.
# Keys: "deadline_reminder_GW{id}", "round_completed_GW{id}"

from gcs_utils import read_json, write_json

TRACKER_FILE = "posted_tracker.json"

# In-memory cache — loaded once, updated on every mark_as_posted() call
_cache: dict | None = None


def _load() -> dict:
    global _cache
    if _cache is None:
        _cache = read_json(TRACKER_FILE)
    return _cache


def has_been_posted(key: str) -> bool:
    return key in _load()


def mark_as_posted(key: str) -> None:
    data = _load()
    data[key] = True
    write_json(TRACKER_FILE, data)  # persist to GCS/disk
