# 🤖 Channel Copier Bot

A personal-use Telegram bot to copy content from source channels to your destination channel with smart bandwidth management.

## ✨ Features

- 🔐 Owner/Admin/User role system
- 📱 Login via phone+OTP or session string  
- 🔗 Search & connect any channel you're a member of
- 📊 Channel content analysis
- 📥 Copy by range or entire channel
- 🎯 Filter by type (video/PDF/document)
- ⚡ Native copy first (zero bandwidth)
- 💾 Auto-fallback to download+upload for restricted content
- 🛡 4.5 GB bandwidth safety limit
- ✍️ Custom caption signature
- ⏯ Pause/Resume/Stop/Skip controls
- 📢 Broadcast to authorized users

## 🚀 Deployment on Render

### 1. Get Required Credentials

- **API_ID & API_HASH** → https://my.telegram.org
- **BOT_TOKEN** → @BotFather on Telegram
- **OWNER_ID** → Your Telegram user ID (from @userinfobot)

### 2. Deploy

1. Fork this repo
2. Create a new Web Service on [Render](https://render.com)
3. Connect your repository
4. Add environment variables:
   - `API_ID`
   - `API_HASH`
   - `BOT_TOKEN`
   - `OWNER_ID`
   - `BOT_SIGNATURE` (optional)
   - `BANDWIDTH_LIMIT_GB` (optional, default 4.5)
5. Deploy!

### 3. First Time Setup

1. Start a chat with your bot
2. Send `/start` to verify access
3. Login: `/session <your_session_string>` OR `/login`
4. Set destination: `/setdest <channel_name>`
5. Connect source: `/connect <channel_name>`
6. Analyze: `/analyze`
7. Copy: `/copy 1-50` or `/v 1-100`

## 📚 Commands

### Basic
- `/start` - Welcome
- `/help` - Command list  
- `/status` - Bot status
- `/progress` - Copy progress

### Auth (Owner/Admin)
- `/login` - Phone+OTP login
- `/session <string>` - Session string login
- `/logout` - Logout

### Channels
- `/connect <name>` - Connect source
- `/setdest <name>` - Set destination
- `/analyze` - Analyze source

### Copy
- `/copy 1-50` - Copy range
- `/copy all` - Copy everything
- `/v 1-50` - Only videos
- `/p 1-50` - Only PDFs
- `/d 1-50` - Only documents

### Control
- `/pause` `/resume` `/stop` `/skip`

### User Management (Owner)
- `/addadmin <id>` - Add admin
- `/adduser <id>` - Add monitor user
- `/broadcast <msg>` - Message all users

## ⚠️ Notes

- Bot uses **in-memory storage** — session and settings reset on restart
- After Render restart, run `/session` or `/login` again
- Uses `copy_message()` (zero bandwidth) first; falls back to download+upload
- When 4.5 GB used, switches to **copy-only mode** to protect quota

## 🛠 Tech Stack

- Python 3.11+
- Pyrogram 2.0
- TgCrypto (fast encryption)
- aiohttp (web server for Render)
- loguru (logging)

## 📝 License

Personal use only.

— Made with ❤️ by @XyrDeveloper
