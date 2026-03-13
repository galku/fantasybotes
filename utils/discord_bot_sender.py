# utils/discord_bot_sender.py

import os
import discord
import asyncio
import json
from discord import Embed
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

_SERVER_CONFIGS = None

def _get_server_configs():
    global _SERVER_CONFIGS
    if _SERVER_CONFIGS is None:
        with open("servers.json", "r") as f:
            _SERVER_CONFIGS = json.load(f)
    return _SERVER_CONFIGS

intents = discord.Intents.default()

class DiscordMessenger(discord.Client):
    def __init__(self, channel_id, message=None, embed=None):
        super().__init__(intents=intents)
        self.channel_id = channel_id
        self.message = message
        self.embed = embed

    async def on_ready(self):
        try:
            channel = await self.fetch_channel(self.channel_id)
            if not isinstance(channel, discord.TextChannel):
                print(f"🚫 Kanal-ID {self.channel_id} er ikke en tekstkanal.")
            else:
                if self.embed:
                    await channel.send(embed=self.embed)
                    print(f"✅ Melding sendt til kanal {channel.name} (embed).")
                elif self.message:
                    for msg in split_message(self.message):
                        await channel.send(msg)
                        print(f"✅ Delvis melding sendt til kanal {channel.name}.")
        except discord.Forbidden as e:
            print(f"🚨 Feil ved sending til kanal {self.channel_id}: {e}")
        except discord.HTTPException as e:
            print(f"🚨 HTTP-feil ved sending: {e}")
        finally:
            await self.close()

def split_message(message, limit=2000):
    if len(message) <= limit:
        return [message]

    lines = message.splitlines(keepends=True)
    chunks = []
    current = ""

    for line in lines:
        if len(current) + len(line) <= limit:
            current += line
        else:
            chunks.append(current)
            current = line

    if current:
        chunks.append(current)

    return chunks

def post_to_discord(message, guild_id, channel_type="log", embed=None):
    config = next((s for s in _get_server_configs() if s["guild_id"] == guild_id), None)
    if not config:
        print(f"⚠️ Fant ingen konfig for guild {guild_id}")
        return

    channel_id = config.get("log_channel_id") if channel_type == "log" else config.get("news_channel_id")

    if not channel_id:
        print(f"❌ Mangler kanal-ID for {channel_type} i guild {guild_id}")
        return

    messenger = DiscordMessenger(channel_id=channel_id, message=message, embed=embed)
    asyncio.run(messenger.start(TOKEN))
