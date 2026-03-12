import asyncio
import os
import requests
import random
import datetime
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import API_ID, API_HASH, BOT_TOKEN
import database as db

app = Client("beatnova_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

BOT_NAME = "BeatNova"
BOT_USERNAME = "@SHADE_SONG_BOT"
DEVELOPER = "@ZeroShader"
START_TIME = datetime.datetime.now()

# In-memory only (quiz state, today counter)
active_quiz = {}
today_downloads = {"count": 0, "date": datetime.date.today()}

PLACEHOLDERS = ["[song]", "[song name]", "[name]", "[artist]", "[line]", "[mood]", "[type]", "[a-z]"]

# ========== HELPER FUNCTIONS ==========

def update_today_stats():
    today = datetime.date.today()
    if today_downloads["date"] != today:
        today_downloads["count"] = 0
        today_downloads["date"] = today

def get_badges(user_id):
    user = db.get_user(user_id)
    downloads = user["downloads"] if user else 0
    streak = user["streak"] if user else 0
    favs = db.count_favorites(user_id)
    rated = db.user_rated_count(user_id)
    badges = []
    if downloads >= 1: badges.append("🎵 First Download")
    if downloads >= 10: badges.append("🎧 Music Fan")
    if downloads >= 50: badges.append("🎸 Music Lover")
    if downloads >= 100: badges.append("🥇 Music Master")
    if downloads >= 500: badges.append("💎 Legend")
    if streak >= 3: badges.append("🔥 3-Day Streak")
    if streak >= 7: badges.append("⚡ 7-Day Streak")
    if streak >= 30: badges.append("👑 30-Day Streak")
    if favs >= 10: badges.append("⭐ Collector")
    if rated >= 5: badges.append("📊 Critic")
    return badges if badges else ["🌱 Just Starting!"]

def get_level(downloads):
    if downloads < 10: return "🥉 Beginner"
    elif downloads < 50: return "🥈 Music Lover"
    elif downloads < 100: return "🥇 Music Master"
    else: return "💎 Legend"

def get_user_genre_from_history(user_id):
    songs = db.get_history(user_id, 50)
    if not songs: return "Unknown"
    hindi = sum(1 for s in songs if any(w in s.lower() for w in ["hindi","tum","dil","pyar","ishq","tera","mera"]))
    english = sum(1 for s in songs if any(w in s.lower() for w in ["love","baby","night","light","heart"]))
    punjabi = sum(1 for s in songs if any(w in s.lower() for w in ["punjabi","jatt","kudi","yaar"]))
    counts = {"Hindi 🇮🇳": hindi, "English 🌍": english, "Punjabi 🎵": punjabi}
    return max(counts, key=counts.get)

def search_jiosaavn(query):
    try:
        url = f"https://jiosaavn-api-privatecvc2.vercel.app/search/songs?query={query}&page=1&limit=10"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        data = r.json()
        results = data["data"]["results"]
        if not results: return None, None, None, None
        query_words = query.lower().split()
        best = None
        for song in results:
            match_count = sum(1 for word in query_words if word in song["name"].lower())
            if match_count >= len(query_words) * 0.6:
                best = song
                break
        if not best: best = results[0]
        return best["downloadUrl"][-1]["link"], f"{best['name']} - {best['primaryArtists']}", int(best["duration"]), best
    except Exception as e:
        print(f"Search error: {e}")
        return None, None, None, None

def search_jiosaavn_quality(query, quality="320"):
    try:
        url = f"https://jiosaavn-api-privatecvc2.vercel.app/search/songs?query={query}&page=1&limit=10"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        data = r.json()
        results = data["data"]["results"]
        if not results: return None, None, None, None
        best = results[0]
        dl_urls = best.get("downloadUrl", [])
        quality_map = {"128": 0, "192": 1, "320": -1}
        try: dl_url = dl_urls[quality_map.get(quality, -1)]["link"]
        except: dl_url = dl_urls[-1]["link"]
        return dl_url, f"{best['name']} - {best['primaryArtists']}", int(best["duration"]), best
    except Exception as e:
        print(f"Quality search error: {e}")
        return None, None, None, None

def search_jiosaavn_multiple(query, limit=8):
    try:
        url = f"https://jiosaavn-api-privatecvc2.vercel.app/search/songs?query={query}&page=1&limit={limit}"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        return r.json()["data"]["results"]
    except: return []

def get_lyrics(query):
    try:
        parts = query.split("-")
        title = parts[0].strip()
        artist = parts[-1].strip() if len(parts) >= 2 else ""
        r = requests.get(f"https://lrclib.net/api/search?track_name={title}&artist_name={artist}",
                        headers={"User-Agent": "MusicBot/1.0"}, timeout=15)
        data = r.json()
        if not data: return None, None
        return data[0].get("plainLyrics"), f"{data[0].get('trackName', title)} - {data[0].get('artistName', artist)}"
    except Exception as e:
        print(f"Lyrics error: {e}")
        return None, None

def fetch_quote():
    try:
        r = requests.get("https://api.quotable.io/random?tags=music", timeout=10)
        data = r.json()
        return f'💬 "{data["content"]}"\n\n— {data["author"]}'
    except:
        return random.choice([
            '💬 "Without music, life would be a mistake." — Nietzsche',
            '💬 "Where words fail, music speaks." — H.C. Andersen',
            '💬 "One good thing about music, when it hits you, you feel no pain." — Bob Marley',
            '💬 "Music gives a soul to the universe, wings to the mind." — Plato',
        ])

def download_song(url, title):
    os.makedirs("dl", exist_ok=True)
    safe = "".join(c for c in title if c.isalnum() or c in " -_")[:50]
    path = f"dl/{safe}.mp3"
    r = requests.get(url, stream=True, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    with open(path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
    return path



async def send_song(m, query, msg, quality="320"):
    dl_url, title, duration, song_data = search_jiosaavn_quality(query, quality)
    if not dl_url:
        await msg.edit("❌ Song not found! Try a different name.")
        return
    await msg.edit(f"⬇️ **Downloading:** `{title}`...")
    path = download_song(dl_url, title)
    mins, secs = duration // 60, duration % 60
    user_id = m.from_user.id

    update_today_stats()
    today_downloads["count"] += 1
    db.increment_bot_stat("total_downloads")
    db.ensure_user(user_id, m.from_user.first_name)
    db.update_streak(user_id)
    db.increment_downloads(user_id)
    db.add_history(user_id, title)
    db.save_last_downloaded(user_id, title, f"{mins}:{secs:02d}", m.from_user.first_name)
    db.increment_song_downloads(title)

    await msg.edit(f"📤 **Sending:** `{title}`...")
    album = song_data.get("album", {}).get("name", "Unknown") if song_data else "Unknown"
    year = song_data.get("year", "Unknown") if song_data else "Unknown"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Share", switch_inline_query=title),
         InlineKeyboardButton("⭐ Save", callback_data=f"save_{title[:40]}")],
        [InlineKeyboardButton("🎵 Similar", callback_data=f"sim_{title[:40]}"),
         InlineKeyboardButton("🎤 Lyrics", callback_data=f"lyr_{title[:35]}")]
    ])
    await app.send_audio(
        m.chat.id, path,
        caption=f"🎵 **{title}**\n💿 {album} | 📅 {year}\n⏱ {mins}:{secs:02d} | 🎧 {quality}kbps\n👤 {m.from_user.first_name}\n\n🤖 {BOT_NAME} | {BOT_USERNAME}",
        title=title, duration=duration, reply_markup=keyboard
    )
    await msg.delete()
    try: os.remove(path)
    except: pass

# ========== CALLBACKS ==========

@app.on_callback_query(filters.regex(r"^save_"))
async def save_callback(_, cb):
    song_title = cb.data[5:]
    user_id = cb.from_user.id
    db.ensure_user(user_id, cb.from_user.first_name)
    if db.is_favorite(user_id, song_title):
        await cb.answer("⭐ Already in favorites!", show_alert=False)
        return
    db.add_favorite(user_id, song_title)
    db.increment_song_favorites(song_title)
    await cb.answer("⭐ Saved to favorites!", show_alert=True)

@app.on_callback_query(filters.regex(r"^sim_"))
async def similar_callback(_, cb):
    song_title = cb.data[4:]
    msg = await cb.message.reply("🔍 Finding similar...")
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

@app.on_callback_query(filters.regex(r"^lyr_"))
async def lyrics_callback(_, cb):
    song_title = cb.data[4:]
    msg = await cb.message.reply("🔍 Fetching lyrics...")
    lyrics_text, title = get_lyrics(song_title)
    if not lyrics_text:
        await msg.edit("❌ Lyrics not found!")
        await cb.answer()
        return
    header = f"📝 **Lyrics: {title}**\n\n"
    full = header + lyrics_text
    if len(full) <= 4096:
        await msg.edit(full)
    else:
        await msg.edit(header + lyrics_text[:4000])
        remaining = lyrics_text[4000:]
        while remaining:
            await cb.message.reply(remaining[:4096])
            remaining = remaining[4096:]
    await cb.answer()

@app.on_callback_query(filters.regex("dl_birthday"))
async def birthday_dl(_, cb):
    await cb.answer()
    msg = await cb.message.reply("⬇️ Downloading...")
    await send_song(cb.message, "Baar Baar Din Yeh Aaye", msg)

