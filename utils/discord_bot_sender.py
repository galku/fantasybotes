# utils/discord_bot_sender.py

import os
import json
import asyncio
import discord
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CONFIG_FILE = "servers.json"

try:
    with open(CONFIG_FILE, "r") as f:
        SERVER_CONFIG = json.load(f)
except Exception as e:
    print(f"🚨 Feil ved lasting av {CONFIG_FILE}: {e}")
    SERVER_CONFIG = []

def get_channel_id(guild_id, channel_type="log"):
    for server in SERVER_CONFIG:
        if server.get("guild_id") == guild_id:
            return server.get(f"{channel_type}_channel_id")
    print(f"⚠️ Fant ikke konfigurasjon for guild {guild_id}")
    return None

class DiscordMessenger(discord.Client):
    def __init__(self, message, channel_id):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.message = message
        self.channel_id = int(channel_id)

    async def on_ready(self):
        try:
            channel = self.get_channel(self.channel_id)
            if channel is None:
                print(f"❌ Fant ikke kanal med ID: {self.channel_id}")
            else:
                await channel.send(self.message)
                print(f"✅ Sendte melding til kanal {self.channel_id}")
        except Exception as e:
            print(f"🚨 Feil under sending av melding: {e}")
        await self.close()

def post_to_discord(guild_id, message, channel_type="log"):
    channel_id = get_channel_id(guild_id, channel_type)
    if not channel_id:
        print(f"🚫 Ingen kanal-ID funnet for type '{channel_type}' i guild {guild_id}")
        return
    try:
        print(f"📬 Sender melding til guild {guild_id}, kanal-type '{channel_type}' med ID: {channel_id}")
        loop = asyncio.get_event_loop()
        loop.run_until_complete(DiscordMessenger(message, channel_id).start(TOKEN))
    except Exception as e:
        print(f"🚨 Klarte ikke poste til Discord: {e}")