import os
import json
import time
import asyncio
import subprocess
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

from main import (
    fetch_event, fetch_all_events, fetch_upcoming_event,
    get_name_lookup, format_message, get_bootstrap_data,
    fetch_league_standings,
)
from bootstrap_diff import compare_players, fetch_bootstrap_data, load_previous_data
from cache_utils import save_cache
from posted_tracker import has_been_posted, mark_as_posted
import news_log

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
NEWS_INTERVAL_MINUTES = int(os.getenv("NEWS_INTERVAL_MINUTES", "30"))
DEADLINE_CHECK_INTERVAL = 15  # minutes
ADMIN_USERNAMES = set(os.getenv("ADMIN_USERNAMES", "galku").split(","))

with open("servers.json") as f:
    SERVERS = json.load(f)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Player status emoji map for !skade command
STATUS_EMOJI = {
    "i": "🚑",  # injured
    "d": "⚠️",  # doubtful
    "u": "❌",  # unavailable
    "s": "🟨",  # suspended
    "n": "⏸️",  # not in squad
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def split_message(message: str, limit: int = 2000) -> list[str]:
    if len(message) <= limit:
        return [message]
    lines = message.splitlines(keepends=True)
    chunks, current = [], ""
    for line in lines:
        if len(current) + len(line) <= limit:
            current += line
        else:
            chunks.append(current)
            current = line
    if current:
        chunks.append(current)
    return chunks


async def send_to_channel(channel_id: int, message: str) -> None:
    """Send a (possibly long) message to a channel, splitting at 2000 chars."""
    try:
        channel = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)
        for chunk in split_message(message):
            await channel.send(chunk)
    except discord.Forbidden:
        err = f"🚫 Mangler tilgang til å sende til kanal `{channel_id}` — sjekk botrollen"
        print(err)
        # Notify all log channels (skip the failing channel to avoid loop)
        for server in SERVERS:
            lc = server.get("log_channel_id")
            if lc and lc != channel_id:
                try:
                    ch = bot.get_channel(lc) or await bot.fetch_channel(lc)
                    await ch.send(err)
                except Exception:
                    pass
    except Exception as e:
        print(f"❌ Feil ved sending til kanal {channel_id}: {e}")


async def ctx_send(ctx, message: str) -> None:
    """Reply to a command context, splitting long messages automatically."""
    for chunk in split_message(message):
        await ctx.send(chunk)


async def log_command(ctx, command_text: str) -> None:
    """Delete the command message and log who ran it to the server's log channel."""
    try:
        await ctx.message.delete()
    except discord.NotFound:
        pass  # already deleted (e.g. two instances running)
    server = next((s for s in SERVERS if s["guild_id"] == ctx.guild.id), None)
    if server and server.get("log_channel_id"):
        await send_to_channel(
            server["log_channel_id"],
            f"👤 {ctx.author.mention} kjørte: `{command_text}`"
        )


async def log_error(ctx, message: str) -> None:
    """Send an error message to the server's log channel, never to the news channel."""
    server = next((s for s in SERVERS if s["guild_id"] == ctx.guild.id), None)
    if server and server.get("log_channel_id"):
        await send_to_channel(server["log_channel_id"], message)
    else:
        print(f"❌ {message}")


async def log_to_servers(message: str) -> None:
    """Send a service/error message to every server's log channel."""
    for server in SERVERS:
        channel_id = server.get("log_channel_id")
        if channel_id:
            await send_to_channel(channel_id, message)


async def news_to_servers(message: str) -> None:
    """Broadcast a news message to every server's news channel."""
    for server in SERVERS:
        channel_id = server.get("news_channel_id")
        if channel_id:
            await send_to_channel(channel_id, message)


# ---------------------------------------------------------------------------
# Bot events
# ---------------------------------------------------------------------------