@app.on_callback_query(filters.regex(r"^rate_"))
async def rate_callback(_, cb):
    parts = cb.data.split("_")
    rating, song = int(parts[1]), "_".join(parts[2:])
    db.save_rating(cb.from_user.id, song, rating)
    avg, count = db.get_avg_rating(song)
    await cb.answer(f"✅ Rated {rating}⭐", show_alert=False)
    try:
        await cb.message.edit_reply_markup(InlineKeyboardMarkup([[
            InlineKeyboardButton(f"⭐ {avg:.1f}/5 ({count} votes)", callback_data="none")
        ]]))
    except: pass

@app.on_callback_query(filters.regex(r"^qual_"))
async def quality_callback(_, cb):
    parts = cb.data.split("_")
    quality, song = parts[1], "_".join(parts[2:])
    await cb.answer(f"Downloading {quality}kbps...", show_alert=False)
    msg = await cb.message.reply(f"⬇️ Downloading `{song}` in **{quality}kbps**...")
    await send_song(cb.message, song, msg, quality)

@app.on_callback_query(filters.regex(r"^help_(?!back)"))
async def help_category(_, cb):
    cat = cb.data[5:]
    texts = {
        "download": (
            "🎵 **Download & Search**\n\n"
            "📥 `/download [song]` — Download song\n"
            "🎧 `/quality [song]` — Choose quality\n"
            "🎵 `/preview [song]` — 30 sec preview\n"
            "🔍 `/search [song]` — Search top 5\n"
            "ℹ️ `/info [song]` — Song details\n"
            "📝 `/lyrics [song - artist]` — Full lyrics\n"
            "📦 `/batch` — Download multiple\n"
            "🎛 `/remix [song]` — Remix versions\n"
            "🎸 `/acoustic [song]` — Acoustic versions\n"
            "🎤 `/cover [song]` — Cover versions\n"
            "🎼 `/lofi [song]` — Lo-Fi versions"
        ),
        "discover": (
            "🌍 **Browse & Discover**\n\n"
            "🤖 `/ai_playlist [activity]`\n"
            "💿 `/album [name]`\n"
            "💿 `/albuminfo [name]`\n"
            "🎤 `/artist [name]`\n"
            "ℹ️ `/artistinfo [name]`\n"
            "🎂 `/birthday [name]`\n"
            "🔗 `/chain [song]`\n"
            "📅 `/daily`\n"
            "🌐 `/english` `/hindi` `/punjabi`\n"
            "🔤 `/findlyrics [line]`\n"
            "🎸 `/genre [type]`\n"
            "🎼 `/karaoke [song]`\n"
            "🔤 `/letter [A-Z]`\n"
            "🎭 `/mood [type]`\n"
            "🆕 `/newreleases`\n"
            "🌙 `/night`\n"
            "🎵 `/playlist [mood]`\n"
            "🎲 `/random`\n"
            "🎯 `/recommend`\n"
            "🌍 `/regional [lang]`\n"
            "⏱ `/short`\n"
            "🎵 `/similar [song]`\n"
            "🎤 `/similarartist [name]`\n"
            "🏆 `/topartist [name]`\n"
            "🎬 `/topbollywood`\n"
            "🇮🇳 `/topindia`\n"
            "🔥 `/top2025`\n"
            "🔥 `/trendingartist`\n"
            "🌍 `/trending`\n"
            "🎭 `/vibe [song]`\n"
            "📅 `/year [2000-2024]`\n"
            "💿 `/discography [artist]`\n"
            "🎵 `/duet [artist1] [artist2]`"
        ),
        "games": (
            "🎮 **Games & Fun**\n\n"
            "⚖️ `/compare [s1] | [s2]`\n"
            "📅 `/challenge` — Daily challenge\n"
            "🎯 `/fillblank` — Fill lyrics blank\n"
            "🎯 `/guesssong` — Guess the song\n"
            "🎮 `/musicquiz` — Music quiz\n"
            "🎤 `/artistquiz` — Artist quiz\n"
            "💬 `/quote` — Music quote\n"
            "⭐ `/rate [song]` — Rate a song\n"
            "🎵 `/topsongs` — Top rated\n"
            "🏆 `/tournament` — Song tournament\n"
            "📅 `/yeargame` — Year guess game"
        ),
        "account": (
            "👤 **My Account**\n\n"
            "🏅 `/badges` — My badges\n"
            "💾 `/favorites` — My favorites\n"
            "📊 `/genrestats` — Genre breakdown\n"
            "📜 `/history` — Recent songs\n"
            "🤝 `/invite` — Invite friends\n"
            "🎵 `/lastdownload` — Last song\n"
            "🏆 `/leaderboard` — Top users\n"
            "👤 `/mystats` — My stats\n"
            "📝 `/note [song] [text]` — Song note\n"
            "👤 `/profile` — My profile\n"
            "🗑 `/removefav [song]`\n"
            "⭐ `/save [song]`\n"
            "📤 `/share [song]` — Share card\n"
            "🔔 `/subscribe` — Daily song\n"
            "🔕 `/unsubscribe`\n"
            "🔥 `/streak` — My streak\n"
            "📋 `/wishlist [song]` — Wishlist\n"
            "📋 `/mywishlist` — View wishlist"
        ),
        "stats": (
            "📊 **Stats & Info**\n\n"
            "📊 `/activestats` — Most active users\n"
            "⏱ `/ping` — Server latency\n"
            "📤 `/share [song]` — Share card\n"
            "🎵 `/songstats [song]` — Song analytics\n"
            "📊 `/stats` — Bot stats\n"
            "📅 `/todaystats` — Today's stats\n"
            "⏰ `/uptime` — Bot uptime"
        )
    }
    text = texts.get(cat, "❌ Unknown category!")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="help_back")]])
    await cb.message.edit_text(text, reply_markup=keyboard)
    await cb.answer()

@app.on_callback_query(filters.regex(r"^help_back$"))
async def help_back(_, cb):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎵 Download & Search", callback_data="help_download"),
         InlineKeyboardButton("🌍 Discover", callback_data="help_discover")],
        [InlineKeyboardButton("🎮 Games & Fun", callback_data="help_games"),
         InlineKeyboardButton("👤 My Account", callback_data="help_account")],
        [InlineKeyboardButton("📊 Stats & Info", callback_data="help_stats")]
    ])
    await cb.message.edit_text(
        f"❓ **{BOT_NAME} Help Menu**\n\nChoose a category:",
        reply_markup=keyboard
    )
    await cb.answer()

@app.on_callback_query(filters.regex(r"^none$"))
async def none_cb(_, cb):
    await cb.answer()

# ========== COMMANDS A to Z ==========

# A

