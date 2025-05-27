import os
import subprocess
import json
from utils.discord_bot_sender import post_to_discord

SERVERS_FILE = "servers.json"

def load_servers():
    try:
        with open(SERVERS_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"🚨 Klarte ikke laste {SERVERS_FILE}: {e}")
        return []

def run_diff():
    try:
        print("🔍 Kjører bootstrap_diff.py...")
        result = subprocess.run(["python", "bootstrap_diff.py"], capture_output=True, text=True)

        if result.returncode != 0:
            print(f"🚨 Feil i bootstrap_diff.py: {result.stderr}")
            for server in load_servers():
                post_to_discord(f"🚨 Feil i bootstrap_diff.py: {result.stderr}", channel_type="log", guild_id=server["guild_id"])
            return

        output = result.stdout.strip()
        if output:
            for server in load_servers():
                post_to_discord(output, channel_type="news", guild_id=server["guild_id"])
        else:
            for server in load_servers():
                post_to_discord("✅ Ingen relevante endringer funnet.\n💾 Lagret snapshot av bootstrap_static for neste sammenligning.", channel_type="log", guild_id=server["guild_id"])

    except Exception as e:
        print(f"🚨 Feil ved kjøring av bootstrap_runner: {e}")
        for server in load_servers():
            post_to_discord(f"🚨 Feil ved kjøring av bootstrap_runner: {e}", channel_type="log", guild_id=server["guild_id"])

if __name__ == "__main__":
    run_diff()
