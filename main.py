import asyncio
import os
import requests
import random
import datetime
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from config import API_ID, API_HASH, BOT_TOKEN

app = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

favorites = {}
history = {}
stats = {"total_downloads": 0, "users": set()}
last_downloaded = {}
user_stats = {}

MOOD_SONGS = {
    "happy": ["Happy Pharrell Williams", "Uptown Funk Bruno Mars", "Badtameez Dil", "Gallan Goodiyaan", "Balam Pichkari"],
    "sad": ["Tum Hi Ho", "Channa Mereya", "Agar Tum Saath Ho", "Judaai", "Phir Le Aya Dil"],
    "party": ["Lungi Dance", "DJ Waley Babu", "Kar Gayi Chull", "Saturday Saturday", "Dance Ka Bhoot"],
    "romantic": ["Tum Hi Ho", "Raataan Lambiyan", "Kesariya", "Hawayein", "Tera Ban Jaunga"],
    "workout": ["Till I Collapse Eminem", "Lose Yourself Eminem", "Eye of the Tiger", "Believer Imagine Dragons", "Thunder Imagine Dragons"],
    "chill": ["Iktara", "Kabira", "Khaabon Ke Parinday", "Tum Se Hi", "O Re Piya"]
}

RANDOM_SONGS = [
    "Tum Hi Ho", "Kesariya", "Raataan Lambiyan", "Blinding Lights",
    "Shape of You", "Mujhe Peene Do", "Hawayein", "Channa Mereya",
    "Agar Tum Saath Ho", "Gallan Goodiyaan", "Badtameez Dil",
    "Tera Ban Jaunga", "O Maahi", "Apna Bana Le", "Sajni",
    "Tere Vaaste", "Naina Darshan Raval", "Ik Vaari Aa",
    "Kabira", "Iktara", "Phir Le Aya Dil", "Judaai"
]

DAILY_SONGS = [
    "Tum Hi Ho", "Kesariya", "Blinding Lights", "Shape of You",
    "Raataan Lambiyan", "Hawayein", "Channa Mereya", "O Maahi",
    "Apna Bana Le", "Sajni", "Tera Ban Jaunga", "Mujhe Peene Do",
    "Gallan Goodiyaan", "Badtameez Dil", "Ik Vaari Aa",
    "Believer", "Thunder", "Senorita", "Photograph Ed Sheeran",
    "Perfect Ed Sheeran", "Tere Vaaste", "Naina Darshan Raval",
    "Kabira", "Iktara", "Phir Le Aya Dil", "Judaai",
    "Dil Diya Gallan", "Bekhayali", "Bulleya", "Ae Dil Hai Mushkil"
]

BIRTHDAY_SONGS = [
    "Baar Baar Din Yeh Aaye",
    "Happy Birthday To You",
    "Tumhi Ho Bandhu Cocktail",
    "Janam Janam Arijit Singh",
    "Zindagi Na Milegi Dobara",
    "Tum Jiyo Hazaron Saal",
    "Din Shagna Da"
]

NIGHT_SONGS = [
    "O Re Piya", "Tum Se Hi", "Iktara", "Kabira",
    "Khaabon Ke Parinday", "Phir Le Aya Dil", "Judaai",
    "Ae Dil Hai Mushkil", "Bekhayali", "Bulleya"
]

SHORT_SONGS = [
    "Kesariya short", "Tum Hi Ho", "Senorita",
    "Gallan Goodiyaan", "Naina Darshan Raval",
    "Tere Vaaste", "Sajni"
]

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

def get_lyrics(query):
    try:
        url = f"https://jiosaavn-api-privatecvc2.vercel.app/search/songs?query={query}&page=1&limit=1"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=15)
        data = r.json()
        results = data["data"]["results"]
        if not results:
            return None, None
        song = results[0]
        song_id = song["id"]
        title = f"{song['name']} - {song['primaryArtists']}"
        lyrics_url = f"https://jiosaavn-api-privatecvc2.vercel.app/songs/{song_id}/lyrics"
        lr = requests.get(lyrics_url, headers=headers, timeout=15)
        ldata = lr.json()
        lyrics = ldata.get("data", {}).get("lyrics", None)
        return lyrics, title
    except Exception as e:
        print(f"Lyrics error: {e}")
        return None, None

