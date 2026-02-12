
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
import motor.motor_asyncio


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
VOUCH_CHANNEL_ID = 1470447530725609533
SERVICE_LOG_CHANNEL_ID = 1470490292166721687
EMBED_COLOR = 0x00f7ff
# Add this with your other IDs
LEVEL_LOG_CHANNEL_ID = 1471099337537749032  # Replace with your actual channel ID
CORE_TEAM = {
    1380723814115315803: "The Atomic Vault",
    1203199020189753354: "Sir Haruto",
    1351156564739751956: "Ifad_plays",
    1414709841112600579: "marloww",
    1155023196907647006: "Crazy Captain"
}
# --- MONGODB SETUP ---
# Fetching the URL from Render's Environment Variables
# --- MONGODB SETUP ---
MONGO_URL = os.getenv("MONGO_URL")

if not MONGO_URL:
    print("❌ ERROR: MONGO_URL environment variable is missing!")
    # This stops the bot from trying to connect to localhost
    cluster = None 
else:
    # Adding tlsAllowInvalidCertificates helps avoid connection issues on some hosts
    cluster = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL, tlsAllowInvalidCertificates=True)
    db = cluster["AtomicVault"]
# Collections (Think of these as your new "JSON Files")
xp_col = db["levels"]
vouch_col = db["vouches"]
service_stats_col = db["service_stats"]
active_services_col = db["active_services"]
config_col = db["bot_config"] # Stores Pulse & Global Settings
# ─── BOT CLASS ─────────────────────────────────────────────
# ─── BOT CLASS ─────────────────────────────────────────────
class VaultBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        self.afk_users = {}

    async def setup_hook(self):
        await self.migrate_json_to_mongo()
        self.vault_pulse.start()
        await self.tree.sync()
        print("🛰️ Vault Systems Synchronized with Cloud Database.")

    async def migrate_json_to_mongo(self):
        import json
        files_to_migrate = {
            "xp.json": {"col": xp_col, "field": "xp"},
            "vouches.json": {"col": vouch_col, "field": "count"},
            "service_stats.json": {"col": service_stats_col, "field": "completed"}
        }
        for filename, info in files_to_migrate.items():
            if os.path.exists(filename):
                try:
                    with open(filename, "r") as f:
                        data = json.load(f)
                        for uid, val in data.items():
                            await info["col"].update_one(
                                {"_id": str(uid)},
                                {"$set": {info["field"]: val}},
                                upsert=True
                            )
                    print(f"✅ SUCCESS: {filename} migrated.")
                    os.rename(filename, f"migrated_{filename}")
                except Exception as e:
                    print(f"❌ Error migrating {filename}: {e}")

    # --- THE PULSE LOOP (Fixed Indentation & MongoDB) ---
    @tasks.loop(seconds=60)
    async def vault_pulse(self):
        # Fetch config from MongoDB
        config = await config_col.find_one({"_id": "pulse"}) or {}
        if not config.get("channel_id"): 
            return
        
        channel = self.get_channel(config["channel_id"])
        guild = self.get_guild(ALLOWED_GUILD_ID)
        if not channel or not guild: 
            return

        # Calculate Total Vouches from MongoDB
        total_vouches = 0
        async for doc in vouch_col.find():
            total_vouches += doc.get("count", 0)

        # Get Top Contributor from MongoDB
        top_user_doc = await vouch_col.find().sort("count", -1).limit(1).to_list(length=1)
        if top_user_doc:
            top_user = top_user_doc[0]
            top_contributor = f"<@{top_user['_id']}> ({top_user['count']}⭐)"
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
            await config_col.update_one(
                {"_id": "pulse"}, 
                {"$set": {"last_msg_id": new_msg.id}}, 
                upsert=True
            )

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
    # Ignore bots and DMs
    if message.author.bot or not message.guild:
        return

    # ─── 1. AFK LOGIC ──────────────────────────────────────
    if message.author.id in bot.afk_users:
        data = bot.afk_users.pop(message.author.id)
        duration = afk_time_ago(int(time.time()) - data["time"])
        await message.channel.send(
            f"👋 Welcome back **{message.author.display_name}**\n⏱️ AFK for: {duration}",
            delete_after=6
        )

    for user in message.mentions:
        if user.id in bot.afk_users:
            data = bot.afk_users[user.id]
            duration = afk_time_ago(int(time.time()) - data["time"])
            await message.channel.send(
                f"💤 **{user.display_name} is AFK**\n📌 Reason: {data['reason']}\n⏱️ {duration}",
                delete_after=8
            )

    # ─── 2. XP + LEVELING SYSTEM (MongoDB Version) ─────────
    user_id = str(message.author.id)

    # Fetch from MongoDB
    user_data = await xp_col.find_one({"_id": user_id})
    current_xp = user_data["xp"] if user_data else 0

    # XP calculation
    if message.author.id in CORE_TEAM:
        added_xp = random.randint(50, 150)
        boost_text = " (10× Staff Boost! 🔥)"
    else:
        added_xp = random.randint(5, 15)
        boost_text = ""

    new_xp = current_xp + added_xp
    
    # Save to MongoDB
    await xp_col.update_one({"_id": user_id}, {"$set": {"xp": new_xp}}, upsert=True)

    # Level calculation
    old_level = current_xp // 100
    new_level = new_xp // 100

    # Level-up handling
    if new_level > old_level:
        level_titles = {
            1:  "Newbie Adventurer",
            5:  "Sea Explorer",
            10: "Fruit Hunter",
            15: "Raid Participant",
            20: "Awakened Grinder",
            25: "Bounty Chaser",
            30: "Sea Beast Slayer",
            40: "Mirage Hunter",
            50: "Legendary Pirate",
            60: "God of the Seas",
        }

        title = level_titles.get(new_level, "Adventurer")
        role_name = f"Level {new_level} - {title}"

        # ─── ROLE CHECK (No Creation) ───
        # This will ONLY give the role if it already exists in your server
        role = discord.utils.get(message.guild.roles, name=role_name)
        
        if role:
            try:
                await message.author.add_roles(role)
            except discord.Forbidden:
                print(f"❌ Cannot add role {role_name}: Check bot role hierarchy.")

        # Level-up announcement
        embed = discord.Embed(
            title="🎉 LEVEL UP!",
            description=f"{message.author.mention} has reached **Level {new_level}**!{boost_text}",
            color=0x00ff88 if message.author.id not in CORE_TEAM else 0xffaa00
        )
        embed.add_field(name="New Rank", value=title, inline=False)
        embed.set_thumbnail(url=message.author.display_avatar.url)
        embed.set_footer(text="Keep chatting to level up! 🍍")

        # ─── LOGGING ───
        log_channel = bot.get_channel(LEVEL_LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(content=f"Congrats {message.author.mention}!", embed=embed)
        else:
            # Fallback to current channel if log channel is missing
            await message.channel.send(embed=embed, delete_after=10)

    # ─── 3. PROCESS COMMANDS ──────────────────────────────
    # This is CRITICAL for !ping and other prefix commands to work
    await bot.process_commands(message)# ─── PREFIX COMMANDS ────────────────────────────────────
@bot.command()
async def ping(ctx):
    await ctx.send("⚡ Atomic Vault is online")

@bot.command()
async def afk(ctx, *, reason="AFK"):
    bot.afk_users[ctx.author.id] = {"reason": reason, "time": int(time.time())}
    await ctx.send(f"💤 **AFK set:** {reason}", delete_after=6)

# ─── SLASH COMMANDS ─────────────────────────────────────
@tree.command(name="level", description="Check your level and XP progress")
async def level(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    user_id = str(target.id)
    
    # FIX: Fetch from MongoDB instead of bot.xp_data
    user_data = await xp_col.find_one({"_id": user_id})
    xp = user_data["xp"] if user_data else 0
    
    level = xp // 100
    next_level_xp = (level + 1) * 100
    progress = xp % 100
    bar = "🟦" * (progress // 10) + "⬛" * (10 - (progress // 10))
    
    embed = discord.Embed(title=f"{target.display_name}'s Level", color=0x00f7ff)
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="Level", value=f"**{level}**", inline=True)
    embed.add_field(name="Total XP", value=f"{xp}", inline=True)
    embed.add_field(name="Progress", value=f"{bar} ({progress}/100)", inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)
@tree.command(name="levelsboard", description="Top members by level")
async def levelsboard(interaction: discord.Interaction):
    # FIX: Get top 10 users directly from MongoDB sorted by XP
    cursor = xp_col.find().sort("xp", -1).limit(10)
    top_users = await cursor.to_list(length=10)

    if not top_users:
        return await interaction.response.send_message("No levels yet 😔", ephemeral=True)
    
    embed = discord.Embed(title="🏆 Level Leaderboard", color=0x00f7ff)
    for i, data in enumerate(top_users, 1):
        user_id = data["_id"]
        xp = data["xp"]
        lvl = xp // 100
        embed.add_field(name=f"#{i} Member ID: {user_id}", value=f"Lvl {lvl} | XP: {xp}", inline=False)
    
    await interaction.response.send_message(embed=embed)@tree.command(name="ping", description="Check bot latency")
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong `{round(bot.latency * 1000)}ms`", ephemeral=True)
@tree.command(name="vouch", description="Give a member a Vault Vouch")
async def vouch(interaction: discord.Interaction, target: discord.Member, reason: str):
    if target.id == interaction.user.id:
        return await interaction.response.send_message("❌ You cannot vouch for yourself.", ephemeral=True)

    # 1. Update/Increment vouch count in MongoDB
    target_id = str(target.id)
    result = await vouch_col.find_one_and_update(
        {"_id": target_id},
        {"$inc": {"count": 1}},
        upsert=True,
        return_document=True
    )
    total = result.get("count", 1)

    # 2. Clearance Logic
    if target.id in CORE_TEAM: 
        clearance = f"⭐ {CORE_TEAM[target.id]}"
    elif total >= 25: 
        clearance = "💎 ELITE"
    elif total >= 10: 
        clearance = "✅ TRUSTED"
    else: 
        clearance = "👤 MEMBER"

    # 3. Create Embed
    public_embed = discord.Embed(title="💠 NEW VAULT VOUCH", color=0x00ff00)
    public_embed.set_thumbnail(url=target.display_avatar.url)
    public_embed.add_field(name="👤 Recipient", value=target.mention, inline=True)
    public_embed.add_field(name="👤 From", value=interaction.user.mention, inline=True)
    public_embed.add_field(name="🌟 Total Vouches", value=f"`{total}`", inline=True)
    public_embed.add_field(name="📝 Reason", value=f"```fix\n{reason}```", inline=False)
    public_embed.add_field(name="🛰️ Clearance", value=f"`{clearance}`", inline=True)
    public_embed.set_footer(text="Atomic Vault Security System")
    
    # 4. Send to Vouch Channel
    v_chan = bot.get_channel(VOUCH_CHANNEL_ID)
    if v_chan: 
        await v_chan.send(embed=public_embed)
    
    # 5. Update Recent Activity in MongoDB
    await config_col.update_one(
        {"_id": "pulse"},
        {"$set": {"recent_action": f"⭐ {interaction.user.name} vouched {target.name}"}},
        upsert=True
    )
    
    # Refresh the pulse dashboard
    bot.loop.create_task(bot.vault_pulse())

    await interaction.response.send_message(f"✅ Vouch posted in <#{VOUCH_CHANNEL_ID}>", ephemeral=True)
@tree.command(name="stats", description="Check profile stats")
async def stats(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    target_id = str(target.id)

    # Fetch data from multiple collections
    vouch_data = await vouch_col.find_one({"_id": target_id})
    service_data = await service_stats_col.find_one({"_id": target_id})
    
    vouches = vouch_data.get("count", 0) if vouch_data else 0
    services = service_data.get("completed", 0) if service_data else 0

    color = 0x00ffff if target.id in CORE_TEAM else EMBED_COLOR
    embed = discord.Embed(title="📊 Vault Profile", color=color)
    embed.set_author(name=target.display_name, icon_url=target.display_avatar.url)
    
    # Clearance Logic
    if target.id in CORE_TEAM: clearance = f"⭐ {CORE_TEAM[target.id]}"
    elif vouches >= 25: clearance = "💎 ELITE"
    elif vouches >= 10: clearance = "✅ TRUSTED"
    else: clearance = "👤 MEMBER"

    embed.add_field(name="🛰️ Clearance", value=f"`{clearance}`", inline=True)
    embed.add_field(name="🌟 Total Vouches", value=f"`{vouches}`", inline=True)
    
    if target.id in CORE_TEAM:
        embed.add_field(name="🛠️ Jobs Completed", value=f"`{services}`", inline=True)
    
    # Visual Progress Bar
    bar_length = 10
    progress = min(int(vouches / 25 * bar_length), bar_length)
    bar = "🟦" * progress + "⬛" * (bar_length - progress)
    embed.add_field(name="📈 Trust Progress (to Elite)", value=f"{bar}", inline=False)
    
    await interaction.response.send_message(embed=embed)
# ─── SERVICE SYSTEM ──────────────────────────────────────
@tree.command(name="create-service", description="Staff: Create a service")
async def create_service(interaction: discord.Interaction, customer: discord.Member, service_name: str):
    if interaction.user.id not in CORE_TEAM: 
        return await interaction.response.send_message("❌ Unauthorized", ephemeral=True)

    s_otp, e_otp, c_otp = generate_otp(), generate_otp(), generate_otp()
    
    # Save to MongoDB
    await active_services_col.update_one(
        {"_id": str(customer.id)},
        {"$set": {
            "name": service_name,
            "staff": interaction.user.name,
            "staff_id": interaction.user.id,
            "s_otp": s_otp,
            "e_otp": e_otp,
            "c_otp": c_otp,
            "status": "PENDING"
        }},
        upsert=True
    )
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
    if interaction.user.id not in CORE_TEAM:
        return await interaction.response.send_message("❌ Unauthorized", ephemeral=True)

    # Fetch the active job from MongoDB
    job = await active_services_col.find_one({"_id": str(customer.id)})
    
    if not job or otp != job["e_otp"]: 
        return await interaction.response.send_message("❌ Invalid OTP. Verification failed.", ephemeral=True)

    # Increment Staff Stats in MongoDB
    staff_id = str(interaction.user.id)
    stats_result = await service_stats_col.find_one_and_update(
        {"_id": staff_id},
        {"$inc": {"completed": 1}},
        upsert=True,
        return_document=True
    )
    total_jobs = stats_result.get("completed", 1)

    # --- GENERATE RECEIPT ---
    receipt = discord.Embed(title="📄 SERVICE COMPLETION RECEIPT", color=0x2bff88)
    receipt.set_author(name="Atomic Vault Ledger", icon_url=interaction.user.display_avatar.url)
    
    receipt.add_field(name="🛠️ Service Type", value=f"`{job['name']}`", inline=False)
    receipt.add_field(name="👤 Customer", value=customer.mention, inline=True)
    receipt.add_field(name="👑 Staff", value=interaction.user.mention, inline=True)
    receipt.add_field(name="🌟 Staff Total Jobs", value=f"`{total_jobs}`", inline=True)
    receipt.set_footer(text=f"ID: {generate_otp()} • {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Log to Channel
    log_chan = bot.get_channel(SERVICE_LOG_CHANNEL_ID)
    if log_chan:
        await log_chan.send(embed=receipt)

    # Remove from Active Services in MongoDB
    await active_services_col.delete_one({"_id": str(customer.id)})

    await interaction.response.send_message(content="🏁 **Service Finalized.** Receipt generated.", embed=receipt)
@tree.command(name="cancel-service", description="Staff: Verify Cancel OTP")
async def cancel_service(interaction: discord.Interaction, customer: discord.Member, otp: str, reason: str):
    if interaction.user.id not in CORE_TEAM:
        return await interaction.response.send_message("❌ Unauthorized", ephemeral=True)

    # 1. Look for the active job in MongoDB
    job = await active_services_col.find_one({"_id": str(customer.id)})
    
    # 2. Check if job exists and OTP matches
    if not job:
        return await interaction.response.send_message("🛰️ No active service found for this user.", ephemeral=True)
    
    if otp != job["c_otp"]:
        return await interaction.response.send_message("❌ Invalid Cancel OTP. Verification failed.", ephemeral=True)

    # 3. Remove the job from the database
    await active_services_col.delete_one({"_id": str(customer.id)})

    # 4. Create a Cancel Log Embed
    cancel_embed = discord.Embed(title="🚫 SERVICE VOIDED", color=0xff4444)
    cancel_embed.add_field(name="🛠️ Service", value=f"`{job['name']}`", inline=True)
    cancel_embed.add_field(name="👤 Customer", value=customer.mention, inline=True)
    cancel_embed.add_field(name="👑 Cancelled By", value=interaction.user.mention, inline=True)
    cancel_embed.add_field(name="📝 Reason", value=f"```fix\n{reason}```", inline=False)
    cancel_embed.set_footer(text=f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Send log to channel
    log_chan = bot.get_channel(SERVICE_LOG_CHANNEL_ID)
    if log_chan:
        await log_chan.send(embed=cancel_embed)

    await interaction.response.send_message(f"✅ Service for {customer.mention} has been successfully voided.")@tree.command(name="view-active", description="Staff: View all active services")
async def view_active(interaction: discord.Interaction):
    if interaction.user.id not in CORE_TEAM: 
        return await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
    
    # Fetch all documents from the active collection
    cursor = active_services_col.find({})
    active_jobs = await cursor.to_list(length=100)
    
    if not active_jobs: 
        return await interaction.response.send_message("🛰️ No active services.", ephemeral=True)
    
    embed = discord.Embed(title="🛰️ CURRENT ACTIVE SERVICES", color=EMBED_COLOR)
    for job in active_jobs:
        customer_id = job["_id"]
        embed.add_field(
            name=f"🛠️ {job['name']}", 
            value=f"**Customer:** <@{customer_id}>\n**Staff:** {job['staff']}\n**Status:** `{job['status']}`", 
            inline=False
        )
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
@tree.command(name="help", description="Access the Atomic Vault command directory")
async def help_command(interaction: discord.Interaction):
    # Check if user is in your CORE_TEAM
    is_staff = interaction.user.id in CORE_TEAM
    # Check if user has admin/mod permissions for the Mod section
    is_admin = interaction.user.guild_permissions.administrator
    is_mod = interaction.user.guild_permissions.moderate_members

    embed = discord.Embed(
        title="🛡️ ATOMIC VAULT | SYSTEM DIRECTORY",
        description="*Welcome to the Vault. Systems are currently OPERATIONAL.*",
        color=EMBED_COLOR
    )

    # --- MEMBER SECTION ---
    embed.add_field(
        name="🔑 MEMBER OPERATIONS",
        value=(
            "> `/my-service` — View your active OTPs & status.\n"
            "> `/stats` — Check your profile, vouches, and trust bar.\n"
            "> `/vouch` — Record a successful transaction for a member."
        ),
        inline=False
    )

    # --- STAFF SECTION ---
    if is_staff:
        embed.add_field(
            name="🛠️ STAFF OPERATIONS",
            value=(
                "> `/create-service` — Initiate job & generate secret OTPs.\n"
                "> `/start-service` — Verify Start OTP to begin.\n"
                "> `/complete-service` — Verify End OTP & log receipt.\n"
                "> `/cancel-service` — Void an active job with Cancel OTP.\n"
                "> `/view-active` — Monitor all global active tasks."
            ),
            inline=False
        )

    # --- MODERATION SECTION ---
    if is_admin or is_mod:
        embed.add_field(
            name="🔨 MODERATION & ADMIN",
            value=(
                "> `/mute` / `/unmute` — Manage member communication.\n"
                "> `/kick` / `/ban` — Remove threats from the Vault.\n"
                "> `/set-pulse` — Deploy/Relocate the live Pulse dashboard.\n"
                "> `/setup` — Auto-configure categories and channels."
            ),
            inline=False


@tree.command(name="dailyspin", description="Spin the daily wheel!")
@app_commands.checks.cooldown(1, 86400)
async def dailyspin(interaction: discord.Interaction):
    rewards = ["Kitsune luck! 🍁", "Leopard speed 🐆", "Dough awakening 🍩", "Just a Banana 🍌"]
    result = random.choice(rewards)
    embed = discord.Embed(title="🎰 Daily Spin!", description=f"{interaction.user.mention}: **{result}**", color=0x00f7ff)
    await interaction.response.send_message(embed=embed)

@tree.command(name="roast", description="Roast someone")
async def roast(interaction: discord.Interaction, target: discord.Member):
    if target == interaction.user:
        return await interaction.response.send_message("Don't roast yourself bro 😂", ephemeral=True)
    roasts = [f"{target.mention} is a Buddha spammer 🤡", f"{target.mention} lost to a lvl 1 pirate 💀"]
    await interaction.response.send_message(random.choice(roasts))

# ─── FINAL COMMANDS ─────────────────────────────────────────

@tree.command(name="help", description="Access the Atomic Vault directory")
async def help_command(interaction: discord.Interaction):
    is_staff = interaction.user.id in CORE_TEAM
    embed = discord.Embed(
        title="🛡️ ATOMIC VAULT | SYSTEM DIRECTORY",
        description="*Welcome to the Vault. Systems are currently OPERATIONAL.*",
        color=EMBED_COLOR
    )

    embed.add_field(
        name="🛰️ UTILITIES", 
        value="> `!afk [reason]` — Set status\n> `/ping` — Check latency", 
        inline=False
    )

    embed.set_footer(text=f"User: {interaction.user.display_name} • Aura: W Code Active")
    
    if bot.user.display_avatar:
        embed.set_thumbnail(url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ─── FINAL STARTUP ──────────────────────────────────────────

if __name__ == "__main__":
    # 1. Start the Flask web server first
    print("🌐 Initializing Keep-Alive...")
    keep_alive()
    
    # 2. Start the Discord Bot
    print("🤖 Connecting to Discord...")
    try:
        if not TOKEN:
            print("❌ TOKEN MISSING: Check your Render Environment Variables!")
        else:
            bot.run(TOKEN)
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")
