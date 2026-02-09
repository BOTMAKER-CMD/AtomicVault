import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import time
import re
import os
import random
import string
import asyncio
from datetime import timedelta
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Vault Status: OPERATIONAL"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ─── CONFIGURATION ──────────────────────────────────────────
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

ALLOWED_GUILD_ID = 1380731003655557192
VOUCH_CHANNEL_ID = 1464895725786890466
SERVICE_LOG_CHANNEL_ID = 1470490292166721687
VOUCH_FILE = "vouches.json"
SERVICE_DATA_FILE = "service_stats.json"
ACTIVE_SERVICES_FILE = "active_services.json"
PULSE_FILE = "pulse_config.json"
EMBED_COLOR = 0x00f7ff

CORE_TEAM = {
    1380723814115315803: "The Atomic Vault",
    1203199020189753354: "Sir Haruto",
    1351156564739751956: "Ifad_plays",
    1414709841112600579: "marloww",
    1155023196907647006: "Crazy Captain"
}

# ─── BOT CLASS ─────────────────────────────────────────────
class VaultBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        self.afk_users = {}

    async def setup_hook(self):
        self.vault_pulse.start()
        await self.tree.sync()

    # --- THE PULSE LOOP ---
    @tasks.loop(seconds=60)
    async def vault_pulse(self):
        config = self.load_json(PULSE_FILE)
        if not config.get("channel_id"): return
        
        channel = self.get_channel(config["channel_id"])
        guild = self.get_guild(ALLOWED_GUILD_ID)
        if not channel or not guild: return

        vouch_data = self.load_json(VOUCH_FILE)
        total_vouches = sum(vouch_data.values())
        
        if vouch_data:
            top_user_id = max(vouch_data, key=vouch_data.get)
            top_contributor = f"<@{top_user_id}> ({vouch_data[top_user_id]}⭐)"
        else:
            top_contributor = "None yet"

        embed = discord.Embed(title="💠 ATOMIC VAULT: LIVE PULSE", color=EMBED_COLOR)
        embed.add_field(name="👑 Vault Architect", value="<@1155023196907647006>", inline=True)
        embed.add_field(name="⚙️ Engine", value="`Python 3.12`", inline=True)
        embed.add_field(name="🛰️ Status", value="`OPERATIONAL`", inline=True)
        embed.add_field(name="🧠 Latency", value=f"`{round(self.latency * 1000)}ms`", inline=True)
        embed.add_field(name="👥 Population", value=f"`{guild.member_count}`", inline=True)
        embed.add_field(name="🌟 Total Vouches", value=f"`{total_vouches}`", inline=True)
        embed.add_field(name="🏆 Top Contributor", value=top_contributor, inline=True)
        
        recent_event = config.get("recent_action", "Monitoring Active")
        embed.add_field(name="📟 Recent Activity", value=f"```fix\n> {recent_event}```", inline=False)
        embed.set_footer(text=f"Last Sync: {time.strftime('%H:%M:%S')} • W Code Aura Active")

        msg_id = config.get("last_msg_id")
        try:
            msg = await channel.fetch_message(msg_id)
            await msg.edit(embed=embed)
        except:
            new_msg = await channel.send(embed=embed)
            config["last_msg_id"] = new_msg.id
            self.save_json(PULSE_FILE, config)

    def load_json(self, filename):
        if not os.path.exists(filename):
            with open(filename, "w") as f: json.dump({}, f)
            return {}
        try:
            with open(filename, "r") as f: return json.load(f)
        except: return {}

    def save_json(self, filename, data):
        with open(filename, "w") as f: json.dump(data, f, indent=4)

bot = VaultBot()
tree = bot.tree

# ─── UTILITIES ──────────────────────────────────────────
def afk_time_ago(seconds):
    mins = seconds // 60
    if mins < 60: return f"{mins}m"
    hrs = mins // 60
    if hrs < 24: return f"{hrs}h"
    return f"{hrs // 24}d"

def parse_duration(duration: str):
    match = re.fullmatch(r"(\d+)([smhd])", duration.lower())
    if not match: return None
    amount, unit = match.groups()
    return {"s": timedelta(seconds=int(amount)), "m": timedelta(minutes=int(amount)), 
            "h": timedelta(hours=int(amount)), "d": timedelta(days=int(amount))}.get(unit)

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

