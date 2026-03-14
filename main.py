import os
import json
import time
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from cache_utils import load_cache, save_cache

load_dotenv()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
BASE_API_URL = os.getenv("BASE_API_URL")

if not BASE_API_URL:
    raise Exception("BASE_API_URL må settes i .env-filen")

API_URL = BASE_API_URL + "events/"
BOOTSTRAP_URL = BASE_API_URL + "bootstrap-static/"
DREAM_TEAM_URL = BASE_API_URL + "dream-team/"
LEAGUES_URL = BASE_API_URL + "leagues-classic/"
ENTRY_URL = BASE_API_URL + "entry/"

# ---------------------------------------------------------------------------
# Cache TTL configuration — all overridable via .env (values in minutes)
#
#   BOOTSTRAP_CACHE_TTL_MINUTES   default 180   bootstrap-static (spillere, lag)
#   EVENTS_CACHE_TTL_MINUTES      default 320   events-liste (runder, deadlines)
#   STANDINGS_CACHE_TTL_MINUTES   default 120   ligatabell
#   LIVE_CACHE_TTL_MINUTES        default 120   live-poeng per runde
#   PICKS_CACHE_TTL_MINUTES       default 10080 lagoppstilling per entry/GW (7 dager)
#   DREAM_TEAM_CACHE_TTL_MINUTES  default 10080 rundens lag (7 dager)
# ---------------------------------------------------------------------------
BOOTSTRAP_CACHE_TTL   = int(os.getenv("BOOTSTRAP_CACHE_TTL_MINUTES",  180))   * 60
EVENTS_CACHE_TTL      = int(os.getenv("EVENTS_CACHE_TTL_MINUTES",     320))   * 60
STANDINGS_CACHE_TTL   = int(os.getenv("STANDINGS_CACHE_TTL_MINUTES",  120))   * 60
LIVE_CACHE_TTL        = int(os.getenv("LIVE_CACHE_TTL_MINUTES",       120))   * 60
PICKS_CACHE_TTL       = int(os.getenv("PICKS_CACHE_TTL_MINUTES",      10080)) * 60
DREAM_TEAM_CACHE_TTL  = int(os.getenv("DREAM_TEAM_CACHE_TTL_MINUTES", 10080)) * 60

CACHE_FILE      = "cache.json"
BOOTSTRAP_FILE  = "bootstrap_cache.json"


def get_bootstrap_data() -> dict:
    """Return full bootstrap-static data (player list, teams, etc.), cached."""
    cache = load_cache(BOOTSTRAP_FILE, BOOTSTRAP_CACHE_TTL)
    if not cache:
        print("🌐 Henter bootstrap-static på nytt...")
        r = requests.get(BOOTSTRAP_URL)
        cache = r.json()
        save_cache(BOOTSTRAP_FILE, cache)
    else:
        print("📂 Bruker cachet bootstrap-static")
    return cache


def get_name_lookup():
    cache = get_bootstrap_data()
    elements = cache.get("elements", [])
    name_map = {e["id"]: f"{e['first_name']} {e['second_name']}" for e in elements}
    type_map = {e["id"]: e["element_type"] for e in elements}
    return name_map, type_map


def _load_events() -> list:
    """Return events list from cache or API, saving to cache on fetch."""
    cache_data = load_cache(CACHE_FILE, EVENTS_CACHE_TTL)
    if cache_data and "events" in cache_data:
        return cache_data["events"]
    response = requests.get(API_URL)
    if response.status_code != 200:
        raise Exception(f"API-kall feilet med statuskode: {response.status_code}")
    events = response.json()
    if not isinstance(events, list):
        raise ValueError(f"Forventet liste fra API, fikk: {type(events)}")
    save_cache(CACHE_FILE, {"events": events})
    return events


def fetch_event(event_id: int = None):
    try:
        events = _load_events()
        if event_id is not None:
            return next((ev for ev in events if ev.get("id") == event_id), None)
        return next((ev for ev in events if ev.get("is_current")), None)
    except Exception as e:
        print(f"⚠️ Feil i fetch_event(): {e}")
        return None


def fetch_upcoming_event():
    """Return the current active event, or the next upcoming one if between rounds."""
    try:
        events = _load_events()
        current = next((ev for ev in events if ev.get("is_current")), None)
        if current:
            return current
        now = int(time.time())
        upcoming = [ev for ev in events if (ev.get("deadline_time_epoch") or 0) > now]
        return min(upcoming, key=lambda e: e["deadline_time_epoch"]) if upcoming else None
    except Exception as e:
        print(f"⚠️ Feil i fetch_upcoming_event(): {e}")
        return None


