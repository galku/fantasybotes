# utils/bootstrap.py
# Denne håndterer lasting av cache, henter gjeldende runde og gjør om deadlines til lokal tid og Discord-format.

import json
import os
from datetime import datetime, timezone, timedelta

CACHE_FILE = "bootstrap_cache.json"

def load_bootstrap_cache():
    if not os.path.exists(CACHE_FILE):
        raise FileNotFoundError(f"Finner ikke {CACHE_FILE}")

    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def get_current_event(events):
    for event in events:
        if event.get("is_current"):
            return event
    raise ValueError("Fant ingen gjeldende runde")

def get_event_by_id(events, event_id):
    for event in events:
        if event.get("id") == event_id:
            return event
    return None

def deadline_time_to_local(deadline_epoch):
    # Juster for norsk tid (CET/CEST) – tar utgangspunkt i UTC+2
    return datetime.fromtimestamp(deadline_epoch, tz=timezone.utc).astimezone(timezone(timedelta(hours=2)))

def format_discord_timestamp(epoch):
    return f"<t:{epoch}:F>"