# ─── EVENTS ─────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    for guild in bot.guilds:
        if guild.id != ALLOWED_GUILD_ID:
            await guild.leave()
            print(f"❌ Left unauthorized server: {guild.name}")
    
    activity = discord.Activity(type=discord.ActivityType.competing, name="the Atomic Vault 💠")
    await bot.change_presence(status=discord.Status.dnd, activity=activity)

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild: return
    
    if message.author.id in bot.afk_users:
        data = bot.afk_users.pop(message.author.id)
        duration = afk_time_ago(int(time.time()) - data["time"])
        await message.channel.send(f"👋 Welcome back **{message.author.display_name}**\n⏱️ AFK for: {duration}", delete_after=6)
    
    for user in message.mentions:
        if user.id in bot.afk_users:
            data = bot.afk_users[user.id]
            duration = afk_time_ago(int(time.time()) - data["time"])
            await message.channel.send(f"💤 **{user.display_name} is AFK**\n📌 Reason: {data['reason']}\n⏱️ {duration}", delete_after=8)
            
    await bot.process_commands(message)

@bot.event
async def on_member_join(member):
    if member.guild.id == ALLOWED_GUILD_ID:
        config = bot.load_json(PULSE_FILE)
        config["recent_action"] = f"📥 New Arrival: {member.name}"
        bot.save_json(PULSE_FILE, config)
        bot.loop.create_task(bot.vault_pulse())

@bot.event
async def on_member_remove(member):
    if member.guild.id == ALLOWED_GUILD_ID:
        config = bot.load_json(PULSE_FILE)
        config["recent_action"] = f"📤 Member Left: {member.name}"
        bot.save_json(PULSE_FILE, config)
        bot.loop.create_task(bot.vault_pulse())

# ─── PREFIX COMMANDS ────────────────────────────────────
@bot.command()
async def ping(ctx):
    await ctx.send("⚡ Atomic Vault is online")

@bot.command()
async def afk(ctx, *, reason="AFK"):
    bot.afk_users[ctx.author.id] = {"reason": reason, "time": int(time.time())}
    await ctx.send(f"💤 **AFK set:** {reason}", delete_after=6)

# ─── SLASH COMMANDS ─────────────────────────────────────
@tree.command(name="ping", description="Check bot latency")
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong `{round(bot.latency * 1000)}ms`", ephemeral=True)

@tree.command(name="vouch", description="Give a member a Vault Vouch")
async def vouch(interaction: discord.Interaction, target: discord.Member, reason: str):
    if target.id == interaction.user.id:
        return await interaction.response.send_message("❌ You cannot vouch for yourself.", ephemeral=True)

    data = bot.load_json(VOUCH_FILE)
    data[str(target.id)] = data.get(str(target.id), 0) + 1
    total = data[str(target.id)]
    bot.save_json(VOUCH_FILE, data)

    # Clearance Logic
    if target.id in CORE_TEAM: clearance = f"⭐ {CORE_TEAM[target.id]}"
    elif total >= 25: clearance = "💎 ELITE"
    elif total >= 10: clearance = "✅ TRUSTED"
    else: clearance = "👤 MEMBER"

    public_embed = discord.Embed(title="💠 NEW VAULT VOUCH", color=0x00ff00)
    public_embed.set_thumbnail(url=target.display_avatar.url)
    public_embed.add_field(name="👤 Recipient", value=target.mention, inline=True)
    public_embed.add_field(name="👤 From", value=interaction.user.mention, inline=True)
    public_embed.add_field(name="🌟 Total Vouches", value=f"`{total}`", inline=True)
    public_embed.add_field(name="📝 Reason", value=f"```fix\n{reason}```", inline=False)
    public_embed.add_field(name="🛰️ Clearance", value=f"`{clearance}`", inline=True)
    public_embed.set_footer(text="Atomic Vault Security System")
    
    v_chan = bot.get_channel(VOUCH_CHANNEL_ID)
    if v_chan: await v_chan.send(embed=public_embed)
    
    config = bot.load_json(PULSE_FILE)
    config["recent_action"] = f"⭐ {interaction.user.name} vouched {target.name}"
    bot.save_json(PULSE_FILE, config)
    bot.loop.create_task(bot.vault_pulse())

    await interaction.response.send_message(f"✅ Vouch posted in <#{VOUCH_CHANNEL_ID}>", ephemeral=True)

