# 📊 bootstrap_diff.py – sammenligner ny og gammel bootstrap-static

import os
import json
import requests
from cache_utils import load_cache, save_cache
from dotenv import load_dotenv

load_dotenv()

BOOTSTRAP_FILE = "bootstrap_cache.json"
PREVIOUS_FILE = "bootstrap_previous.json"
NEWS_CHANNEL_ID = os.getenv("DISCORD_NEWS_CHANNEL_ID")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")


def load_latest_bootstrap():
    if not os.path.exists(BOOTSTRAP_FILE):
        print("🚫 Fant ikke cachet bootstrap-static.")
        return None
    with open(BOOTSTRAP_FILE, "r") as f:
        return json.load(f)


def load_previous():
    if not os.path.exists(PREVIOUS_FILE):
        return {}
    with open(PREVIOUS_FILE, "r") as f:
        return json.load(f)


def detect_changes(new_data, old_data):
    messages = []
    new_elements = {e["id"]: e for e in new_data.get("elements", [])}
    old_elements = {e["id"]: e for e in old_data.get("elements", [])}

    for player_id, new in new_elements.items():
        old = old_elements.get(player_id)
        if not old:
            continue

        name = f"{new['first_name']} {new['second_name']}"

        # Prisendringer med datainnlegg for å legge til "komma" (e.g. Kasper Høgh som 10.9 fremfor 109)
        try:
            new_value = float(new.get("now_cost", 0)) / 10
            old_value = float(old.get("now_cost", 0)) / 10
        except (TypeError, ValueError):
            continue

        if new_value != old_value:
            delta = new_value - old_value
            emoji = "📈" if delta > 0 else "📉"
            messages.append(f"{emoji} {name} prisendring: {old_value:.1f} ➝ {new_value:.1f}")

        # Nyheter
        if new.get("news") and new.get("news") != old.get("news"):
            messages.append(f"📰 {name} – Nyhet: {new['news']}")

    return messages


def save_current_as_previous():
    try:
        with open(BOOTSTRAP_FILE, "r") as f:
            current = json.load(f)
        with open(PREVIOUS_FILE, "w") as f:
            json.dump(current, f, indent=2)
        print("💾 Lagret snapshot av bootstrap_static for neste sammenligning.")
    except Exception as e:
        print(f"⚠️ Klarte ikke lagre snapshot: {e}")


def post_to_discord_channel(content: str):
    if not DISCORD_BOT_TOKEN or not NEWS_CHANNEL_ID:
        print("🚫 Discord-token eller kanal-ID mangler.")
        return

    url = f"https://discord.com/api/v10/channels/{NEWS_CHANNEL_ID}/messages"
    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {"content": content[:2000]}

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200 or response.status_code == 204:
        print("✅ Endringer postet til Discord.")
    else:
        print(f"⚠️ Feil ved posting til Discord: {response.status_code} – {response.text}")


if __name__ == "__main__":
    new_data = load_latest_bootstrap()
    old_data = load_previous()

    if new_data and old_data:
        changes = detect_changes(new_data, old_data)
        if changes:
            message = "**🔔 Oppdateringer i Fantasy-data:**\n" + "\n".join(f"> {line}" for line in changes)
            print(message)
            post_to_discord_channel(message)
        else:
            print("✅ Ingen relevante endringer funnet.")
    else:
        print("⚠️ Mangler data for sammenligning.")

    save_current_as_previous()