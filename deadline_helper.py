# deadline_helper.py
# Funksjonalitet for å håndtere deadline-relaterte operasjoner i Eliteserien Fantasy.
#	•	lasting og parsing av bootstrap_cache.json
#	•	logikk for å finne nåværende og forrige runde
#	•	støtte for Discord timestamps og tidspunktberegning

import json
import time
from datetime import datetime, timezone

def load_bootstrap_cache(path="bootstrap_cache.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_current_event(bootstrap):
    return next((e for e in bootstrap["events"] if e.get("is_current")), None)

def get_previous_event(bootstrap):
    current_index = next((i for i, e in enumerate(bootstrap["events"]) if e.get("is_current")), None)
    if current_index and current_index > 0:
        return bootstrap["events"][current_index - 1]
    return None

def format_discord_timestamp(epoch):
    return f"<t:{epoch}:F>"

def is_time_to_post(deadline_epoch, offset_hours=6):
    now = int(time.time())
    scheduled_time = deadline_epoch - offset_hours * 3600
    return scheduled_time <= now < scheduled_time + 60

def build_deadline_message(event, bootstrap):
    deadline_epoch = event["deadline_time_epoch"]
    readable_time = format_discord_timestamp(deadline_epoch)

    most_selected = next((p for p in bootstrap["elements"] if p["id"] == event.get("most_selected_player")), None)
    most_captained = next((p for p in bootstrap["elements"] if p["id"] == event.get("most_captained_player")), None)

    chips = event.get("chip_plays", [])
    chip_summary = "\n".join(f"{c['chip_name'].capitalize()}: {c['num_played']}" for c in chips) or "Ingen chips brukt"

    message = f"**Runde {event['id']}** \n> ⏳ Deadline: {readable_time}\n> 👥 Mest valgt: {most_selected['web_name'] if most_selected else 'Ukjent'}\n> 🎯 Mest kaptein: {most_captained['web_name'] if most_captained else 'Ukjent'}\n\n> **Chips brukt:**\n> {chip_summary}"
    return message

if __name__ == "__main__":
    bs = load_bootstrap_cache()
    event = get_current_event(bs)
    print(build_deadline_message(event, bs))
