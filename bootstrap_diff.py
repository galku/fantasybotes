# bootstrap_diff.py
import os
import sys
import json
import requests
from datetime import datetime
from cache_utils import save_cache
from utils.discord_bot_sender import post_to_discord
from dotenv import load_dotenv

load_dotenv()

BOOTSTRAP_URL = os.getenv("BASE_API_URL") + "bootstrap-static/"
PREVIOUS_FILE = "bootstrap_previous.json"

# Hent servers.json for direktekjøring
with open("servers.json", "r") as f:
    SERVER_CONFIGS = json.load(f)


def fetch_bootstrap_data():
    print("📡 Laster ned bootstrap-static fra API")
    try:
        response = requests.get(BOOTSTRAP_URL)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"🚨 Feil ved henting av bootstrap: {e}", file=sys.stderr)
        return None


def load_previous_data():
    print(f"📂 Laster tidligere cache fra {PREVIOUS_FILE}")
    try:
        with open(PREVIOUS_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Kunne ikke laste tidligere cache: {e}", file=sys.stderr)
        return None


def compare_players(current, previous):
    output = []
    team_lookup = {team["code"]: team["name"] for team in current.get("teams", [])}
    prev_players = {p["id"]: p for p in previous.get("elements", [])} if previous else {}

    print(f"🔍 Sammenligner {len(current.get('elements', []))} spillere")

    for player in current.get("elements", []):
        pid = player["id"]
        name = f"{player['first_name']} {player['second_name']}"
        team_name = team_lookup.get(player["team_code"], "Ukjent lag")
        prev = prev_players.get(pid)

        if not prev:
            continue

        if player["now_cost"] != prev.get("now_cost"):
            old = prev["now_cost"] / 10
            new = player["now_cost"] / 10
            emoji = "📈" if new > old else "📉"
            output.append(f"{emoji} Prisendring for {name} ({team_name}): {old:.1f} ➝ {new:.1f}")

        if player["news"] and player["news"] != prev.get("news", ""):
            output.append(f"📰 Nyhet for {name} ({team_name}): {player['news']}")

    return output


def main():
    current = fetch_bootstrap_data()
    if not current:
        return None

    previous = load_previous_data()
    messages = compare_players(current, previous)

    save_cache(PREVIOUS_FILE, current)

    if messages:
        combined = "\n".join(["🔔 Oppdateringer i Fantasy-data:"] + messages)
        print("✅ Endringer funnet. Sender til nyhetskanaler...")
        return combined
    else:
        print("✅ Ingen relevante endringer funnet.")
        return None


if __name__ == "__main__":
    try:
        result = main()
        for server in SERVER_CONFIGS:
            guild_id = server["guild_id"]
            if result:
                post_to_discord(result, guild_id=guild_id, channel_type="news")
            else:
                post_to_discord("✅ Ingen endringer å vise i direkte kjøring.", guild_id=guild_id, channel_type="log")
    except Exception as e:
        print(f"🛑 Uventet feil i bootstrap_diff: {e}", file=sys.stderr)