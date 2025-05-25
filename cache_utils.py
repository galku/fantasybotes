import os
import json
import time
from typing import Optional


def load_cache(filename: str, ttl_seconds: int) -> Optional[dict]:
    """Laster cache fra fil hvis den er gyldig ut fra TTL."""
    if not os.path.exists(filename):
        return None
    try:
        with open(filename, "r") as f:
            data = json.load(f)
            timestamp = data.get("_timestamp")
            if not timestamp or time.time() - timestamp > ttl_seconds:
                print(f"🔁 Cache '{filename}' er utløpt.")
                return None
            return data
    except Exception as e:
        print(f"⚠️ Kunne ikke laste cache fra {filename}: {e}")
        return None


def save_cache(filename: str, content: dict):
    """Lagrer cache til fil med nytt tidsstempel."""
    try:
        with open(filename, "w") as f:
            json.dump({"_timestamp": time.time(), **content}, f, indent=2)
        print(f"💾 Cache lagret til {filename}")
    except Exception as e:
        print(f"⚠️ Kunne ikke skrive cache til {filename}: {e}")
