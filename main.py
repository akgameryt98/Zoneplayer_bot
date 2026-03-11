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
song_ratings = {}
active_quiz = {}

# ============ HELPER FUNCTIONS ============
def search_jiosaavn(query):
    try:
        url = f"https://jiosaavn-api-privatecvc2.vercel.app/search/songs?query={query}&page=1&limit=5"
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
        return dl_url, f"{title} - {artist}", duration, song
    except Exception as e:
        print(f"Search error: {e}")
        return None, None, None, None

def search_jiosaavn_multiple(query, limit=8):
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
        parts = query.split("-")
        if len(parts) >= 2:
            artist = parts[-1].strip()
            title = parts[0].strip()
        else:
            title = query.strip()
            artist = ""
        url = f"https://lrclib.net/api/search?track_name={title}&artist_name={artist}"
        headers = {"User-Agent": "MusicBot/1.0"}
        r = requests.get(url, headers=headers, timeout=15)
        data = r.json()
        if not data:
            return None, None
        lyrics = data[0].get("plainLyrics", None)
        title_full = f"{data[0].get('trackName', title)} - {data[0].get('artistName', artist)}"
        return lyrics, title_full
    except Exception as e:
        print(f"Lyrics error: {e}")
        return None, None

def fetch_quote():
    try:
        r = requests.get("https://api.quotable.io/random?tags=music", timeout=10)
        data = r.json()
        return f'💬 "{data["content"]}"\n\n— {data["author"]}'
    except:
        try:
            r = requests.get("https://zenquotes.io/api/random", timeout=10)
            data = r.json()
            return f'💬 "{data[0]["q"]}"\n\n— {data[0]["a"]}'
        except:
            fallback = [
                '💬 "Without music, life would be a mistake." — Nietzsche',
                '💬 "Where words fail, music speaks." — H.C. Andersen',
                '💬 "One good thing about music, when it hits you, you feel no pain." — Bob Marley',
                '💬 "Music gives a soul to the universe, wings to the mind." — Plato',
                '💬 "Sangeet woh bhasha hai jo seedha dil se baat karti hai!" 🇮🇳'
            ]
            return random.choice(fallback)

def fetch_quiz():
    try:
        results = search_jiosaavn_multiple("hindi popular songs", 20)
        if results:
            song = random.choice(results)
            title = song["name"]
            artist = song["primaryArtists"]
            lyrics_data, _ = get_lyrics(f"{title} - {artist}")
            if lyrics_data:
                lines = [l.strip() for l in lyrics_data.split("\n") if len(l.strip()) > 20]
                if lines:
                    line = random.choice(lines[:10])
                    return line, title.lower(), title, artist
        return None, None, None, None
    except:
        return None, None, None, None

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
    dl_url, title, duration, song_data = search_jiosaavn(query)
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
        [InlineKeyboardButton("📤 Share", switch_inline_query=title),
         InlineKeyboardButton("⭐ Save", callback_data=f"save_{title[:40]}")],
        [InlineKeyboardButton("🎵 Similar", callback_data=f"similar_{title[:40]}"),
         InlineKeyboardButton("ℹ️ Info", callback_data=f"info_{title[:40]}")]
    ])
    album = song_data.get("album", {}).get("name", "Unknown") if song_data else "Unknown"
    year = song_data.get("year", "Unknown") if song_data else "Unknown"
    await app.send_audio(
        m.chat.id, path,
        caption=(
            f"🎵 **{title}**\n"
            f"💿 Album: {album}\n"
            f"📅 Year: {year}\n"
            f"⏱ Duration: {mins}:{secs:02d}\n"
            f"👤 Requested by: {m.from_user.first_name}"
        ),
        title=title, duration=duration, reply_markup=keyboard
    )
    await msg.delete()
    try:
        os.remove(path)
    except:
        pass

# ============ CALLBACKS ============

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
    await callback.answer("⭐ Saved to favorites!", show_alert=True)

