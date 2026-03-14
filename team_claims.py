# team_claims.py
# Maps Discord user IDs to their claimed FPL team entry.
# Stored in GCS (or local fallback), memory-first like posted_tracker.

from gcs_utils import read_json, write_json

CLAIMS_FILE = "team_claims.json"
_cache: dict | None = None


def _load() -> dict:
    global _cache
    if _cache is None:
        _cache = read_json(CLAIMS_FILE, default={})
    return _cache


def get_claim(discord_user_id) -> dict | None:
    """Return {entry_id, entry_name, discord_name} for a Discord user, or None."""
    return _load().get(str(discord_user_id))


def set_claim(discord_user_id, entry_id: int, entry_name: str, discord_name: str) -> None:
    data = _load()
    data[str(discord_user_id)] = {
        "entry_id": entry_id,
        "entry_name": entry_name,
        "discord_name": discord_name,
    }
    write_json(CLAIMS_FILE, data)


def find_by_discord_name(name: str) -> dict | None:
    """Find a claim by stored Discord display name (case-insensitive exact match)."""
    name_lower = name.lower()
    for claim in _load().values():
        if claim.get("discord_name", "").lower() == name_lower:
            return claim
    return None


def find_by_entry_id(entry_id: int) -> dict | None:
    """Return the claim for a given entry_id if already taken, else None."""
    for claim in _load().values():
        if claim.get("entry_id") == entry_id:
            return claim
    return None