@bot.event
async def on_ready():
    print(f"🤖 Bot klar: {bot.user}")

    # Set configurable interval before starting
    news_update.change_interval(minutes=NEWS_INTERVAL_MINUTES)

    deadline_reminder.start()
    news_update.start()
    round_completed_check.start()

    await log_to_servers(
        f"🤖 **Fantasybot er klar!** PID: `{os.getpid()}` — Nyheter sjekkes hvert {NEWS_INTERVAL_MINUTES}. minutt."
    )


# ---------------------------------------------------------------------------
# Task: deadline reminder — fires ~1 hour before each gameweek deadline
# ---------------------------------------------------------------------------

@tasks.loop(minutes=DEADLINE_CHECK_INTERVAL)
async def deadline_reminder():
    try:
        event = await asyncio.to_thread(fetch_upcoming_event)
        if not event:
            return

        deadline_epoch = event.get("deadline_time_epoch")
        if not deadline_epoch:
            return

        seconds_until = deadline_epoch - int(time.time())
        # Post when within the 1-hour window, plus one check interval as
        # buffer to ensure we don't miss it between two checks.
        window = 3600 + DEADLINE_CHECK_INTERVAL * 60
        if not (0 < seconds_until <= window):
            return

        tracker_key = f"deadline_reminder_GW{event['id']}"
        if await asyncio.to_thread(has_been_posted, tracker_key):
            return

        name_lookup = await asyncio.to_thread(get_name_lookup)
        message_body = await asyncio.to_thread(format_message, event, name_lookup)

        for server in SERVERS:
            role_id = server.get("mention_role_id")
            mention = f"<@&{role_id}>\n" if role_id else ""
            full_message = (
                f"{mention}⏰ **1 time til deadline for Runde {event['id']}!**\n\n"
                f"{message_body}"
            )
            channel_id = server.get("news_channel_id")
            if channel_id:
                await send_to_channel(channel_id, full_message)

        await asyncio.to_thread(mark_as_posted, tracker_key)

    except Exception as e:
        await log_to_servers(f"🛑 Feil i deadline_reminder: {e}")


@deadline_reminder.before_loop
async def before_deadline_reminder():
    await bot.wait_until_ready()


# ---------------------------------------------------------------------------
# Task: news update — checks for player price changes and injury news
# ---------------------------------------------------------------------------

@tasks.loop(minutes=30)  # overridden in on_ready via change_interval()
async def news_update():
    try:
        current = await asyncio.to_thread(fetch_bootstrap_data)
        if not current:
            await log_to_servers("🚨 Kunne ikke hente Fantasy-data fra API.")
            return

        previous = await asyncio.to_thread(load_previous_data)

        if previous is None:
            # First run: seed news_log with all players that currently have news
            team_lookup = {t["code"]: t["name"] for t in current.get("teams", [])}
            ts = int(time.time())
            seed_entries = [
                {
                    "type": "news",
                    "text": f"📰 Nyhet for {p['first_name']} {p['second_name']} ({team_lookup.get(p['team_code'], 'Ukjent lag')}): {p['news']}",
                    "ts": ts,
                }
                for p in current.get("elements", []) if p.get("news")
            ]
            if seed_entries:
                await asyncio.to_thread(news_log.append_entries, seed_entries)
                print(f"🌱 Seeded news_log med {len(seed_entries)} spillere med nyheter.")
            await asyncio.to_thread(save_cache, "bootstrap_previous.json", current)
            return

        messages = compare_players(current, previous)
        await asyncio.to_thread(save_cache, "bootstrap_previous.json", current)

        if not messages:
            print("✅ Ingen Fantasy-endringer funnet.")
            return

        # Log each entry to the rolling news log so !skade can query history
        ts = int(time.time())
        entries = [
            {"type": m["type"], "text": m["news_text"], "ts": ts}
            for m in messages
        ]
        await asyncio.to_thread(news_log.append_entries, entries)

        # News content → news channels
        news_text = "\n".join(["🔔 **Oppdateringer i Fantasy-data:**"] + [m["news_text"] for m in messages])
        await news_to_servers(news_text)

        # Compact diff → log channels only
        log_lines = [m["log_text"] for m in messages]
        await log_to_servers("📋 **Fantasy-data oppdatert:**\n" + "\n".join(log_lines))

    except Exception as e:
        await log_to_servers(f"🛑 Feil i news_update: {e}")


