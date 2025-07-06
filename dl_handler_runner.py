import json
import time
from utils.bootstrap import get_current_gameweek_info
from utils.news_tracker import get_news_since_last_deadline
from utils.deadline_formatter import format_deadline_message
from utils.discord_bot_sender import post_to_discord
from cache_utils import load_cache, save_cache
from main import CACHE_TTL_SECONDS,CACHE_FILE
from bootstrap_runner import SERVERS_FILE

def notify_deadlines():
    print("🔔 Kjører deadline-påminnelse...")
    gameweek = get_current_gameweek_info()
    if not gameweek:
        print("❌ Kunne ikke finne gjeldende runde.")
        return

    event_id = str(gameweek["id"])
    deadline_epoch = gameweek.get("deadline_time_epoch")
    if not deadline_epoch:
        print("❌ Ingen deadline funnet for runden.")
        return

    now = int(time.time())
    seconds_until_deadline = deadline_epoch - now

    if seconds_until_deadline > 2 * 3600:
        print(f"⏱️ Det er fortsatt mer enn 2 timer til deadline ({seconds_until_deadline} sek).")
        return

    cache = load_cache(CACHE_FILE, CACHE_TTL_SECONDS) or {}

    already_posted = cache.get("_posted", [])
    if event_id in already_posted:
        print(f"⏳ Runde {event_id} er allerede postet. Hopper over.")
        return

    # Hent serverdefinisjoner
    with open(SERVERS_FILE, "r", encoding="utf-8") as f:
        SERVERS = json.load(f)

    for server in SERVERS:
        guild_id = server["guild_id"]
        league_id = server["league_id"]
        role_id = server.get("mention_role_id")
        mention = f"<@&{role_id}>" if role_id else ""

        # Lag melding
        header, details = format_deadline_message(gameweek)
        news_summary = get_news_since_last_deadline(gameweek_id=int(event_id), league_id=league_id)
        message = f"{mention} ⏰ Husk å sette opp laget før deadline!\n\n{header}\n\n> {details}\n\n> {news_summary}"

        # Post meldingen
        post_to_discord(
            message=message,
            channel_type="news",
            guild_id=guild_id
        )

    # Oppdater cache
    cache.setdefault("_posted", []).append(event_id)
    save_cache(CACHE_FILE, cache)

if __name__ == "__main__":
    notify_deadlines()