def fetch_all_events() -> list:
    """Return list of all gameweek events, respecting events cache TTL."""
    try:
        return _load_events()
    except Exception as e:
        print(f"⚠️ Feil i fetch_all_events(): {e}")
        return []


def fetch_dream_team(event_id: int) -> dict:
    cache_file = f"dream_team_{event_id}.json"
    cached = load_cache(cache_file, DREAM_TEAM_CACHE_TTL)
    if cached:
        return cached
    r = requests.get(DREAM_TEAM_URL + str(event_id) + "/")
    data = r.json()
    save_cache(cache_file, data)
    return data


def fetch_league_standings(league_id: int) -> dict:
    """Return standings for a classic league, fetching all pages. Cached."""
    cache_file = f"standings_{league_id}.json"
    cached = load_cache(cache_file, STANDINGS_CACHE_TTL)
    if cached:
        return cached

    url = LEAGUES_URL + str(league_id) + "/standings/"
    r = requests.get(url)
    r.raise_for_status()
    data = r.json()

    all_results = list(data.get("standings", {}).get("results", []))
    page = 1
    while data.get("standings", {}).get("has_next", False):
        page += 1
        r = requests.get(url, params={"page_standings": page})
        r.raise_for_status()
        data = r.json()
        all_results.extend(data.get("standings", {}).get("results", []))

    data.setdefault("standings", {})["results"] = all_results
    save_cache(cache_file, data)
    return data


def fetch_live_event(event_id: int) -> dict:
    """Return live points for all elements in a gameweek. Cached."""
    cache_file = f"live_{event_id}.json"
    cached = load_cache(cache_file, LIVE_CACHE_TTL)
    if cached:
        return cached
    r = requests.get(API_URL + str(event_id) + "/live/")
    r.raise_for_status()
    data = r.json()
    save_cache(cache_file, data)
    return data


def fetch_entry_picks(entry_id: int, event_id: int) -> dict:
    """Return picks for a team in a specific gameweek. Cached per entry/GW."""
    cache_file = f"picks_{entry_id}_{event_id}.json"
    cached = load_cache(cache_file, PICKS_CACHE_TTL)
    if cached:
        return cached
    r = requests.get(ENTRY_URL + str(entry_id) + f"/event/{event_id}/picks/")
    r.raise_for_status()
    data = r.json()
    save_cache(cache_file, data)
    return data


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

    msg += "\n📊 **Chips brukt:** 📊\n"
    chips = event.get("chip_plays", [])
    if chips:
        msg += "> " + "\n> ".join(
            f"{format_chip_name(c['chip_name'])[1]} {format_chip_name(c['chip_name'])[0]}: {c['num_played']}"
            for c in chips
        ) + "\n"
    else:
        msg += "> ⚠️ Data ikke tilgjengelig. Sannsynligvis er ikke runden spilt ennå.\n"

    if event.get("finished"):
        dream = fetch_dream_team(event["id"])
        team = dream.get("team", [])
        msg += "\n🌟 **Rundens lag:**\n"
        if team:
            sorted_team = sorted(team, key=lambda x: x.get("position", 99))
            msg += "> " + "\n> ".join(
                f"{ {1: '🧤', 2: '🛡️', 3: '🍋', 4: '⚔️'}.get(type_map.get(p['element']), '❔') } {name_map.get(p['element'], 'Ukjent')} – {p['points']} poeng"
                for p in sorted_team
            ) + "\n"
        else:
            msg += "> Ingen data for rundens lag.\n"

    return msg


def post_to_discord(content):
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ DISCORD_WEBHOOK_URL er ikke satt — kan ikke sende webhook.")
        return
    payload = {"content": content}
    r = requests.post(DISCORD_WEBHOOK_URL, json=payload)
    print("Posted to Discord:", r.status_code)


def main():
    try:
        event = fetch_event()
        if event:
            cache = load_cache(CACHE_FILE, EVENTS_CACHE_TTL)
            if cache and str(event['id']) in cache.get("_posted", []):
                print(f"⏳ Runde {event['id']} er allerede postet. Hopper over.")
                return

            names = get_name_lookup()
            message = format_message(event, names)
            post_to_discord(message)

            if cache:
                cache.setdefault("_posted", []).append(str(event['id']))
                save_cache(CACHE_FILE, cache)

        else:
            print("🚫 Ingen aktiv runde funnet.")

    except Exception as e:
        print("Feil ved henting eller posting:", e)


if __name__ == "__main__":
    main()
