# Atomic Vault Discord Bot

## Overview
A Discord bot for moderation and community management. Features include:
- AFK system
- Vouch system
- Moderation commands (ban, kick, mute, unmute)
- Slash commands support

## Architecture
- **AtomicVault.py**: Main bot file with all commands and event handlers
- **server.py**: Flask keep-alive server (runs on port 5000)
- **vouches.json**: Storage for user vouches

## Required Secrets
- `DISCORD_TOKEN`: Discord bot token from the Discord Developer Portal

## Running the Bot
The bot is run via the "Discord Bot" workflow which executes `python AtomicVault.py`.
The Flask server starts automatically to keep the bot alive on Replit.

## Dependencies
- discord.py==2.4.0
- python-dotenv
- flask
