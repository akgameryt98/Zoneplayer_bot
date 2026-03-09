import asyncio
import os
import yt_dlp
from telethon import TelegramClient, events
from config import API_ID, API_HASH, BOT_TOKEN

bot = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

def search_and_download(query):
    os.makedirs("dl", exist_ok=True)
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": "dl/%(id)s.%(ext)s",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "128",
        }],
        "quiet": True,
        "noplaylist": True,
        "source_address": "0.0.0.0",
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"],
            }
        },
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.185 Mobile Safari/537.36",
        },
        "default_search": "ytsearch1",
    }
    with yt_dlp.YoutubeDL(ydl_opts) as y:
        info = y.extract_info(query, download=True)
        if "entries" in info:
            info = info["entries"][0]
        path = f"dl/{info['id']}.mp3"
        return path, info["title"], info.get("duration", 0)

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
        "▶️ /play [song name]\n"
        "▶️ /play [youtube link]\n\n"
        "**Example:**\n"
        "`/play Arijit Singh Tum Hi Ho`"
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
        await msg.edit("⬇️ **Downloading...** please wait 30 sec")
        path, title, duration = search_and_download(query)

        mins = duration // 60
        secs = duration % 60
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
            voice_note=False
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
