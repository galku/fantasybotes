import os
import json
import subprocess
import traceback
from utils.discord_bot_sender import post_to_discord
from dotenv import load_dotenv
load_dotenv()

SERVERS_FILE = "servers.json"

try:
    with open(SERVERS_FILE, "r") as f:
        SERVERS = json.load(f)
except (FileNotFoundError, json.JSONDecodeError) as e:
    print(f"🚨 Feil ved lasting av {SERVERS_FILE}: {e}")
    SERVERS = []

def run_diff():
    print("🔍 Kjører bootstrap_diff.py...")
    try:
        result = subprocess.run(["python3", "bootstrap_diff.py"], capture_output=True, text=True)

        output = result.stdout.strip()
        if result.returncode != 0:
            error_msg = f"🚨 Feil i bootstrap_diff.py: {result.stderr.strip()}"
            print(error_msg)
            for server in SERVERS:
                post_to_discord(error_msg, server["guild_id"], channel_type="log")
            return

        lines = output.splitlines()
        snapshot_line = next((line for line in lines if line.startswith("💾")), None)

        news_lines = [line for line in lines if not line.startswith("💾")]
        if news_lines:
            news_block = "\n".join(news_lines)
            for server in SERVERS:
                post_to_discord(news_block, server["guild_id"], channel_type="news")
        else:
            for server in SERVERS:
                post_to_discord("✅ Ingen relevante endringer funnet.", server["guild_id"], channel_type="log")

        if snapshot_line:
            for server in SERVERS:
                post_to_discord(snapshot_line, server["guild_id"], channel_type="log")

    except Exception as e:
        err_trace = traceback.format_exc()
        print(f"🚨 Unntak i bootstrap_runner: {e}\n{err_trace}")
        for server in SERVERS:
            post_to_discord(
                f"🚨 Unntak i bootstrap_runner:\n{e}\n{err_trace}",
                server["guild_id"],
                channel_type="log"
            )

if __name__ == "__main__":
    run_diff()