@news_update.before_loop
async def before_news_update():
    await bot.wait_until_ready()


# ---------------------------------------------------------------------------
# Task: round completed — posts summary when a gameweek finishes
# ---------------------------------------------------------------------------

@tasks.loop(minutes=15)
async def round_completed_check():
    try:
        events = await asyncio.to_thread(fetch_all_events)
        if not events:
            return

        # Only post when FPL has finalised the round (top_element_info populated)
        finished = [
            e for e in events
            if e.get("finished") and isinstance(e.get("top_element_info"), dict)
        ]
        if not finished:
            return

        event = max(finished, key=lambda e: e["id"])
        tracker_key = f"round_completed_GW{event['id']}"
        if await asyncio.to_thread(has_been_posted, tracker_key):
            return

        name_lookup = await asyncio.to_thread(get_name_lookup)
        message_body = await asyncio.to_thread(format_message, event, name_lookup)
        full_message = f"📊 **Runde {event['id']} er ferdig!**\n\n{message_body}"

        await news_to_servers(full_message)

        # Post league leader for each server
        for server in SERVERS:
            league_id = server.get("league_id")
            channel_id = server.get("news_channel_id")
            if not league_id or not channel_id:
                continue
            try:
                data = await asyncio.to_thread(fetch_league_standings, league_id)
                league_name = data.get("league", {}).get("name", "ligaen")
                results = data.get("standings", {}).get("results", [])
                leader = next((r for r in results if r.get("rank") == 1), None)
                if leader:
                    await send_to_channel(
                        channel_id,
                        f"🏆 Leder av **{league_name}** er **{leader['entry_name']}** ({leader['total']} poeng)"
                    )
            except Exception as e:
                await log_to_servers(f"⚠️ Kunne ikke hente ligaleder for liga {league_id}: {e}")

        await asyncio.to_thread(mark_as_posted, tracker_key)

    except Exception as e:
        await log_to_servers(f"🛑 Feil i round_completed_check: {e}")


@round_completed_check.before_loop
async def before_round_completed_check():
    await bot.wait_until_ready()


# ---------------------------------------------------------------------------
# Command: !deadline [runde_nr]
# ---------------------------------------------------------------------------

@bot.command(name="deadline")
async def deadline_cmd(ctx, runde_nr: str = None):
    try:
        await log_command(ctx, f"!deadline {runde_nr or ''}".strip())
        print(f"[{ctx.message.created_at}] '!deadline' trigget av {ctx.author} i {ctx.channel} (arg: {runde_nr})")

        if runde_nr and not runde_nr.isdigit():
            print(f"Ignorerer ugyldig argument '{runde_nr}' fra {ctx.author}")
            runde_nr = None

        event = await asyncio.to_thread(fetch_event, int(runde_nr) if runde_nr else None)

        if not event:
            await ctx.send(
                f"🚫 Ukjent runde: {runde_nr}. Velg en runde mellom 1 og 30.\n"
                "Skriv bare `!deadline` for å se aktiv runde."
            )
            return

        name_lookup = await asyncio.to_thread(get_name_lookup)
        message = await asyncio.to_thread(format_message, event, name_lookup)
        lines = message.split("\n")
        lines[0] += f" (bedt om av {ctx.author.mention})"
        await ctx_send(ctx, "\n".join(lines))

    except Exception as e:
        await log_error(ctx, f"🛑 Feil i !deadline: {e}")




# ---------------------------------------------------------------------------
# Command: !nyheter [antall=20]
# Shows the last N entries from the rolling news log (prices + injuries).
# ---------------------------------------------------------------------------

