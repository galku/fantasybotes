import json
import os
import time
import traceback

CACHE_TIMESTAMP_FILE = "cache_timestamp.json"


def save_cache(filename, data):
    try:
        with open(filename, "w") as f:
            json.dump(data, f)
        update_cache_timestamp()
    except Exception as e:
        print(f"🚨 Feil ved lagring av cachefil '{filename}': {e}")


def load_cache(filename):
    if not os.path.exists(filename):
        return None
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"🚨 Feil ved lasting av cachefil '{filename}': {e}")
        return None


def update_cache_timestamp():
    try:
        timestamp_data = {"last_updated": int(time.time())}
        with open(CACHE_TIMESTAMP_FILE, "w") as f:
            json.dump(timestamp_data, f)
    except Exception as e:
        print(f"⚠️ Kunne ikke oppdatere cache-timestamp: {e}")


def is_cache_expired(ttl_seconds):
    try:
        if not os.path.exists(CACHE_TIMESTAMP_FILE):
            return True
        with open(CACHE_TIMESTAMP_FILE, "r") as f:
            data = json.load(f)
        last_updated = data.get("last_updated", 0)
        age = time.time() - last_updated
        return age > ttl_seconds
    except Exception as e:
        print(f"⚠️ Feil ved validering av cache-timestamp: {e}")
        return True