@tree.command(name="stats", description="Check profile stats")
async def stats(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    v_data = bot.load_json(VOUCH_FILE)
    s_data = bot.load_json(SERVICE_DATA_FILE)
    vouches = v_data.get(str(target.id), 0)
    services = s_data.get(str(target.id), 0)

    color = 0x00ffff if target.id in CORE_TEAM else EMBED_COLOR
    embed = discord.Embed(title="📊 Vault Profile", color=color)
    embed.set_author(name=target.display_name, icon_url=target.display_avatar.url)
    embed.add_field(name="🛰️ Clearance", value=f"`{CORE_TEAM.get(target.id, '👤 MEMBER')}`", inline=True)
    embed.add_field(name="🌟 Total Vouches", value=f"`{vouches}`", inline=True)
    
    if target.id in CORE_TEAM:
        embed.add_field(name="🛠️ Jobs Completed", value=f"`{services}`", inline=True)
    
    bar_length = 10
    progress = min(int(vouches / 25 * bar_length), bar_length)
    bar = "🟦" * progress + "⬛" * (bar_length - progress)
    embed.add_field(name="📈 Trust Progress", value=f"{bar}", inline=False)
    embed.set_footer(text="Atomic Vault Security • W Aura Active")
    
    await interaction.response.send_message(embed=embed)

# ─── SERVICE SYSTEM ──────────────────────────────────────
@tree.command(name="create-service", description="Staff: Create a service")
async def create_service(interaction: discord.Interaction, customer: discord.Member, service_name: str):
    if interaction.user.id not in CORE_TEAM: return await interaction.response.send_message("❌ Unauthorized", ephemeral=True)

    active = bot.load_json(ACTIVE_SERVICES_FILE)
    s_otp, e_otp, c_otp = generate_otp(), generate_otp(), generate_otp()
    active[str(customer.id)] = {"name": service_name, "staff": interaction.user.name, "s_otp": s_otp, "e_otp": e_otp, "c_otp": c_otp, "status": "PENDING"}
    bot.save_json(ACTIVE_SERVICES_FILE, active)

    log_chan = bot.get_channel(SERVICE_LOG_CHANNEL_ID)
    if log_chan: await log_chan.send(embed=discord.Embed(title="📝 SERVICE CREATED", description=f"**{service_name}** for {customer.mention}", color=0xffa500))

    try:
        dm = discord.Embed(title="💠 VAULT SERVICE CODES", color=EMBED_COLOR)
        dm.add_field(name="🔑 START OTP", value=f"`{s_otp}`", inline=True)
        dm.add_field(name="🔒 END OTP", value=f"`{e_otp}`", inline=True)
        dm.add_field(name="🚫 CANCEL OTP", value=f"`{c_otp}`", inline=True)
        await customer.send(embed=dm)
        await interaction.response.send_message(f"✅ Service created for {customer.name}.", ephemeral=True)
    except: await interaction.response.send_message("⚠️ Failed to DM customer.", ephemeral=True)

@tree.command(name="start-service", description="Staff: Verify Start OTP")
async def start_service(interaction: discord.Interaction, customer: discord.Member, otp: str):
    active = bot.load_json(ACTIVE_SERVICES_FILE)
    job = active.get(str(customer.id))
    if not job or otp != job["s_otp"]: return await interaction.response.send_message("❌ Invalid OTP", ephemeral=True)
    job["status"] = "IN_PROGRESS"
    bot.save_json(ACTIVE_SERVICES_FILE, active)
    await interaction.response.send_message(f"⚙️ Service started for {customer.mention}")

@tree.command(name="complete-service", description="Staff: Verify End OTP and generate receipt")
async def complete_service(interaction: discord.Interaction, customer: discord.Member, otp: str):
    active = bot.load_json(ACTIVE_SERVICES_FILE)
    job = active.get(str(customer.id))
    
    if not job or otp != job["e_otp"]: 
        return await interaction.response.send_message("❌ Invalid OTP. Verification failed.", ephemeral=True)

    # Update Stats
    stats = bot.load_json(SERVICE_DATA_FILE)
    stats[str(interaction.user.id)] = stats.get(str(interaction.user.id), 0) + 1
    bot.save_json(SERVICE_DATA_FILE, stats)

    # --- GENERATE RECEIPT ---
    receipt = discord.Embed(title="📄 SERVICE COMPLETION RECEIPT", color=0x2bff88) # Success Green
    receipt.set_author(name="Atomic Vault Ledger", icon_url=interaction.user.display_avatar.url)
    
    receipt.add_field(name="🛠️ Service Type", value=f"`{job['name']}`", inline=False)
    receipt.add_field(name="👤 Customer", value=customer.mention, inline=True)
    receipt.add_field(name="👑 Staff", value=interaction.user.mention, inline=True)
    receipt.add_field(name="🛰️ Status", value="`VERIFIED & LOGGED`", inline=True)
    receipt.add_field(name="🌟 Staff Total Jobs", value=f"`{stats[str(interaction.user.id)]}`", inline=True)
    
    receipt.set_footer(text=f"ID: {generate_otp()}-{generate_otp()} • {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Send to Log Channel
    log_chan = bot.get_channel(SERVICE_LOG_CHANNEL_ID)
    if log_chan:
        await log_chan.send(embed=receipt)

    # Clean up active job
    del active[str(customer.id)]
    bot.save_json(ACTIVE_SERVICES_FILE, active)

    # Response to Staff
    await interaction.response.send_message(content="🏁 **Service Finalized.** Receipt generated in logs.", embed=receipt)@tree.command(name="cancel-service", description="Staff: Verify Cancel OTP")
async def cancel_service(interaction: discord.Interaction, customer: discord.Member, otp: str, reason: str):
    active = bot.load_json(ACTIVE_SERVICES_FILE)
    job = active.get(str(customer.id))
    if not job or otp != job["c_otp"]: return await interaction.response.send_message("❌ Invalid OTP", ephemeral=True)

    del active[str(customer.id)]
    bot.save_json(ACTIVE_SERVICES_FILE, active)
    await interaction.response.send_message(f"🚫 Service voided: {reason}")

@tree.command(name="view-active", description="Staff: View all active services")
async def view_active(interaction: discord.Interaction):
    if interaction.user.id not in CORE_TEAM: return await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
    active = bot.load_json(ACTIVE_SERVICES_FILE)
    if not active: return await interaction.response.send_message("🛰️ No active services.", ephemeral=True)
    
    embed = discord.Embed(title="🛰️ CURRENT ACTIVE SERVICES", color=EMBED_COLOR)
    for cid, data in active.items():
        embed.add_field(name=f"🛠️ {data['name']}", value=f"**Customer:** <@{cid}>\n**Status:** `{data['status']}`", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ─── MODERATION ──────────────────────────────────────────
@tree.command(name="ban", description="Ban a member")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    if member.id == interaction.user.id: return await interaction.response.send_message("❌ Cannot ban self.", ephemeral=True)
    await member.ban(reason=reason)
    await interaction.response.send_message(f"🔨 Banned {member}")

@tree.command(name="kick", description="Kick a member")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    await member.kick(reason=reason)
    await interaction.response.send_message(f"👢 Kicked {member}")

@tree.command(name="unban", description="Unban a user by ID")
@app_commands.checks.has_permissions(ban_members=True)
async def unban(interaction: discord.Interaction, user_id: str, reason: str = "No reason"):
    user = await bot.fetch_user(int(user_id))
    await interaction.guild.unban(user, reason=reason)
    await interaction.response.send_message(f"✅ Unbanned {user.name}")

@tree.command(name="mute", description="Mute a member")
@app_commands.checks.has_permissions(moderate_members=True)
async def mute(interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "No reason"):
    delta = parse_duration(duration)
    if not delta: return await interaction.response.send_message("❌ Use 10s / 5m / 2h / 1d", ephemeral=True)
    await member.timeout(delta, reason=reason)
    await interaction.response.send_message(f"🔇 Muted {member} for {duration}")

@tree.command(name="unmute", description="Unmute a member")
@app_commands.checks.has_permissions(moderate_members=True)
async def unmute(interaction: discord.Interaction, member: discord.Member):
    await member.timeout(None)
    await interaction.response.send_message(f"🔊 Unmuted {member}")

@tree.command(name="set-pulse", description="Deploy the Atomic Pulse dashboard")
@app_commands.checks.has_permissions(administrator=True)
async def set_pulse(interaction: discord.Interaction):
    config = bot.load_json(PULSE_FILE)
    config["channel_id"] = interaction.channel_id
    config["last_msg_id"] = None
    config["recent_action"] = f"Vault Pulse Initialized by {interaction.user.name}"
    bot.save_json(PULSE_FILE, config)
    bot.loop.create_task(bot.vault_pulse())
    await interaction.response.send_message("💠 Vault Link Established.", ephemeral=True)
@tree.command(name="my-service", description="Customer: View your active service details and OTPs")
async def my_service(interaction: discord.Interaction):
    active = bot.load_json(ACTIVE_SERVICES_FILE)
    job = active.get(str(interaction.user.id))
    
    if not job:
        return await interaction.response.send_message("🛰️ **No active services found** linked to your ID.", ephemeral=True)
    
    embed = discord.Embed(title="💠 YOUR ACTIVE SERVICE", color=EMBED_COLOR)
    embed.add_field(name="🛠️ Operation", value=f"`{job['name']}`", inline=False)
    embed.add_field(name="👤 Assigned Staff", value=f"`{job['staff']}`", inline=True)
    embed.add_field(name="🛰️ Status", value=f"`{job['status']}`", inline=True)
    
    # Provide keys again in case they lost them
    embed.add_field(name="🔑 START OTP", value=f"||{job['s_otp']}||", inline=True)
    embed.add_field(name="🔒 END OTP", value=f"||{job['e_otp']}||", inline=True)
    embed.add_field(name="🚫 CANCEL OTP", value=f"||{job['c_otp']}||", inline=True)
    
    embed.set_footer(text="Keep these codes confidential. Click to reveal.")
    await interaction.response.send_message(embed=embed, ephemeral=True)
keep_alive()
bot.run(TOKEN)