@app.on_callback_query(filters.regex(r"^similar_"))
async def similar_callback(_, callback):
    song_title = callback.data[8:]
    msg = await callback.message.reply(f"🔍 Finding similar songs...")
    results = search_jiosaavn_multiple(f"songs like {song_title}", 6)
    if not results:
        await msg.edit("❌ No similar songs found!")
        return
    text = f"🎵 **Similar to** `{song_title}`:\n\n"
    for i, s in enumerate(results, 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    text += "\n📥 Use `/download [song name]` to download!"
    await msg.edit(text)
    await callback.answer()

@app.on_callback_query(filters.regex(r"^info_"))
async def info_callback(_, callback):
    song_title = callback.data[5:]
    msg = await callback.message.reply(f"🔍 Getting info...")
    dl_url, title, duration, song_data = search_jiosaavn(song_title)
    if not song_data:
        await msg.edit("❌ Info not found!")
        return
    mins = duration // 60
    secs = duration % 60
    album = song_data.get("album", {}).get("name", "Unknown")
    year = song_data.get("year", "Unknown")
    language = song_data.get("language", "Unknown").capitalize()
    await msg.edit(
        f"ℹ️ **Song Info:**\n\n"
        f"🎵 **Title:** {song_data['name']}\n"
        f"👤 **Artist:** {song_data['primaryArtists']}\n"
        f"💿 **Album:** {album}\n"
        f"📅 **Year:** {year}\n"
        f"🌐 **Language:** {language}\n"
        f"⏱ **Duration:** {mins}:{secs:02d}\n\n"
        f"📥 `/download {song_data['name']}` to download!"
    )
    await callback.answer()

@app.on_callback_query(filters.regex("dl_birthday"))
async def birthday_download(_, callback):
    await callback.answer("Downloading...", show_alert=False)
    msg = await callback.message.reply("⬇️ **Downloading birthday song...**")
    await send_song(callback.message, "Baar Baar Din Yeh Aaye", msg)

@app.on_callback_query(filters.regex(r"^rate_"))
async def rate_callback(_, callback):
    parts = callback.data.split("_")
    rating = parts[1]
    song = "_".join(parts[2:])
    user_id = callback.from_user.id
    if song not in song_ratings:
        song_ratings[song] = []
    song_ratings[song].append(int(rating))
    avg = sum(song_ratings[song]) / len(song_ratings[song])
    await callback.answer(f"✅ You rated {rating}⭐", show_alert=False)
    await callback.message.edit_reply_markup(
        InlineKeyboardMarkup([[
            InlineKeyboardButton(f"⭐ Avg: {avg:.1f} ({len(song_ratings[song])} votes)", callback_data="none")
        ]])
    )

# ============ COMMANDS ============

@app.on_message(filters.command("start"))
async def start(_, m: Message):
    await m.reply(
        f"🎵 **Welcome to Music Bot!**\n"
        f"Hello {m.from_user.first_name}! 👋\n\n"
        "**Commands:**\n\n"
        "📥 `/download [song]` - Download song\n"
        "🔍 `/search [song]` - Search top 5\n"
        "ℹ️ `/info [song]` - Song details\n"
        "📝 `/lyrics [song - artist]` - Song lyrics\n"
        "🎭 `/mood [type]` - Songs by mood\n"
        "🎸 `/genre [type]` - Songs by genre\n"
        "🌐 `/hindi` `/punjabi` `/english` - By language\n"
        "🎤 `/artist [name]` - Songs by artist\n"
        "🏆 `/top [artist]` - Artist top songs\n"
        "💿 `/album [name]` - Album songs\n"
        "🔤 `/letter [A-Z]` - Songs by letter\n"
        "🎲 `/random` - Random song\n"
        "🎵 `/similar [song]` - Similar songs\n"
        "📅 `/daily` - Today's song\n"
        "🌍 `/trending` - Trending now\n"
        "🎯 `/recommend` - For you\n"
        "⏱ `/short` - Under 3 mins\n"
        "🌙 `/night` - Late night songs\n"
        "🎂 `/birthday [name]` - Birthday songs\n"
        "🎵 `/playlist [mood]` - Full playlist\n"
        "🌍 `/regional [language]` - Regional songs\n"
        "📅 `/decade [80s/90s/2000s/2010s/2020s]`\n"
        "🎭 `/vibe [song]` - Song mood analysis\n"
        "🤖 `/ai_playlist [activity]` - AI playlist\n"
        "💬 `/quote` - Music quote\n"
        "🎯 `/guesssong` - Guess the song!\n"
        "⭐ `/rate [song]` - Rate a song\n"
        "🏆 `/topsongs` - Top rated songs\n"
        "⚖️ `/compare [song1] | [song2]` - Compare songs\n"
        "📦 `/batch` - Download multiple songs\n"
        "🔤 `/findlyrics [line]` - Find song by lyrics\n"
        "📊 `/topindia` `/topbollywood` `/top2025`\n"
        "⭐ `/save [song]` - Save favorite\n"
        "🗑 `/removefav [song]` - Remove favorite\n"
        "💾 `/favorites` - View favorites\n"
        "📜 `/history` - Recent songs\n"
        "📊 `/stats` - Bot stats\n"
        "👤 `/mystats` - My stats\n"
        "🎵 `/lastdownload` - Last song\n"
        "❓ `/help` - Help\n\n"
        "🔜 **Coming Soon:**\n"
        "🎙 `/play` - Voice Chat\n"
        "⏸ `/pause` `/resume` `/stop` `/queue`"
    )

@app.on_message(filters.command("help"))
async def help_cmd(_, m: Message):
    await m.reply(
        "❓ **Help Menu:**\n\n"
        "📥 `/download Tum Hi Ho`\n"
        "🔍 `/search Arijit Singh`\n"
        "ℹ️ `/info Blinding Lights`\n"
        "📝 `/lyrics Tum Hi Ho - Arijit Singh`\n"
        "🎭 `/mood happy/sad/party/romantic/workout/chill`\n"
        "🎸 `/genre rock/pop/jazz/classical/rap/indie`\n"
        "🌐 `/hindi` `/punjabi` `/english`\n"
        "🎤 `/artist Arijit Singh`\n"
        "🏆 `/top Arijit Singh`\n"
        "💿 `/album Aashiqui 2`\n"
        "🔤 `/letter T`\n"
        "🎲 `/random`\n"
        "🎵 `/similar Tum Hi Ho`\n"
        "📅 `/daily`\n"
        "🌍 `/trending`\n"
        "🎯 `/recommend`\n"
        "⏱ `/short`\n"
        "🌙 `/night`\n"
        "🎂 `/birthday Rahul`\n"
        "🎵 `/playlist happy`\n"
        "🌍 `/regional marathi`\n"
        "📅 `/decade 90s`\n"
        "🎭 `/vibe Tum Hi Ho`\n"
        "🤖 `/ai_playlist gym`\n"
        "💬 `/quote`\n"
        "🎯 `/guesssong`\n"
        "⭐ `/rate Tum Hi Ho`\n"
        "🏆 `/topsongs`\n"
        "⚖️ `/compare Tum Hi Ho | Kesariya`\n"
        "📦 `/batch`\n"
        "🔤 `/findlyrics tere bin nahi lagda`\n"
        "📊 `/topindia` `/topbollywood` `/top2025`\n"
        "⭐ `/save Tum Hi Ho`\n"
        "🗑 `/removefav Tum Hi Ho`\n"
        "💾 `/favorites`\n"
        "📜 `/history`\n"
        "📊 `/stats`\n"
        "👤 `/mystats`\n"
        "🎵 `/lastdownload`"
    )

@app.on_message(filters.command("play"))
async def play_coming_soon(_, m: Message):
    await m.reply("🔜 **Coming Soon!**\n\nVoice Chat playback is under development.\n\nUse 📥 `/download [song]` for now!")

@app.on_message(filters.command("download"))
async def download(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip() in ["[song]", "[song name]"]:
        await m.reply("❌ Please write a song name!\nExample: `/download Tum Hi Ho`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"🔍 **Searching:** `{query}`...")
    await send_song(m, query, msg)

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
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 Random Song", callback_data="random_fetch"),
         InlineKeyboardButton("🔥 Trending", callback_data="trending_fetch")]
    ])
    await msg.edit(text, reply_markup=keyboard)

