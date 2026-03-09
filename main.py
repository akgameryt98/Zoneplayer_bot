import asyncio
import os
from pyrofork import Client, filters
from pyrofork.types import Message
from pytgcalls import PyTgCalls
from pytgcalls.types import Update
from pytgcalls.types.input_stream import AudioPiped
import yt_dlp
from youtubesearchpython import VideosSearch
from config import API_ID, API_HASH, BOT_TOKEN

app = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
call_py = PyTgCalls(app)
queues = {}

def search_youtube(query):
    search = VideosSearch(query, limit=1)
    results = search.result()
    if results["result"]:
        video = results["result"][0]
        return video["link"], video["title"], video["duration"]
    return None, None, None

def download_audio(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '128',
        }],
        'quiet': True,
    }
    os.makedirs('downloads', exist_ok=True)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = f"downloads/{info['id']}.mp3"
        return filename, info['title']

@app.on_message(filters.command("start"))
async def start(client, message: Message):
    await message.reply_text(
        "🎵 **Music Bot Ready!**\n\n"
        "**Commands:**\n"
        "▶️ `/play [song name]` - Song bajao\n"
        "⏸️ `/pause` - Pause karo\n"
        "▶️ `/resume` - Resume karo\n"
        "⏹️ `/stop` - Band karo\n"
        "📋 `/queue` - Queue dekho\n\n"
        "**Pehle Voice Chat join karo, phir /play use karo!**"
    )

@app.on_message(filters.command("play"))
async def play(client, message: Message):
    chat_id = message.chat.id
    if len(message.command) < 2:
        await message.reply_text("❌ Song ka naam likho!\nExample: `/play Arijit Singh Tum Hi Ho`")
        return
    query = " ".join(message.command[1:])
    searching_msg = await message.reply_text(f"🔍 **Searching:** `{query}`...")
    url, title, duration = search_youtube(query)
    if not url:
        await searching_msg.edit("❌ Song nahi mila! Dobara try karo.")
        return
    await searching_msg.edit(f"⬇️ **Downloading:** `{title}`...")
    try:
        file_path, song_title = download_audio(url)
        if chat_id not in queues:
            queues[chat_id] = []
        queues[chat_id].append({
            'file': file_path,
            'title': song_title,
            'duration': duration,
            'requested_by': message.from_user.first_name
        })
        if len(queues[chat_id]) == 1:
            await play_next(chat_id)
            await searching_msg.edit(
                f"🎵 **Playing Now:**\n"
                f"🎶 {song_title}\n"
                f"⏱️ Duration: {duration}\n"
                f"👤 Requested by: {message.from_user.first_name}"
            )
        else:
            await searching_msg.edit(
                f"📋 **Added to Queue:**\n"
                f"🎶 {song_title}\n"
                f"📍 Position: {len(queues[chat_id])}"
            )
    except Exception as e:
        await searching_msg.edit(f"❌ Error: {str(e)}")

async def play_next(chat_id):
    if chat_id in queues and queues[chat_id]:
        song = queues[chat_id][0]
        try:
            await call_py.join_group_call(
                chat_id,
                AudioPiped(song['file']),
                stream_type=None
            )
        except Exception as e:
            print(f"Error playing: {e}")

@app.on_message(filters.command("pause"))
async def pause(client, message: Message):
    try:
        await call_py.pause_stream(message.chat.id)
        await message.reply_text("⏸️ **Paused!**")
    except:
        await message.reply_text("❌ Koi song nahi chal raha!")

@app.on_message(filters.command("resume"))
async def resume(client, message: Message):
    try:
        await call_py.resume_stream(message.chat.id)
        await message.reply_text("▶️ **Resumed!**")
    except:
        await message.reply_text("❌ Koi song pause nahi hai!")

@app.on_message(filters.command("stop"))
async def stop(client, message: Message):
    chat_id = message.chat.id
    try:
        await call_py.leave_group_call(chat_id)
        if chat_id in queues:
            queues[chat_id] = []
        await message.reply_text("⏹️ **Stopped!**")
    except:
        await message.reply_text("❌ Bot Voice Chat mein nahi hai!")

@app.on_message(filters.command("queue"))
async def show_queue(client, message: Message):
    chat_id = message.chat.id
    if chat_id not in queues or not queues[chat_id]:
        await message.reply_text("📋 Queue khali hai!")
        return
    queue_text = "📋 **Queue:**\n\n"
    for i, song in enumerate(queues[chat_id], 1):
        status = "▶️ Playing" if i == 1 else f"#{i}"
        queue_text += f"{status} - {song['title']}\n"
    await message.reply_text(queue_text)

@call_py.on_stream_end()
async def stream_ended(client, update: Update):
    chat_id = update.chat_id
    if chat_id in queues and queues[chat_id]:
        queues[chat_id].pop(0)
        if queues[chat_id]:
            await play_next(chat_id)
        else:
            await call_py.leave_group_call(chat_id)

async def main():
    print("🎵 Music Bot Starting...")
    await app.start()
    await call_py.start()
    print("✅ Bot Ready!")
    await asyncio.get_event_loop().run_forever()

if __name__ == "__main__":
    asyncio.run(main())