def download_song(url, title):
    os.makedirs("dl", exist_ok=True)
    safe_title = "".join(c for c in title if c.isalnum() or c in " -_")[:50]
    path = f"dl/{safe_title}.mp3"
    r = requests.get(url, stream=True, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    with open(path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    return path

async def send_song(m, query, msg):
    dl_url, title, duration = search_jiosaavn(query)
    if not dl_url:
        await msg.edit("❌ Song not found! Please try a different name.")
        return

    await msg.edit(f"⬇️ **Downloading:** `{title}`...")
    path = download_song(dl_url, title)

    mins = duration // 60
    secs = duration % 60

    user_id = m.from_user.id
    stats["total_downloads"] += 1
    stats["users"].add(user_id)

    if user_id not in history:
        history[user_id] = []
    history[user_id].insert(0, title)
    if len(history[user_id]) > 10:
        history[user_id] = history[user_id][:10]

    if user_id not in user_stats:
        user_stats[user_id] = {"downloads": 0, "songs": []}
    user_stats[user_id]["downloads"] += 1
    user_stats[user_id]["songs"].append(title)

    last_downloaded[user_id] = {
        "title": title,
        "duration": f"{mins}:{secs:02d}",
        "by": m.from_user.first_name
    }

    await msg.edit(f"📤 **Sending:** `{title}`...")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Share Song", switch_inline_query=title)],
        [InlineKeyboardButton("⭐ Save to Favorites", callback_data=f"save_{title[:40]}")]
    ])

    await app.send_audio(
        m.chat.id,
        path,
        caption=(
            f"🎵 **{title}**\n"
            f"⏱ Duration: {mins}:{secs:02d}\n"
            f"👤 Requested by: {m.from_user.first_name}"
        ),
        title=title,
        duration=duration,
        reply_markup=keyboard
    )
    await msg.delete()

    try:
        os.remove(path)
    except:
        pass

@app.on_callback_query(filters.regex(r"^save_"))
async def save_callback(_, callback):
    song_title = callback.data[5:]
    user_id = callback.from_user.id
    if user_id not in favorites:
        favorites[user_id] = []
    if song_title in favorites[user_id]:
        await callback.answer("⭐ Already in favorites!", show_alert=False)
        return
    favorites[user_id].append(song_title)
    await callback.answer("⭐ Saved to favorites!", show_alert=False)

@app.on_callback_query(filters.regex("dl_birthday"))
async def birthday_download(_, callback):
    await callback.answer("Downloading...", show_alert=False)
    msg = await callback.message.reply("⬇️ **Downloading birthday song...**")
    await send_song(callback.message, "Baar Baar Din Yeh Aaye", msg)

@app.on_message(filters.command("start"))
async def start(_, m: Message):
    await m.reply(
        f"🎵 **Welcome to Music Bot!**\n"
        f"Hello {m.from_user.first_name}! 👋\n\n"
        "**Commands:**\n\n"
        "📥 `/download [song]` - Download song\n"
        "🔍 `/search [song]` - Search top 5 results\n"
        "ℹ️ `/info [song]` - Song details\n"
        "📝 `/lyrics [song]` - Song lyrics\n"
        "🎭 `/mood [type]` - Songs by mood\n"
        "🌐 `/hindi` `/punjabi` `/english` - By language\n"
        "🎤 `/artist [name]` - Songs by artist\n"
        "🎲 `/random` - Random song\n"
        "🎵 `/similar [song]` - Similar songs\n"
        "📅 `/daily` - Today's recommended song\n"
        "🌍 `/trending` - Trending songs\n"
        "🎯 `/recommend` - Recommended for you\n"
        "⏱ `/short` - Songs under 3 mins\n"
        "🌙 `/night` - Late night songs\n"
        "🎂 `/birthday [name]` - Birthday songs\n"
        "🎵 `/playlist [mood]` - Download playlist\n"
        "⭐ `/save [song]` - Save to favorites\n"
        "🗑 `/removefav [song]` - Remove favorite\n"
        "💾 `/favorites` - View favorites\n"
        "📜 `/history` - Last 10 songs\n"
        "🎵 `/top10` - Top trending\n"
        "📊 `/stats` - Bot statistics\n"
        "👤 `/mystats` - My personal stats\n"
        "🎵 `/lastdownload` - Last downloaded\n"
        "❓ `/help` - Help menu\n\n"
        "🔜 **Coming Soon:**\n"
        "🎙 `/play` - Voice Chat playback\n"
        "⏸ `/pause` `/resume` `/stop` `/queue`"
    )

