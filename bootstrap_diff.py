import os
import json
import subprocess
import traceback
from utils.discord_bot_sender import post_to_discord

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
        result = subprocess.run(
            ["python", "bootstrap_diff.py"], capture_output=True, text=True, timeout=60
        )

        if result.returncode != 0:
            error_msg = f"🚨 Feil i bootstrap_diff.py: {result.stderr.strip()}"
            print(error_msg)
            for server in SERVERS:
                try:
                    post_to_discord(server["log_channel_id"], error_msg)
                except Exception as e:
                    print(f"⚠️ Feil ved sending til {server['guild_name']}: {e}")
            return

        output = result.stdout.strip()

        if not output:
            msg = "⚠️ Ingen output fra bootstrap_diff.py."
            print(msg)
            for server in SERVERS:
                try:
                    post_to_discord(server["log_channel_id"], msg)
                except Exception as e:
                    print(f"⚠️ Feil ved sending til {server['guild_name']}: {e}")
            return

        # Nyhetsblokk
        if "🔔" in output:
            lines = output.splitlines()
            news_block = "\n".join(
                line for line in lines if line.startswith(("🔔", "📉", "📈", "📰"))
            )
            if news_block:
                for server in SERVERS:
                    try:
                        post_to_discord(server["news_channel_id"], news_block)
                    except Exception as e:
                        print(f"⚠️ Feil ved nyhets-posting til {server['guild_name']}: {e}")
            else:
                print("⚠️ Fant ikke formatert nyhetsblokk.")

        else:
            for server in SERVERS:
                try:
                    post_to_discord(server["log_channel_id"], "✅ Ingen relevante endringer funnet.")
                except Exception as e:
                    print(f"⚠️ Feil ved logg-posting til {server['guild_name']}: {e}")

        # Snapshot
        if "💾" in output:
            snapshot_line = next((line for line in output.splitlines() if line.startswith("💾")), None)
            if snapshot_line:
                for server in SERVERS:
                    try:
                        post_to_discord(server["log_channel_id"], snapshot_line)
                    except Exception as e:
                        print(f"⚠️ Feil ved snapshot-posting til {server['guild_name']}: {e}")

    except subprocess.TimeoutExpired:
        timeout_msg = "⏱️ bootstrap_diff.py brukte for lang tid (>60s) og ble stoppet."
        print(timeout_msg)
        for server in SERVERS:
            try:
                post_to_discord(server["log_channel_id"], timeout_msg)
            except Exception as e:
                print(f"⚠️ Feil ved timeout-posting til {server['guild_name']}: {e}")

    except Exception as e:
        err_trace = traceback.format_exc()
        print(f"🚨 Uventet feil: {e}\n{err_trace}")
        for server in SERVERS:
            try:
                post_to_discord(server["log_channel_id"], f"🚨 Unntak:\n{e}\n{err_trace}")
            except Exception as inner_e:
                print(f"⚠️ Feil ved feilhåndtering for {server['guild_name']}: {inner_e}")

if __name__ == "__main__":
    run_diff()