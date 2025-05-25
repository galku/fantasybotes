import os
import json
import time
import requests
import subprocess
from datetime import datetime, timezone
from dotenv import load_dotenv
from cache_utils import load_cache, save_cache

load_dotenv()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
BASE_API_URL = os.getenv("BASE_API_URL")
BOOTSTRAP_CACHE_TTL = int(os.getenv("BOOTSTRAP_CACHE_TTL_MINUTES", 180)) * 60

if not BASE_API_URL:
    raise Exception("BASE_API_URL må settes i .env-filen")

API_URL = BASE_API_URL + "events/"
BOOTSTRAP_URL = BASE_API_URL + "bootstrap-static/"
DREAM_TEAM_URL = BASE_API_URL + "dream-team/"
CACHE_FILE = "cache.json"
BOOTSTRAP_FILE = "bootstrap_cache.json"
CACHE_TTL_SECONDS = 320 * 60

if not DISCORD_WEBHOOK_URL:
    raise Exception("DISCORD_WEBHOOK_URL må settes i .env-filen")

def get_name_lookup():
    cache = load_cache(BOOTSTRAP_FILE, BOOTSTRAP_CACHE_TTL)
    if not cache:
        print("🌐 Henter bootstrap-static på nytt...")
        r = requests.get(BOOTSTRAP_URL)
        cache = r.json()
        save_cache(BOOTSTRAP_FILE, cache)
        print("🚀 Kjører diff-sjekk for bootstrap-static...")
        subprocess.run(["python", "bootstrap_diff.py"])
    else:
        print("📂 Bruker cachet bootstrap-static")

    elements = cache.get("elements", [])
    element_types = {t["id"]: t for t in cache.get("element_types", [])}

    name_map = {e["id"]: f"{e['first_name']} {e['second_name']}" for e in elements}
    type_map = {e["id"]: e["element_type"] for e in elements}
    return name_map, type_map

def save_event_cache(events):
    save_cache(CACHE_FILE, {"events": events})

def fetch_event(event_id: int = None):
    try:
        cache = load_cache(CACHE_FILE, CACHE_TTL_SECONDS)
        if cache and "events" in cache:
            events = cache["events"]
        else:
            response = requests.get(API_URL)
            if response.status_code != 200:
                raise Exception(f"API-kall feilet med statuskode: {response.status_code}")
            events = response.json()
            if not isinstance(events, list):
                raise ValueError(f"Forventet liste fra API, fikk: {type(events)}")
            save_event_cache(events)

        if event_id is not None:
            match = next((ev for ev in events if ev.get("id") == event_id), None)
            if not match:
                print(f"⚠️ Ingen runde med id={event_id} funnet.")
            return match

        return next((ev for ev in events if ev.get("is_current")), None)

    except Exception as e:
        print(f"⚠️ Feil i fetch_event(): {e}")
        return None

def fetch_dream_team(event_id):
    r = requests.get(DREAM_TEAM_URL + str(event_id) + "/")
    return r.json()

def format_chip_name(raw_name):
    mapping = {
        "2capt": ("To Kapteiner", "⚓"),
        "rich": ("Rik Onkel", "💰"),
        "frush": ("Spissrush", "🏎️"),
        "wildcard": ("Wildcard", "🎴")
    }
    return mapping.get(raw_name.lower(), (raw_name.capitalize(), "🎲"))

def format_message(event, name_lookup):
    name_map, type_map = name_lookup

    if event.get("is_current"):
        status_emoji = "🏃 Runde pågår"
    elif event.get("finished"):
        status_emoji = "✅ Runde ferdig"
    else:
        status_emoji = "⏳ Runde ikke startet"

    epoch = event.get("deadline_time_epoch")
    msg = f"🔹 **Runde {event['id']} –** Deadline: <t:{epoch}:F> 🔹\n"

    def name_or_unknown(key):
        val = event.get(key)
        return name_map.get(val, "Ukjent") if val else "?"

    # 🧩 Status & nøkkelinformasjon
    msg += "> **Status:** {}\n".format(status_emoji)
    msg += "> **Overganger:** {}\n".format(event.get('transfers_made', 0))
    msg += "> **Mest valgt:** {} 🏋️\n".format(name_or_unknown('most_selected'))
    msg += "> **Mest inn:** {}\n".format(name_or_unknown('most_transferred_in'))
    msg += "> **Kaptein:** {} 🧑‍✈️\n".format(name_or_unknown('most_captained'))
    msg += "> **Visekaptein:** {} 🧑‍🎓\n".format(name_or_unknown('most_vice_captained'))

    top_info = event.get("top_element_info")
    if isinstance(top_info, dict) and "points" in top_info:
        top_player = name_or_unknown("top_element")
        msg += "> **Toppspiller:** {} ({} poeng) 🫡\n".format(top_player, top_info['points'])
    else:
        msg += "> **Toppspiller:** Ikke tilgjengelig ennå 🫡\n"

    # 📊 Chips brukt
    msg += "\n📊 **Chips brukt:** 📊\n"
    chips = event.get("chip_plays", [])
    if chips:
        msg += "> "  # Start blokksitat
        msg += "\n> ".join(
            f"{format_chip_name(chip['chip_name'])[1]} {format_chip_name(chip['chip_name'])[0]}: {chip['num_played']}"
            for chip in chips
        )
        msg += "\n"
    else:
        msg += "> ⚠️ Data ikke tilgjengelig. Sannsynligvis er ikke runden spilt ennå.\n"

    # 🌟 Rundens lag
    if event.get("finished"):
        dream = fetch_dream_team(event["id"])
        team = dream.get("team", [])
        msg += "\n🌟 **Rundens lag:**\n"
        if team:
            sorted_team = sorted(team, key=lambda x: x.get("position", 99))
            msg += "> "
            msg += "\n> ".join(
                f"{ {1: '🧤', 2: '🛡️', 3: '🍋', 4: '⚔️'}.get(type_map.get(p['element']), '❔') } {name_map.get(p['element'], 'Ukjent')} – {p['points']} poeng"
                for p in sorted_team
            )
            msg += "\n"
        else:
            msg += "> Ingen data for rundens lag.\n"

    return msg

def post_to_discord(content):
    payload = {"content": content}
    r = requests.post(DISCORD_WEBHOOK_URL, json=payload)
    print("Posted to Discord:", r.status_code)

def main():
    try:
        event = fetch_event()
        if event:
            cache = load_cache(CACHE_FILE, CACHE_TTL_SECONDS)
            if cache and str(event['id']) in cache.get("_posted", []):
                print(f"⏳ Runde {event['id']} er allerede postet. Hopper over.")
                return

            names = get_name_lookup()
            message = format_message(event, names)
            post_to_discord(message)

            if cache:
                cache.setdefault("_posted", []).append(str(event['id']))
                save_event_cache(cache["events"])
        else:
            print("🚫 Ingen aktiv runde funnet.")
    except Exception as e:
        print("Feil ved henting eller posting:", e)

if __name__ == "__main__":
    main()
