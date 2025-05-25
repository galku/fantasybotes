import os
import requests
from dotenv import load_dotenv

load_dotenv()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
BASE_API_URL = os.getenv("BASE_API_URL", "https://fantasy.tv2.no/api/")
API_URL = BASE_API_URL + "events/"
BOOTSTRAP_URL = BASE_API_URL + "bootstrap-static/"
DREAM_TEAM_URL = BASE_API_URL + "dream-team/"
PLAYERSTATS_URL = BASE_API_URL + "element-summary/"
FANTASYLIGA_URL = BASE_API_URL + "leagues-classic/"
FANTASYPLAYERDATA_URL = BASE_API_URL + "entry/"


if not DISCORD_WEBHOOK_URL or not BASE_API_URL:
    raise Exception("Miljøvariabler er ikke satt korrekt")

def get_name_lookup():
    r = requests.get(BOOTSTRAP_URL)
    elements = r.json().get("elements", [])
    return {e["id"]: f"{e['first_name']} {e['second_name']}" for e in elements}

def fetch_event():
    r = requests.get(API_URL)
    if r.status_code != 200:
        raise Exception(f"API-kall feilet med statuskode: {r.status_code}")
    data = r.json()
    return next((e for e in data if e.get("is_current")), None)

def fetch_dream_team(event_id):
    r = requests.get(DREAM_TEAM_URL + str(event_id) + "/")
    return r.json()

def format_chip_name(raw_name):
    mapping = {
        "2capt": "To Kapteiner",
        "rich": "Rik Onkel",
        "frush": "Spissrush",
        "wildcard": "Wildcard"
    }
    return mapping.get(raw_name.lower(), raw_name.capitalize())

def format_message(event, name_lookup):
    finished = event.get("finished")
    status_emoji = "✅ Runde ferdig" if finished else "⏳ Runde pågår"
    top_player = name_lookup.get(event["top_element"], "Ukjent")
    top_points = event["top_element_info"]["points"]

    msg = f"{status_emoji}\n"
    msg += f"🔹 Runde {event['id']} - Deadline: {event['deadline_time']}\n"
    msg += f"📊 Overføringer: {event['transfers_made']}\n"
    msg += f"🏋️ Mest valgt: {name_lookup.get(event['most_selected'], 'Ukjent')}\n"
    msg += f"📊 Mest inn: {name_lookup.get(event['most_transferred_in'], 'Ukjent')}\n"
    msg += f"🧙 Kaptein: {name_lookup.get(event['most_captained'], 'Ukjent')}\n"
    msg += f"🤷 Visekaptein: {name_lookup.get(event['most_vice_captained'], 'Ukjent')}\n"
    msg += f"🔝 Toppspiller: {top_player} ({top_points} poeng)\n"
    msg += "\n🧪 Chips brukt:\n"
    for chip in event.get("chip_plays", []):
        chip_name = format_chip_name(chip['chip_name'])
        msg += f"  🎲 {chip_name}: {chip['num_played']}\n"

    if finished:
        dream = fetch_dream_team(event["id"])
        players = [name_lookup.get(p["element"], "Ukjent") for p in dream]
        msg += "\n🌟 Rundens lag:\n"
        for name in players:
            msg += f"  ⚽ {name}\n"

    return msg

def post_to_discord(content):
    payload = {"content": content}
    r = requests.post(DISCORD_WEBHOOK_URL, json=payload)
    print("Posted to Discord:", r.status_code)

def main():
    try:
        event = fetch_event()
        if event:
            names = get_name_lookup()
            message = format_message(event, names)
            post_to_discord(message)
        else:
            print("Ingen aktiv runde funnet.")
    except Exception as e:
        print("Feil ved henting eller posting:", e)

if __name__ == "__main__":
    main()