# dl_handler_runner.py
# Synkron versjon med klar struktur og modularitet

import json
from utils.bootstrap import get_current_gameweek_info
from utils.news_tracker import get_news_since_last_deadline
from utils.deadline_formatter import format_deadline_message
from utils.discord_bot_sender import post_to_discord

SERVERS_FILE = "servers.json"

# Hent serverdefinisjoner
with open(SERVERS_FILE, "r") as f:
    SERVERS = json.load(f)

def notify_deadlines():
    print("🔔 Kjører deadline-påminnelse...")
    gameweek = get_current_gameweek_info()
    if not gameweek:
        print("❌ Kunne ikke finne gjeldende runde.")
        return

    for server in SERVERS:
        league_id = server.get("league_id")
        guild_id = server.get("guild_id")

        # Lag meldingen om deadline
        header, details = format_deadline_message(gameweek)

        # Hent relevante nyheter siden forrige deadline
        news_summary = get_news_since_last_deadline(gameweek_id=gameweek["id"], league_id=league_id)

        # Slå sammen alt til én blokk
        combined_message = f"{header}\n\n> {details}\n\n> {news_summary}"

        # Post til nyhetskanalen
        post_to_discord(
            message=combined_message,
            channel_type="news",
            guild_id=guild_id
        )

if __name__ == "__main__":
    notify_deadlines()
