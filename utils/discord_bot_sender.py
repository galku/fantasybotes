# utils/discord_bot_sender.py

import os
import discord
import asyncio
import json
from discord import Embed
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Last inn konfigurasjon
with open("servers.json", "r") as f:
    SERVER_CONFIGS = json.load(f)

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
                else:
                    await channel.send(self.message)
                print(f"✅ Melding sendt til kanal {channel.name}.")
        except discord.Forbidden as e:
            print(f"🚨 Feil ved sending til kanal {self.channel_id}: {e}")
        except discord.HTTPException as e:
            print(f"🚨 HTTP-feil ved sending: {e}")
        finally:
            await self.close()

async def _send_async(channel_id, message=None, embed=None):
    client = DiscordMessenger(channel_id=channel_id, message=message, embed=embed)
    async with client:
        await client.start(TOKEN)

def post_to_discord(message, guild_id, channel_type="log", embed=None):
    config = next((s for s in SERVER_CONFIGS if s["guild_id"] == guild_id), None)
    if not config:
        print(f"⚠️ Fant ingen konfig for guild {guild_id}")
        return

    channel_id = config.get("log_channel_id") if channel_type == "log" else config.get("news_channel_id")
    if not channel_id:
        print(f"❌ Mangler kanal-ID for {channel_type} i guild {guild_id}")
        return

    asyncio.run(_send_async(channel_id=channel_id, message=message, embed=embed))