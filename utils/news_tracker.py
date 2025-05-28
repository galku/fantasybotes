# utils/news_tracker.py

import json
import os
from datetime import datetime

NEWS_LOG_FILE = "news_log.json"

# Les inn tidligere lagrede nyheter

def load_news_log():
    if not os.path.exists(NEWS_LOG_FILE):
        return {}
    try:
        with open(NEWS_LOG_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

# Lagre oppdatert nyhetslogg
def save_news_log(log_data):
    with open(NEWS_LOG_FILE, "w") as f:
        json.dump(log_data, f, indent=2)

# Returnerer summerte nyheter siden forrige deadline (placeholder)
def get_news_since_last_deadline(gameweek_id: int, league_id: int) -> str:
    log_data = load_news_log()

    # Midlertidig - disse skal hentes fra ekte endringskilder senere
    fresh_news = {
        "123": ["🔔 Skadet igjen!", "📈 Verdien har steget 0.1M"],
        "234": ["📰 Ny kontrakt signert"]
    }

    league_log = log_data.setdefault(str(league_id), {})
    gw_log = league_log.setdefault(str(gameweek_id), {})

    # Finn kun nye nyheter (ikke duplikater)
    new_entries = {}
    for player_id, messages in fresh_news.items():
        existing = gw_log.setdefault(player_id, [])
        for msg in messages:
            if msg not in existing:
                existing.append(msg)
                new_entries.setdefault(player_id, []).append(msg)

    save_news_log(log_data)

    if not new_entries:
        return "Ingen nye spilleroppdateringer siden forrige runde."

    # Returner oppsummert blokkmelding
    summary_lines = []
    for pid, msgs in new_entries.items():
        player_block = f"Spiller {pid}:\n" + "\n".join(msgs)
        summary_lines.append(player_block)

    return "\n\n".join(summary_lines)
