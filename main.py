port asyncio
import os
import requests
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from config import API_ID, API_HASH, BOT_TOKEN

app = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Store user favorites and history
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
            return None, None, None, None
        song = results[0]
        title = song["name"]
        artist = song["primaryArtists"]
        dl_url = song["downloadUrl"][-1]["link"]
        duration = int(song["duration"])
        image = song["image"][-1]["link"] if song.get("image") else None
        return dl_url, f"{title} - {artist}", duration, image
    except Exception as e:
        print(f"Search error: {e}")
        return None, None, None, None

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
        "**Commands:**\n"
        "▶️ `/play [song]` - Play song\n"
        "🔍 `/search [song]` - Search top 5 results\n"
        "📥 `/download [song]` - Download song\n"
        "⭐ `/save [song]` - Save to favorites\n"
        "💾 `/favorites` - My saved songs\n"
        "📜 `/history` - Last 10 songs\n"
        "🎵 `/top10` - Top requested songs\n"
        "ℹ️ `/info [song]` - Song details\n"
        "❓ `/help` - Help"
    )

@app.on_message(filters.command("help"))
async def help_cmd(_, m: Message):
    await m.reply(
        "❓ **Help Menu:**\n\n"
        "▶️ `/play Tum Hi Ho` - Song bajao\n"
        "🔍 `/search Shape of You` - 5 results dikho\n"
        "📥 `/download Kesariya` - File download karo\n"
        "⭐ `/save Tum Hi Ho` - Favorites mein save karo\n"
        "💾 `/favorites` - Saved songs dekho\n"
        "📜 `/history` - Recent songs\n"
        "ℹ️ `/info Blinding Lights` - Song info dekho"
    )

@app.on_message(filters.command(["play", "download"]))
async def play(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2:
        await m.reply("❌ Song ka naam likho!\nExample: `/play Tum Hi Ho`")
        return

    query = parts[1].strip()
    msg = await m.reply(f"🔍 **Searching:** `{query}`...")

    try:
        dl_url, title, duration, image = search_jiosaavn(query)
        if not dl_url:
            await msg.edit("❌ Song not found! Try different name.")
            return

        await msg.edit(f"⬇️ **Downloading:** `{title}`...")
        path = download_song(dl_url, title)

        mins = duration // 60
        secs = duration % 60

        # Save to history
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
                f"👤 Requested by: {m.from_user.first_name}\n\n"
                f"💡 `/save {title}` to add to favorites"
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

    text += "▶️ Use `/play [song name]` to play any song!"
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
        await m.reply(f"⭐ `{query}` already in favorites!")
        return

    if len(favorites[user_id]) >= 20:
        await m.reply("❌ Favorites full! Max 20 songs. Remove some with `/removefav`")
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
    text += "\n▶️ Use `/play [song name]` to play!"
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
        await m.reply(f"❌ `{query}` not in favorites!")
        return

    favorites[user_id].remove(query)
    await m.reply(f"🗑 **Removed from favorites:** `{query}`")

@app.on_message(filters.command("history"))
async def show_history(_, m: Message):
    user_id = m.from_user.id

    if user_id not in history or not history[user_id]:
        await m.reply("📜 No history yet!\nPlay some songs first.")
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
            f"▶️ `/play {title}` to play!"
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
        "▶️ `/play [song name]` to play any!"
    )

print("✅ Bot started!")
app.run()