@app.on_message(filters.command("help"))
async def help_cmd(_, m: Message):
    await m.reply(
        "❓ **Help Menu:**\n\n"
        "📥 `/download Tum Hi Ho`\n"
        "🔍 `/search Arijit Singh`\n"
        "ℹ️ `/info Blinding Lights`\n"
        "📝 `/lyrics Tum Hi Ho`\n"
        "🎭 `/mood happy/sad/party/romantic/workout/chill`\n"
        "🌐 `/hindi` `/punjabi` `/english`\n"
        "🎤 `/artist Arijit Singh`\n"
        "🎲 `/random`\n"
        "🎵 `/similar Tum Hi Ho`\n"
        "📅 `/daily`\n"
        "🌍 `/trending`\n"
        "🎯 `/recommend`\n"
        "⏱ `/short`\n"
        "🌙 `/night`\n"
        "🎂 `/birthday Rahul`\n"
        "🎵 `/playlist happy`\n"
        "⭐ `/save Tum Hi Ho`\n"
        "🗑 `/removefav Tum Hi Ho`\n"
        "💾 `/favorites`\n"
        "📜 `/history`\n"
        "🎵 `/top10`\n"
        "📊 `/stats`\n"
        "👤 `/mystats`\n"
        "🎵 `/lastdownload`"
    )

@app.on_message(filters.command("play"))
async def play_coming_soon(_, m: Message):
    await m.reply(
        "🔜 **Coming Soon!**\n\n"
        "Voice Chat playback is under development.\n\n"
        "Use 📥 `/download [song]` for now!"
    )

