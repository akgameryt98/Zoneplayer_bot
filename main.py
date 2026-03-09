import asyncio
import os
import yt_dlp
from youtubesearchpython import VideosSearch
from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import AudioPiped
from config import API_ID, API_HASH, BOT_TOKEN

app = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
pytgcalls = PyTgCalls(app)
queues = {}

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
        "format": "bestaudio",
        "outtmpl": "dl/%(id)s.%(ext)s",
        "quiet": True,
    }
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(url, download=True)
        return f"dl/{info['id']}.{info['ext']}", info["title"]

@app.on_message(filters.command("start"))
async def start(_, m: Message):
    await m.reply("🎵 Music Bot!\n/play [song] - bajao\n/pause - pause\n/resume - resume\n/stop - band karo")

@app.on_message(filters.command("play"))
async def play(_, m: Message):
    if len(m.command) < 2:
        await m.reply("❌ /play ke baad song naam likho")
        return
    q = " ".join(m.command[1:])
    msg = await m.reply(f"🔍 Searching: {q}")
    url, title, dur = search_yt(q)
    if not url:
        await msg.edit("❌ Song nahi mila!")
        return
    await msg.edit(f"⬇️ Downloading: {title}")
    try:
        path, name = dl_audio(url)
        cid = m.chat.id
        if cid not in queues:
            queues[cid] = []
        queues[cid].append({"file": path, "title": name})
        if len(queues[cid]) == 1:
            await pytgcalls.join_group_call(cid, AudioPiped(path))
            await msg.edit(f"▶️ Playing: {name}\n⏱ {dur}")
        else:
            await msg.edit(f"📋 Queue mein add: {name} (#{len(queues[cid])})")
    except Exception as e:
        await msg.edit(f"❌ Error: {e}")

@app.on_message(filters.command("pause"))
async def pause(_, m: Message):
    try:
        await pytgcalls.pause_stream(m.chat.id)
        await m.reply("⏸️ Paused!")
    except:
        await m.reply("❌ Kuch nahi chal raha!")

@app.on_message(filters.command("resume"))
async def resume(_, m: Message):
    try:
        await pytgcalls.resume_stream(m.chat.id)
        await m.reply("▶️ Resumed!")
    except:
        await m.reply("❌ Paused nahi hai!")

@app.on_message(filters.command("stop"))
async def stop(_, m: Message):
    try:
        await pytgcalls.leave_group_call(m.chat.id)
        queues[m.chat.id] = []
        await m.reply("⏹️ Stopped!")
    except:
        await m.reply("❌ Bot VC mein nahi!")

async def main():
    await app.start()
    await pytgcalls.start()
    print("✅ Bot chalu!")
    await asyncio.get_event_loop().run_forever()

asyncio.run(main())