@bot.command(name="nyheter")
async def nyheter_cmd(ctx, antall: str = "20"):
    """Show current players with news from live bootstrap data, sorted by team."""
    try:
        await log_command(ctx, f"!nyheter {antall}")
        if not antall.isdigit():
            await ctx.send("Bruk: `!nyheter [antall]` — f.eks. `!nyheter 50`")
            return

        n = min(int(antall), 200)
        bootstrap = await asyncio.to_thread(get_bootstrap_data)

        team_lookup = {t["id"]: t["name"] for t in bootstrap.get("teams", [])}
        players_with_news = [
            p for p in bootstrap.get("elements", []) if p.get("news")
        ]

        if not players_with_news:
            await ctx.send("✅ Ingen spillere med aktive nyheter/skader akkurat nå.")
            return

        # Sort by team name, then player name
        players_with_news.sort(key=lambda p: (team_lookup.get(p["team"], ""), p["second_name"]))
        players_with_news = players_with_news[:n]

        lines = []
        for p in players_with_news:
            name = f"{p['first_name']} {p['second_name']}"
            team = team_lookup.get(p["team"], "Ukjent lag")
            emoji = STATUS_EMOJI.get(p.get("status", ""), "❓")
            chance = p.get("chance_of_playing_next_round")
            chance_str = f" ({chance}%)" if chance is not None else ""
            lines.append(f"> {emoji} **{name}** ({team}){chance_str}: {p['news']}")

        message = (
            f"📰 **Aktive nyheter/skader – {len(lines)} spillere:** (bedt om av {ctx.author.mention})\n"
            + "\n".join(lines)
        )
        await ctx_send(ctx, message)

    except Exception as e:
        await log_error(ctx, f"🛑 Feil i !nyheter: {e}")


# ---------------------------------------------------------------------------
# Command: !skade [lagnavn | antall]
#   !skade fredrikstad  →  current injuries for players from that team
#   !skade 50           →  last 50 injury news entries from the log
# ---------------------------------------------------------------------------

@bot.command(name="skade")
async def skade_cmd(ctx, *, arg: str = None):
    try:
        await log_command(ctx, f"!skade {arg or ''}".strip())
        if arg is None:
            await ctx.send(
                "Bruk:\n"
                "> `!skade [lagnavn]` — vis skader for et spesifikt lag\n"
                "> `!skade [antall]` — vis siste N skademeldinger"
            )
            return

        arg = arg.strip()

        if arg.isdigit():
            # Show last N injury-type entries from the news log
            n = min(int(arg), 100)
            entries = await asyncio.to_thread(news_log.get_recent, n, "news")
            if not entries:
                await ctx.send("Ingen skademeldinger logget ennå.")
                return
            lines = [f"<t:{e['ts']}:d> {e['text']}" for e in entries]
            message = f"🏥 **Siste {len(lines)} skademeldinger:** (bedt om av {ctx.author.mention})\n" + "\n".join(lines)
            await ctx_send(ctx, message)
            return

        # Team lookup — query current bootstrap data
        bootstrap = await asyncio.to_thread(get_bootstrap_data)
        query = arg.lower()
        matched_team = next(
            (t for t in bootstrap.get("teams", []) if query in t["name"].lower()),
            None,
        )
        if not matched_team:
            await ctx.send(f"🚫 Fant ikke lag som inneholder **{arg}**.")
            return

        injured = [
            p for p in bootstrap.get("elements", [])
            if p["team"] == matched_team["id"] and p.get("news")
        ]

        if not injured:
            await ctx.send(f"✅ Ingen skade/forfall-meldinger for **{matched_team['name']}**.")
            return

        lines = []
        for p in injured:
            name = f"{p['first_name']} {p['second_name']}"
            emoji = STATUS_EMOJI.get(p.get("status", ""), "❓")
            chance = p.get("chance_of_playing_next_round")
            chance_str = f" ({chance}%)" if chance is not None else ""
            lines.append(f"> {emoji} **{name}**{chance_str}: {p['news']}")

        message = f"🏥 **Skader/Forfall – {matched_team['name']}:** (bedt om av {ctx.author.mention})\n" + "\n".join(lines)
        await ctx_send(ctx, message)

    except Exception as e:
        await log_error(ctx, f"🛑 Feil i !skade: {e}")


