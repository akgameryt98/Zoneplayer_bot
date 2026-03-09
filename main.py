import asyncio
import os
import requests
from telethon import TelegramClient, events
from config import API_ID, API_HASH, BOT_TOKEN

bot = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

def search_jiosaavn(query):
    try:
        # New API endpoint
        url = f"https://jiosaavn-api-privatecvc2.vercel.app/search/songs?query={query}&page=1&limit=1"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=15)
        data = r.json()
        results = data["data"]["results"]
        if not results:
            return None, None, None
        song = results[0]
        title = song["name"]
        artist = song["primaryArtists"]
        download_urls = song["downloadUrl"]
        # Get highest quality
        dl_url = download_urls[-1]["link"]
        duration = int(song["duration"])
        return dl_url, f"{title} - {artist}", duration
    except Exception as e:
        print(f"Search error: {e}")
        return None, None, None

def download_song(url, title):
    os.makedirs("dl", exist_ok=True)
    safe_title = "".join(c for c in title if c.isalnum() or c in " -_")[:50]
    path = f"dl/{safe_title}.mp3"
    r = requests.get(url, stream=True, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    with open(path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    return path

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.reply(
        "🎵 **Music Bot Ready!**\n\n"
        "▶️ /play [song name] - Play song\n"
        "/help - Show commands"
    )

@bot.on(events.NewMessage(pattern='/help'))
async def help_cmd(event):
    await event.reply(
        "📋 **Commands:**\n\n"
        "▶️ /play [song name]\n\n"
        "**Examples:**\n"
        "`/play Tum Hi Ho`\n"
        "`/play Mujhe Peene Do`\n"
        "`/play Shape of You`"
    )

@bot.on(events.NewMessage(pattern='/play'))
async def play(event):
    text = event.message.text
    parts = text.split(None, 1)

    if len(parts) < 2:
        await event.reply("❌ Please write song name!\nExample: `/play Tum Hi Ho`")
        return

    query = parts[1].strip()
    msg = await event.reply(f"🔍 **Searching:** `{query}`...")

    try:
        dl_url, title, duration = search_jiosaavn(query)

        if not dl_url:
            await msg.edit("❌ Song not found! Please try different name.")
            return

        await msg.edit(f"⬇️ **Downloading:** `{title}`...")
        path = download_song(dl_url, title)

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
                f"👤 Requested by: {event.sender.first_name}"
            ),
        )
        await msg.delete()

        try:
            os.remove(path)
        except:
            pass

    except Exception as e:
        await msg.edit(f"❌ Error: `{str(e)}`")

print("✅ Bot started!")
bot.run_until_disconnected()
