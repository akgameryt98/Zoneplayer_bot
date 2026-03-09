import asyncio
import os
import requests
import yt_dlp
from telethon import TelegramClient, events
from config import API_ID, API_HASH, BOT_TOKEN

bot = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

def search_jiosaavn(query):
    try:
        url = f"https://saavn.dev/api/search/songs?query={query}&limit=1"
        r = requests.get(url, timeout=10)
        data = r.json()
        song = data["data"]["results"][0]
        title = song["name"]
        artist = song["artists"]["primary"][0]["name"]
        # Highest quality download URL
        dl_url = song["downloadUrl"][-1]["url"]
        duration = song["duration"]
        return dl_url, f"{title} - {artist}", duration
    except Exception as e:
        return None, None, None

def download_song(url, title):
    os.makedirs("dl", exist_ok=True)
    safe_title = "".join(c for c in title if c.isalnum() or c in " -_")[:50]
    path = f"dl/{safe_title}.mp3"
    r = requests.get(url, stream=True, timeout=30)
    with open(path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    return path

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.reply(
        "🎵 **Music Bot Ready!**\n\n"
        "▶️ /play [song name] - Song bajao\n"
        "/help - Help dekho"
    )

@bot.on(events.NewMessage(pattern='/help'))
async def help_cmd(event):
    await event.reply(
        "📋 **Commands:**\n\n"
        "▶️ /play [song name]\n\n"
        "**Example:**\n"
        "`/play Arijit Singh Tum Hi Ho`\n"
        "`/play mujhe peene do`"
    )

@bot.on(events.NewMessage(pattern='/play'))
async def play(event):
    text = event.message.text
    parts = text.split(None, 1)

    if len(parts) < 2:
        await event.reply("❌ Song ka naam likho!\nExample: `/play Arijit Singh`")
        return

    query = parts[1].strip()
    msg = await event.reply(f"🔍 **Searching:** `{query}`...")

    try:
        dl_url, title, duration = search_jiosaavn(query)

        if not dl_url:
            await msg.edit("❌ Song nahi mila! Dobara try karo.")
            return

        await msg.edit(f"⬇️ **Downloading:** `{title}`...")
        path = download_song(dl_url, title)

        mins = int(duration) // 60
        secs = int(duration) % 60
        dur_str = f"{mins}:{secs:02d}"

        await msg.edit(f"📤 **Sending:** `{title}`...")

        await bot.send_file(
            event.chat_id,
            path,
            caption=(
                f"🎵 **{title}**\n"
                f"⏱ Duration: {dur_str}\n"
                f"👤 By: {event.sender.first_name}"
            ),
        )
        await msg.delete()

        try:
            os.remove(path)
        except:
            pass

    except Exception as e:
        await msg.edit(f"❌ Error: `{str(e)}`")

print("✅ Bot chalu ho gaya!")
bot.run_until_disconnected()
