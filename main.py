import asyncio
import os
import requests
from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import AudioPiped
from pytgcalls.types.input_stream.quality import HighQualityAudio
from config import API_ID, API_HASH, BOT_TOKEN

app = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
call_py = PyTgCalls(app)
queues = {}

def search_jiosaavn(query):
    try:
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
        dl_url = song["downloadUrl"][-1]["link"]
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

async def play_next(chat_id):
    if chat_id in queues and queues[chat_id]:
        song = queues[chat_id][0]
        await call_py.join_group_call(
            chat_id,
            AudioPiped(
                song["file"],
                HighQualityAudio()
            )
        )

@app.on_message(filters.command("start"))
async def start(_, m: Message):
    await m.reply(
        "🎵 **VC Music Bot Ready!**\n\n"
        "▶️ /play [song] - Play in Voice Chat\n"
        "⏸️ /pause - Pause\n"
        "▶️ /resume - Resume\n"
        "⏹️ /stop - Stop\n"
        "📋 /queue - Show queue\n\n"
        "⚠️ First start Voice Chat in group!"
    )

@app.on_message(filters.command("play"))
async def play(_, m: Message):
    chat_id = m.chat.id
    if len(m.command) < 2:
        await m.reply("❌ Write song name!\nExample: `/play Tum Hi Ho`")
        return

    query = " ".join(m.command[1:])
    msg = await m.reply(f"🔍 **Searching:** `{query}`...")

    try:
        dl_url, title, duration = search_jiosaavn(query)
        if not dl_url:
            await msg.edit("❌ Song not found!")
            return

        await msg.edit(f"⬇️ **Downloading:** `{title}`...")
        path = download_song(dl_url, title)

        mins = duration // 60
        secs = duration % 60

        if chat_id not in queues:
            queues[chat_id] = []

        queues[chat_id].append({
            "file": path,
            "title": title,
            "duration": f"{mins}:{secs:02d}",
            "by": m.from_user.first_name
        })

        if len(queues[chat_id]) == 1:
            await play_next(chat_id)
            await msg.edit(
                f"🎵 **Now Playing in VC:**\n"
                f"🎶 {title}\n"
                f"⏱ Duration: {mins}:{secs:02d}\n"
                f"👤 Requested by: {m.from_user.first_name}"
            )
        else:
            await msg.edit(
                f"📋 **Added to Queue:**\n"
                f"🎶 {title}\n"
                f"📍 Position: #{len(queues[chat_id])}"
            )

    except Exception as e:
        await msg.edit(f"❌ Error: `{str(e)}`")

@app.on_message(filters.command("pause"))
async def pause(_, m: Message):
    try:
        await call_py.pause_stream(m.chat.id)
        await m.reply("⏸️ **Paused!**")
    except:
        await m.reply("❌ Nothing playing!")

@app.on_message(filters.command("resume"))
async def resume(_, m: Message):
    try:
        await call_py.resume_stream(m.chat.id)
        await m.reply("▶️ **Resumed!**")
    except:
        await m.reply("❌ Nothing paused!")

@app.on_message(filters.command("stop"))
async def stop(_, m: Message):
    chat_id = m.chat.id
    try:
        await call_py.leave_group_call(chat_id)
        queues[chat_id] = []
        await m.reply("⏹️ **Stopped!**")
    except:
        await m.reply("❌ Bot not in VC!")

@app.on_message(filters.command("queue"))
async def show_queue(_, m: Message):
    chat_id = m.chat.id
    if chat_id not in queues or not queues[chat_id]:
        await m.reply("📋 Queue is empty!")
        return
    text = "📋 **Queue:**\n\n"
    for i, song in enumerate(queues[chat_id], 1):
        status = "▶️ Playing" if i == 1 else f"#{i}"
        text += f"{status} - {song['title']}\n"
    await m.reply(text)

@call_py.on_stream_end()
async def stream_ended(_, update):
    chat_id = update.chat_id
    if chat_id in queues and queues[chat_id]:
        queues[chat_id].pop(0)
        if queues[chat_id]:
            await play_next(chat_id)
        else:
            await call_py.leave_group_call(chat_id)

async def main():
    await app.start()
    await call_py.start()
    print("✅ VC Music Bot Ready!")
    await asyncio.get_event_loop().run_forever()

asyncio.run(main())