@app.on_message(filters.command("acoustic"))
async def acoustic(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Example: `/acoustic Tum Hi Ho`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"🎸 **Searching acoustic:** `{query}`...")
    results = []
    for q in [f"{query} acoustic", f"{query} unplugged", f"{query} acoustic version"]:
        results += search_jiosaavn_multiple(q, 3)
    seen, unique = set(), []
    for s in results:
        if s["name"] not in seen:
            seen.add(s["name"])
            unique.append(s)
    if not unique:
        await msg.edit(f"❌ No acoustic found!\n💡 Try: `/download {query} acoustic`")
        return
    text = f"🎸 **Acoustic/Unplugged: `{query}`**\n\n"
    for i, s in enumerate(unique[:6], 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

@app.on_message(filters.command("activestats"))
async def activestats(_, m: Message):
    users = db.get_all_users()
    if not users:
        await m.reply("❌ No data yet!")
        return
    text = "📊 **Most Active Users:**\n\n"
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    for i, u in enumerate(users[:5], 0):
        text += f"{medals[i]} **{u['name']}** — {u['downloads']} downloads\n"
    await m.reply(text)

@app.on_message(filters.command("ai_playlist"))
async def ai_playlist(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("🤖 **Choose activity:**\n`/ai_playlist gym` 💪\n`/ai_playlist study` 📚\n`/ai_playlist heartbreak` 💔\n`/ai_playlist sleep` 😴\n`/ai_playlist party` 🎉\n`/ai_playlist romantic` 💕\n`/ai_playlist morning` 🌅\n`/ai_playlist roadtrip` 🚗")
        return
    activity = parts[1].strip().lower()
    queries = {
        "gym": "workout gym motivation", "study": "study focus calm instrumental",
        "heartbreak": "heartbreak sad emotional hindi", "sleep": "sleep relaxing calm",
        "party": "party dance upbeat hindi", "romantic": "romantic love songs",
        "morning": "morning fresh motivational", "roadtrip": "roadtrip travel songs"
    }
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

@app.on_message(filters.command("albuminfo"))
async def albuminfo(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Example: `/albuminfo Divide`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"💿 **Fetching album info:** `{query}`...")
    results = search_jiosaavn_multiple(f"{query} album", 10)
    if not results:
        await msg.edit("❌ Album not found!")
        return
    album_name = results[0].get("album", {}).get("name", query)
    artist = results[0].get("primaryArtists", "Unknown")
    year = results[0].get("year", "Unknown")
    lang = results[0].get("language", "Unknown").capitalize()
    song_count = len(results)
    total_dur = sum(int(s.get("duration", 0)) for s in results)
    total_mins = total_dur // 60
    text = (
        f"💿 **{album_name}**\n\n"
        f"👤 **Artist:** {artist}\n"
        f"📅 **Year:** {year}\n"
        f"🌐 **Language:** {lang}\n"
        f"🎵 **Songs:** {song_count}+\n"
        f"⏱ **Total Duration:** ~{total_mins} mins\n\n"
        f"**Tracklist:**\n"
    )
    for i, s in enumerate(results[:10], 1):
        d = int(s["duration"])
        text += f"{i}. {s['name']} ({d//60}:{d%60:02d})\n"
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

@app.on_message(filters.command("artistinfo"))
async def artistinfo(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Example: `/artistinfo Arijit Singh`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"🎤 **Fetching artist info:** `{query}`...")
    results = search_jiosaavn_multiple(f"{query} songs", 10)
    if not results:
        await msg.edit("❌ Artist not found!")
        return
    artist_name = results[0].get("primaryArtists", query).split(",")[0].strip()
    years = [int(s.get("year", 0)) for s in results if s.get("year", "").isdigit()]
    since = min(years) if years else "Unknown"
    langs = list(set(s.get("language", "").capitalize() for s in results if s.get("language")))
    lang_str = " / ".join(langs[:3]) if langs else "Unknown"
    song_count = len(results)
    text = (
        f"🎤 **{artist_name}**\n\n"
        f"🎵 **Known Songs:** {song_count}+\n"
        f"🎸 **Genres:** Bollywood / {lang_str}\n"
        f"📅 **Active Since:** {since}\n"
        f"🌐 **Language:** {lang_str}\n\n"
        f"**Popular Songs:**\n"
    )
    for i, s in enumerate(results[:5], 1):
        text += f"{i}. {s['name']}\n"
    text += f"\n🎵 `/artist {query}` — See all songs"
    await msg.edit(text)

@app.on_message(filters.command("artistquiz"))
async def artistquiz(_, m: Message):
    msg = await m.reply("🎤 **Preparing Artist Quiz...**")
    chat_id = m.chat.id
    results = search_jiosaavn_multiple("popular bollywood songs", 20)
    if not results:
        await msg.edit("❌ Could not fetch!")
        return
    correct = random.choice(results)
    correct_song = correct["name"]
    correct_artist = correct["primaryArtists"].split(",")[0].strip()
    wrong_artists = list(set([s["primaryArtists"].split(",")[0].strip() for s in results if s["primaryArtists"].split(",")[0].strip() != correct_artist]))
    options = [correct_artist] + random.sample(wrong_artists, min(3, len(wrong_artists)))
    random.shuffle(options)
    labels = ["A", "B", "C", "D"]
    active_quiz[chat_id] = {"answer": correct_artist.lower(), "title": correct_song, "artist": correct_artist, "type": "artistquiz", "options": options}
    text = f"🎤 **Artist Quiz!**\n\n🎵 **Song:** {correct_song}\n\n❓ **Who sang this song?**\n\n"
    for i, opt in enumerate(options):
        text += f"**{labels[i]}.** {opt}\n"
    text += "\n💭 Reply A, B, C or D!\n⏱ 20 seconds!"
    await msg.edit(text)
    await asyncio.sleep(20)
    if chat_id in active_quiz and active_quiz[chat_id].get("type") == "artistquiz":
        del active_quiz[chat_id]
        idx = options.index(correct_artist) if correct_artist in options else 0
        await m.reply(f"⏱ **Time's up!**\nAnswer: **{labels[idx]}. {correct_artist}**")

# B

@app.on_message(filters.command("badges"))
async def badges(_, m: Message):
    user_id = m.from_user.id
    user = db.get_user(user_id) or {}
    downloads = user.get("downloads", 0)
    badge_list = get_badges(user_id)
    text = f"🏅 **{m.from_user.first_name}'s Badges:**\n\n"
    for b in badge_list:
        text += f"• {b}\n"
    text += f"\n📥 Downloads: {downloads} | Level: {get_level(downloads)}"
    await m.reply(text)

@app.on_message(filters.command("batch"))
async def batch(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await m.reply("📦 **Batch Download!**\n\nFormat:\n```\n/batch Tum Hi Ho\nKesariya\nBlinding Lights```\n\n⚠️ Max 5 songs!")
        return
    songs = [s.strip() for s in parts[1].strip().split("\n") if s.strip()][:5]
    if not songs:
        await m.reply("❌ Song names likho!")
        return
    await m.reply(f"📦 **Downloading {len(songs)} songs...**\n⚠️ Wait karo!")
    for i, song in enumerate(songs, 1):
        try:
            msg = await m.reply(f"⬇️ **{i}/{len(songs)}:** `{song}`...")
            await send_song(m, song, msg)
            await asyncio.sleep(2)
        except:
            await m.reply(f"❌ **{song}** failed!")

@app.on_message(filters.command("birthday"))
async def birthday(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Example: `/birthday Rahul`")
        return
    name = parts[1].strip()
    msg = await m.reply("🎂 **Fetching birthday songs...**")
    results = search_jiosaavn_multiple("birthday songs hindi english", 7)
    text = f"🎂 **Happy Birthday {name}!** 🎉\n\n🎵 **Songs:**\n\n"
    for i, s in enumerate(results, 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    text += f"\n🎊 Wishing **{name}** a wonderful birthday! 🎈🥳"
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🎵 Download Birthday Song", callback_data="dl_birthday")]])
    await msg.edit(text, reply_markup=keyboard)

# C

@app.on_message(filters.command("chain"))
async def chain(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Example: `/chain Tum Hi Ho`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"🔗 **Starting chain from:** `{query}`...")
    dl_url, title, duration, song_data = search_jiosaavn(query)
    if not song_data:
        await msg.edit("❌ Song not found!")
        return
    song_name = song_data["name"]
    last_letter = song_name[-1].upper()
    results = search_jiosaavn_multiple(f"songs starting with {last_letter} hindi", 10)
    filtered = [s for s in results if s["name"][0].upper() == last_letter and s["name"].lower() != song_name.lower()] or results[:5]
    text = f"🔗 **Song Chain:**\n\n🎵 **{song_name}** → Last letter: **{last_letter}**\n\n"
    text += f"🎵 **Next songs starting with '{last_letter}':**\n\n"
    for i, s in enumerate(filtered[:5], 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    if filtered:
        text += f"\n🔗 Continue: `/chain {filtered[0]['name']}`"
    await msg.edit(text)

@app.on_message(filters.command("challenge"))
async def challenge(_, m: Message):
    now = datetime.datetime.now()
    random.seed(now.day + now.month * 100 + now.year)
    results = search_jiosaavn_multiple("popular hindi songs", 20)
    if not results:
        await m.reply("❌ Could not fetch!")
        return
    song = random.choice(results)
    random.seed()
    title = song["name"]
    artist = song["primaryArtists"]
    lyrics_text, _ = get_lyrics(f"{title} - {artist}")
    if lyrics_text:
        lines = [l.strip() for l in lyrics_text.split("\n") if len(l.strip()) > 20]
        line = random.choice(lines[:10]) if lines else f"Hint: Artist is **{artist}**"
    else:
        line = f"Hint: Artist is **{artist}**"
    chat_id = m.chat.id
    active_quiz[chat_id] = {"answer": title.lower(), "title": title, "artist": artist, "type": "guess"}
    await m.reply(
        f"🎯 **Daily Challenge!**\n📅 {now.strftime('%d %b %Y')}\n\n"
        f"🎵 **Guess this song:**\n_{line}_\n\n"
        f"💭 Reply with song name!\n⏱ 30 seconds!\nUse `/skip` to skip."
    )
    await asyncio.sleep(30)
    if chat_id in active_quiz and active_quiz[chat_id].get("type") == "guess":
        del active_quiz[chat_id]
        await m.reply(f"⏱ **Time's up!**\nAnswer: **{title}** by {artist}")

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
        f"**1️⃣ {data1['name']}**\n👤 {data1['primaryArtists']}\n"
        f"💿 {data1.get('album',{}).get('name','Unknown')} | 📅 {data1.get('year','?')}\n"
        f"⏱ {d1//60}:{d1%60:02d}\n\n**VS**\n\n"
        f"**2️⃣ {data2['name']}**\n👤 {data2['primaryArtists']}\n"
        f"💿 {data2.get('album',{}).get('name','Unknown')} | 📅 {data2.get('year','?')}\n"
        f"⏱ {d2//60}:{d2%60:02d}\n\n"
        f"📥 `/download {data1['name']}` or `/download {data2['name']}`"
    )

@app.on_message(filters.command("cover"))
async def cover(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Example: `/cover Tum Hi Ho`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"🎤 **Searching covers:** `{query}`...")
    results = []
    for q in [f"{query} cover", f"{query} cover version", f"{query} covered by"]:
        results += search_jiosaavn_multiple(q, 3)
    seen, unique = set(), []
    for s in results:
        if s["name"] not in seen:
            seen.add(s["name"])
            unique.append(s)
    if not unique:
        await msg.edit(f"❌ No covers found!\n💡 Try: `/download {query} cover`")
        return
    text = f"🎤 **Covers of:** `{query}`\n\n"
    for i, s in enumerate(unique[:6], 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

# D

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

@app.on_message(filters.command("discography"))
async def discography(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Example: `/discography Arijit Singh`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"💿 **Fetching discography:** `{query}`...")
    results = []
    for q in [f"{query} songs", f"best of {query}", f"{query} hits"]:
        results += search_jiosaavn_multiple(q, 5)
    seen, unique = set(), []
    for s in results:
        if s["name"] not in seen:
            seen.add(s["name"])
            unique.append(s)
    if not unique:
        await msg.edit("❌ No songs found!")
        return
    text = f"💿 **{query}'s Discography ({len(unique)} songs):**\n\n"
    for i, s in enumerate(unique[:15], 1):
        d = int(s["duration"])
        text += f"{i}. **{s['name']}** | ⏱ {d//60}:{d%60:02d}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

@app.on_message(filters.command("download"))
async def download(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Song name likho!\nExample: `/download Tum Hi Ho`")
        return
    msg = await m.reply(f"🔍 **Searching:** `{parts[1].strip()}`...")
    await send_song(m, parts[1].strip(), msg)

@app.on_message(filters.command("duet"))
async def duet(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await m.reply("❌ Example: `/duet Arijit Singh Shreya Ghoshal`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"🎶 **Fetching duets:** `{query}`...")
    results = search_jiosaavn_multiple(f"{query} duet collab", 8)
    if not results:
        await msg.edit("❌ No results!")
        return
    text = f"🎶 **Duets/Collabs: {query}**\n\n"
    for i, s in enumerate(results, 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

# E

@app.on_message(filters.command("english"))
async def english(_, m: Message):
    msg = await m.reply("🔍 **Fetching English songs...**")
    results = search_jiosaavn_multiple("top english hits 2024", 8)
    text = "🎵 **Top English Songs:**\n\n"
    for i, s in enumerate(results, 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

# F

@app.on_message(filters.command("favorites"))
async def show_favorites(_, m: Message):
    user_id = m.from_user.id
    favs = db.get_favorites(user_id)
    if not favs:
        await m.reply("💾 No favorites yet!\nUse `/save [song]`")
        return
    text = "⭐ **Your Favorites:**\n\n"
    for i, s in enumerate(favs, 1):
        text += f"{i}. {s}\n"
    text += "\n📥 `/download [song name]`"
    await m.reply(text)

@app.on_message(filters.command("fillblank"))
async def fillblank(_, m: Message):
    msg = await m.reply("🎯 **Preparing Fill-in-the-Blank...**")
    chat_id = m.chat.id
    results = search_jiosaavn_multiple("popular hindi songs", 15)
    if not results:
        await msg.edit("❌ Could not fetch!")
        return
    song = random.choice(results)
    title, artist = song["name"], song["primaryArtists"]
    lyrics_text, _ = get_lyrics(f"{title} - {artist}")
    if not lyrics_text:
        await msg.edit("❌ Could not get lyrics! Try again.")
        return
    lines = [l.strip() for l in lyrics_text.split("\n") if len(l.strip()) > 25]
    if not lines:
        await msg.edit("❌ Could not get lyrics! Try again.")
        return
    line = random.choice(lines[:15])
    words = line.split()
    blank_idx = random.randint(1, len(words)-2)
    answer = words[blank_idx].lower().strip(",.!?")
    words[blank_idx] = "______"
    blanked_line = " ".join(words)
    active_quiz[chat_id] = {"answer": answer, "title": title, "artist": artist, "type": "fillblank"}
    await msg.edit(
        f"🎯 **Fill in the Blank!**\n\n"
        f"🎵 **Song:** {title}\n👤 **Artist:** {artist}\n\n"
        f"**Complete the lyric:**\n_{blanked_line}_\n\n"
        f"💭 Reply with the missing word!\n⏱ 20 seconds!\nUse `/skip` to skip."
    )
    await asyncio.sleep(20)
    if chat_id in active_quiz and active_quiz[chat_id].get("type") == "fillblank":
        del active_quiz[chat_id]
        await m.reply(f"⏱ **Time's up!**\nAnswer: **{answer}**\nSong: **{title}** by {artist}")

@app.on_message(filters.command("findlyrics"))
async def findlyrics(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Example: `/findlyrics tere bin nahi lagda`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"🔤 **Searching by lyrics:** `{query}`...")
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
            text = f"🔤 **Possible songs:**\n\n"
            for i, s in enumerate(results, 1):
                text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
            await msg.edit(text)
    except Exception as e:
        await msg.edit(f"❌ Error: `{str(e)}`")

# G

@app.on_message(filters.command("genre"))
async def genre(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("🎸 **Choose:**\n`/genre rock` `/genre pop` `/genre jazz`\n`/genre classical` `/genre rap` `/genre indie`\n`/genre sufi` `/genre folk`")
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

@app.on_message(filters.command("genrestats"))
async def genrestats(_, m: Message):
    user_id = m.from_user.id
    songs = db.get_history(user_id, 50)
    if not songs:
        await m.reply("❌ No history yet!\nDownload songs first.")
        return
    total = len(songs)
    hindi = sum(1 for s in songs if any(w in s.lower() for w in ["hindi","tum","dil","pyar","ishq","tera","mera","aaj"]))
    english = sum(1 for s in songs if any(w in s.lower() for w in ["love","baby","night","light","heart","you","my"]))
    punjabi = sum(1 for s in songs if any(w in s.lower() for w in ["punjabi","jatt","kudi","yaar","sohne"]))
    other = total - hindi - english - punjabi
    def pct(n): return f"{(n/total*100):.0f}%" if total > 0 else "0%"
    await m.reply(
        f"📊 **{m.from_user.first_name}'s Genre Breakdown:**\n\n"
        f"🇮🇳 Hindi: {hindi} songs ({pct(hindi)})\n"
        f"🌍 English: {english} songs ({pct(english)})\n"
        f"🎵 Punjabi: {punjabi} songs ({pct(punjabi)})\n"
        f"🎶 Other: {other} songs ({pct(other)})\n\n"
        f"📥 Total Downloads: {total}"
    )

@app.on_message(filters.command("guesssong"))
async def guesssong(_, m: Message):
    msg = await m.reply("🎯 **Fetching quiz song...**")
    chat_id = m.chat.id
    results = search_jiosaavn_multiple("popular hindi songs", 15)
    if not results:
        await msg.edit("❌ Could not fetch!")
        return
    song = random.choice(results)
    title, artist = song["name"], song["primaryArtists"]
    lyrics_text, _ = get_lyrics(f"{title} - {artist}")
    if lyrics_text:
        lines = [l.strip() for l in lyrics_text.split("\n") if len(l.strip()) > 20]
        line = random.choice(lines[:10]) if lines else f"Hint: Artist is **{artist}**"
    else:
        line = f"Hint: Artist is **{artist}**"
    active_quiz[chat_id] = {"answer": title.lower(), "title": title, "artist": artist, "type": "guess"}
    await msg.edit(
        f"🎯 **Guess The Song!**\n\n🎵 **Lyrics:**\n_{line}_\n\n"
        f"💭 Reply with song name!\n⏱ 30 seconds!\nUse `/skip` to skip."
    )
    await asyncio.sleep(30)
    if chat_id in active_quiz and active_quiz[chat_id].get("type") == "guess":
        del active_quiz[chat_id]
        await m.reply(f"⏱ **Time's up!**\nAnswer: **{title}** by {artist}")

# H

@app.on_message(filters.command("help"))
async def help_cmd(_, m: Message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎵 Download & Search", callback_data="help_download"),
         InlineKeyboardButton("🌍 Discover", callback_data="help_discover")],
        [InlineKeyboardButton("🎮 Games & Fun", callback_data="help_games"),
         InlineKeyboardButton("👤 My Account", callback_data="help_account")],
        [InlineKeyboardButton("📊 Stats & Info", callback_data="help_stats")]
    ])
    await m.reply(
        f"❓ **{BOT_NAME} Help Menu**\n\nChoose a category below 👇",
        reply_markup=keyboard
    )

@app.on_message(filters.command("hindi"))
async def hindi(_, m: Message):
    msg = await m.reply("🔍 **Fetching Hindi songs...**")
    results = search_jiosaavn_multiple("top hindi songs 2024", 8)
    text = "🇮🇳 **Top Hindi Songs:**\n\n"
    for i, s in enumerate(results, 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

@app.on_message(filters.command("history"))
async def show_history(_, m: Message):
    user_id = m.from_user.id
    songs = db.get_history(user_id)
    if not songs:
        await m.reply("📜 No history yet!")
        return
    text = "📜 **Recent Songs:**\n\n"
    for i, s in enumerate(songs, 1):
        text += f"{i}. {s}\n"
    await m.reply(text)

# I

@app.on_message(filters.command("info"))
async def song_info(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Example: `/info Tum Hi Ho`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"🔍 **Getting info:** `{query}`...")
    dl_url, title, duration, song_data = search_jiosaavn(query)
    if not song_data:
        await msg.edit("❌ Song not found!")
        return
    mins, secs = duration // 60, duration % 60
    g_stats = db.get_song_global_stats(song_data['name'])
    await msg.edit(
        f"ℹ️ **Song Info:**\n\n"
        f"🎵 **Title:** {song_data['name']}\n"
        f"👤 **Artist:** {song_data['primaryArtists']}\n"
        f"💿 **Album:** {song_data.get('album', {}).get('name', 'Unknown')}\n"
        f"📅 **Year:** {song_data.get('year', 'Unknown')}\n"
        f"🌐 **Language:** {song_data.get('language', 'Unknown').capitalize()}\n"
        f"⏱ **Duration:** {mins}:{secs:02d}\n"
        f"📥 **Bot Downloads:** {g_stats.get('downloads', 0)}\n\n"
        f"📥 `/download {song_data['name']}`"
    )

@app.on_message(filters.command("invite"))
async def invite(_, m: Message):
    user_id = m.from_user.id
    db.ensure_user(user_id, m.from_user.first_name)
    await m.reply(
        f"🤝 **Invite Friends to {BOT_NAME}!**\n\n"
        f"Share this bot with your friends:\n"
        f"👉 {BOT_USERNAME}\n\n"
        f"📊 **Your Invite Points:** 0\n\n"
        f"🏆 Top inviters appear on `/leaderboard`!\n\n"
        f"_Share the music, spread the love!_ 🎵"
    )

# K

@app.on_message(filters.command("karaoke"))
async def karaoke(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Example: `/karaoke Tum Hi Ho`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"🎼 **Searching karaoke/instrumental:** `{query}`...")
    results = []
    for q in [f"{query} karaoke", f"{query} instrumental", f"{query} without vocals", f"{query} music only"]:
        results += search_jiosaavn_multiple(q, 3)
    seen, unique = set(), []
    for s in results:
        if s["name"] not in seen:
            seen.add(s["name"])
            unique.append(s)
    if not unique:
        await msg.edit(f"❌ No karaoke found!\n💡 Try:\n📥 `/download {query} karaoke`\n📥 `/download {query} instrumental`")
        return
    text = f"🎼 **Karaoke/Instrumental: `{query}`**\n\n"
    for i, s in enumerate(unique[:6], 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

# L

@app.on_message(filters.command("lastdownload"))
async def lastdownload(_, m: Message):
    user_id = m.from_user.id
    s = db.get_last_downloaded(user_id)
    if not s:
        await m.reply("🎵 No song downloaded yet!")
        return
    await m.reply(f"🎵 **Last Downloaded:**\n\n🎶 **{s['title']}**\n⏱ {s['duration']} | 👤 {s['by_name']}\n\n📥 `/download {s['title']}`")

@app.on_message(filters.command("leaderboard"))
async def leaderboard(_, m: Message):
    users = db.get_all_users()
    if not users:
        await m.reply("❌ No data yet!")
        return
    text = "🏆 **Top Music Lovers:**\n\n"
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for i, u in enumerate(users[:10], 0):
        streak_text = f" 🔥{u['streak']}" if u.get("streak", 0) >= 3 else ""
        text += f"{medals[i]} **{u['name']}** — {u['downloads']} downloads{streak_text}\n"
    text += "\n📥 Download more to climb up! 🚀"
    await m.reply(text)

@app.on_message(filters.command("letter"))
async def letter(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await m.reply("❌ Example: `/letter T`")
        return
    l = parts[1].strip()[0].upper()
    if not l.isalpha():
        await m.reply("❌ Valid letter likho!")
        return
    msg = await m.reply(f"🔤 **Songs starting with:** `{l}`...")
    results = search_jiosaavn_multiple(f"songs starting with {l} hindi", 10)
    filtered = [s for s in results if s["name"].upper().startswith(l)] or results[:8]
    text = f"🔤 **Songs Starting with '{l}':**\n\n"
    for i, s in enumerate(filtered[:8], 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

@app.on_message(filters.command("lofi"))
async def lofi(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Example: `/lofi Tum Hi Ho`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"🎵 **Searching Lo-Fi:** `{query}`...")
    results = []
    for q in [f"{query} lofi", f"{query} lo-fi", f"{query} lofi remix", f"lofi {query}"]:
        results += search_jiosaavn_multiple(q, 3)
    seen, unique = set(), []
    for s in results:
        if s["name"] not in seen:
            seen.add(s["name"])
            unique.append(s)
    if not unique:
        await msg.edit(f"❌ No Lo-Fi found!\n💡 Try: `/download {query} lofi`")
        return
    text = f"🎵 **Lo-Fi versions of:** `{query}`\n\n"
    for i, s in enumerate(unique[:6], 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

@app.on_message(filters.command("lyrics"))
async def lyrics(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Format: `/lyrics Song - Artist`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"🔍 **Searching lyrics:** `{query}`...")
    lyrics_text, title = get_lyrics(query)
    if not lyrics_text:
        await msg.edit("❌ Lyrics not found!")
        return
    header = f"📝 **Lyrics: {title}**\n\n"
    full = header + lyrics_text
    if len(full) <= 4096:
        await msg.edit(full)
    else:
        await msg.edit(header + lyrics_text[:4000])
        remaining = lyrics_text[4000:]
        while remaining:
            await m.reply(remaining[:4096])
            remaining = remaining[4096:]

# M

@app.on_message(filters.command("mood"))
async def mood(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("🎭 **Choose mood:**\n`/mood happy` `/mood sad` `/mood party`\n`/mood romantic` `/mood workout` `/mood chill`")
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

@app.on_message(filters.command("musicquiz"))
async def musicquiz(_, m: Message):
    msg = await m.reply("🎮 **Preparing Music Quiz...**")
    chat_id = m.chat.id
    results = search_jiosaavn_multiple("popular bollywood songs", 20)
    if not results:
        await msg.edit("❌ Could not fetch!")
        return
    correct_song = random.choice(results)
    correct_title = correct_song["name"]
    correct_artist = correct_song["primaryArtists"]
    wrong_songs = [s for s in results if s["name"] != correct_title]
    wrong_options = random.sample(wrong_songs, min(3, len(wrong_songs)))
    options = [correct_title] + [s["name"] for s in wrong_options]
    random.shuffle(options)
    correct_idx = options.index(correct_title)
    labels = ["A", "B", "C", "D"]
    active_quiz[chat_id] = {"answer": correct_title.lower(), "title": correct_title, "artist": correct_artist, "type": "quiz", "options": options}
    text = f"🎮 **Music Quiz!**\n\n👤 **Artist:** {correct_artist}\n\n❓ **Which song is by this artist?**\n\n"
    for i, opt in enumerate(options):
        text += f"**{labels[i]}.** {opt}\n"
    text += "\n💭 Reply A, B, C or D!\n⏱ 20 seconds!"
    await msg.edit(text)
    await asyncio.sleep(20)
    if chat_id in active_quiz and active_quiz[chat_id].get("type") == "quiz":
        del active_quiz[chat_id]
        await m.reply(f"⏱ **Time's up!**\nAnswer: **{labels[correct_idx]}. {correct_title}** by {correct_artist}")

@app.on_message(filters.command("mystats"))
async def mystats(_, m: Message):
    user_id = m.from_user.id
    user = db.get_user(user_id)
    if not user or user["downloads"] == 0:
        await m.reply(f"👤 **{m.from_user.first_name}'s Stats:**\n\n📥 Downloads: 0\n\nStart downloading! 🎵")
        return
    songs = db.get_history(user_id, 50)
    most = max(set(songs), key=songs.count) if songs else "None"
    await m.reply(
        f"👤 **{m.from_user.first_name}'s Stats:**\n\n"
        f"📥 Downloads: {user['downloads']}\n"
        f"🎵 Most Downloaded: {most}\n"
        f"📜 History: {len(db.get_history(user_id))}\n"
        f"⭐ Favorites: {db.count_favorites(user_id)}\n"
        f"🔥 Streak: {user.get('streak', 0)} days\n"
        f"🎸 Fav Genre: {get_user_genre_from_history(user_id)}\n"
        f"🏅 Level: {get_level(user['downloads'])}"
    )

@app.on_message(filters.command("mywishlist"))
async def mywishlist(_, m: Message):
    user_id = m.from_user.id
    items = db.get_wishlist(user_id)
    if not items:
        await m.reply("📋 Wishlist empty!\nUse `/wishlist [song]` to add.")
        return
    text = "📋 **Your Wishlist:**\n\n"
    for i, s in enumerate(items, 1):
        text += f"{i}. {s}\n"
    text += "\n📥 `/download [song name]` to download!"
    await m.reply(text)

# N

@app.on_message(filters.command("newreleases"))
async def newreleases(_, m: Message):
    msg = await m.reply("🆕 **Fetching latest releases...**")
    results = []
    for q in ["new songs 2025", "latest hindi 2025", "new releases bollywood 2025"]:
        results += search_jiosaavn_multiple(q, 4)
    seen, unique = set(), []
    for s in results:
        if s["name"] not in seen:
            seen.add(s["name"])
            unique.append(s)
    if not unique:
        await msg.edit("❌ Could not fetch!")
        return
    text = "🆕 **Latest Releases:**\n\n"
    for i, s in enumerate(unique[:10], 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
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

@app.on_message(filters.command("note"))
async def note(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or "|" not in parts[1]:
        await m.reply("❌ Format: `/note Song Name | Your note`\nExample: `/note Tum Hi Ho | Best song ever!`")
        return
    song, note_text = parts[1].split("|", 1)
    song, note_text = song.strip(), note_text.strip()
    db.save_note(m.from_user.id, song, note_text)
    await m.reply(f"📝 **Note saved!**\n\n🎵 **{song}**\n💬 _{note_text}_")

# P

@app.on_message(filters.command("ping"))
async def ping(_, m: Message):
    start = datetime.datetime.now()
    msg = await m.reply("🏓 **Pinging...**")
    end = datetime.datetime.now()
    latency = (end - start).microseconds // 1000
    await msg.edit(f"🏓 **Pong!**\n\n⚡ Latency: **{latency}ms**\n🤖 Bot: {BOT_NAME}\n✅ Status: Online")

@app.on_message(filters.command("play"))
async def play_cs(_, m: Message):
    await m.reply("🔜 **Coming Soon!**\n\nUse 📥 `/download [song]` for now!")

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
    await m.reply(f"🎵 **{mood_type.capitalize()} Playlist** {emojis[mood_type]}\nDownloading {len(results)} songs...\n⚠️ Few minutes!")
    for s in results:
        try:
            msg = await m.reply(f"⬇️ `{s['name']}`...")
            await send_song(m, s["name"], msg)
            await asyncio.sleep(2)
        except: pass

@app.on_message(filters.command("preview"))
async def preview(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Example: `/preview Tum Hi Ho`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"🎵 **Fetching preview:** `{query}`...")
    try:
        url = f"https://jiosaavn-api-privatecvc2.vercel.app/search/songs?query={query}&page=1&limit=1"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        results = r.json()["data"]["results"]
        if not results:
            await msg.edit("❌ Song not found!")
            return
        song = results[0]
        preview_url = song.get("previewUrl") or song["downloadUrl"][0]["link"]
        title, artist = song["name"], song["primaryArtists"]
        await msg.edit(f"⬇️ **Downloading preview:** `{title}`...")
        path = download_song(preview_url, f"preview_{title}")
        await app.send_audio(m.chat.id, path, caption=f"🎵 **Preview:** {title} - {artist}", title=f"Preview - {title}")
        await msg.delete()
        try: os.remove(path)
        except: pass
    except Exception as e:
        await msg.edit(f"❌ Error: `{str(e)}`")

@app.on_message(filters.command("profile"))
async def profile(_, m: Message):
    user_id = m.from_user.id
    db.ensure_user(user_id, m.from_user.first_name)
    user = db.get_user(user_id)
    downloads = user["downloads"]
    songs = db.get_history(user_id, 50)
    most = max(set(songs), key=songs.count) if songs else "None"
    badge_list = get_badges(user_id)
    await m.reply(
        f"👤 **{m.from_user.first_name}'s Profile**\n\n"
        f"📅 Since: {user.get('joined', 'Unknown')}\n"
        f"📥 Downloads: {downloads}\n"
        f"🎵 Top Song: {most}\n"
        f"🎸 Genre: {get_user_genre_from_history(user_id)}\n"
        f"⭐ Favorites: {db.count_favorites(user_id)}\n"
        f"📜 History: {len(db.get_history(user_id))}\n"
        f"🔥 Streak: {user.get('streak', 0)} days\n"
        f"🔔 Subscribed: {'Yes ✅' if db.is_subscribed(user_id) else 'No ❌'}\n"
        f"🏅 Level: {get_level(downloads)}\n\n"
        f"**Badges:** {' '.join(badge_list[:3])}"
    )

@app.on_message(filters.command("punjabi"))
async def punjabi(_, m: Message):
    msg = await m.reply("🔍 **Fetching Punjabi songs...**")
    results = search_jiosaavn_multiple("top punjabi songs 2024", 8)
    text = "🎵 **Top Punjabi Songs:**\n\n"
    for i, s in enumerate(results, 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

# Q

@app.on_message(filters.command("quality"))
async def quality_select(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Example: `/quality Tum Hi Ho`")
        return
    song = parts[1].strip()
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🎵 128 kbps", callback_data=f"qual_128_{song[:30]}"),
        InlineKeyboardButton("🎵 192 kbps", callback_data=f"qual_192_{song[:30]}"),
        InlineKeyboardButton("🎵 320 kbps", callback_data=f"qual_320_{song[:30]}"),
    ]])
    await m.reply(f"🎧 **Select Quality:**\n`{song}`\n\n128kbps — Saves data 📶\n192kbps — Balanced ⚖️\n320kbps — Best quality 🎵", reply_markup=keyboard)

@app.on_message(filters.command("quote"))
async def quote(_, m: Message):
    msg = await m.reply("💬 **Fetching quote...**")
    await msg.edit(f"💬 **Music Quote:**\n\n{fetch_quote()}")

# R

@app.on_message(filters.command("random"))
async def random_song(_, m: Message):
    keywords = ["hindi popular 2024", "bollywood hits", "top songs india", "english hits", "punjabi popular", "romantic songs", "party songs hindi"]
    msg = await m.reply("🎲 **Fetching random song...**")
    results = search_jiosaavn_multiple(random.choice(keywords), 20)
    if not results:
        await msg.edit("❌ No songs found!")
        return
    await send_song(m, random.choice(results)["name"], msg)

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

@app.on_message(filters.command("regional"))
async def regional(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("🌍 **Choose:**\n`/regional marathi` `/regional tamil` `/regional telugu`\n`/regional bhojpuri` `/regional bengali` `/regional gujarati`\n`/regional kannada` `/regional malayalam`")
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

@app.on_message(filters.command("remix"))
async def remix(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Example: `/remix Husn`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"🎛 **Searching remixes:** `{query}`...")
    results = []
    for q in [f"{query} remix", f"{query} dj remix", f"{query} club remix"]:
        results += search_jiosaavn_multiple(q, 3)
    seen, unique = set(), []
    for s in results:
        if s["name"] not in seen:
            seen.add(s["name"])
            unique.append(s)
    if not unique:
        await msg.edit(f"❌ No remixes found!\n💡 Try: `/download {query} remix`")
        return
    text = f"🎛 **Remixes of:** `{query}`\n\n"
    for i, s in enumerate(unique[:6], 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

@app.on_message(filters.command("removefav"))
async def removefav(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Example: `/removefav Tum Hi Ho`")
        return
    query = parts[1].strip()
    if db.remove_favorite(m.from_user.id, query):
        await m.reply(f"🗑 **Removed:** `{query}`")
    else:
        await m.reply("❌ Not in favorites!")

# S

@app.on_message(filters.command("save"))
async def save(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Example: `/save Tum Hi Ho`")
        return
    query = parts[1].strip()
    user_id = m.from_user.id
    db.ensure_user(user_id, m.from_user.first_name)
    if db.is_favorite(user_id, query):
        await m.reply("⭐ Already in favorites!")
        return
    if db.count_favorites(user_id) >= 20:
        await m.reply("❌ Favorites full! Max 20.")
        return
    db.add_favorite(user_id, query)
    db.increment_song_favorites(query)
    await m.reply(f"⭐ **Saved:** `{query}`")

@app.on_message(filters.command("search"))
async def search(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Example: `/search Arijit Singh`")
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
    text += "📥 `/download [song name]`"
    await msg.edit(text)

@app.on_message(filters.command("share"))
async def share(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Example: `/share Tum Hi Ho`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"📤 **Creating share card...**")
    dl_url, title, duration, song_data = search_jiosaavn(query)
    if not song_data:
        await msg.edit("❌ Song not found!")
        return
    mins, secs = duration // 60, duration % 60
    g_stats = db.get_song_global_stats(song_data['name'])
    avg_rating, _ = db.get_avg_rating(song_data['name'][:25])
    share_text = (
        f"🎵 **{song_data['name']}**\n"
        f"👤 Artist: {song_data['primaryArtists']}\n"
        f"💿 Album: {song_data.get('album',{}).get('name','Unknown')}\n"
        f"⏱ Duration: {mins}:{secs:02d}\n"
        f"📅 Year: {song_data.get('year','Unknown')}\n"
        f"⭐ Rating: {avg_rating:.1f}/5\n\n"
        f"🎧 Download from **{BOT_NAME}**\n"
        f"👉 {BOT_USERNAME}"
    )
    await msg.edit(share_text)

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
    try:
        sr = requests.get(f"https://jiosaavn-api-privatecvc2.vercel.app/songs/{song_data['id']}/suggestions", headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        similar_list = sr.json().get("data", [])
    except:
        similar_list = []
    if not similar_list:
        similar_list = search_jiosaavn_multiple(f"{song_data['primaryArtists'].split(',')[0]} songs", 6)
        text = f"🎵 **Similar to** `{query}`:\n\n"
        for i, s in enumerate(similar_list, 1):
            text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    else:
        text = f"🎵 **Similar to** `{query}`:\n\n"
        for i, s in enumerate(similar_list[:8], 1):
            text += f"{i}. **{s.get('name','Unknown')}** - {s.get('primaryArtists','Unknown')}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

@app.on_message(filters.command("similarartist"))
async def similarartist(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Example: `/similarartist Arijit Singh`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"🎤 **Finding similar artists...**")
    results = search_jiosaavn_multiple(f"artists like {query}", 8)
    if not results:
        await msg.edit("❌ No results!")
        return
    artists = list(dict.fromkeys([s["primaryArtists"].split(",")[0].strip() for s in results]))
    artists = [a for a in artists if a.lower() != query.lower()][:6]
    text = f"🎤 **Artists Similar to {query}:**\n\n"
    for i, a in enumerate(artists, 1):
        text += f"{i}. **{a}**\n"
    text += f"\n🎵 Use `/artist [name]` to see their songs!"
    await msg.edit(text)

@app.on_message(filters.command("skip"))
async def skip(_, m: Message):
    chat_id = m.chat.id
    if chat_id not in active_quiz:
        await m.reply("❌ No active quiz!")
        return
    quiz = active_quiz.pop(chat_id)
    await m.reply(f"⏭ **Skipped!**\nAnswer: **{quiz['title']}** by {quiz['artist']}")

@app.on_message(filters.command("songstats"))
async def songstats(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Example: `/songstats Husn`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"📊 **Fetching stats:** `{query}`...")
    dl_url, title, duration, song_data = search_jiosaavn(query)
    if not song_data:
        await msg.edit("❌ Song not found!")
        return
    song_name = song_data['name']
    g_stats = db.get_song_global_stats(song_name)
    avg_rating, vote_count = db.get_avg_rating(song_name[:25])
    await msg.edit(
        f"📊 **{song_name}**\n\n"
        f"👤 {song_data['primaryArtists']}\n"
        f"💿 {song_data.get('album',{}).get('name','Unknown')} | 📅 {song_data.get('year','Unknown')}\n\n"
        f"📥 **Bot Downloads:** {g_stats['downloads']}\n"
        f"⭐ **Favorites:** {g_stats['favorites']}\n"
        f"🌟 **Rating:** {'⭐ ' + f'{avg_rating:.1f}/5 ({vote_count} votes)' if vote_count > 0 else 'Not rated yet'}\n\n"
        f"📥 `/download {song_name}`"
    )

@app.on_message(filters.command("start"))
async def start(_, m: Message):
    user_id = m.from_user.id
    db.ensure_user(user_id, m.from_user.first_name)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎵 Download & Search", callback_data="help_download"),
         InlineKeyboardButton("🌍 Discover", callback_data="help_discover")],
        [InlineKeyboardButton("🎮 Games & Fun", callback_data="help_games"),
         InlineKeyboardButton("👤 My Account", callback_data="help_account")],
        [InlineKeyboardButton("📊 Stats & Info", callback_data="help_stats")]
    ])
    await m.reply(
        f"🎵 **Welcome to {BOT_NAME}!**\n"
        f"Hello {m.from_user.first_name}! 👋\n\n"
        f"🤖 Your ultimate music companion!\n"
        f"Search, download, discover & play!\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🚀 **Quick Start:**\n"
        f"📥 `/download Tum Hi Ho`\n"
        f"🔍 `/search Arijit Singh`\n"
        f"🎭 `/mood happy`\n"
        f"🌍 `/trending`\n"
        f"🎮 `/guesssong`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 **Browse all commands below** 👇\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⚠️ **Bug/Issue?** Contact: {DEVELOPER}",
        reply_markup=keyboard
    )

@app.on_message(filters.command("stats"))
async def bot_stats(_, m: Message):
    update_today_stats()
    uptime = datetime.datetime.now() - START_TIME
    hours = int(uptime.total_seconds() // 3600)
    mins = int((uptime.total_seconds() % 3600) // 60)
    await m.reply(
        f"📊 **{BOT_NAME} Statistics:**\n\n"
        f"👥 Total Users: {db.get_total_users()}\n"
        f"📥 Total Downloads: {db.get_total_downloads()}\n"
        f"📅 Today's Downloads: {today_downloads['count']}\n"
        f"⭐ Rated Songs: {db.get_total_users()}\n"
        f"🔔 Subscribers: {len(db.get_subscribers())}\n"
        f"⏰ Uptime: {hours}h {mins}m\n"
        f"🎵 Database: JioSaavn\n\n"
        f"🔜 Voice Chat: Coming Soon!\n"
        f"⚠️ Issues? Contact: {DEVELOPER}"
    )

@app.on_message(filters.command("streak"))
async def streak(_, m: Message):
    user_id = m.from_user.id
    u = db.get_user(user_id)
    current_streak = u['streak'] if u else 0
    if current_streak == 0:
        await m.reply(f"🔥 **Streak: 0 days**\n\nDownload a song today to start your streak!")
        return
    if current_streak >= 30: emoji = "👑"
    elif current_streak >= 7: emoji = "⚡"
    elif current_streak >= 3: emoji = "🔥"
    else: emoji = "✨"
    await m.reply(
        f"{emoji} **{m.from_user.first_name}'s Streak:**\n\n"
        f"🔥 **{current_streak} day streak!**\n\n"
        f"{'👑 Legendary streak!' if current_streak >= 30 else '⚡ Week streak! Amazing!' if current_streak >= 7 else '🔥 3 days! Keep going!' if current_streak >= 3 else '✨ Good start! Keep going!'}\n\n"
        f"📥 Download daily to keep it going!"
    )

@app.on_message(filters.command("subscribe"))
async def subscribe(_, m: Message):
    user_id = m.from_user.id
    if db.is_subscribed(user_id):
        await m.reply("🔔 Already subscribed!\nUse `/unsubscribe` to stop.")
        return
    db.ensure_user(user_id, m.from_user.first_name)
    db.set_subscribed(user_id, True)
    await m.reply("🔔 **Subscribed!**\n\nYou'll receive a daily song every morning at 9 AM!\nUse `/unsubscribe` to stop anytime.")

# T

@app.on_message(filters.command("todaystats"))
async def todaystats(_, m: Message):
    update_today_stats()
    await m.reply(
        f"📅 **Today's Stats:**\n\n"
        f"📥 Downloads Today: {stats['today_downloads']}\n"
        f"👥 Total Users: {len(stats['users'])}\n"
        f"📊 Date: {datetime.date.today().strftime('%d %b %Y')}"
    )

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

@app.on_message(filters.command("topbollywood"))
async def topbollywood(_, m: Message):
    msg = await m.reply("🎬 **Fetching Top Bollywood...**")
    results = search_jiosaavn_multiple("top bollywood hits 2024", 5)
    results += search_jiosaavn_multiple("best bollywood songs popular", 5)
    seen, unique = set(), []
    for s in results:
        if s["name"] not in seen:
            seen.add(s["name"])
            unique.append(s)
    text = "🎬 **Top Bollywood Songs:**\n\n"
    for i, s in enumerate(unique[:10], 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

@app.on_message(filters.command("topindia"))
async def topindia(_, m: Message):
    msg = await m.reply("🇮🇳 **Fetching Top India...**")
    results = search_jiosaavn_multiple("hindi hits popular 2024", 5)
    results += search_jiosaavn_multiple("trending bollywood 2024", 5)
    seen, unique = set(), []
    for s in results:
        if s["name"] not in seen:
            seen.add(s["name"])
            unique.append(s)
    text = "🇮🇳 **Top Songs in India:**\n\n"
    for i, s in enumerate(unique[:10], 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

@app.on_message(filters.command("topsongs"))
async def topsongs(_, m: Message):
    top = db.get_top_rated_songs()
    if not top:
        await m.reply("❌ No rated songs yet!\nUse `/rate [song]`")
        return
    text = "🏆 **Top Rated Songs:**\n\n"
    for i, row in enumerate(top, 1):
        text += f"{i}. **{row['song']}** — ⭐ {row['avg_r']:.1f}/5 ({row['cnt']} votes)\n"
    await m.reply(text)

@app.on_message(filters.command("top2025"))
async def top2025(_, m: Message):
    msg = await m.reply("🔥 **Fetching Top 2025...**")
    results = search_jiosaavn_multiple("top hits 2025 new songs", 5)
    results += search_jiosaavn_multiple("new 2025 bollywood songs", 5)
    seen, unique = set(), []
    for s in results:
        if s["name"] not in seen:
            seen.add(s["name"])
            unique.append(s)
    text = "🔥 **Top Songs of 2025:**\n\n"
    for i, s in enumerate(unique[:10], 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

@app.on_message(filters.command("tournament"))
async def tournament(_, m: Message):
    msg = await m.reply("🏆 **Setting up Tournament...**")
    results = search_jiosaavn_multiple("popular hindi songs hits", 8)
    if len(results) < 4:
        await msg.edit("❌ Could not fetch songs!")
        return
    songs = [s["name"] for s in results[:8]]
    text = "🏆 **Song Tournament!**\n\n"
    text += "**🎵 Today's Contestants:**\n\n"
    for i, s in enumerate(songs, 1):
        text += f"{i}. {s}\n"
    text += "\n**Vote:** Reply with the number of your favourite song!\n"
    text += f"Who should win? 🎵"
    await msg.edit(text)

@app.on_message(filters.command("trendingartist"))
async def trendingartist(_, m: Message):
    msg = await m.reply("🔥 **Fetching Trending Artists...**")
    results = []
    for q in ["trending hindi 2024", "popular bollywood 2024", "viral songs 2024", "top india 2024"]:
        results += search_jiosaavn_multiple(q, 5)
    artists = []
    seen_artists = set()
    for s in results:
        for a in s.get("primaryArtists", "").split(","):
            a = a.strip()
            if a and a not in seen_artists:
                seen_artists.add(a)
                artists.append(a)
    if not artists:
        await msg.edit("❌ Could not fetch!")
        return
    text = "🔥 **Trending Artists:**\n\n"
    for i, a in enumerate(artists[:10], 1):
        text += f"{i}. **{a}**\n"
    text += f"\n🎵 Use `/artist [name]` to see their songs!"
    await msg.edit(text)

@app.on_message(filters.command("trending"))
async def trending(_, m: Message):
    msg = await m.reply("🌍 **Fetching trending...**")
    results = search_jiosaavn_multiple("trending india 2024 top hits", 5)
    results += search_jiosaavn_multiple("viral hindi songs 2024", 5)
    seen, unique = set(), []
    for s in results:
        if s["name"] not in seen:
            seen.add(s["name"])
            unique.append(s)
    if not unique:
        await msg.edit("❌ Could not fetch!")
        return
    text = "🌍 **Trending Right Now:**\n\n"
    for i, s in enumerate(unique[:10], 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

# U

@app.on_message(filters.command("unsubscribe"))
async def unsubscribe(_, m: Message):
    user_id = m.from_user.id
    if not db.is_subscribed(user_id):
        await m.reply("❌ Not subscribed!\nUse `/subscribe` to start.")
        return
    db.set_subscribed(user_id, False)
    await m.reply("🔕 **Unsubscribed!**\nYou won't receive daily songs anymore.")

@app.on_message(filters.command("uptime"))
async def uptime(_, m: Message):
    uptime_delta = datetime.datetime.now() - START_TIME
    total_seconds = int(uptime_delta.total_seconds())
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    mins = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    await m.reply(
        f"⏰ **{BOT_NAME} Uptime:**\n\n"
        f"🕐 **{days}d {hours}h {mins}m {secs}s**\n\n"
        f"✅ Status: Online\n"
        f"🎵 Database: JioSaavn\n"
        f"🤖 Bot: {BOT_USERNAME}"
    )

# V

@app.on_message(filters.command("vibe"))
async def vibe(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Example: `/vibe Tum Hi Ho`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"🎭 **Analyzing vibe:** `{query}`...")
    dl_url, title, duration, song_data = search_jiosaavn(query)
    if not song_data:
        await msg.edit("❌ Song not found!")
        return
    name = song_data.get("name", "").lower()
    mins, secs = duration // 60, duration % 60
    if any(k in name for k in ["sad","dard","judai","alvida","rona","toota","bekhayali","tanha"]):
        vibe_r, desc = "😢 Sad / Emotional", "Perfect for heartfelt moments."
    elif any(k in name for k in ["love","ishq","pyar","mohabbat","dil","kesariya","raataan","tera"]):
        vibe_r, desc = "💕 Romantic", "Perfect for love and special moments."
    elif any(k in name for k in ["happy","khushi","dance","party","gallan","badtameez"]):
        vibe_r, desc = "😊 Happy / Upbeat", "Perfect for cheerful moments!"
    elif any(k in name for k in ["power","fire","thunder","believer","warrior"]):
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

# W

@app.on_message(filters.command("wishlist"))
async def wishlist(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Example: `/wishlist Tum Hi Ho`\nView: `/mywishlist`")
        return
    query = parts[1].strip()
    user_id = m.from_user.id
    db.ensure_user(user_id, m.from_user.first_name)
    if not db.add_wishlist(user_id, query):
        await m.reply("📋 Already in wishlist!")
        return
    await m.reply(f"📋 **Added to Wishlist:** `{query}`\n\nView: `/mywishlist`\nDownload: `/download {query}`")

# Y

@app.on_message(filters.command("year"))
async def year_cmd(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await m.reply("❌ Example: `/year 2000`")
        return
    year = parts[1].strip()
    if not year.isdigit() or not (1990 <= int(year) <= 2025):
        await m.reply("❌ Valid year likho (1990-2025)!\nExample: `/year 2005`")
        return
    msg = await m.reply(f"📅 **Fetching songs from {year}...**")
    results = search_jiosaavn_multiple(f"hindi songs {year} hits", 8)
    if not results:
        await msg.edit("❌ No songs found!")
        return
    text = f"📅 **Songs from {year}:**\n\n"
    for i, s in enumerate(results, 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

@app.on_message(filters.command("yeargame"))
async def yeargame(_, m: Message):
    msg = await m.reply("📅 **Preparing Year Game...**")
    chat_id = m.chat.id
    results = search_jiosaavn_multiple("popular hindi songs hits", 15)
    songs_with_year = [s for s in results if s.get("year", "").isdigit()]
    if not songs_with_year:
        await msg.edit("❌ Could not fetch! Try again.")
        return
    song = random.choice(songs_with_year)
    title = song["name"]
    artist = song["primaryArtists"]
    correct_year = song["year"]
    active_quiz[chat_id] = {"answer": correct_year, "title": title, "artist": artist, "type": "yeargame"}
    await msg.edit(
        f"📅 **Year Guess Game!**\n\n"
        f"🎵 **Song:** {title}\n"
        f"👤 **Artist:** {artist}\n\n"
        f"❓ **Which year was this released?**\n\n"
        f"💭 Reply with the year!\n⏱ 20 seconds!\nUse `/skip` to skip."
    )
    await asyncio.sleep(20)
    if chat_id in active_quiz and active_quiz[chat_id].get("type") == "yeargame":
        del active_quiz[chat_id]
        await m.reply(f"⏱ **Time's up!**\nAnswer: **{correct_year}**\nSong: **{title}** by {artist}")

# ========== QUIZ CHECK (always last) ==========

@app.on_message(filters.text & ~filters.regex(r"^/"))
async def quiz_check(_, m: Message):
    chat_id = m.chat.id
    if chat_id not in active_quiz:
        return
    quiz = active_quiz[chat_id]
    user_ans = m.text.strip().lower()
    correct = quiz["answer"].lower()
    quiz_type = quiz.get("type", "guess")

    if quiz_type in ("quiz", "artistquiz"):
        option_map = {"a": 0, "b": 1, "c": 2, "d": 3}
        if user_ans in option_map:
            selected = quiz["options"][option_map[user_ans]]
            if selected.lower() == correct:
                del active_quiz[chat_id]
                await m.reply(f"✅ **Correct! {m.from_user.first_name}!** 🎉\n🎵 **{quiz['title']}** by {quiz['artist']}\n\n📥 `/download {quiz['title']}`")
            else:
                await m.reply(f"❌ **Wrong!** Try again!\n💡 Hint: Starts with **{quiz['title'][0]}**")

    elif quiz_type == "fillblank":
        if user_ans == correct or correct in user_ans:
            del active_quiz[chat_id]
            await m.reply(f"✅ **Correct! {m.from_user.first_name}!** 🎉\nThe word was: **{correct}**\n🎵 **{quiz['title']}** by {quiz['artist']}")
        else:
            await m.reply(f"❌ **Wrong!** Try again!\n💡 Hint: Starts with **{correct[0]}**")

    elif quiz_type == "yeargame":
        if user_ans == correct or user_ans in correct:
            del active_quiz[chat_id]
            await m.reply(f"✅ **Correct! {m.from_user.first_name}!** 🎉\nYear: **{correct}**\n🎵 **{quiz['title']}** by {quiz['artist']}")
        else:
            try:
                diff = abs(int(user_ans) - int(correct))
                hint = "🔥 Very close!" if diff <= 2 else "📅 Try again!"
                await m.reply(f"❌ **Wrong!** {hint}")
            except:
                await m.reply("❌ **Wrong!** Reply with a year number.")

    else:  # guess
        if any(w in user_ans for w in correct.split() if len(w) > 3):
            del active_quiz[chat_id]
            await m.reply(f"✅ **Correct! {m.from_user.first_name}!** 🎉\n🎵 **{quiz['title']}** by {quiz['artist']}\n\n📥 `/download {quiz['title']}`")

# ========== DAILY SONG TASK ==========

async def send_daily_songs():
    while True:
        now = datetime.datetime.now()
        if now.hour == 9 and now.minute == 0:
            subs = db.get_subscribers()
            if subs:
                results = search_jiosaavn_multiple("popular hindi songs 2024", 20)
                if results:
                    song = random.choice(results)
                    for user_id in subs:
                        try:
                            msg_obj = await app.send_message(user_id,
                                f"🔔 **Good Morning! Daily Song from {BOT_NAME}:**\n\n"
                                f"🎵 `{song['name']}`\n\n⬇️ Downloading...")
                            await send_song(msg_obj, song["name"], msg_obj)
                        except: pass
        await asyncio.sleep(60)

async def main():
    await app.start()
    db.init_db()
    print(f"✅ {BOT_NAME} started!")
    asyncio.create_task(send_daily_songs())
    await asyncio.Event().wait()

app.run(main())
