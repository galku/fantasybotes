import os
import json
import discord
from discord.ext import commands
from dotenv import load_dotenv
from main import fetch_event, get_name_lookup, format_message, load_cache, save_cache, CACHE_FILE, CACHE_TTL_SECONDS

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"🤖 Bot er klar! Logget inn som {bot.user}")

@bot.command(name="deadline")
async def deadline(ctx, runde_nr: str = None):
    try:
        await ctx.message.delete()
        print(f"[{ctx.message.created_at}] '!deadline' trigget av {ctx.author} i {ctx.channel} med argument: {runde_nr}")

        if runde_nr and not runde_nr.isdigit():
            print(f"[{ctx.message.created_at}] Ignorerer ugyldig argument '{runde_nr}' fra {ctx.author}")
            runde_nr = None

        event_id = int(runde_nr) if runde_nr else None
        event = fetch_event(event_id)
        print(f"🎯 fetch_event({event_id}) returnerte: {type(event)}")

        if not event:
            await ctx.send(
                f"🚫 Ukjent runde: {runde_nr}. Velg en runde mellom 1 og 30.\n"
                "Er du usikker på hvilken runde som er aktiv nå, skriv bare `!deadline`."
            )
            print(f"[{ctx.message.created_at}] Ukjent rundeforespørsel: {runde_nr} fra {ctx.author}")
            return

        # Caching: unngå dobbelposting ved defaultkall
        cache = load_cache(CACHE_FILE, CACHE_TTL_SECONDS)
        cache_key = str(event["id"])
        if cache and "_timestamp" in cache and "events" in cache:
            posted_ids = cache.get("_posted", [])
            if cache_key in posted_ids and not runde_nr:
                print(f"⏳ Runde {event['id']} er allerede postet (automatisk). Hopper over.")
                return

        names = get_name_lookup()
        message = format_message(event, names)
        await ctx.send(message)

        if not runde_nr:
            if "_posted" not in cache:
                cache["_posted"] = []
            cache["_posted"].append(cache_key)
            save_cache(cache["events"])

    except Exception as e:
        print(f"[{ctx.message.created_at}] Feil ved håndtering av '!deadline': {e}")
        await ctx.send(f"Feil: {e}")

bot.run(TOKEN)