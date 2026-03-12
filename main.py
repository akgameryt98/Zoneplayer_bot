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

PLACEHOLDERS = ["[song]", "[song name]", "[name]", "[artist]", "[line]", "[mood]", "[type]", "[a-z]"]

def search_jiosaavn(query):
    try:
        url = f"https://jiosaavn-api-privatecvc2.vercel.app/search/songs?query={query}&page=1&limit=10"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=15)
        data = r.json()
        results = data["data"]["results"]
        if not results:
            return None, None, None, None
        query_words = query.lower().split()
        best = None
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
        dl_url = best["downloadUrl"][-1]["link"]
        duration = int(best["duration"])
        return dl_url, f"{title} - {artist}", duration, best
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
        fallback = [
            '💬 "Without music, life would be a mistake." — Nietzsche',
            '💬 "Where words fail, music speaks." — H.C. Andersen',
            '💬 "One good thing about music, when it hits you, you feel no pain." — Bob Marley',
            '💬 "Music gives a soul to the universe, wings to the mind." — Plato',
            '💬 "Sangeet woh bhasha hai jo seedha dil se baat karti hai!" 🇮🇳'
        ]
        return random.choice(fallback)

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
        await msg.edit("❌ Song not found! Try a different name.")
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
    last_downloaded[user_id] = {"title": title, "duration": f"{mins}:{secs:02d}", "by": m.from_user.first_name}
    await msg.edit(f"📤 **Sending:** `{title}`...")
    album = song_data.get("album", {}).get("name", "Unknown") if song_data else "Unknown"
    year = song_data.get("year", "Unknown") if song_data else "Unknown"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Share", switch_inline_query=title),
         InlineKeyboardButton("⭐ Save", callback_data=f"save_{title[:40]}")],
        [InlineKeyboardButton("🎵 Similar", callback_data=f"sim_{title[:40]}"),
         InlineKeyboardButton("ℹ️ Info", callback_data=f"inf_{title[:40]}")]
    ])
    await app.send_audio(
        m.chat.id, path,
        caption=(f"🎵 **{title}**\n💿 {album} | 📅 {year}\n⏱ {mins}:{secs:02d}\n👤 {m.from_user.first_name}"),
        title=title, duration=duration, reply_markup=keyboard
    )
    await msg.delete()
    try:
        os.remove(path)
    except:
        pass

# ========== CALLBACKS ==========

@app.on_callback_query(filters.regex(r"^save_"))
async def save_callback(_, cb):
    song_title = cb.data[5:]
    user_id = cb.from_user.id
    if user_id not in favorites:
        favorites[user_id] = []
    if song_title in favorites[user_id]:
        await cb.answer("⭐ Already in favorites!", show_alert=False)
        return
    favorites[user_id].append(song_title)
    await cb.answer("⭐ Saved!", show_alert=True)

@app.on_callback_query(filters.regex(r"^sim_"))
async def similar_callback(_, cb):
    song_title = cb.data[4:]
    msg = await cb.message.reply(f"🔍 Finding similar...")
    results = search_jiosaavn_multiple(f"songs like {song_title}", 6)
    if not results:
        await msg.edit("❌ No similar songs found!")
        await cb.answer()
        return
    text = f"🎵 **Similar to** `{song_title}`:\n\n"
    for i, s in enumerate(results, 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)
    await cb.answer()

@app.on_callback_query(filters.regex(r"^inf_"))
async def info_callback(_, cb):
    song_title = cb.data[4:]
    msg = await cb.message.reply("🔍 Getting info...")
    dl_url, title, duration, song_data = search_jiosaavn(song_title)
    if not song_data:
        await msg.edit("❌ Not found!")
        await cb.answer()
        return
    mins = duration // 60
    secs = duration % 60
    await msg.edit(
        f"ℹ️ **{song_data['name']}**\n"
        f"👤 {song_data['primaryArtists']}\n"
        f"💿 {song_data.get('album', {}).get('name', 'Unknown')}\n"
        f"📅 {song_data.get('year', 'Unknown')}\n"
        f"⏱ {mins}:{secs:02d}"
    )
    await cb.answer()

@app.on_callback_query(filters.regex("dl_birthday"))
async def birthday_dl(_, cb):
    await cb.answer()
    msg = await cb.message.reply("⬇️ Downloading...")
    await send_song(cb.message, "Baar Baar Din Yeh Aaye", msg)

@app.on_callback_query(filters.regex(r"^rate_"))
async def rate_callback(_, cb):
    parts = cb.data.split("_")
    rating = int(parts[1])
    song = "_".join(parts[2:])
    if song not in song_ratings:
        song_ratings[song] = []
    song_ratings[song].append(rating)
    avg = sum(song_ratings[song]) / len(song_ratings[song])
    await cb.answer(f"✅ Rated {rating}⭐", show_alert=False)

