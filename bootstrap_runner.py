import os
import json
import subprocess
import traceback
from utils.discord_bot_sender import post_to_discord

# Last inn servers.json
SERVERS_FILE = "servers.json"

try:
    with open(SERVERS_FILE, "r") as f:
        SERVERS = json.load(f)
except FileNotFoundError:
    print(f"❌ Fant ikke {SERVERS_FILE}. Sørg for at fila eksisterer.")
    SERVERS = []
except json.JSONDecodeError as e:
    print(f"🚨 Klarte ikke parse {SERVERS_FILE}: {e}")
    SERVERS = []

def run_diff():
    print("🔍 Kjører bootstrap_diff.py...")
    try:
        import sys
        python_executable = sys.executable
        result = subprocess.run([python_executable, "bootstrap_diff.py"], capture_output=True, text=True)

        if result.returncode != 0:
            error_msg = f"🚨 Feil i bootstrap_diff.py: {result.stderr.strip()}"
            print(error_msg)
            for server in SERVERS:
                post_to_discord(guild_id=server["guild_id"], message=error_msg, channel_type="log")
            return

        output = result.stdout.strip()

        if "🔔" in output:
            # Finn nyhetslinjer og send til nyhetskanaler
            lines = output.splitlines()
            news_block = "\n".join(line for line in lines if line.startswith("🔔") or line.startswith("📉") or line.startswith("📈") or line.startswith("📰"))
            if news_block:
                for server in SERVERS:
                    post_to_discord(guild_id=server["guild_id"], message=news_block, channel_type="news")
            else:
                print("⚠️ Fant ikke formatert nyhetsblokk.")
        else:
            # Ingen relevante endringer
            for server in SERVERS:
                post_to_discord(guild_id=server["guild_id"], message="✅ Ingen relevante endringer funnet.", channel_type="log")

        if "💾" in output:
            snapshot_line = next((line for line in output.splitlines() if line.startswith("💾")), None)
            if snapshot_line:
                for server in SERVERS:
                    post_to_discord(guild_id=server["guild_id"], message=snapshot_line, channel_type="log")

    except Exception as e:
        err_trace = traceback.format_exc()
        print(f"🚨 Unntak: {e}\n{err_trace}")
        for server in SERVERS:
            post_to_discord(guild_id=server["guild_id"], message=f"🚨 Unntak i bootstrap_runner:\n{e}\n{err_trace}", channel_type="log")

if __name__ == "__main__":
    run_diff()
