import asyncio
import os
import requests
from pyrogram import Client, filters
from pyrogram.types import Message
from config import API_ID, API_HASH, BOT_TOKEN

app = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

favorites = {}
history = {}

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

def search_jiosaavn_multiple(query, limit=5):
    try:
        url = f"https://jiosaavn-api-privatecvc2.vercel.app/search/songs?query={query}&page=1&limit={limit}"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=15)
        data = r.json()
        return data["data"]["results"]
    except:
        return []

def download_song(url, title):
    os.makedirs("dl", exist_ok=True)
    safe_title = "".join(c for c in title if c.isalnum() or c in " -_")[:50]
    path = f"dl/{safe_title}.mp3"
    r = requests.get(url, stream=True, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    with open(path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    return path

@app.on_message(filters.command("start"))
async def start(_, m: Message):
    await m.reply(
        "🎵 **Welcome to Music Bot!**\n\n"
        "**Available Commands:**\n\n"
        "📥 `/download [song]` - Download song as audio file\n"
        "🔍 `/search [song]` - Search top 5 results\n"
        "ℹ️ `/info [song]` - Get song details\n"
        "⭐ `/save [song]` - Save to favorites\n"
        "🗑 `/removefav [song]` - Remove from favorites\n"
        "💾 `/favorites` - View saved songs\n"
        "📜 `/history` - View last 10 played songs\n"
        "🎵 `/top10` - Top trending songs\n"
        "❓ `/help` - Help menu\n\n"
        "🔜 **Coming Soon:**\n"
        "🎙 `/play [song]` - Play in Voice Chat\n"
        "⏸ `/pause` - Pause playback\n"
        "▶️ `/resume` - Resume playback\n"
        "⏹ `/stop` - Stop playback\n"
        "📋 `/queue` - View song queue"
    )

@app.on_message(filters.command("help"))
async def help_cmd(_, m: Message):
    await m.reply(
        "❓ **Help Menu:**\n\n"
        "📥 `/download Tum Hi Ho` - Download song\n"
        "🔍 `/search Arijit Singh` - Search 5 results\n"
        "ℹ️ `/info Blinding Lights` - Song info\n"
        "⭐ `/save Tum Hi Ho` - Add to favorites\n"
        "🗑 `/removefav Tum Hi Ho` - Remove from favorites\n"
        "💾 `/favorites` - View your favorites\n"
        "📜 `/history` - Recent songs\n"
        "🎵 `/top10` - Top trending songs\n\n"
        "🔜 **Coming Soon:**\n"
        "🎙 Voice Chat playback feature!"
    )

@app.on_message(filters.command("play"))
async def play_coming_soon(_, m: Message):
    await m.reply(
        "🔜 **Coming Soon!**\n\n"
        "Voice Chat play feature is under development.\n\n"
        "Meanwhile use:\n"
        "📥 `/download [song]` - Download song now!"
    )

@app.on_message(filters.command("download"))
async def download(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2:
        await m.reply("❌ Please write song name!\nExample: `/download Tum Hi Ho`")
        return

    query = parts[1].strip()
    msg = await m.reply(f"🔍 **Searching:** `{query}`...")

    try:
        dl_url, title, duration = search_jiosaavn(query)
        if not dl_url:
            await msg.edit("❌ Song not found! Please try a different name.")
            return

        await msg.edit(f"⬇️ **Downloading:** `{title}`...")
        path = download_song(dl_url, title)

        mins = duration // 60
        secs = duration % 60

        user_id = m.from_user.id
        if user_id not in history:
            history[user_id] = []
        history[user_id].insert(0, title)
        if len(history[user_id]) > 10:
            history[user_id] = history[user_id][:10]

        await msg.edit(f"📤 **Sending:** `{title}`...")
        await app.send_audio(
            m.chat.id,
            path,
            caption=(
                f"🎵 **{title}**\n"
                f"⏱ Duration: {mins}:{secs:02d}\n"
                f"👤 Requested by: {m.from_user.first_name}"
            ),
            title=title,
            duration=duration
        )
        await msg.delete()

        try:
            os.remove(path)
        except:
            pass

    except Exception as e:
        await msg.edit(f"❌ Error: `{str(e)}`")

@app.on_message(filters.command("search"))
async def search(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2:
        await m.reply("❌ Example: `/search Arijit Singh`")
        return

    query = parts[1].strip()
    msg = await m.reply(f"🔍 **Searching:** `{query}`...")

    results = search_jiosaavn_multiple(query, 5)
    if not results:
        await msg.edit("❌ No results found!")
        return

    text = f"🔍 **Search Results for:** `{query}`\n\n"
    for i, song in enumerate(results, 1):
        title = song["name"]
        artist = song["primaryArtists"]
        duration = int(song["duration"])
        mins = duration // 60
        secs = duration % 60
        text += f"{i}. **{title}**\n   👤 {artist} | ⏱ {mins}:{secs:02d}\n\n"

    text += "📥 Use `/download [song name]` to download!"
    await msg.edit(text)

@app.on_message(filters.command("save"))
async def save_favorite(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2:
        await m.reply("❌ Example: `/save Tum Hi Ho`")
        return

    query = parts[1].strip()
    user_id = m.from_user.id

    if user_id not in favorites:
        favorites[user_id] = []

    if query in favorites[user_id]:
        await m.reply(f"⭐ `{query}` is already in your favorites!")
        return

    if len(favorites[user_id]) >= 20:
        await m.reply("❌ Favorites full! Maximum 20 songs allowed.")
        return

    favorites[user_id].append(query)
    await m.reply(f"⭐ **Saved to favorites:** `{query}`")

@app.on_message(filters.command("favorites"))
async def show_favorites(_, m: Message):
    user_id = m.from_user.id

    if user_id not in favorites or not favorites[user_id]:
        await m.reply("💾 No favorites yet!\nUse `/save [song name]` to add songs.")
        return

    text = "⭐ **Your Favorites:**\n\n"
    for i, song in enumerate(favorites[user_id], 1):
        text += f"{i}. {song}\n"
    text += "\n📥 Use `/download [song name]` to download!"
    await m.reply(text)

@app.on_message(filters.command("removefav"))
async def remove_favorite(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2:
        await m.reply("❌ Example: `/removefav Tum Hi Ho`")
        return

    query = parts[1].strip()
    user_id = m.from_user.id

    if user_id not in favorites or query not in favorites[user_id]:
        await m.reply(f"❌ `{query}` is not in your favorites!")
        return

    favorites[user_id].remove(query)
    await m.reply(f"🗑 **Removed from favorites:** `{query}`")

@app.on_message(filters.command("history"))
async def show_history(_, m: Message):
    user_id = m.from_user.id

    if user_id not in history or not history[user_id]:
        await m.reply("📜 No history yet!\nDownload some songs first.")
        return

    text = "📜 **Your Recent Songs:**\n\n"
    for i, song in enumerate(history[user_id], 1):
        text += f"{i}. {song}\n"
    await m.reply(text)

@app.on_message(filters.command("info"))
async def song_info(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2:
        await m.reply("❌ Example: `/info Tum Hi Ho`")
        return

    query = parts[1].strip()
    msg = await m.reply(f"🔍 **Getting info:** `{query}`...")

    try:
        url = f"https://jiosaavn-api-privatecvc2.vercel.app/search/songs?query={query}&page=1&limit=1"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=15)
        data = r.json()
        results = data["data"]["results"]

        if not results:
            await msg.edit("❌ Song not found!")
            return

        song = results[0]
        title = song["name"]
        artist = song["primaryArtists"]
        album = song.get("album", {}).get("name", "Unknown")
        year = song.get("year", "Unknown")
        duration = int(song["duration"])
        mins = duration // 60
        secs = duration % 60
        language = song.get("language", "Unknown").capitalize()

        await msg.edit(
            f"ℹ️ **Song Info:**\n\n"
            f"🎵 **Title:** {title}\n"
            f"👤 **Artist:** {artist}\n"
            f"💿 **Album:** {album}\n"
            f"📅 **Year:** {year}\n"
            f"🌐 **Language:** {language}\n"
            f"⏱ **Duration:** {mins}:{secs:02d}\n\n"
            f"📥 `/download {title}` to download!"
        )

    except Exception as e:
        await msg.edit(f"❌ Error: `{str(e)}`")

@app.on_message(filters.command("top10"))
async def top10(_, m: Message):
    await m.reply(
        "🎵 **Top 10 Trending Songs (India):**\n\n"
        "1. Tum Hi Ho - Arijit Singh\n"
        "2. Kesariya - Arijit Singh\n"
        "3. Raataan Lambiyan - Jubin Nautiyal\n"
        "4. Apna Bana Le - Arijit Singh\n"
        "5. O Maahi - Arijit Singh\n"
        "6. Teri Baaton Mein - Stebin Ben\n"
        "7. Sajni - Arijit Singh\n"
        "8. Tere Vaaste - Varun Jain\n"
        "9. Naina - Darshan Raval\n"
        "10. Ik Vaari Aa - Arijit Singh\n\n"
        "📥 `/download [song name]` to download any!"
    )

print("✅ Bot started!")
app.run()