@app.on_callback_query(filters.regex(r"^none$"))
async def none_callback(_, cb):
    await cb.answer()

# ========== COMMANDS ==========

@app.on_message(filters.command("start"))
async def start(_, m: Message):
    await m.reply(
        f"🎵 **Welcome to Music Bot!**\n"
        f"Hello {m.from_user.first_name}! 👋\n\n"
        "**Commands:**\n\n"
        "📥 `/download [song]` - Download song\n"
        "🔍 `/search [song]` - Search top 5\n"
        "ℹ️ `/info [song]` - Song details\n"
        "📝 `/lyrics [song - artist]` - Lyrics\n"
        "🎭 `/mood [type]` - Mood songs\n"
        "🎸 `/genre [type]` - Genre songs\n"
        "🌐 `/hindi` `/punjabi` `/english`\n"
        "🎤 `/artist [name]` - Artist songs\n"
        "🏆 `/topartist [name]` - Artist top songs\n"
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
        "🌍 `/regional [language]` - Regional\n"
        "🎭 `/vibe [song]` - Vibe analysis\n"
        "🤖 `/ai_playlist [activity]` - AI playlist\n"
        "💬 `/quote` - Music quote\n"
        "🎯 `/guesssong` - Guess the song!\n"
        "⭐ `/rate [song]` - Rate song\n"
        "🏆 `/topsongs` - Top rated\n"
        "⚖️ `/compare [s1] | [s2]` - Compare\n"
        "📦 `/batch` - Multiple download\n"
        "🔤 `/findlyrics [line]` - Find by lyrics\n"
        "📊 `/topindia` `/topbollywood` `/top2025`\n"
        "⭐ `/save [song]` - Save favorite\n"
        "🗑 `/removefav [song]` - Remove\n"
        "💾 `/favorites` - View favorites\n"
        "📜 `/history` - Recent songs\n"
        "📊 `/stats` - Bot stats\n"
        "👤 `/mystats` - My stats\n"
        "🎵 `/lastdownload` - Last song\n"
        "❓ `/help` - Help\n\n"
        "🔜 **Coming Soon:** 🎙 `/play` Voice Chat"
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
        "🎸 `/genre rock/pop/jazz/classical/rap/indie/sufi/folk`\n"
        "🌐 `/hindi` `/punjabi` `/english`\n"
        "🎤 `/artist Arijit Singh`\n"
        "🏆 `/topartist Arijit Singh`\n"
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
async def play_cs(_, m: Message):
    await m.reply("🔜 **Coming Soon!**\n\nUse 📥 `/download [song]` for now!")

@app.on_message(filters.command("download"))
async def download(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Song name likho!\nExample: `/download Tum Hi Ho`")
        return
    msg = await m.reply(f"🔍 **Searching:** `{parts[1].strip()}`...")
    await send_song(m, parts[1].strip(), msg)

@app.on_message(filters.command("search"))
async def search(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Song name likho!\nExample: `/search Arijit Singh`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"🔍 **Searching:** `{query}`...")
    results = search_jiosaavn_multiple(query, 5)
    if not results:
        await msg.edit("❌ No results found!")
        return
    text = f"🔍 **Results for:** `{query}`\n\n"
    for i, song in enumerate(results, 1):
        d = int(song["duration"])
        text += f"{i}. **{song['name']}**\n   👤 {song['primaryArtists']} | ⏱ {d//60}:{d%60:02d}\n\n"
    text += "📥 `/download [song name]` to download!"
    await msg.edit(text)

@app.on_message(filters.command("info"))
async def song_info(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Song name likho!\nExample: `/info Tum Hi Ho`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"🔍 **Getting info:** `{query}`...")
    dl_url, title, duration, song_data = search_jiosaavn(query)
    if not song_data:
        await msg.edit("❌ Song not found!")
        return
    mins = duration // 60
    secs = duration % 60
    await msg.edit(
        f"ℹ️ **Song Info:**\n\n"
        f"🎵 **Title:** {song_data['name']}\n"
        f"👤 **Artist:** {song_data['primaryArtists']}\n"
        f"💿 **Album:** {song_data.get('album', {}).get('name', 'Unknown')}\n"
        f"📅 **Year:** {song_data.get('year', 'Unknown')}\n"
        f"🌐 **Language:** {song_data.get('language', 'Unknown').capitalize()}\n"
        f"⏱ **Duration:** {mins}:{secs:02d}\n\n"
        f"📥 `/download {song_data['name']}` to download!"
    )

@app.on_message(filters.command("lyrics"))
async def lyrics(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Format: `/lyrics Song - Artist`\nExample: `/lyrics Shape of You - Ed Sheeran`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"🔍 **Searching lyrics:** `{query}`...")
    lyrics_text, title = get_lyrics(query)
    if not lyrics_text:
        await msg.edit("❌ Lyrics not found!\nTry: `/lyrics Song Name - Artist Name`")
        return
    header = f"📝 **Lyrics: {title}**\n\n"
    full_text = header + lyrics_text
    if len(full_text) <= 4096:
        await msg.edit(full_text)
    else:
        await msg.edit(header + lyrics_text[:4000])
        remaining = lyrics_text[4000:]
        while remaining:
            chunk = remaining[:4096]
            remaining = remaining[4096:]
            await m.reply(chunk)

@app.on_message(filters.command("mood"))
async def mood(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("🎭 **Choose mood:**\n`/mood happy` 😊\n`/mood sad` 😢\n`/mood party` 🎉\n`/mood romantic` 💕\n`/mood workout` 💪\n`/mood chill` 😌")
        return
    mood_type = parts[1].strip().lower()
    queries = {"happy": "happy upbeat bollywood", "sad": "sad emotional hindi", "party": "party dance hindi", "romantic": "romantic love hindi", "workout": "workout gym motivation", "chill": "chill relaxing hindi"}
    emojis = {"happy": "😊", "sad": "😢", "party": "🎉", "romantic": "💕", "workout": "💪", "chill": "😌"}
    if mood_type not in queries:
        await m.reply("❌ Available: `happy` `sad` `party` `romantic` `workout` `chill`")
        return
    msg = await m.reply(f"🎭 **Fetching {mood_type} songs...**")
    results = search_jiosaavn_multiple(queries[mood_type], 8)
    if not results:
        await msg.edit("❌ No songs found!")
        return
    text = f"🎭 **{mood_type.capitalize()} Songs** {emojis[mood_type]}\n\n"
    for i, s in enumerate(results, 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

@app.on_message(filters.command("genre"))
async def genre(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("🎸 **Choose genre:**\n`/genre rock` 🎸\n`/genre pop` 🎵\n`/genre jazz` 🎷\n`/genre classical` 🎻\n`/genre rap` 🎤\n`/genre indie` 🌿\n`/genre sufi` 🌙\n`/genre folk` 🪘")
        return
    g = parts[1].strip().lower()
    queries = {"rock": "rock songs", "pop": "pop hits", "jazz": "jazz music", "classical": "classical instrumental", "rap": "rap hip hop", "indie": "indie hindi", "sufi": "sufi songs", "folk": "folk india"}
    emojis = {"rock": "🎸", "pop": "🎵", "jazz": "🎷", "classical": "🎻", "rap": "🎤", "indie": "🌿", "sufi": "🌙", "folk": "🪘"}
    if g not in queries:
        await m.reply("❌ Available: `rock` `pop` `jazz` `classical` `rap` `indie` `sufi` `folk`")
        return
    msg = await m.reply(f"🔍 **Fetching {g} songs...**")
    results = search_jiosaavn_multiple(queries[g], 8)
    if not results:
        await msg.edit("❌ No songs found!")
        return
    text = f"{emojis[g]} **{g.capitalize()} Songs:**\n\n"
    for i, s in enumerate(results, 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

@app.on_message(filters.command("hindi"))
async def hindi(_, m: Message):
    msg = await m.reply("🔍 **Fetching Hindi songs...**")
    results = search_jiosaavn_multiple("top hindi songs 2024", 8)
    text = "🇮🇳 **Top Hindi Songs:**\n\n"
    for i, s in enumerate(results, 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

@app.on_message(filters.command("punjabi"))
async def punjabi(_, m: Message):
    msg = await m.reply("🔍 **Fetching Punjabi songs...**")
    results = search_jiosaavn_multiple("top punjabi songs 2024", 8)
    text = "🎵 **Top Punjabi Songs:**\n\n"
    for i, s in enumerate(results, 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

@app.on_message(filters.command("english"))
async def english(_, m: Message):
    msg = await m.reply("🔍 **Fetching English songs...**")
    results = search_jiosaavn_multiple("top english hits 2024", 8)
    text = "🎵 **Top English Songs:**\n\n"
    for i, s in enumerate(results, 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

@app.on_message(filters.command("artist"))
async def artist(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Example: `/artist Arijit Singh`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"🔍 **Fetching songs by:** `{query}`...")
    results = search_jiosaavn_multiple(f"{query} songs", 8)
    if not results:
        await msg.edit("❌ No results!")
        return
    text = f"🎤 **Songs by {query}:**\n\n"
    for i, s in enumerate(results, 1):
        d = int(s["duration"])
        text += f"{i}. **{s['name']}** | ⏱ {d//60}:{d%60:02d}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

@app.on_message(filters.command("topartist"))
async def topartist(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Example: `/topartist Arijit Singh`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"🏆 **Fetching top songs by:** `{query}`...")
    results = search_jiosaavn_multiple(f"best of {query}", 8)
    if not results:
        await msg.edit("❌ No results!")
        return
    text = f"🏆 **Top Songs by {query}:**\n\n"
    for i, s in enumerate(results, 1):
        d = int(s["duration"])
        text += f"{i}. **{s['name']}** | ⏱ {d//60}:{d%60:02d}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

@app.on_message(filters.command("album"))
async def album(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Example: `/album Aashiqui 2`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"💿 **Fetching album:** `{query}`...")
    results = search_jiosaavn_multiple(f"{query} album", 8)
    if not results:
        await msg.edit("❌ Not found!")
        return
    text = f"💿 **Album: {query}**\n\n"
    for i, s in enumerate(results, 1):
        d = int(s["duration"])
        text += f"{i}. **{s['name']}** - {s['primaryArtists']} | ⏱ {d//60}:{d%60:02d}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

@app.on_message(filters.command("letter"))
async def letter(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await m.reply("❌ Example: `/letter T`")
        return
    l = parts[1].strip()[0].upper()
    if not l.isalpha():
        await m.reply("❌ Valid letter likhو!")
        return
    msg = await m.reply(f"🔤 **Fetching songs starting with:** `{l}`...")
    results = search_jiosaavn_multiple(f"songs starting with {l} hindi", 10)
    filtered = [s for s in results if s["name"].upper().startswith(l)] or results[:8]
    text = f"🔤 **Songs Starting with '{l}':**\n\n"
    for i, s in enumerate(filtered[:8], 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

@app.on_message(filters.command("random"))
async def random_song(_, m: Message):
    keywords = ["hindi popular 2024", "bollywood hits", "top songs india", "english hits", "punjabi popular", "romantic songs", "party songs hindi"]
    msg = await m.reply("🎲 **Fetching random song...**")
    results = search_jiosaavn_multiple(random.choice(keywords), 20)
    if not results:
        await msg.edit("❌ No songs found!")
        return
    await send_song(m, random.choice(results)["name"], msg)

@app.on_message(filters.command("similar"))
async def similar(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Example: `/similar Tum Hi Ho`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"🔍 **Finding similar to:** `{query}`...")
    dl_url, title, duration, song_data = search_jiosaavn(query)
    if not song_data:
        await msg.edit("❌ Song not found!")
        return
    song_id = song_data["id"]
    artist_name = song_data["primaryArtists"].split(",")[0].strip()
    try:
        sr = requests.get(f"https://jiosaavn-api-privatecvc2.vercel.app/songs/{song_id}/suggestions", headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        similar_list = sr.json().get("data", [])
    except:
        similar_list = []
    if not similar_list:
        similar_list = search_jiosaavn_multiple(f"{artist_name} songs", 6)
        text = f"🎵 **Similar to** `{query}`:\n\n"
        for i, s in enumerate(similar_list, 1):
            text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    else:
        text = f"🎵 **Similar to** `{query}`:\n\n"
        for i, s in enumerate(similar_list[:8], 1):
            text += f"{i}. **{s.get('name', 'Unknown')}** - {s.get('primaryArtists', 'Unknown')}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

@app.on_message(filters.command("daily"))
async def daily(_, m: Message):
    now = datetime.datetime.now()
    keywords = ["hindi hits popular", "bollywood popular songs", "top songs india", "romantic hindi", "new hindi songs 2024"]
    random.seed(now.day + now.month * 100)
    query = random.choice(keywords)
    random.seed()
    msg = await m.reply("📅 **Fetching today's song...**")
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
        await msg.edit("❌ Could not fetch!")
        return
    text = "🌍 **Trending Right Now:**\n\n"
    for i, s in enumerate(results, 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

@app.on_message(filters.command("recommend"))
async def recommend(_, m: Message):
    user_id = m.from_user.id
    msg = await m.reply("🎯 **Finding recommendations...**")
    if user_id in history and history[user_id]:
        last = history[user_id][0]
        results = search_jiosaavn_multiple(f"songs like {last}", 5)
        text = "🎯 **Based on Your History:**\n\n"
    else:
        results = search_jiosaavn_multiple("best hindi songs popular", 5)
        text = "🎯 **Recommended for You:**\n\n"
    if not results:
        await msg.edit("❌ Could not fetch!")
        return
    for i, s in enumerate(results, 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

@app.on_message(filters.command("short"))
async def short(_, m: Message):
    msg = await m.reply("⏱ **Fetching short songs...**")
    results = search_jiosaavn_multiple("short songs 2 minutes", 15)
    text = "⏱ **Short Songs (Under 3 Mins):**\n\n"
    count = 0
    for s in results:
        d = int(s["duration"])
        if d <= 180:
            count += 1
            text += f"{count}. **{s['name']}** - {s['primaryArtists']} | ⏱ {d//60}:{d%60:02d}\n"
    if count == 0:
        await msg.edit("❌ No short songs found!")
        return
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

@app.on_message(filters.command("night"))
async def night(_, m: Message):
    msg = await m.reply("🌙 **Fetching late night songs...**")
    results = search_jiosaavn_multiple("late night chill sad songs hindi", 10)
    if not results:
        await msg.edit("❌ No songs found!")
        return
    await send_song(m, random.choice(results)["name"], msg)

@app.on_message(filters.command("birthday"))
async def birthday(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Name likho!\nExample: `/birthday Rahul`")
        return
    name = parts[1].strip()
    msg = await m.reply(f"🎂 **Fetching birthday songs...**")
    results = search_jiosaavn_multiple("birthday songs hindi english", 7)
    text = f"🎂 **Happy Birthday {name}!** 🎉\n\n🎵 **Songs:**\n\n"
    for i, s in enumerate(results, 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    text += f"\n🎊 Wishing **{name}** a wonderful birthday! 🎈🥳"
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🎵 Download Birthday Song", callback_data="dl_birthday")]])
    await msg.edit(text, reply_markup=keyboard)

@app.on_message(filters.command("playlist"))
async def playlist(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Example: `/playlist happy`\nAvailable: `happy` `sad` `party` `romantic` `workout` `chill`")
        return
    mood_type = parts[1].strip().lower()
    queries = {"happy": "happy upbeat bollywood", "sad": "sad emotional hindi", "party": "party dance hindi", "romantic": "romantic love hindi", "workout": "workout gym motivation", "chill": "chill relaxing hindi"}
    emojis = {"happy": "😊", "sad": "😢", "party": "🎉", "romantic": "💕", "workout": "💪", "chill": "😌"}
    if mood_type not in queries:
        await m.reply("❌ Available: `happy` `sad` `party` `romantic` `workout` `chill`")
        return
    results = search_jiosaavn_multiple(queries[mood_type], 5)
    await m.reply(f"🎵 **{mood_type.capitalize()} Playlist** {emojis[mood_type]}\nDownloading {len(results)} songs...\n⚠️ Few minutes lagenge!")
    for s in results:
        try:
            msg = await m.reply(f"⬇️ `{s['name']}`...")
            await send_song(m, s["name"], msg)
            await asyncio.sleep(2)
        except:
            pass

@app.on_message(filters.command("regional"))
async def regional(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("🌍 **Choose:**\n`/regional marathi`\n`/regional tamil`\n`/regional telugu`\n`/regional bhojpuri`\n`/regional bengali`\n`/regional gujarati`\n`/regional kannada`\n`/regional malayalam`")
        return
    lang = parts[1].strip().lower()
    msg = await m.reply(f"🌍 **Fetching {lang} songs...**")
    results = search_jiosaavn_multiple(f"top {lang} songs popular", 8)
    if not results:
        await msg.edit("❌ No songs found!")
        return
    text = f"🌍 **Top {lang.capitalize()} Songs:**\n\n"
    for i, s in enumerate(results, 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

@app.on_message(filters.command("vibe"))
async def vibe(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Song name likho!\nExample: `/vibe Tum Hi Ho`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"🎭 **Analyzing vibe:** `{query}`...")
    dl_url, title, duration, song_data = search_jiosaavn(query)
    if not song_data:
        await msg.edit("❌ Song not found!")
        return
    name = song_data.get("name", "").lower()
    mins = duration // 60
    secs = duration % 60
    sad_kw = ["sad", "dard", "judai", "alvida", "rona", "toota", "bekhayali", "tanha"]
    romantic_kw = ["love", "ishq", "pyar", "mohabbat", "dil", "kesariya", "raataan", "tera"]
    happy_kw = ["happy", "khushi", "dance", "party", "gallan", "badtameez"]
    energetic_kw = ["power", "fire", "thunder", "believer", "warrior", "bhoot"]
    if any(k in name for k in sad_kw):
        vibe_r, desc = "😢 Sad / Emotional", "Perfect for heartfelt moments."
    elif any(k in name for k in romantic_kw):
        vibe_r, desc = "💕 Romantic", "Perfect for love and special moments."
    elif any(k in name for k in happy_kw):
        vibe_r, desc = "😊 Happy / Upbeat", "Perfect for cheerful moments!"
    elif any(k in name for k in energetic_kw):
        vibe_r, desc = "💪 Energetic", "Perfect for workouts!"
    elif duration > 300:
        vibe_r, desc = "🎭 Epic / Cinematic", "Epic long song!"
    elif duration < 180:
        vibe_r, desc = "⚡ Short & Punchy", "Short but powerful!"
    else:
        vibe_r, desc = "😌 Chill / Neutral", "Good for any time!"
    await msg.edit(
        f"🎭 **Vibe Analysis:**\n\n"
        f"🎵 **{song_data['name']}**\n"
        f"👤 {song_data['primaryArtists']}\n"
        f"⏱ {mins}:{secs:02d} | 🌐 {song_data.get('language','Unknown').capitalize()}\n\n"
        f"**Vibe:** {vibe_r}\n📝 {desc}"
    )

@app.on_message(filters.command("ai_playlist"))
async def ai_playlist(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("🤖 **Choose activity:**\n`/ai_playlist gym` 💪\n`/ai_playlist study` 📚\n`/ai_playlist heartbreak` 💔\n`/ai_playlist sleep` 😴\n`/ai_playlist party` 🎉\n`/ai_playlist romantic` 💕\n`/ai_playlist morning` 🌅\n`/ai_playlist roadtrip` 🚗")
        return
    activity = parts[1].strip().lower()
    queries = {"gym": "workout gym motivation", "study": "study focus calm instrumental", "heartbreak": "heartbreak sad emotional hindi", "sleep": "sleep relaxing calm", "party": "party dance upbeat hindi", "romantic": "romantic love songs", "morning": "morning fresh motivational", "roadtrip": "roadtrip travel songs"}
    emojis = {"gym": "💪", "study": "📚", "heartbreak": "💔", "sleep": "😴", "party": "🎉", "romantic": "💕", "morning": "🌅", "roadtrip": "🚗"}
    if activity not in queries:
        await m.reply("❌ Available: `gym` `study` `heartbreak` `sleep` `party` `romantic` `morning` `roadtrip`")
        return
    msg = await m.reply(f"🤖 **Creating AI Playlist: {activity}...**")
    results = search_jiosaavn_multiple(queries[activity], 8)
    if not results:
        await msg.edit("❌ No songs found!")
        return
    text = f"🤖 **AI Playlist: {activity.capitalize()}** {emojis[activity]}\n\n"
    for i, s in enumerate(results, 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

@app.on_message(filters.command("quote"))
async def quote(_, m: Message):
    msg = await m.reply("💬 **Fetching quote...**")
    await msg.edit(f"💬 **Music Quote:**\n\n{fetch_quote()}")

@app.on_message(filters.command("guesssong"))
async def guesssong(_, m: Message):
    msg = await m.reply("🎯 **Fetching quiz song...**")
    chat_id = m.chat.id
    results = search_jiosaavn_multiple("popular hindi songs", 15)
    if not results:
        await msg.edit("❌ Could not fetch!")
        return
    song = random.choice(results)
    title = song["name"]
    artist = song["primaryArtists"]
    lyrics_text, _ = get_lyrics(f"{title} - {artist}")
    if lyrics_text:
        lines = [l.strip() for l in lyrics_text.split("\n") if len(l.strip()) > 20]
        line = random.choice(lines[:10]) if lines else f"Hint: Artist is **{artist}**"
    else:
        line = f"Hint: Artist is **{artist}**"
    active_quiz[chat_id] = {"answer": title.lower(), "title": title, "artist": artist}
    await msg.edit(
        f"🎯 **Guess The Song!**\n\n"
        f"🎵 **Lyrics:**\n_{line}_\n\n"
        f"💭 Reply with song name!\n⏱ 30 seconds!\n\n"
        f"Use `/skip` to skip."
    )
    await asyncio.sleep(30)
    if chat_id in active_quiz:
        del active_quiz[chat_id]
        await m.reply(f"⏱ **Time's up!**\nAnswer: **{title}** by {artist}")

@app.on_message(filters.command("skip"))
async def skip(_, m: Message):
    chat_id = m.chat.id
    if chat_id not in active_quiz:
        await m.reply("❌ No active quiz!")
        return
    quiz = active_quiz.pop(chat_id)
    await m.reply(f"⏭ **Skipped!**\nAnswer: **{quiz['title']}** by {quiz['artist']}")

@app.on_message(filters.text & ~filters.regex(r"^/"))
async def quiz_check(_, m: Message):
    chat_id = m.chat.id
    if chat_id not in active_quiz:
        return
    quiz = active_quiz[chat_id]
    user_ans = m.text.strip().lower()
    correct = quiz["answer"].lower()
    if any(w in user_ans for w in correct.split() if len(w) > 3):
        del active_quiz[chat_id]
        await m.reply(f"✅ **Correct! Well done {m.from_user.first_name}!** 🎉\n🎵 **{quiz['title']}** by {quiz['artist']}\n\n📥 `/download {quiz['title']}`")

@app.on_message(filters.command("rate"))
async def rate(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Example: `/rate Tum Hi Ho`")
        return
    song = parts[1].strip()
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("1⭐", callback_data=f"rate_1_{song[:25]}"),
        InlineKeyboardButton("2⭐", callback_data=f"rate_2_{song[:25]}"),
        InlineKeyboardButton("3⭐", callback_data=f"rate_3_{song[:25]}"),
        InlineKeyboardButton("4⭐", callback_data=f"rate_4_{song[:25]}"),
        InlineKeyboardButton("5⭐", callback_data=f"rate_5_{song[:25]}"),
    ]])
    await m.reply(f"⭐ **Rate:** `{song}`", reply_markup=keyboard)

@app.on_message(filters.command("topsongs"))
async def topsongs(_, m: Message):
    if not song_ratings:
        await m.reply("❌ No rated songs yet!\nUse `/rate [song]` to rate.")
        return
    sorted_s = sorted(song_ratings.items(), key=lambda x: sum(x[1])/len(x[1]), reverse=True)
    text = "🏆 **Top Rated Songs:**\n\n"
    for i, (song, ratings) in enumerate(sorted_s[:10], 1):
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
    s1, s2 = songs[0].strip(), songs[1].strip()
    msg = await m.reply("⚖️ **Comparing...**")
    _, t1, d1, data1 = search_jiosaavn(s1)
    _, t2, d2, data2 = search_jiosaavn(s2)
    if not data1 or not data2:
        await msg.edit("❌ One or both songs not found!")
        return
    await msg.edit(
        f"⚖️ **Song Comparison:**\n\n"
        f"**1️⃣ {data1['name']}**\n"
        f"👤 {data1['primaryArtists']}\n"
        f"💿 {data1.get('album',{}).get('name','Unknown')}\n"
        f"⏱ {d1//60}:{d1%60:02d} | 📅 {data1.get('year','?')}\n\n"
        f"**VS**\n\n"
        f"**2️⃣ {data2['name']}**\n"
        f"👤 {data2['primaryArtists']}\n"
        f"💿 {data2.get('album',{}).get('name','Unknown')}\n"
        f"⏱ {d2//60}:{d2%60:02d} | 📅 {data2.get('year','?')}\n\n"
        f"📥 `/download {data1['name']}` or `/download {data2['name']}`"
    )

@app.on_message(filters.command("batch"))
async def batch(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await m.reply(
            "📦 **Batch Download!**\n\n"
            "Seedha songs list ke saath likho:\n\n"
            "```\n/batch Tum Hi Ho\nKesariya\nBlinding Lights```\n\n"
            "⚠️ Max 5 songs!"
        )
        return
    
    songs = [s.strip() for s in parts[1].strip().split("\n") if s.strip()]
    songs = songs[:5]
    
    if not songs:
        await m.reply("❌ Write song name!")
        return
    
    await m.reply(f"📦 **Downloading {len(songs)} songs...**\n⚠️ Thoda wait karo!")
    
    for i, song in enumerate(songs, 1):
        try:
            msg = await m.reply(f"⬇️ **{i}/{len(songs)}:** `{song}`...")
            await send_song(m, song, msg)
            await asyncio.sleep(2)
        except Exception as e:
            await m.reply(f"❌ **{song}** - Error: `{str(e)}`")

@app.on_message(filters.command("findlyrics"))
async def findlyrics(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Example: `/findlyrics tere bin nahi lagda`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"🔤 **Searching song by lyrics:** `{query}`...")
    try:
        r = requests.get(f"https://lrclib.net/api/search?q={query}", headers={"User-Agent": "MusicBot/1.0"}, timeout=15)
        data = r.json()
        if data:
            text = f"🔤 **Songs matching:** `{query}`\n\n"
            for i, item in enumerate(data[:5], 1):
                text += f"{i}. **{item.get('trackName','Unknown')}** - {item.get('artistName','Unknown')}\n"
            text += "\n📥 `/download [song name]`"
            await msg.edit(text)
        else:
            results = search_jiosaavn_multiple(query, 5)
            text = f"🔤 **Possible songs:** `{query}`\n\n"
            for i, s in enumerate(results, 1):
                text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
            await msg.edit(text)
    except Exception as e:
        await msg.edit(f"❌ Error: `{str(e)}`")

@app.on_message(filters.command("topindia"))
async def topindia(_, m: Message):
    msg = await m.reply("🇮🇳 **Fetching Top India songs...**")
    results = search_jiosaavn_multiple("top india trending songs 2024", 10)
    text = "🇮🇳 **Top Songs in India:**\n\n"
    for i, s in enumerate(results, 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

@app.on_message(filters.command("topbollywood"))
async def topbollywood(_, m: Message):
    msg = await m.reply("🎬 **Fetching Top Bollywood...**")
    results = search_jiosaavn_multiple("top bollywood hits 2024", 10)
    text = "🎬 **Top Bollywood Songs:**\n\n"
    for i, s in enumerate(results, 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

@app.on_message(filters.command("top2025"))
async def top2025(_, m: Message):
    msg = await m.reply("🔥 **Fetching Top 2025 songs...**")
    results = search_jiosaavn_multiple("top hits 2025 new songs", 10)
    text = "🔥 **Top Songs of 2025:**\n\n"
    for i, s in enumerate(results, 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

@app.on_message(filters.command("save"))
async def save(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Example: `/save Tum Hi Ho`")
        return
    query = parts[1].strip()
    user_id = m.from_user.id
    if user_id not in favorites:
        favorites[user_id] = []
    if query in favorites[user_id]:
        await m.reply(f"⭐ Already in favorites!")
        return
    if len(favorites[user_id]) >= 20:
        await m.reply("❌ Favorites full! Max 20.")
        return
    favorites[user_id].append(query)
    await m.reply(f"⭐ **Saved:** `{query}`")

@app.on_message(filters.command("favorites"))
async def show_favorites(_, m: Message):
    user_id = m.from_user.id
    if user_id not in favorites or not favorites[user_id]:
        await m.reply("💾 No favorites!\nUse `/save [song]`")
        return
    text = "⭐ **Your Favorites:**\n\n"
    for i, s in enumerate(favorites[user_id], 1):
        text += f"{i}. {s}\n"
    text += "\n📥 `/download [song name]`"
    await m.reply(text)

@app.on_message(filters.command("removefav"))
async def removefav(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Example: `/removefav Tum Hi Ho`")
        return
    query = parts[1].strip()
    user_id = m.from_user.id
    if user_id not in favorites or query not in favorites[user_id]:
        await m.reply(f"❌ Not in favorites!")
        return
    favorites[user_id].remove(query)
    await m.reply(f"🗑 **Removed:** `{query}`")

@app.on_message(filters.command("history"))
async def show_history(_, m: Message):
    user_id = m.from_user.id
    if user_id not in history or not history[user_id]:
        await m.reply("📜 No history yet!")
        return
    text = "📜 **Recent Songs:**\n\n"
    for i, s in enumerate(history[user_id], 1):
        text += f"{i}. {s}\n"
    await m.reply(text)

@app.on_message(filters.command("stats"))
async def bot_stats(_, m: Message):
    await m.reply(
        f"📊 **Bot Statistics:**\n\n"
        f"👥 Users: {len(stats['users'])}\n"
        f"📥 Downloads: {stats['total_downloads']}\n"
        f"⭐ Rated Songs: {len(song_ratings)}\n"
        f"🎵 Database: JioSaavn\n\n"
        f"🔜 Voice Chat: Coming Soon!"
    )

@app.on_message(filters.command("mystats"))
async def mystats(_, m: Message):
    user_id = m.from_user.id
    if user_id not in user_stats or user_stats[user_id]["downloads"] == 0:
        await m.reply(f"👤 **{m.from_user.first_name}'s Stats:**\n\n📥 Downloads: 0\n\nStart downloading! 🎵")
        return
    total = user_stats[user_id]["downloads"]
    songs = user_stats[user_id]["songs"]
    most = max(set(songs), key=songs.count) if songs else "None"
    await m.reply(
        f"👤 **{m.from_user.first_name}'s Stats:**\n\n"
        f"📥 Downloads: {total}\n"
        f"🎵 Most Downloaded: {most}\n"
        f"📜 History: {len(history.get(user_id, []))}\n"
        f"⭐ Favorites: {len(favorites.get(user_id, []))}"
    )

@app.on_message(filters.command("lastdownload"))
async def lastdownload(_, m: Message):
    user_id = m.from_user.id
    if user_id not in last_downloaded:
        await m.reply("🎵 No song downloaded yet!\nUse `/download [song]`")
        return
    s = last_downloaded[user_id]
    await m.reply(
        f"🎵 **Last Downloaded:**\n\n"
        f"🎶 **{s['title']}**\n"
        f"⏱ {s['duration']} | 👤 {s['by']}\n\n"
        f"📥 `/download {s['title']}`"
    )

print("✅ Bot started!")
app.run()