@app.on_message(filters.command("lyrics"))
async def lyrics(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await m.reply("❌ Format: `/lyrics Song Name - Artist`\nExample: `/lyrics Shape of You - Ed Sheeran`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"🔍 **Searching lyrics:** `{query}`...")
    try:
        lyrics_text, title = get_lyrics(query)
        if not lyrics_text:
            await msg.edit(f"❌ Lyrics not found!\n\nTry: `/lyrics Song - Artist Name`\nExample: `/lyrics Shape of You - Ed Sheeran`")
            return
        if len(lyrics_text) > 4000:
            lyrics_text = lyrics_text[:4000] + "\n\n... *(lyrics truncated)*"
        await msg.edit(f"📝 **Lyrics: {title}**\n\n{lyrics_text}")
    except Exception as e:
        await msg.edit(f"❌ Error: `{str(e)}`")

@app.on_message(filters.command("info"))
async def song_info(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await m.reply("❌ Example: `/info Tum Hi Ho`")
        return
    query = parts[1].strip().lower()
    msg = await m.reply(f"🔍 **Getting info:** `{query}`...")
    try:
        url = f"https://jiosaavn-api-privatecvc2.vercel.app/search/songs?query={query}&page=1&limit=10"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=15)
        data = r.json()
        results = data["data"]["results"]
        if not results:
            await msg.edit("❌ Song not found!")
            return

        # Best match dhundho
        best = None
        query_words = query.lower().split()
        for song in results:
            song_name = song["name"].lower()
            match_count = sum(1 for word in query_words if word in song_name)
            if match_count >= len(query_words) * 0.6:
                best = song
                break
        if not best:
            best = results[0]

        title = best["name"]
        artist = best["primaryArtists"]
        album = best.get("album", {}).get("name", "Unknown")
        year = best.get("year", "Unknown")
        duration = int(best["duration"])
        mins = duration // 60
        secs = duration % 60
        language = best.get("language", "Unknown").capitalize()

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
        
@app.on_message(filters.command("mood"))
async def mood(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await m.reply("🎭 **Choose a mood:**\n\n`/mood happy` 😊\n`/mood sad` 😢\n`/mood party` 🎉\n`/mood romantic` 💕\n`/mood workout` 💪\n`/mood chill` 😌")
        return
    mood_type = parts[1].strip().lower()
    mood_queries = {
        "happy": "happy upbeat bollywood songs",
        "sad": "sad emotional hindi songs",
        "party": "party dance hindi songs",
        "romantic": "romantic hindi love songs",
        "workout": "workout gym motivation songs",
        "chill": "chill relaxing hindi songs"
    }
    if mood_type not in mood_queries:
        await m.reply("❌ Invalid mood!\nAvailable: `happy` `sad` `party` `romantic` `workout` `chill`")
        return
    emojis = {"happy": "😊", "sad": "😢", "party": "🎉", "romantic": "💕", "workout": "💪", "chill": "😌"}
    msg = await m.reply(f"🎭 **Fetching {mood_type} songs...**")
    results = search_jiosaavn_multiple(mood_queries[mood_type], 8)
    if not results:
        await msg.edit("❌ No songs found!")
        return
    text = f"🎭 **{mood_type.capitalize()} Songs** {emojis[mood_type]}\n\n"
    for i, song in enumerate(results, 1):
        text += f"{i}. **{song['name']}** - {song['primaryArtists']}\n"
    text += "\n📥 Use `/download [song name]` to download!"
    await msg.edit(text)

@app.on_message(filters.command("genre"))
async def genre(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await m.reply("🎸 **Choose genre:**\n\n`/genre rock` 🎸\n`/genre pop` 🎵\n`/genre jazz` 🎷\n`/genre classical` 🎻\n`/genre rap` 🎤\n`/genre indie` 🌿\n`/genre sufi` 🌙\n`/genre folk` 🪘")
        return
    genre_type = parts[1].strip().lower()
    genre_queries = {
        "rock": "rock songs hindi english",
        "pop": "pop hits songs",
        "jazz": "jazz music songs",
        "classical": "classical music instrumental",
        "rap": "rap hip hop songs",
        "indie": "indie pop hindi songs",
        "sufi": "sufi songs hindi",
        "folk": "folk music india"
    }
    genre_emojis = {"rock": "🎸", "pop": "🎵", "jazz": "🎷", "classical": "🎻", "rap": "🎤", "indie": "🌿", "sufi": "🌙", "folk": "🪘"}
    if genre_type not in genre_queries:
        await m.reply("❌ Invalid genre!\nAvailable: `rock` `pop` `jazz` `classical` `rap` `indie` `sufi` `folk`")
        return
    msg = await m.reply(f"🔍 **Fetching {genre_type} songs...**")
    results = search_jiosaavn_multiple(genre_queries[genre_type], 8)
    if not results:
        await msg.edit("❌ No songs found!")
        return
    text = f"{genre_emojis[genre_type]} **{genre_type.capitalize()} Songs:**\n\n"
    for i, song in enumerate(results, 1):
        text += f"{i}. **{song['name']}** - {song['primaryArtists']}\n"
    text += "\n📥 Use `/download [song name]` to download!"
    await msg.edit(text)

@app.on_message(filters.command("hindi"))
async def hindi(_, m: Message):
    msg = await m.reply("🔍 **Fetching Hindi songs...**")
    results = search_jiosaavn_multiple("top hindi songs 2024", 8)
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
    msg = await m.reply("🔍 **Fetching Punjabi songs...**")
    results = search_jiosaavn_multiple("top punjabi songs 2024", 8)
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
    msg = await m.reply("🔍 **Fetching English songs...**")
    results = search_jiosaavn_multiple("top english hits 2024", 8)
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
    msg = await m.reply(f"🔍 **Fetching songs by:** `{query}`...")
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

@app.on_message(filters.command("top"))
async def top_artist(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await m.reply("❌ Example: `/top Arijit Singh`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"🏆 **Fetching top songs by:** `{query}`...")
    results = search_jiosaavn_multiple(f"best of {query}", 8)
    if not results:
        await msg.edit("❌ No results found!")
        return
    text = f"🏆 **Top Songs by {query}:**\n\n"
    for i, song in enumerate(results, 1):
        duration = int(song["duration"])
        mins = duration // 60
        secs = duration % 60
        text += f"{i}. **{song['name']}** | ⏱ {mins}:{secs:02d}\n"
    text += "\n📥 Use `/download [song name]` to download!"
    await msg.edit(text)

@app.on_message(filters.command("album"))
async def album(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await m.reply("❌ Example: `/album Aashiqui 2`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"💿 **Fetching album:** `{query}`...")
    results = search_jiosaavn_multiple(f"{query} album", 8)
    if not results:
        await msg.edit("❌ Album not found!")
        return
    text = f"💿 **Album: {query}**\n\n"
    for i, song in enumerate(results, 1):
        duration = int(song["duration"])
        mins = duration // 60
        secs = duration % 60
        text += f"{i}. **{song['name']}** - {song['primaryArtists']} | ⏱ {mins}:{secs:02d}\n"
    text += "\n📥 Use `/download [song name]` to download!"
    await msg.edit(text)

@app.on_message(filters.command("letter"))
async def letter(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await m.reply("❌ Example: `/letter A`")
        return
    l = parts[1].strip()[0].upper()
    if not l.isalpha():
        await m.reply("❌ Please write a valid letter!")
        return
    msg = await m.reply(f"🔤 **Fetching songs starting with:** `{l}`...")
    results = search_jiosaavn_multiple(f"songs starting with {l} hindi", 10)
    filtered = [s for s in results if s["name"].upper().startswith(l)]
    if not filtered:
        filtered = results[:8]
    text = f"🔤 **Songs Starting with '{l}':**\n\n"
    for i, song in enumerate(filtered[:8], 1):
        text += f"{i}. **{song['name']}** - {song['primaryArtists']}\n"
    text += "\n📥 Use `/download [song name]` to download!"
    await msg.edit(text)

@app.on_message(filters.command("random"))
async def random_song(_, m: Message):
    keywords = ["hindi popular", "bollywood hits", "top songs", "english hits", "punjabi popular", "romantic songs", "party songs"]
    query = random.choice(keywords)
    msg = await m.reply("🎲 **Fetching random song...**")
    results = search_jiosaavn_multiple(query, 20)
    if not results:
        await msg.edit("❌ No songs found!")
        return
    song = random.choice(results)
    await send_song(m, song["name"], msg)

@app.on_message(filters.command("similar"))
async def similar_songs(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await m.reply("❌ Example: `/similar Tum Hi Ho`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"🔍 **Finding similar songs for:** `{query}`...")
    try:
        dl_url, title, duration, song_data = search_jiosaavn(query)
        if not song_data:
            await msg.edit("❌ Song not found!")
            return
        song_id = song_data["id"]
        artist_name = song_data["primaryArtists"].split(",")[0].strip()
        similar_url = f"https://jiosaavn-api-privatecvc2.vercel.app/songs/{song_id}/suggestions"
        sr = requests.get(similar_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        sdata = sr.json()
        similar = sdata.get("data", [])
        if not similar:
            results = search_jiosaavn_multiple(f"{artist_name} songs", 6)
            text = f"🎵 **Similar to** `{query}`:\n\n"
            for i, s in enumerate(results, 1):
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
    keywords = ["hindi hits", "bollywood popular", "top songs india", "romantic hindi", "new hindi songs"]
    random.seed(now.day + now.month * 100)
    query = random.choice(keywords)
    random.seed()
    msg = await m.reply("📅 **Fetching today's recommended song...**")
    results = search_jiosaavn_multiple(query, 20)
    if not results:
        await msg.edit("❌ No songs found!")
        return
    random.seed(now.day * now.month)
    song = random.choice(results)
    random.seed()
    await send_song(m, song["name"], msg)

@app.on_message(filters.command("trending"))
async def trending(_, m: Message):
    msg = await m.reply("🌍 **Fetching trending songs...**")
    results = search_jiosaavn_multiple("trending india 2024 top hits", 10)
    if not results:
        results = search_jiosaavn_multiple("bollywood top hits", 10)
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
    msg = await m.reply("🎯 **Finding recommendations...**")
    if user_id in history and history[user_id]:
        last_song = history[user_id][0]
        results = search_jiosaavn_multiple(f"songs like {last_song}", 5)
        text = f"🎯 **Recommended Based on Your History:**\n\n"
    else:
        results = search_jiosaavn_multiple("best hindi songs popular", 5)
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
    msg = await m.reply("⏱ **Fetching short songs (under 3 mins)...**")
    results = search_jiosaavn_multiple("short songs 2 minutes", 15)
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
        text = "❌ No short songs found!\nTry `/search [song name]` instead."
    else:
        text += "\n📥 Use `/download [song name]` to download!"
    await msg.edit(text)

@app.on_message(filters.command("night"))
async def night_songs(_, m: Message):
    msg = await m.reply("🌙 **Fetching late night songs...**")
    results = search_jiosaavn_multiple("late night chill sad songs hindi", 10)
    if not results:
        await msg.edit("❌ No songs found!")
        return
    song = random.choice(results)
    await send_song(m, song["name"], msg)

@app.on_message(filters.command("birthday"))
async def birthday(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip() in ["[name]"]:
        await m.reply("❌ Please write a name!\nExample: `/birthday Rahul`")
        return
    name = parts[1].strip()
    msg = await m.reply(f"🎂 **Fetching birthday songs for {name}...**")
    results = search_jiosaavn_multiple("birthday songs hindi english", 7)
    text = f"🎂 **Happy Birthday {name}!** 🎉\n\n🎵 **Birthday Songs:**\n\n"
    for i, song in enumerate(results, 1):
        text += f"{i}. **{song['name']}** - {song['primaryArtists']}\n"
    text += f"\n🎊 Wishing **{name}** a wonderful birthday! 🎈🥳"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎵 Download Birthday Song", callback_data="dl_birthday")]
    ])
    await msg.edit(text, reply_markup=keyboard)

@app.on_message(filters.command("playlist"))
async def playlist(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await m.reply("❌ Example: `/playlist happy`\n\nAvailable: `happy` `sad` `party` `romantic` `workout` `chill`")
        return
    mood_type = parts[1].strip().lower()
    mood_queries = {
        "happy": "happy upbeat bollywood songs",
        "sad": "sad emotional hindi songs",
        "party": "party dance hindi songs",
        "romantic": "romantic hindi love songs",
        "workout": "workout gym motivation songs",
        "chill": "chill relaxing hindi songs"
    }
    if mood_type not in mood_queries:
        await m.reply("❌ Available: `happy` `sad` `party` `romantic` `workout` `chill`")
        return
    emojis = {"happy": "😊", "sad": "😢", "party": "🎉", "romantic": "💕", "workout": "💪", "chill": "😌"}
    results = search_jiosaavn_multiple(mood_queries[mood_type], 5)
    await m.reply(f"🎵 **{mood_type.capitalize()} Playlist** {emojis[mood_type]}\n\nDownloading {len(results)} songs...\n⚠️ This may take a few minutes!")
    for song in results:
        try:
            msg = await m.reply(f"⬇️ Downloading: `{song['name']}`...")
            await send_song(m, song["name"], msg)
            await asyncio.sleep(2)
        except:
            pass

@app.on_message(filters.command("regional"))
async def regional(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await m.reply("🌍 **Choose language:**\n\n`/regional marathi`\n`/regional tamil`\n`/regional telugu`\n`/regional bhojpuri`\n`/regional bengali`\n`/regional gujarati`\n`/regional kannada`\n`/regional malayalam`")
        return
    lang = parts[1].strip().lower()
    msg = await m.reply(f"🌍 **Fetching {lang} songs...**")
    results = search_jiosaavn_multiple(f"top {lang} songs popular", 8)
    if not results:
        await msg.edit("❌ No songs found!")
        return
    text = f"🌍 **Top {lang.capitalize()} Songs:**\n\n"
    for i, song in enumerate(results, 1):
        text += f"{i}. **{song['name']}** - {song['primaryArtists']}\n"
    text += "\n📥 Use `/download [song name]` to download!"
    await msg.edit(text)
    
@app.on_message(filters.command("vibe"))
async def vibe(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await m.reply("❌ Example: `/vibe Tum Hi Ho`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"🎭 **Analyzing vibe of:** `{query}`...")
    dl_url, title, duration, song_data = search_jiosaavn(query)
    if not song_data:
        await msg.edit("❌ Song not found!")
        return
    name = song_data.get("name", "").lower()
    language = song_data.get("language", "Unknown")
    mins = duration // 60
    secs = duration % 60
    sad_kw = ["sad", "dard", "judai", "alvida", "rona", "aansu", "toota", "bekhayali", "tanha", "akela"]
    happy_kw = ["happy", "khushi", "dance", "party", "gallan", "badtameez", "celebrate"]
    romantic_kw = ["love", "ishq", "pyar", "mohabbat", "dil", "kesariya", "raataan", "tum hi ho", "tera"]
    energetic_kw = ["workout", "power", "fire", "thunder", "believer", "warrior", "rocky"]
    if any(k in name for k in sad_kw):
        vibe_result = "😢 Sad / Emotional"
        desc = "This song has sad and emotional vibes. Perfect for those heartfelt moments."
    elif any(k in name for k in romantic_kw):
        vibe_result = "💕 Romantic"
        desc = "This song has romantic vibes. Perfect for love and special moments."
    elif any(k in name for k in happy_kw):
        vibe_result = "😊 Happy / Upbeat"
        desc = "This song has happy and upbeat vibes. Perfect for cheerful moments!"
    elif any(k in name for k in energetic_kw):
        vibe_result = "💪 Energetic"
        desc = "This song has energetic vibes. Perfect for workouts!"
    elif duration < 180:
        vibe_result = "⚡ Short & Punchy"
        desc = "Short but powerful song!"
    elif duration > 300:
        vibe_result = "🎭 Epic / Cinematic"
        desc = "This is an epic long song with cinematic feel."
    else:
        vibe_result = "😌 Chill / Neutral"
        desc = "This song has chill and neutral vibes. Good for any time!"
    await msg.edit(
        f"🎭 **Vibe Analysis:**\n\n"
        f"🎵 **Song:** {song_data['name']}\n"
        f"👤 **Artist:** {song_data['primaryArtists']}\n"
        f"⏱ **Duration:** {mins}:{secs:02d}\n"
        f"🌐 **Language:** {language.capitalize()}\n\n"
        f"**Vibe:** {vibe_result}\n"
        f"📝 {desc}"
    )

@app.on_message(filters.command("ai_playlist"))
async def ai_playlist(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await m.reply("🤖 **Choose activity:**\n\n`/ai_playlist gym`\n`/ai_playlist study`\n`/ai_playlist heartbreak`\n`/ai_playlist sleep`\n`/ai_playlist party`\n`/ai_playlist romantic`\n`/ai_playlist morning`\n`/ai_playlist roadtrip`")
        return
    activity = parts[1].strip().lower()
    activity_queries = {
        "gym": "workout gym motivation energetic songs",
        "study": "study focus calm instrumental music",
        "heartbreak": "heartbreak sad emotional songs hindi",
        "sleep": "sleep relaxing calm lullaby songs",
        "party": "party dance upbeat songs hindi",
        "romantic": "romantic love songs hindi english",
        "morning": "morning fresh upbeat motivational songs",
        "roadtrip": "roadtrip travel songs hindi english"
    }
    activity_emojis = {
        "gym": "💪", "study": "📚", "heartbreak": "💔",
        "sleep": "😴", "party": "🎉", "romantic": "💕",
        "morning": "🌅", "roadtrip": "🚗"
    }
    if activity not in activity_queries:
        await m.reply("❌ Available: `gym` `study` `heartbreak` `sleep` `party` `romantic` `morning` `roadtrip`")
        return
    msg = await m.reply(f"🤖 **Creating AI Playlist for {activity}...**")
    results = search_jiosaavn_multiple(activity_queries[activity], 8)
    if not results:
        await msg.edit("❌ No songs found!")
        return
    emoji = activity_emojis[activity]
    text = f"🤖 **AI Playlist: {activity.capitalize()}** {emoji}\n\n"
    for i, song in enumerate(results, 1):
        text += f"{i}. **{song['name']}** - {song['primaryArtists']}\n"
    text += f"\n📥 Use `/download [song name]` to download!\n"
    text += f"🎵 Or use `/playlist {activity}` to download all!"
    await msg.edit(text)

@app.on_message(filters.command("quote"))
async def quote(_, m: Message):
    msg = await m.reply("💬 **Fetching music quote...**")
    q = fetch_quote()
    await msg.edit(f"💬 **Music Quote:**\n\n{q}")

@app.on_message(filters.command("guesssong"))
async def guesssong(_, m: Message):
    msg = await m.reply("🎯 **Fetching a song for quiz...**")
    chat_id = m.chat.id
    line, answer, title, artist = fetch_quiz()
    if not line:
        results = search_jiosaavn_multiple("popular hindi songs", 10)
        if results:
            song = random.choice(results)
            title = song["name"]
            artist = song["primaryArtists"]
            answer = title.lower()
            line = f"Hint: Artist is **{artist}**"
        else:
            await msg.edit("❌ Could not fetch quiz! Try again.")
            return
    active_quiz[chat_id] = {"answer": answer, "title": title, "artist": artist}
    await msg.edit(
        f"🎯 **Guess The Song!**\n\n"
        f"🎵 **Lyrics line:**\n_{line}_\n\n"
        f"💭 **Reply with the song name!**\n"
        f"⏱ You have 30 seconds!\n\n"
        f"Use `/skip` to skip this question."
    )
    await asyncio.sleep(30)
    if chat_id in active_quiz:
        del active_quiz[chat_id]
        await m.reply(f"⏱ **Time's up!**\nThe answer was: **{title}** by {artist}")

@app.on_message(filters.command("skip"))
async def skip_quiz(_, m: Message):
    chat_id = m.chat.id
    if chat_id not in active_quiz:
        await m.reply("❌ No active quiz!")
        return
    quiz = active_quiz[chat_id]
    del active_quiz[chat_id]
    await m.reply(f"⏭ **Skipped!**\nThe answer was: **{quiz['title']}** by {quiz['artist']}")

@app.on_message(filters.text & ~filters.command(""))
async def check_quiz_answer(_, m: Message):
    chat_id = m.chat.id
    if chat_id not in active_quiz:
        return
    quiz = active_quiz[chat_id]
    user_answer = m.text.strip().lower()
    correct_answer = quiz["answer"].lower()
    if any(word in user_answer for word in correct_answer.split() if len(word) > 3):
        del active_quiz[chat_id]
        await m.reply(
            f"✅ **Correct! Well done {m.from_user.first_name}!** 🎉\n\n"
            f"🎵 **{quiz['title']}** by {quiz['artist']}\n\n"
            f"📥 `/download {quiz['title']}` to download!"
        )

@app.on_message(filters.command("rate"))
async def rate_song(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await m.reply("❌ Example: `/rate Tum Hi Ho`")
        return
    song = parts[1].strip()
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⭐1", callback_data=f"rate_1_{song[:30]}"),
            InlineKeyboardButton("⭐2", callback_data=f"rate_2_{song[:30]}"),
            InlineKeyboardButton("⭐3", callback_data=f"rate_3_{song[:30]}"),
            InlineKeyboardButton("⭐4", callback_data=f"rate_4_{song[:30]}"),
            InlineKeyboardButton("⭐5", callback_data=f"rate_5_{song[:30]}"),
        ]
    ])
    await m.reply(f"⭐ **Rate:** `{song}`\n\nSelect your rating:", reply_markup=keyboard)

@app.on_message(filters.command("topsongs"))
async def topsongs(_, m: Message):
    if not song_ratings:
        await m.reply("❌ No rated songs yet!\nUse `/rate [song name]` to rate songs.")
        return
    sorted_songs = sorted(song_ratings.items(), key=lambda x: sum(x[1])/len(x[1]), reverse=True)
    text = "🏆 **Top Rated Songs:**\n\n"
    for i, (song, ratings) in enumerate(sorted_songs[:10], 1):
        avg = sum(ratings) / len(ratings)
        text += f"{i}. **{song}**\n   ⭐ {avg:.1f}/5 ({len(ratings)} votes)\n\n"
    await m.reply(text)

@app.on_message(filters.command("compare"))
async def compare(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or "|" not in parts[1]:
        await m.reply("❌ Example: `/compare Tum Hi Ho | Kesariya`")
        return
    songs = parts[1].split("|")
    if len(songs) != 2:
        await m.reply("❌ Example: `/compare Tum Hi Ho | Kesariya`")
        return
    song1 = songs[0].strip()
    song2 = songs[1].strip()
    msg = await m.reply(f"⚖️ **Comparing songs...**")
    dl1, title1, dur1, data1 = search_jiosaavn(song1)
    dl2, title2, dur2, data2 = search_jiosaavn(song2)
    if not data1 or not data2:
        await msg.edit("❌ One or both songs not found!")
        return
    m1, s1 = dur1 // 60, dur1 % 60
    m2, s2 = dur2 // 60, dur2 % 60
    avg1 = sum(song_ratings.get(song1, [0])) / max(len(song_ratings.get(song1, [1])), 1)
    avg2 = sum(song_ratings.get(song2, [0])) / max(len(song_ratings.get(song2, [1])), 1)
    text = (
        f"⚖️ **Song Comparison:**\n\n"
        f"**1️⃣ {data1['name']}**\n"
        f"👤 {data1['primaryArtists']}\n"
        f"💿 {data1.get('album', {}).get('name', 'Unknown')}\n"
        f"⏱ {m1}:{s1:02d}\n"
        f"🌐 {data1.get('language', 'Unknown').capitalize()}\n"
        f"⭐ Rating: {avg1:.1f}/5\n\n"
        f"**VS**\n\n"
        f"**2️⃣ {data2['name']}**\n"
        f"👤 {data2['primaryArtists']}\n"
        f"💿 {data2.get('album', {}).get('name', 'Unknown')}\n"
        f"⏱ {m2}:{s2:02d}\n"
        f"🌐 {data2.get('language', 'Unknown').capitalize()}\n"
        f"⭐ Rating: {avg2:.1f}/5\n\n"
        f"📥 Download: `/download {data1['name']}` or `/download {data2['name']}`"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"👍 {data1['name'][:20]}", callback_data=f"vote_1_{song1[:20]}"),
         InlineKeyboardButton(f"👍 {data2['name'][:20]}", callback_data=f"vote_2_{song2[:20]}")]
    ])
    await msg.edit(text, reply_markup=keyboard)

@app.on_message(filters.command("batch"))
async def batch(_, m: Message):
    await m.reply(
        "📦 **Batch Download Mode!**\n\n"
        "Send me up to 5 song names, one per line:\n\n"
        "Example:\n"
        "```\nTum Hi Ho\nKesariya\nBlinding Lights\nShape of You\nHawayein```\n\n"
        "Reply with your list now! ⬇️"
    )

@app.on_message(filters.command("findlyrics"))
async def findlyrics(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await m.reply("❌ Example: `/findlyrics tere bin nahi lagda`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"🔤 **Searching song for lyrics:** `{query}`...")
    try:
        url = f"https://lrclib.net/api/search?q={query}"
        r = requests.get(url, headers={"User-Agent": "MusicBot/1.0"}, timeout=15)
        data = r.json()
        if not data:
            results = search_jiosaavn_multiple(query, 5)
            if not results:
                await msg.edit("❌ No song found for these lyrics!")
                return
            text = f"🔤 **Songs matching:** `{query}`\n\n"
            for i, song in enumerate(results, 1):
                text += f"{i}. **{song['name']}** - {song['primaryArtists']}\n"
            await msg.edit(text)
            return
        text = f"🔤 **Songs matching lyrics:** `{query}`\n\n"
        for i, item in enumerate(data[:5], 1):
            text += f"{i}. **{item.get('trackName', 'Unknown')}** - {item.get('artistName', 'Unknown')}\n"
        text += "\n📥 Use `/download [song name]` to download!"
        await msg.edit(text)
    except Exception as e:
        await msg.edit(f"❌ Error: `{str(e)}`")

@app.on_message(filters.command("topindia"))
async def topindia(_, m: Message):
    msg = await m.reply("📊 **Fetching Top India songs...**")
    results = search_jiosaavn_multiple("top india trending songs 2024", 10)
    if not results:
        await msg.edit("❌ No results found!")
        return
    text = "🇮🇳 **Top Songs in India:**\n\n"
    for i, song in enumerate(results, 1):
        text += f"{i}. **{song['name']}** - {song['primaryArtists']}\n"
    text += "\n📥 Use `/download [song name]` to download!"
    await msg.edit(text)

@app.on_message(filters.command("topbollywood"))
async def topbollywood(_, m: Message):
    msg = await m.reply("🎬 **Fetching Top Bollywood songs...**")
    results = search_jiosaavn_multiple("top bollywood hits 2024", 10)
    if not results:
        await msg.edit("❌ No results found!")
        return
    text = "🎬 **Top Bollywood Songs:**\n\n"
    for i, song in enumerate(results, 1):
        text += f"{i}. **{song['name']}** - {song['primaryArtists']}\n"
    text += "\n📥 Use `/download [song name]` to download!"
    await msg.edit(text)

@app.on_message(filters.command("top2025"))
async def top2025(_, m: Message):
    msg = await m.reply("🔥 **Fetching Top 2025 songs...**")
    results = search_jiosaavn_multiple("top hits 2025 new songs", 10)
    if not results:
        await msg.edit("❌ No results found!")
        return
    text = "🔥 **Top Songs of 2025:**\n\n"
    for i, song in enumerate(results, 1):
        text += f"{i}. **{song['name']}** - {song['primaryArtists']}\n"
    text += "\n📥 Use `/download [song name]` to download!"
    await msg.edit(text)

@app.on_message(filters.command("save"))
async def save_favorite(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip() in ["[song]"]:
        await m.reply("❌ Example: `/save Tum Hi Ho`")
        return
    query = parts[1].strip()
    user_id = m.from_user.id
    if user_id not in favorites:
        favorites[user_id] = []
    if query in favorites[user_id]:
        await m.reply(f"⭐ `{query}` is already in favorites!")
        return
    if len(favorites[user_id]) >= 20:
        await m.reply("❌ Favorites full! Max 20 songs.")
        return
    favorites[user_id].append(query)
    await m.reply(f"⭐ **Saved:** `{query}`")

@app.on_message(filters.command("favorites"))
async def show_favorites(_, m: Message):
    user_id = m.from_user.id
    if user_id not in favorites or not favorites[user_id]:
        await m.reply("💾 No favorites yet!\nUse `/save [song name]` to add.")
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
        await m.reply(f"❌ `{query}` not in favorites!")
        return
    favorites[user_id].remove(query)
    await m.reply(f"🗑 **Removed:** `{query}`")

@app.on_message(filters.command("history"))
async def show_history(_, m: Message):
    user_id = m.from_user.id
    if user_id not in history or not history[user_id]:
        await m.reply("📜 No history yet!")
        return
    text = "📜 **Your Recent Songs:**\n\n"
    for i, song in enumerate(history[user_id], 1):
        text += f"{i}. {song}\n"
    await m.reply(text)

@app.on_message(filters.command("stats"))
async def bot_stats(_, m: Message):
    await m.reply(
        f"📊 **Bot Statistics:**\n\n"
        f"👥 Total Users: {len(stats['users'])}\n"
        f"📥 Total Downloads: {stats['total_downloads']}\n"
        f"⭐ Rated Songs: {len(song_ratings)}\n"
        f"🎵 Database: JioSaavn (Millions)\n\n"
        f"🔜 Voice Chat: Coming Soon!"
    )

@app.on_message(filters.command("mystats"))
async def my_stats(_, m: Message):
    user_id = m.from_user.id
    if user_id not in user_stats or user_stats[user_id]["downloads"] == 0:
        await m.reply(f"👤 **Your Stats:**\n\n📥 Downloads: 0\n\nStart downloading! 🎵")
        return
    total = user_stats[user_id]["downloads"]
    songs = user_stats[user_id]["songs"]
    most_common = max(set(songs), key=songs.count) if songs else "None"
    await m.reply(
        f"👤 **Your Stats, {m.from_user.first_name}:**\n\n"
        f"📥 Total Downloads: {total}\n"
        f"🎵 Most Downloaded: {most_common}\n"
        f"📜 History: {len(history.get(user_id, []))}\n"
        f"⭐ Favorites: {len(favorites.get(user_id, []))}"
    )

@app.on_message(filters.command("lastdownload"))
async def last_download(_, m: Message):
    user_id = m.from_user.id
    if user_id not in last_downloaded:
        await m.reply("🎵 No song downloaded yet!")
        return
    song = last_downloaded[user_id]
    await m.reply(
        f"🎵 **Last Downloaded:**\n\n"
        f"🎶 **{song['title']}**\n"
        f"⏱ {song['duration']}\n"
        f"👤 By: {song['by']}\n\n"
        f"📥 `/download {song['title']}` to download again!"
    )

print("✅ Bot started!")
app.run()
