import discord
from discord.ext import commands
from discord import app_commands
import json
import time
import re
import os
from datetime import timedelta
from dotenv import load_dotenv
from server import keep_alive

# ─── KEEP ALIVE (for Replit) ────────────────────────────
keep_alive()

# ─── ENV ────────────────────────────────────────────────
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# ─── CONFIG ─────────────────────────────────────────────
BOT_PREFIX = "!"
EMBED_COLOR = 0x00f7ff

ALLOWED_GUILD_ID = 1380731003655557192
ANNOUNCE_CHANNEL_ID = 1380731855048937575
VOUCH_CHANNEL_ID = 1464895725786890466

VOUCH_FILE = "vouches.json"
afk_users = {}

# ─── INTENTS ────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents)
tree = bot.tree
bot.remove_command("help")

# ─── UTILITIES ──────────────────────────────────────────
def parse_duration(duration: str):
    match = re.fullmatch(r"(\d+)([smhd])", duration.lower())
    if not match:
        return None

    amount, unit = match.groups()
    amount = int(amount)

    return {
        "s": timedelta(seconds=amount),
        "m": timedelta(minutes=amount),
        "h": timedelta(hours=amount),
        "d": timedelta(days=amount),
    }.get(unit)

def afk_time_ago(seconds):
    mins = seconds // 60
    if mins < 60:
        return f"{mins}m"
    hrs = mins // 60
    if hrs < 24:
        return f"{hrs}h"
    return f"{hrs // 24}d"

# ─── FILE SETUP ─────────────────────────────────────────
if not os.path.exists(VOUCH_FILE):
    with open(VOUCH_FILE, "w") as f:
        json.dump({}, f)

# ─── EVENTS ─────────────────────────────────────────────
@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Logged in as {bot.user}")

    for guild in bot.guilds:
        if guild.id != ALLOWED_GUILD_ID:
            await guild.leave()
            print(f"❌ Left unauthorized server: {guild.name}")

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="Atomic Vault"
        )
    )

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    if message.author.id in afk_users:
        data = afk_users.pop(message.author.id)
        duration = afk_time_ago(int(time.time()) - data["time"])

        await message.channel.send(
            f"👋 Welcome back **{message.author.display_name}**\n"
            f"⏱️ AFK for: {duration}",
            delete_after=6
        )

    for user in message.mentions:
        if user.id in afk_users:
            data = afk_users[user.id]
            duration = afk_time_ago(int(time.time()) - data["time"])

            await message.channel.send(
                f"💤 **{user.display_name} is AFK**\n"
                f"📌 Reason: {data['reason']}\n"
                f"⏱️ {duration}",
                delete_after=8
            )

    await bot.process_commands(message)

# ─── PREFIX COMMANDS ────────────────────────────────────
@bot.command()
async def ping(ctx):
    await ctx.send("⚡ Atomic Vault is online")

@bot.command()
async def afk(ctx, *, reason="AFK"):
    afk_users[ctx.author.id] = {
        "reason": reason,
        "time": int(time.time())
    }
    await ctx.send(f"💤 **AFK set:** {reason}", delete_after=6)

# ─── SLASH COMMANDS ─────────────────────────────────────
@tree.command(name="ping", description="Check if bot is alive or not")
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"🏓 Pong `{round(bot.latency * 1000)}ms`",
        ephemeral=True
    )

@tree.command(name="vouch", description="vouch a user with reason")
@app_commands.describe(user="User to vouch", message="Vouch message")
async def vouch(interaction: discord.Interaction, user: discord.Member, message: str):

    if user.id == interaction.user.id:
        await interaction.response.send_message(
            "❌ You cannot vouch for yourself.",
            ephemeral=True
        )
        return

    with open(VOUCH_FILE, "r") as f:
        data = json.load(f)

    data[str(user.id)] = data.get(str(user.id), 0) + 1

    with open(VOUCH_FILE, "w") as f:
        json.dump(data, f, indent=4)

    embed = discord.Embed(
        title="🌟 New Vouch",
        description=message,
        color=EMBED_COLOR
    )
    embed.add_field(name="User", value=user.mention)
    embed.add_field(name="Vouched By", value=interaction.user.mention)
    embed.set_thumbnail(url=user.display_avatar.url)

    channel = interaction.guild.get_channel(VOUCH_CHANNEL_ID)
    if channel:
        await channel.send(embed=embed)

    await interaction.response.send_message("✅ Vouch sent!", ephemeral=True)

@tree.command(name="ban", description="bans a user")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    if member.id == interaction.user.id:
        await interaction.response.send_message("❌ You can’t ban yourself.", ephemeral=True)
        return

    await member.ban(reason=reason)
    await interaction.response.send_message(f"🔨 {member} banned.")

@tree.command(name="kick", description="kick a member")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    await member.kick(reason=reason)
    await interaction.response.send_message(f"👢 {member} kicked.")

@tree.command(name="mute", description="time out someone")
@app_commands.checks.has_permissions(moderate_members=True)
async def mute(interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "No reason"):
    delta = parse_duration(duration)
    if not delta:
        await interaction.response.send_message("❌ Use 10s / 5m / 2h / 1d", ephemeral=True)
        return

    await member.timeout(delta, reason=reason)
    await interaction.response.send_message(f"🔇 {member} muted for {duration}")

@tree.command(name="unmute", description="Remove timeout from someone")
@app_commands.checks.has_permissions(moderate_members=True)
async def unmute(interaction: discord.Interaction, member: discord.Member):
    await member.timeout(None)
    await interaction.response.send_message(f"🔊 {member} unmuted")

@tree.command(name="afk", description="Set afk")
async def afk_slash(interaction: discord.Interaction, reason: str = "AFK"):
    afk_users[interaction.user.id] = {
        "reason": reason,
        "time": int(time.time())
    }
    await interaction.response.send_message("💤 AFK enabled", ephemeral=True)
@bot.tree.command(name="unban", description="Unban a user using their ID")
@app_commands.checks.has_permissions(ban_members=True)
async def unban(
    interaction: discord.Interaction,
    user_id: str,
    reason: str = "No reason provided"
):
    user = await bot.fetch_user(int(user_id))
    await interaction.guild.unban(user, reason=reason)

    embed = discord.Embed(
        title="✅ User Unbanned",
        color=0x2bff88
    )
    embed.add_field(name="User", value=f"{user} (`{user.id}`)", inline=False)
    embed.add_field(name="By", value=interaction.user.mention, inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.set_footer(text="Atomic Vault • Moderation")

    await interaction.response.send_message(embed=embed)


# ─── ERROR HANDLING ─────────────────────────────────────
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ No permission.")
    elif isinstance(error, commands.CommandNotFound):
        return
    else:
        print(error)
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ You don’t have permission to use this command.",
            ephemeral=True
        )
    else:
        raise error


# ─── RUN ────────────────────────────────────────────────
bot.run(TOKEN)
