import asyncio
import os
import yt_dlp
from youtubesearchpython import VideosSearch
from telethon import TelegramClient, events
from config import API_ID, API_HASH, BOT_TOKEN

bot = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

def search_yt(query):
    try:
        s = VideosSearch(query, limit=1)
        r = s.result()["result"][0]
        return r["link"], r["title"], r["duration"]
    except:
        return None, None, None

def dl_audio(url):
    os.makedirs("dl", exist_ok=True)
    opts = {
        "format": "bestaudio/best",
        "outtmpl": "dl/%(id)s.%(ext)s",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "128",
        }],
        "quiet": True,
    }
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(url, download=True)
        return f"dl/{info['id']}.mp3", info["title"]

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.reply(
        "🎵 **Music Bot Ready!**\n\n"
        "/play [song] - Song bajao\n"
        "/help - Commands dekho"
    )

@bot.on(events.NewMessage(pattern='/help'))
async def help_cmd(event):
    await event.reply(
        "📋 **Commands:**\n\n"
        "▶️ /play [song name] - Song bajao\n"
        "🔗 /play [youtube link] - Link se bajao"
    )

@bot.on(events.NewMessage(pattern='/play'))
async def play(event):
    text = event.message.text
    parts = text.split(None, 1)
    
    if len(parts) < 2:
        await event.reply("❌ Song ka naam likho!\nExample: `/play Arijit Singh`")
        return
    
    query = parts[1]
    msg = await event.reply(f"🔍 Searching: `{query}`...")
    
    # YouTube search
    if "youtube.com" in query or "youtu.be" in query:
        url = query
        title = "YouTube Video"
        dur = "Unknown"
    else:
        url, title, dur = search_yt(query)
    
    if not url:
        await msg.edit("❌ Song nahi mila!")
        return
    
    await msg.edit(f"⬇️ Downloading: `{title}`...")
    
    try:
        path, name = dl_audio(url)
        await msg.edit(f"📤 Sending: `{name}`...")
        
        # Audio file send karo
        await bot.send_file(
            event.chat_id,
            path,
            caption=f"🎵 **{name}**\n⏱ Duration: {dur}\n👤 Requested by: {event.sender.first_name}",
            attributes=[],
            voice_note=False
        )
        await msg.delete()
        
        # File delete karo space ke liye
        try:
            os.remove(path)
        except:
            pass
            
    except Exception as e:
        await msg.edit(f"❌ Error: {str(e)}")

print("✅ Bot Starting...")
bot.run_until_disconnected()