# ---------------------------------------------------------------------------
# Command: !update  (admin only — galku or ADMIN_USERNAMES env var)
# Pulls latest code from git and restarts the bot via systemd.
# Message is logged before restart since the process is killed by systemd.
# ---------------------------------------------------------------------------

@bot.command(name="update")
async def update_cmd(ctx):
    if ctx.author.name not in ADMIN_USERNAMES:
        await log_error(ctx, f"🚫 {ctx.author.mention} har ikke tilgang til `!update`.")
        return

    await log_command(ctx, "!update")
    server = next((s for s in SERVERS if s["guild_id"] == ctx.guild.id), None)
    log_channel_id = server.get("log_channel_id") if server else None

    async def run_update():
        if log_channel_id:
            await send_to_channel(log_channel_id, "🔄 Henter siste kode fra GitHub...")

        result = await asyncio.to_thread(
            subprocess.run,
            ["git", "-C", "/home/rene_raen/fantasyesbot", "pull"],
            capture_output=True, text=True
        )
        output = result.stdout.strip() or result.stderr.strip()

        if log_channel_id:
            await send_to_channel(log_channel_id, f"📦 Git:\n```\n{output}\n```\nStarter på nytt...")

        await asyncio.to_thread(
            subprocess.run,
            ["systemctl", "--user", "restart", "fantasybot"]
        )

    asyncio.create_task(run_update())


# ---------------------------------------------------------------------------
# Command: !påminnelse  (log channel only)
# Sends the deadline reminder to all news channels, same as the automated
# 1-hour reminder. Restricted to the log channel to avoid accidental use.
# ---------------------------------------------------------------------------

@bot.command(name="påminnelse")
async def paminnelse_cmd(ctx, arg: str = None):
    """Send deadline reminder. Default: news channels. `!påminnelse log`: log channel only."""
    try:
        server = next((s for s in SERVERS if s["guild_id"] == ctx.guild.id), None)
        if not server or ctx.channel.id != server.get("log_channel_id"):
            await log_error(ctx, "⚠️ `!påminnelse` kan kun kjøres fra log-kanalen.")
            return

        send_to_log = (arg and arg.lower() == "log")
        await log_command(ctx, f"!påminnelse{' log' if send_to_log else ''}")

        event = await asyncio.to_thread(fetch_upcoming_event)
        if not event:
            await send_to_channel(server["log_channel_id"], "🚫 Ingen kommende runde funnet.")
            return

        name_lookup = await asyncio.to_thread(get_name_lookup)
        message_body = await asyncio.to_thread(format_message, event, name_lookup)

        if send_to_log:
            # Send only to the current server's log channel
            role_id = server.get("mention_role_id")
            mention = f"<@&{role_id}>\n" if role_id else ""
            full_message = (
                f"{mention}⏰ **1 time til deadline for Runde {event['id']}!**\n\n"
                f"{message_body}"
            )
            await send_to_channel(server["log_channel_id"], full_message)
        else:
            # Broadcast to all servers' news channels
            for s in SERVERS:
                role_id = s.get("mention_role_id")
                mention = f"<@&{role_id}>\n" if role_id else ""
                full_message = (
                    f"{mention}⏰ **1 time til deadline for Runde {event['id']}!**\n\n"
                    f"{message_body}"
                )
                channel_id = s.get("news_channel_id")
                if channel_id:
                    await send_to_channel(channel_id, full_message)

    except Exception as e:
        await log_error(ctx, f"🛑 Feil i !påminnelse: {e}")


# ---------------------------------------------------------------------------
# Command: !rangering
# Lists all entries in the server's league sorted by rank.
# ---------------------------------------------------------------------------