@app.on_message(filters.command("download"))
async def download(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip() in ["[song]", "[song name]"]:
        await m.reply("❌ Please write a song name!\nExample: `/download Tum Hi Ho`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"🔍 **Searching:** `{query}`...")
    await send_song(m, query, msg)

@app.on_message(filters.command("lyrics"))
async def lyrics(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await m.reply("❌ Please write a song name!\nExample: `/lyrics Tum Hi Ho`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"🔍 **Searching lyrics:** `{query}`...")
    try:
        lyrics_text, title = get_lyrics(query)
        if not lyrics_text:
            await msg.edit(f"❌ Lyrics not found for `{query}`!\nTry a different song name.")
            return
        if len(lyrics_text) > 4000:
            lyrics_text = lyrics_text[:4000] + "\n\n... *(lyrics truncated)*"
        await msg.edit(f"📝 **Lyrics: {title}**\n\n{lyrics_text}")
    except Exception as e:
        await msg.edit(f"❌ Error: `{str(e)}`")

@app.on_message(filters.command("search"))
async def search(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
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
        duration = int(song["duration"])
        mins = duration // 60
        secs = duration % 60
        text += f"{i}. **{song['name']}**\n   👤 {song['primaryArtists']} | ⏱ {mins}:{secs:02d}\n\n"
    text += "📥 Use `/download [song name]` to download!"
    await msg.edit(text)

@app.on_message(filters.command("mood"))
async def mood(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await m.reply(
            "🎭 **Choose a mood:**\n\n"
            "`/mood happy` 😊\n`/mood sad` 😢\n"
            "`/mood party` 🎉\n`/mood romantic` 💕\n"
            "`/mood workout` 💪\n`/mood chill` 😌"
        )
        return
    mood_type = parts[1].strip().lower()
    if mood_type not in MOOD_SONGS:
        await m.reply("❌ Invalid mood!\nAvailable: `happy` `sad` `party` `romantic` `workout` `chill`")
        return
    songs = MOOD_SONGS[mood_type]
    emojis = {"happy": "😊", "sad": "😢", "party": "🎉", "romantic": "💕", "workout": "💪", "chill": "😌"}
    text = f"🎭 **{mood_type.capitalize()} Songs** {emojis[mood_type]}\n\n"
    for i, song in enumerate(songs, 1):
        text += f"{i}. {song}\n"
    text += "\n📥 Use `/download [song name]` to download!"
    await m.reply(text)

@app.on_message(filters.command("hindi"))
async def hindi(_, m: Message):
    msg = await m.reply("🔍 **Searching Hindi songs...**")
    results = search_jiosaavn_multiple("hindi hits 2024", 8)
    if not results:
        await msg.edit("❌ No results found!")
        return
    text = "🇮🇳 **Top Hindi Songs:**\n\n"
    for i, song in enumerate(results, 1):
        text += f"{i}. **{song['name']}** - {song['primaryArtists']}\n"
    text += "\n📥 Use `/download [song name]` to download!"
    await msg.edit(text)

@app.on_message(filters.command("punjabi"))
async def punjabi(_, m: Message):
    msg = await m.reply("🔍 **Searching Punjabi songs...**")
    results = search_jiosaavn_multiple("punjabi hits 2024", 8)
    if not results:
        await msg.edit("❌ No results found!")
        return
    text = "🎵 **Top Punjabi Songs:**\n\n"
    for i, song in enumerate(results, 1):
        text += f"{i}. **{song['name']}** - {song['primaryArtists']}\n"
    text += "\n📥 Use `/download [song name]` to download!"
    await msg.edit(text)

@app.on_message(filters.command("english"))
async def english(_, m: Message):
    msg = await m.reply("🔍 **Searching English songs...**")
    results = search_jiosaavn_multiple("english hits 2024", 8)
    if not results:
        await msg.edit("❌ No results found!")
        return
    text = "🎵 **Top English Songs:**\n\n"
    for i, song in enumerate(results, 1):
        text += f"{i}. **{song['name']}** - {song['primaryArtists']}\n"
    text += "\n📥 Use `/download [song name]` to download!"
    await msg.edit(text)

@app.on_message(filters.command("artist"))
async def artist(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await m.reply("❌ Example: `/artist Arijit Singh`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"🔍 **Searching songs by:** `{query}`...")
    results = search_jiosaavn_multiple(f"{query} songs", 8)
    if not results:
        await msg.edit("❌ No results found!")
        return
    text = f"🎤 **Songs by {query}:**\n\n"
    for i, song in enumerate(results, 1):
        duration = int(song["duration"])
        mins = duration // 60
        secs = duration % 60
        text += f"{i}. **{song['name']}** | ⏱ {mins}:{secs:02d}\n"
    text += "\n📥 Use `/download [song name]` to download!"
    await msg.edit(text)

@app.on_message(filters.command("random"))
async def random_song(_, m: Message):
    query = random.choice(RANDOM_SONGS)
    msg = await m.reply(f"🎲 **Random Song:** `{query}`\n⬇️ Downloading...")
    await send_song(m, query, msg)

@app.on_message(filters.command("similar"))
async def similar_songs(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await m.reply("❌ Example: `/similar Tum Hi Ho`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"🔍 **Finding similar songs for:** `{query}`...")
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
        song_id = song["id"]
        artist_name = song["primaryArtists"].split(",")[0].strip()
        similar_url = f"https://jiosaavn-api-privatecvc2.vercel.app/songs/{song_id}/suggestions"
        sr = requests.get(similar_url, headers=headers, timeout=15)
        sdata = sr.json()
        similar = sdata.get("data", [])
        if not similar:
            results2 = search_jiosaavn_multiple(f"{artist_name} songs", 6)
            text = f"🎵 **Similar to** `{query}`:\n\n"
            for i, s in enumerate(results2, 1):
                text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
        else:
            text = f"🎵 **Similar to** `{query}`:\n\n"
            for i, s in enumerate(similar[:8], 1):
                text += f"{i}. **{s['name']}** - {s.get('primaryArtists', 'Unknown')}\n"
        text += "\n📥 Use `/download [song name]` to download!"
        await msg.edit(text)
    except Exception as e:
        await msg.edit(f"❌ Error: `{str(e)}`")

@app.on_message(filters.command("daily"))
async def daily_song(_, m: Message):
    now = datetime.datetime.now()
    index = (now.day * now.month + now.hour) % len(DAILY_SONGS)
    song = DAILY_SONGS[index]
    msg = await m.reply(
        f"📅 **Today's Recommended Song:**\n\n"
        f"🎵 `{song}`\n\n"
        f"⬇️ Downloading for you..."
    )
    await send_song(m, song, msg)

@app.on_message(filters.command("trending"))
async def trending(_, m: Message):
    msg = await m.reply("🌍 **Fetching trending songs...**")
    results = search_jiosaavn_multiple("trending india 2024", 10)
    if not results:
        await msg.edit("❌ Could not fetch trending songs!")
        return
    text = "🌍 **Trending Songs Right Now:**\n\n"
    for i, song in enumerate(results, 1):
        text += f"{i}. **{song['name']}** - {song['primaryArtists']}\n"
    text += "\n📥 Use `/download [song name]` to download!"
    await msg.edit(text)

@app.on_message(filters.command("recommend"))
async def recommend(_, m: Message):
    user_id = m.from_user.id
    msg = await m.reply("🎯 **Finding recommendations for you...**")

    if user_id in history and history[user_id]:
        last_song = history[user_id][0]
        results = search_jiosaavn_multiple(f"similar to {last_song}", 5)
        text = f"🎯 **Recommended Based on Your History:**\n\n"
    else:
        results = search_jiosaavn_multiple("best hindi songs 2024", 5)
        text = "🎯 **Recommended Songs for You:**\n\n"

    if not results:
        await msg.edit("❌ Could not fetch recommendations!")
        return

    for i, song in enumerate(results, 1):
        text += f"{i}. **{song['name']}** - {song['primaryArtists']}\n"
    text += "\n📥 Use `/download [song name]` to download!"
    await msg.edit(text)

@app.on_message(filters.command("short"))
async def short_songs(_, m: Message):
    msg = await m.reply("⏱ **Searching short songs (under 3 mins)...**")
    results = search_jiosaavn_multiple("short songs 3 minutes", 10)
    if not results:
        await msg.edit("❌ No results found!")
        return
    text = "⏱ **Short Songs (Under 3 Mins):**\n\n"
    count = 0
    for song in results:
        duration = int(song["duration"])
        if duration <= 180:
            mins = duration // 60
            secs = duration % 60
            count += 1
            text += f"{count}. **{song['name']}** - {song['primaryArtists']} | ⏱ {mins}:{secs:02d}\n"
    if count == 0:
        text = "❌ No short songs found right now!\nTry `/search [song name]` instead."
    else:
        text += "\n📥 Use `/download [song name]` to download!"
    await msg.edit(text)

@app.on_message(filters.command("night"))
async def night_songs(_, m: Message):
    song = random.choice(NIGHT_SONGS)
    msg = await m.reply(
        f"🌙 **Late Night Song:**\n\n"
        f"🎵 `{song}`\n\n"
        f"⬇️ Downloading for you..."
    )
    await send_song(m, song, msg)

@app.on_message(filters.command("birthday"))
async def birthday(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip() in ["[name]", "[song]"]:
        await m.reply("❌ Please write a name!\nExample: `/birthday Rahul`")
        return
    name = parts[1].strip()
    text = (
        f"🎂 **Happy Birthday {name}!** 🎉\n\n"
        f"🎵 **Birthday Song Suggestions:**\n\n"
    )
    for i, song in enumerate(BIRTHDAY_SONGS, 1):
        text += f"{i}. {song}\n"
    text += f"\n📥 Use `/download [song name]` to download!\n\n"
    text += f"🎊 Wishing **{name}** a wonderful birthday! 🎈🥳"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎵 Download Birthday Song", callback_data="dl_birthday")]
    ])
    await m.reply(text, reply_markup=keyboard)

@app.on_message(filters.command("playlist"))
async def playlist(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await m.reply(
            "❌ Please write a mood!\n"
            "Example: `/playlist happy`\n\n"
            "Available: `happy` `sad` `party` `romantic` `workout` `chill`"
        )
        return
    mood_type = parts[1].strip().lower()
    if mood_type not in MOOD_SONGS:
        await m.reply("❌ Invalid mood!\nAvailable: `happy` `sad` `party` `romantic` `workout` `chill`")
        return
    songs = MOOD_SONGS[mood_type]
    emojis = {"happy": "😊", "sad": "😢", "party": "🎉", "romantic": "💕", "workout": "💪", "chill": "😌"}
    await m.reply(
        f"🎵 **{mood_type.capitalize()} Playlist** {emojis[mood_type]}\n\n"
        f"Downloading {len(songs)} songs...\n"
        f"⚠️ This may take a few minutes!"
    )
    for song in songs:
        try:
            msg = await m.reply(f"⬇️ Downloading: `{song}`...")
            await send_song(m, song, msg)
            await asyncio.sleep(2)
        except:
            pass

@app.on_message(filters.command("save"))
async def save_favorite(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip() in ["[song]", "[song name]"]:
        await m.reply("❌ Please write a song name!\nExample: `/save Tum Hi Ho`")
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
    if len(parts) < 2 or not parts[1].strip():
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
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip() in ["[song]", "[song name]"]:
        await m.reply("❌ Please write a song name!\nExample: `/info Tum Hi Ho`")
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

@app.on_message(filters.command("stats"))
async def bot_stats(_, m: Message):
    total_users = len(stats["users"])
    total_downloads = stats["total_downloads"]
    await m.reply(
        f"📊 **Bot Statistics:**\n\n"
        f"👥 Total Users: {total_users}\n"
        f"📥 Total Downloads: {total_downloads}\n"
        f"🎵 Database: JioSaavn (Millions of songs)\n\n"
        f"🔜 Voice Chat: Coming Soon!"
    )

@app.on_message(filters.command("mystats"))
async def my_stats(_, m: Message):
    user_id = m.from_user.id
    if user_id not in user_stats or user_stats[user_id]["downloads"] == 0:
        await m.reply(
            f"👤 **Your Stats, {m.from_user.first_name}:**\n\n"
            "📥 Downloads: 0\n"
            "🎵 Most Downloaded: None\n\n"
            "Start downloading songs! 🎵"
        )
        return
    total = user_stats[user_id]["downloads"]
    songs = user_stats[user_id]["songs"]
    most_common = max(set(songs), key=songs.count) if songs else "None"
    await m.reply(
        f"👤 **Your Stats, {m.from_user.first_name}:**\n\n"
        f"📥 Total Downloads: {total}\n"
        f"🎵 Most Downloaded: {most_common}\n"
        f"📜 Songs in History: {len(history.get(user_id, []))}\n"
        f"⭐ Favorites Saved: {len(favorites.get(user_id, []))}"
    )

@app.on_message(filters.command("lastdownload"))
async def last_download(_, m: Message):
    user_id = m.from_user.id
    if user_id not in last_downloaded:
        await m.reply("🎵 No song downloaded yet!\nUse `/download [song]` first.")
        return
    song = last_downloaded[user_id]
    await m.reply(
        f"🎵 **Last Downloaded Song:**\n\n"
        f"🎶 **{song['title']}**\n"
        f"⏱ Duration: {song['duration']}\n"
        f"👤 By: {song['by']}\n\n"
        f"📥 `/download {song['title']}` to download again!"
    )

print("✅ Bot started!")
app.run()