@bot.command(name="rangering")
async def rangering_cmd(ctx):
    try:
        await log_command(ctx, "!rangering")
        server = next((s for s in SERVERS if s["guild_id"] == ctx.guild.id), None)
        league_id = server.get("league_id") if server else None
        if not league_id:
            await ctx.send("🚫 Ingen liga konfigurert for denne serveren.")
            return

        data = await asyncio.to_thread(fetch_league_standings, league_id)
        league_name = data.get("league", {}).get("name", "Ligaen")
        results = data.get("standings", {}).get("results", [])

        if not results:
            await ctx.send("🚫 Ingen resultater funnet.")
            return

        MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}
        lines = []
        for r in results:
            rank = r.get("rank", "?")
            prefix = MEDALS.get(rank, f"{rank}.")
            entry = r.get("entry_name", "Ukjent")
            total = r.get("total", 0)
            last_rank = r.get("last_rank", "?")
            lines.append(f"{prefix} **{entry}** – {total} poeng *(sist uke: {last_rank}. plass)*")

        header = f"🏆 **Rangering – {league_name}:** (bedt om av {ctx.author.mention})\n"
        await ctx_send(ctx, header + "\n".join(lines))

    except Exception as e:
        await log_error(ctx, f"🛑 Feil i !rangering: {e}")


# ---------------------------------------------------------------------------
# Command: !sync  (log channel only)
# Triggers news_update immediately — fetches fresh bootstrap data and posts
# any changes to the news channels.
# ---------------------------------------------------------------------------

@bot.command(name="sync")
async def sync_cmd(ctx):
    try:
        server = next((s for s in SERVERS if s["guild_id"] == ctx.guild.id), None)
        if not server or ctx.channel.id != server.get("log_channel_id"):
            await log_error(ctx, "⚠️ `!sync` kan kun kjøres fra log-kanalen.")
            return

        await log_command(ctx, "!sync")
        await send_to_channel(server["log_channel_id"], "🔄 Synkroniserer Fantasy-data...")
        await news_update()
        await send_to_channel(server["log_channel_id"], "✅ Sync ferdig. Eventuelle endringer er postet til nyhetskanaler.")

    except Exception as e:
        await log_error(ctx, f"🛑 Feil i !sync: {e}")


# ---------------------------------------------------------------------------
# Command: !hjelp  (log channel only)
# Lists all commands with descriptions and examples.
# ---------------------------------------------------------------------------

@bot.command(name="hjelp")
async def hjelp_cmd(ctx):
    try:
        server = next((s for s in SERVERS if s["guild_id"] == ctx.guild.id), None)
        if not server or ctx.channel.id != server.get("log_channel_id"):
            await log_error(ctx, "⚠️ `!hjelp` kan kun kjøres fra log-kanalen.")
            return

        await log_command(ctx, "!hjelp")

        msg = (
            "🤖 **Fantasybot** — Eliteserien Fantasy-hjelper\n"
            "> Driftet av **madcow** | Misbruk? `cowness+misbruk@gmail.com`\n"
            "\n"
            "📋 **Kommandoer:**\n"
            "> `!deadline [runde]` — Rundeinfo for aktiv eller angitt runde. Eks: `!deadline` · `!deadline 5`\n"
            "> `!nyheter [antall]` — Aktive skader og nyheter akkurat nå. Eks: `!nyheter` · `!nyheter 50`\n"
            "> `!skade [lag|antall]` — Skader per lag, eller siste N meldinger. Eks: `!skade Rosenborg` · `!skade 30`\n"
            "> `!rangering` — Vis fullstendig ligatabell med poeng og forrige ukes rangering.\n"
            "> `!påminnelse [log]` — Sender deadline-påminnelse til nyhetskanal. Legg til `log` for å teste hit istedet.\n"
            "> `!sync` — Henter fersk Fantasy-data og poster eventuelle endringer til nyhetskanal nå.\n"
            "> `!update` — Git pull + omstart. *(kun admin)*\n"
            "> `!hjelp` — Denne meldingen. *(kun fra log-kanal)*\n"
        )
        await send_to_channel(server["log_channel_id"], msg)

    except Exception as e:
        await log_error(ctx, f"🛑 Feil i !hjelp: {e}")


# ---------------------------------------------------------------------------

bot.run(TOKEN)
