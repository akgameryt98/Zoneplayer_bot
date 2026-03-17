import asyncio
import os
import requests
import random
import datetime
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from config import API_ID, API_HASH, BOT_TOKEN
import database as db
import apis

# ========== USERBOT + PYTGCALLS SETUP ==========

import yt_dlp

USER_STRING = os.environ.get("USER_STRING_SESSION", "")
USER_API_ID = int(os.environ.get("USER_API_ID", 0))
USER_API_HASH = os.environ.get("USER_API_HASH", "")

# Userbot client

# PyTgCalls instance
pytgcalls = None  # Will be initialized in main()



app = Client("beatnova_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

BOT_NAME = "BeatNova"
BOT_USERNAME = "@SHADE_SONG_BOT"
DEVELOPER = "@ZeroShader"
START_TIME = datetime.datetime.now()

active_quiz = {}
group_votes = {}
today_downloads = {"count": 0, "date": datetime.date.today()}


PLACEHOLDERS = ["[song]", "[song name]", "[name]", "[artist]", "[line]", "[mood]", "[type]", "[a-z]"]

MUSIC_FACTS = [
    "🎵 The longest officially released song is over 13 hours long!",
    "🎵 'Happy Birthday to You' was the first song played in space!",
    "🎵 A person's heartbeat syncs to the music they listen to!",
    "🎵 Music can boost workout performance by up to 15%!",
    "🎵 The guitar is the most played instrument in the world!",
    "🎵 Mozart could memorize and write out an entire piece after hearing it once!",
    "🎵 Listening to music releases dopamine — same as chocolate!",
    "🎵 'Bohemian Rhapsody' took 3 weeks to record in 1975!",
    "🎵 India has the world's largest film music industry!",
    "🎵 Arijit Singh has sung over 300 Bollywood songs!",
]

EASTER_EGGS = [
    "🥚 You found an easter egg! Here's a secret: The bot's name BeatNova comes from 'Beat' (music) + 'Nova' (star) ⭐",
    "🎩 Secret unlocked! Did you know @ZeroShader built this bot from scratch? Legends do exist! 👑",
    "🔮 Hidden message: The music never stops if you never stop listening! 🎵",
    "🤫 Psst! Try /party in a group for a surprise! 🎉",
    "🥚 Easter Egg #2: BeatNova processes thousands of songs... and hasn't complained once! 😄",
]



XP_REWARDS = {
    "download": 10,
    "first_download": 50,
    "daily_reward": 25,
    "rate_song": 5,
    "streak_3": 20,
    "streak_7": 50,
    "quiz_win": 30,
}

# ========== HELPERS ==========

def update_today_stats():
    today = datetime.date.today()
    if today_downloads["date"] != today:
        today_downloads["count"] = 0
        today_downloads["date"] = today

def get_xp_bar(xp):
    xp_in_level = xp % 100
    filled = xp_in_level // 10
    bar = "█" * filled + "░" * (10 - filled)
    return f"{bar} {xp_in_level}/100 XP"

def get_level_title(level):
    titles = {1: "🌱 Newbie", 2: "🎵 Listener", 3: "🎧 Music Fan",
              4: "🎸 Music Lover", 5: "🏆 Music Expert",
              6: "💎 Music Master", 7: "👑 Music Legend", 8: "🌟 BeatNova Star"}
    return titles.get(level, f"🔥 Level {level} Pro")

def get_badges(user_id):
    user = db.get_user(user_id) or {}
    downloads = user.get("downloads", 0)
    streak = user.get("streak", 0)
    favs = db.count_favorites(user_id)
    rated = db.user_rated_count(user_id)
    badges = []
    if downloads >= 1: badges.append("🎵 First Download")
    if downloads >= 10: badges.append("🎧 Music Fan")
    if downloads >= 50: badges.append("🎸 Music Lover")
    if downloads >= 100: badges.append("🥇 Music Master")
    if downloads >= 200: badges.append("💎 Legend")
    if downloads >= 500: badges.append("👑 BeatNova Star")
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

def _normalize_song(s):
    """Normalize song dict to consistent format"""
    if not s: return None
    return {
        "name": s.get("name", "Unknown"),
        "primaryArtists": s.get("artist", s.get("primaryArtists", "Unknown")),
        "artist": s.get("artist", s.get("primaryArtists", "Unknown")),
        "album": s.get("album", "Unknown"),  # always string now
        "year": s.get("year", "Unknown"),
        "duration": s.get("duration", 0),
        "language": s.get("language", "Unknown"),
        "download_url": s.get("download_url", ""),
        "id": s.get("id", ""),
        "source": s.get("source", ""),
        "quality": s.get("quality", "320kbps"),
    }

def search_jiosaavn(query):
    """Legacy wrapper - uses apis.py"""
    results = apis.search_songs(query, 10)
    if not results: return None, None, None, None
    s = _normalize_song(results[0])
    title = f"{s['name']} - {s['primaryArtists']}"
    return s.get("download_url"), title, s.get("duration", 0), s

def search_jiosaavn_quality(query, quality="320"):
    """Legacy wrapper - uses apis.py"""
    s = apis.search_song_download(query, quality)
    if not s: return None, None, None, None
    s = _normalize_song(s)
    title = f"{s['name']} - {s['primaryArtists']}"
    return s.get("download_url"), title, s.get("duration", 0), s

def search_jiosaavn_multiple(query, limit=8):
    """Legacy wrapper - uses apis.py"""
    results = apis.search_songs(query, limit)
    # Convert to old format for backward compat
    out = []
    for s in results:
        out.append({
            "name": s["name"],
            "primaryArtists": s["artist"],
            "album": {"name": s.get("album","Unknown")},
            "year": s.get("year","Unknown"),
            "duration": s.get("duration", 0),
            "language": s.get("language","Unknown"),
            "downloadUrl": [{"link": s.get("download_url",""), "url": s.get("download_url","")}],
            "id": s.get("id",""),
        })
    return out[:limit]

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
        ])

def download_song_file(url, title):
    os.makedirs("dl", exist_ok=True)
    safe = "".join(c for c in title if c.isalnum() or c in " -_")[:50]
    path = f"dl/{safe}.mp3"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "audio/mpeg, audio/*, */*",
        "Accept-Encoding": "identity",
        "Connection": "keep-alive",
    }
    # Try up to 3 times
    for attempt in range(3):
        try:
            r = requests.get(url, stream=True, timeout=90,
                           headers=headers, allow_redirects=True)
            if r.status_code not in (200, 206):
                raise Exception(f"HTTP {r.status_code}")
            size = 0
            with open(path, "wb") as f:
                for chunk in r.iter_content(chunk_size=131072):
                    if chunk:
                        f.write(chunk)
                        size += len(chunk)
            if size < 10000:  # Less than 10KB = failed
                raise Exception(f"File too small: {size} bytes")
            return path
        except Exception as e:
            print(f"[download] Attempt {attempt+1} failed: {e}")
            if attempt == 2:
                raise Exception(f"Download failed after 3 tries: {e}")
    return path

async def send_song(m, query, msg, quality="320"):
    dl_url, title, duration, song_data = await asyncio.to_thread(search_jiosaavn_quality, query, quality)
    if not dl_url:
        await msg.edit("❌ Song not found! Try a different name.")
        return

    mins, secs = duration // 60, duration % 60
    user_id = m.from_user.id
    is_first = db.get_user(user_id) is None or db.get_user(user_id)["downloads"] == 0

    # Step 1: Show downloading
    try:
        await msg.edit(f"⬇️ **Downloading:** `{title}`...")
    except: pass

    # Step 2: Download with timeout protection (120 sec max)
    try:
        path = await asyncio.wait_for(
            asyncio.to_thread(download_song_file, dl_url, title),
            timeout=120
        )
    except asyncio.TimeoutError:
        await msg.edit(f"❌ **Timeout!** Server slow hai.\n🔄 Dobara try karo: `/download {query}`")
        return
    except Exception as e:
        err = str(e)
        # Try with alternate URL from different API
        try:
            await msg.edit(f"⚠️ First source failed, trying backup...")
            song_alt = await asyncio.to_thread(apis.search_song_download, query, quality)
            if song_alt and song_alt.get("download_url") and song_alt["download_url"] != dl_url:
                path = await asyncio.wait_for(
                    asyncio.to_thread(download_song_file, song_alt["download_url"], title),
                    timeout=120
                )
            else:
                raise Exception(err)
        except Exception as e2:
            await msg.edit(f"❌ **Download failed!**\n`{str(e2)[:80]}`\n\n🔄 Try: `/download {query}`")
            return

    # Step 3: Update stats AFTER successful download
    update_today_stats()
    today_downloads["count"] += 1
    db.increment_bot_stat("total_downloads")
    db.ensure_user(user_id, m.from_user.first_name)
    db.update_streak(user_id)
    db.increment_downloads(user_id)
    db.add_history(user_id, title)
    db.save_last_downloaded(user_id, title, f"{mins}:{secs:02d}", m.from_user.first_name)
    db.increment_song_downloads(title)

    # XP system
    xp_earned = XP_REWARDS["download"]
    if is_first: xp_earned += XP_REWARDS["first_download"]
    total_xp, new_level = db.add_xp(user_id, xp_earned)

    # Group stats
    if m.chat.type.name in ("GROUP", "SUPERGROUP"):
        db.update_group_stats(m.chat.id, user_id, m.from_user.first_name)

    if song_data:
        album_raw = song_data.get("album", "Unknown")
        album = album_raw.get("name", "Unknown") if isinstance(album_raw, dict) else (str(album_raw) if album_raw else "Unknown")
        year = str(song_data.get("year", "Unknown") or "Unknown")
    else:
        album = "Unknown"
        year = "Unknown"

    reaction_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 Download", callback_data=f"dl_{title[:30]}"),
         InlineKeyboardButton("📝 Lyrics", callback_data=f"lyr_{title[:35]}")],
        [InlineKeyboardButton("🎵 Similar", callback_data=f"sim_{title[:40]}"),
         InlineKeyboardButton("⭐ Save", callback_data=f"save_{title[:40]}")],
        [InlineKeyboardButton("👍 Like", callback_data=f"react_like_{title[:25]}"),
         InlineKeyboardButton("🔥 Fire", callback_data=f"react_fire_{title[:25]}"),
         InlineKeyboardButton("💔 Sad", callback_data=f"react_sad_{title[:25]}")],
    ])

    try:
        await msg.edit("📤 **Sending...**")
    except: pass

    is_group = m.chat.type.name in ("GROUP", "SUPERGROUP")

    # Split title into song name and artist for Telegram display
    song_name = song_data.get("name", title) if song_data else title
    artist_name = song_data.get("primaryArtists", song_data.get("artist", "")) if song_data else ""
    if not artist_name and " - " in title:
        parts_t = title.split(" - ", 1)
        song_name = parts_t[0].strip()
        artist_name = parts_t[1].strip()

    try:
        await app.send_audio(
            m.chat.id, path,
            caption=(f"🎵 **{title}**\n"
                     f"💿 {album} | 📅 {year}\n"
                     f"⏱ {mins}:{secs:02d} | 🎧 {quality}kbps\n"
                     f"👤 {m.from_user.first_name}\n\n"
                     f"🤖 {BOT_NAME} | {BOT_USERNAME}"),
            title=song_name,
            performer=artist_name,
            duration=duration,
            reply_markup=reaction_keyboard
        )
    except Exception as e:
        err_str = str(e)
        if "CHAT_SEND_AUDIO" in err_str or "403" in err_str or "Forbidden" in err_str:
            # Group mein audio permission nahi — PM mein bhejo
            try:
                await app.send_audio(
                    m.from_user.id, path,
                    caption=(f"🎵 **{title}**\n"
                             f"💿 {album} | 📅 {year}\n"
                             f"⏱ {mins}:{secs:02d} | 🎧 {quality}kbps\n"
                             f"🤖 {BOT_NAME} | {BOT_USERNAME}"),
                    title=song_name,
                    performer=artist_name,
                    duration=duration,
                    reply_markup=reaction_keyboard
                )
                try:
                    await msg.edit(
                        f"✅ **{title}**\n"
                        f"📩 Audio permission nahi hai yahan!\n"
                        f"Song aapke PM mein bheja gaya! 👆"
                    )
                except: pass
            except Exception as e2:
                await msg.edit(
                    f"⚠️ **Group mein audio send nahi ho sakta!**\n\n"
                    f"**Fix karo:**\n"
                    f"1. Bot ko **Admin** banao\n"
                    f"2. Ya **Media** permission do\n\n"
                    f"🎵 Song: `{title}`\n"
                    f"📩 Pehle mujhe PM karo: {BOT_USERNAME}"
                )
        else:
            await msg.edit(f"❌ Error: `{err_str[:80]}`")
        try: os.remove(path)
        except: pass
        return

    # Delete "Sending" message
    try:
        await msg.delete()
    except:
        try: await msg.edit("✅")
        except: pass

    # XP notification — sirf private chat mein, group mein spam nahi
    user = db.get_user(user_id)
    streak_bonus = ""
    if user and user["streak"] == 3:
        db.add_xp(user_id, XP_REWARDS["streak_3"])
        streak_bonus = " 🔥+20 streak bonus!"
    elif user and user["streak"] == 7:
        db.add_xp(user_id, XP_REWARDS["streak_7"])
        streak_bonus = " ⚡+50 streak bonus!"

    if is_first:
        xp_msg = (f"🎉 **First Download!** +{xp_earned} XP 🌟\n"
                  f"🏅 Badge: **Music Explorer**{streak_bonus}")
        await m.reply(xp_msg)
    elif not is_group:
        # Private chat mein XP show karo
        await m.reply(f"✨ +{xp_earned} XP{streak_bonus} | {get_xp_bar(total_xp)} Lv.{new_level}")

    try: os.remove(path)
    except: pass

# ========== CALLBACKS ==========

@app.on_callback_query(filters.regex(r"^dl_"))
async def dl_callback(_, cb):
    song = cb.data[3:]
    await cb.answer("Downloading...")
    msg = await cb.message.reply(f"⬇️ Searching `{song}`...")
    await send_song(cb.message, song, msg)

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

@app.on_callback_query(filters.regex(r"^react_"))
async def reaction_callback(_, cb):
    parts = cb.data.split("_")
    reaction = parts[1]
    song = "_".join(parts[2:])
    db.ensure_user(cb.from_user.id, cb.from_user.first_name)
    db.save_reaction(cb.from_user.id, song, reaction)
    all_reactions = db.get_song_reactions(song)
    likes = all_reactions.get("like", 0)
    fires = all_reactions.get("fire", 0)
    sads = all_reactions.get("sad", 0)
    emoji_map = {"like": "👍", "fire": "🔥", "sad": "💔"}
    await cb.answer(f"{emoji_map[reaction]} Reacted!", show_alert=False)
    try:
        await cb.message.edit_reply_markup(InlineKeyboardMarkup([
            [InlineKeyboardButton("📥 Download", callback_data=f"dl_{song[:30]}"),
             InlineKeyboardButton("📝 Lyrics", callback_data=f"lyr_{song[:35]}")],
            [InlineKeyboardButton("🎵 Similar", callback_data=f"sim_{song[:40]}"),
             InlineKeyboardButton("⭐ Save", callback_data=f"save_{song[:40]}")],
            [InlineKeyboardButton(f"👍 {likes}", callback_data=f"react_like_{song[:25]}"),
             InlineKeyboardButton(f"🔥 {fires}", callback_data=f"react_fire_{song[:25]}"),
             InlineKeyboardButton(f"💔 {sads}", callback_data=f"react_sad_{song[:25]}")],
        ]))
    except: pass

@app.on_callback_query(filters.regex("dl_birthday"))
async def birthday_dl(_, cb):
    await cb.answer()
    msg = await cb.message.reply("⬇️ Downloading...")
    await send_song(cb.message, "Baar Baar Din Yeh Aaye", msg)

@app.on_callback_query(filters.regex(r"^rate_"))
async def rate_callback(_, cb):
    parts = cb.data.split("_")
    rating, song = int(parts[1]), "_".join(parts[2:])
    db.ensure_user(cb.from_user.id, cb.from_user.first_name)
    db.save_rating(cb.from_user.id, song, rating)
    db.add_xp(cb.from_user.id, XP_REWARDS["rate_song"])
    avg, count = db.get_avg_rating(song)
    await cb.answer(f"✅ Rated {rating}⭐ +{XP_REWARDS['rate_song']} XP!", show_alert=False)
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

@app.on_callback_query(filters.regex(r"^vote_"))
async def vote_callback(_, cb):
    parts = cb.data.split("_")
    group_id = int(parts[1])
    choice = int(parts[2])
    user_id = cb.from_user.id
    if group_id not in group_votes:
        await cb.answer("Vote ended!", show_alert=False)
        return
    group_votes[group_id]["votes"][user_id] = choice
    await cb.answer(f"✅ Voted for option {choice+1}!", show_alert=False)

@app.on_callback_query(filters.regex(r"^help_(?!back)"))
async def help_category(_, cb):
    cat = cb.data[5:]
    texts = {
        "download": (
            "🎵 **Download & Search**\n\n"
            "📥 `/download [song]`\n🎧 `/quality [song]`\n🎵 `/preview [song]`\n"
            "🔍 `/search [song]`\nℹ️ `/info [song]`\n📝 `/lyrics [song-artist]`\n"
            "📦 `/batch`\n🎛 `/remix [song]`\n🎸 `/acoustic [song]`\n"
            "🎤 `/cover [song]`\n🎼 `/lofi [song]`"
        ),
        "discover": (
            "🌍 **Browse & Discover**\n\n"
            "🤖 `/ai_playlist`\n💿 `/album`\n💿 `/albuminfo`\n🎤 `/artist`\nℹ️ `/artistinfo`\n"
            "🎂 `/birthday`\n🔗 `/chain`\n📅 `/daily`\n🌐 `/english` `/hindi` `/punjabi`\n"
            "🔤 `/findlyrics`\n🎸 `/genre`\n🎼 `/karaoke`\n🔤 `/letter`\n🎭 `/mood`\n"
            "🆕 `/newreleases`\n🌙 `/night`\n🎵 `/playlist`\n🎲 `/random`\n🎯 `/recommend`\n"
            "🌍 `/regional`\n⏱ `/short`\n🎵 `/similar`\n🎤 `/similarartist`\n"
            "🏆 `/topartist`\n🎬 `/topbollywood`\n🇮🇳 `/topindia`\n🔥 `/top2025`\n"
            "🔥 `/trendingartist`\n🌍 `/trending`\n🎭 `/vibe`\n📅 `/year`\n💿 `/discography`"
        ),
        "games": (
            "🎮 **Games & Fun**\n\n"
            "⚖️ `/compare`\n📅 `/challenge`\n🎯 `/fillblank`\n🎯 `/guesssong`\n"
            "🎮 `/musicquiz`\n🎤 `/artistquiz`\n💬 `/quote`\n⭐ `/rate`\n🏆 `/topsongs`\n"
            "🏆 `/tournament`\n📅 `/yeargame`\n🎵 `/musicfact`\n🥚 `/easteregg`\n🔮 `/secret`\n\n"
            "**👥 Group Commands:**\n"
            "🎮 `/groupquiz`\n🎵 `/songbattle`\n📊 `/votesong`\n🎉 `/party`\n"
            "➕ `/addsong`\n⏭ `/skipparty`\n🛑 `/stopparty`\n📋 `/partyqueue`"
        ),
        "account": (
            "👤 **My Account**\n\n"
            "🏅 `/badges`\n💾 `/favorites`\n📊 `/genrestats`\n📜 `/history`\n"
            "🤝 `/invite`\n🎵 `/lastdownload`\n🏆 `/leaderboard`\n👤 `/mystats`\n"
            "📝 `/note`\n👤 `/profile`\n🗑 `/removefav`\n⭐ `/save`\n📤 `/share`\n"
            "🔔 `/subscribe`\n🔕 `/unsubscribe`\n🔥 `/streak`\n🎁 `/dailyreward`\n"
            "📋 `/wishlist`\n📋 `/mywishlist`"
        ),
        "stats": (
            "📊 **Stats & Info**\n\n"
            "📊 `/activestats`\n⏱ `/ping`\n📤 `/share`\n🎵 `/songstats`\n"
            "📊 `/stats`\n📅 `/todaystats`\n⏰ `/uptime`\n\n"
            "**👥 Group Stats:**\n"
            "🏆 `/gleaderboard`\n📊 `/groupstats`\n🥇 `/topuser`"
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
    await cb.message.edit_text(f"❓ **{BOT_NAME} Help Menu**\n\nChoose a category:", reply_markup=keyboard)
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

@app.on_message(filters.command("addsong"))
async def addsong(_, m: Message):
    if m.chat.type.name not in ("GROUP", "SUPERGROUP"):
        await m.reply("❌ Group mein use karo!")
        return
    group_id = m.chat.id
    if not db.get_group_setting(group_id, "party_mode"):
        await m.reply("❌ Party mode active nahi hai!\nPehle `/party` start karo.")
        return
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await m.reply("❌ Example: `/addsong Tum Hi Ho`")
        return
    song = parts[1].strip()
    db.add_to_party_queue(group_id, m.from_user.id, m.from_user.first_name, song)
    queue = db.get_party_queue(group_id)
    msg = await m.reply(f"✅ **Added to queue!** #{len(queue)}\n🎵 `{song}` — Downloading...")
    await send_song(m, song, msg)

@app.on_message(filters.command("ai_playlist"))
async def ai_playlist(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("🤖 **Choose activity:**\n`/ai_playlist gym` 💪\n`/ai_playlist study` 📚\n`/ai_playlist heartbreak` 💔\n`/ai_playlist sleep` 😴\n`/ai_playlist party` 🎉\n`/ai_playlist romantic` 💕\n`/ai_playlist morning` 🌅\n`/ai_playlist roadtrip` 🚗")
        return
    activity = parts[1].strip().lower()
    queries = {"gym": "workout gym motivation", "study": "study focus calm instrumental",
               "heartbreak": "heartbreak sad emotional hindi", "sleep": "sleep relaxing calm",
               "party": "party dance upbeat hindi", "romantic": "romantic love songs",
               "morning": "morning fresh motivational", "roadtrip": "roadtrip travel songs"}
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
    total_dur = sum(int(s.get("duration", 0)) for s in results)
    text = (f"💿 **{album_name}**\n\n👤 **Artist:** {artist}\n📅 **Year:** {year}\n"
            f"🌐 **Language:** {lang}\n🎵 **Songs:** {len(results)}+\n"
            f"⏱ **Total:** ~{total_dur//60} mins\n\n**Tracklist:**\n")
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
    info = apis.get_artist_info(query)
    top_tracks = apis.get_artist_top_tracks(query, 5)
    similar = apis.get_similar_artists(query)[:4]
    if info and info.get("name"):
        listeners = info.get("listeners","Unknown")
        if str(listeners).isdigit():
            listeners = f"{int(listeners):,}"
        text = (f"🎤 **{info['name']}**\n\n"
                f"👥 Listeners: {listeners}\n"
                f"🎸 Genres: {', '.join(info.get('tags',[])[:3]) or 'Unknown'}\n"
                f"🎵 Similar: {', '.join(similar[:3]) or 'Unknown'}\n\n")
        if info.get("bio"):
            text += f"📖 **Bio:** {info['bio'][:200]}...\n\n"
        if top_tracks:
            text += "**🏆 Top Songs:**\n"
            for i, t in enumerate(top_tracks[:5], 1):
                text += f"{i}. {t['name']}\n"
    else:
        results = search_jiosaavn_multiple(f"{query} songs", 8)
        if not results:
            await msg.edit("❌ Artist not found!")
            return
        text = f"🎤 **{query}**\n\n**Popular Songs:**\n"
        for i, s in enumerate(results[:5], 1):
            text += f"{i}. {s['name']}\n"
    text += f"\n🎵 `/topartist {query}` | `/similarartist {query}`"
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
    text = f"🎤 **Artist Quiz!**\n\n🎵 **Song:** {correct_song}\n\n❓ **Who sang this?**\n\n"
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
    db.ensure_user(user_id, m.from_user.first_name)
    user = db.get_user(user_id) or {}
    downloads = user.get("downloads", 0)
    xp = user.get("xp", 0)
    level = user.get("level", 1)
    badge_list = get_badges(user_id)
    text = (f"🏅 **{m.from_user.first_name}'s Badges:**\n\n")
    for b in badge_list:
        text += f"• {b}\n"
    text += (f"\n📥 Downloads: {downloads}\n"
             f"✨ XP: {xp} | {get_xp_bar(xp)}\n"
             f"🎖 Level: {level} — {get_level_title(level)}")
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
    title, artist = song["name"], song["primaryArtists"]
    lyrics_text, _ = get_lyrics(f"{title} - {artist}")
    if lyrics_text:
        lines = [l.strip() for l in lyrics_text.split("\n") if len(l.strip()) > 20]
        line = random.choice(lines[:10]) if lines else f"Hint: Artist is **{artist}**"
    else:
        line = f"Hint: Artist is **{artist}**"
    chat_id = m.chat.id
    active_quiz[chat_id] = {"answer": title.lower(), "title": title, "artist": artist, "type": "guess"}
    await m.reply(f"🎯 **Daily Challenge!**\n📅 {now.strftime('%d %b %Y')}\n\n"
                  f"🎵 **Guess this song:**\n_{line}_\n\n💭 Reply with song name!\n⏱ 30 seconds!")
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
    keywords = ["hindi hits popular", "bollywood popular songs", "top songs india", "romantic hindi"]
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

@app.on_message(filters.command("dailygroup"))
async def dailygroup(_, m: Message):
    if m.chat.type.name not in ("GROUP", "SUPERGROUP"):
        await m.reply("❌ Group mein use karo!")
        return
    current = db.get_group_setting(m.chat.id, "daily_song")
    new_val = 0 if current else 1
    db.set_group_setting(m.chat.id, "daily_song", new_val)
    if new_val:
        await m.reply("🔔 **Daily Group Song: ON!**\nHar roz subah ek song aayega! 🎵")
    else:
        await m.reply("🔕 **Daily Group Song: OFF**")

@app.on_message(filters.command("dailyreward"))
async def dailyreward(_, m: Message):
    user_id = m.from_user.id
    db.ensure_user(user_id, m.from_user.first_name)
    if not db.can_claim_reward(user_id):
        await m.reply("⏰ **Already claimed today!**\nAao kal phir! 🌅\n\nXP earn karne ke liye songs download karo!")
        return
    db.claim_reward(user_id)
    xp_earned = XP_REWARDS["daily_reward"]
    total_xp, level = db.add_xp(user_id, xp_earned)
    user = db.get_user(user_id)
    streak = user.get("streak", 0)
    await m.reply(
        f"🎁 **Daily Reward Claimed!**\n\n"
        f"✨ **+{xp_earned} XP** earned!\n"
        f"🔥 Streak: {streak} days\n"
        f"{get_xp_bar(total_xp)}\n"
        f"🎖 Level: {level} — {get_level_title(level)}\n\n"
        f"Kal phir aao double reward ke liye! 🌟"
    )

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
        await m.reply("❌ Example: `/duet Arijit Shreya`")
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

@app.on_message(filters.command("easteregg"))
async def easteregg(_, m: Message):
    await m.reply(random.choice(EASTER_EGGS))

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
    blanked = " ".join(words)
    active_quiz[chat_id] = {"answer": answer, "title": title, "artist": artist, "type": "fillblank"}
    await msg.edit(f"🎯 **Fill in the Blank!**\n\n🎵 **Song:** {title}\n👤 **Artist:** {artist}\n\n"
                   f"**Complete the lyric:**\n_{blanked}_\n\n💭 Reply with the missing word!\n⏱ 20 seconds!")
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
    results = apis.search_genre(g, 10)
    if not results:
        await msg.edit("❌ No songs found!")
        return
    text = f"{emojis[g]} **{g.capitalize()} Songs:**\n\n"
    for i, s in enumerate(results[:10], 1):
        artist = s.get("artist", s.get("primaryArtists","Unknown"))
        text += f"{i}. **{s['name']}** - {artist}\n"
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
    hindi = sum(1 for s in songs if any(w in s.lower() for w in ["hindi","tum","dil","pyar","ishq","tera","mera"]))
    english = sum(1 for s in songs if any(w in s.lower() for w in ["love","baby","night","light","heart"]))
    punjabi = sum(1 for s in songs if any(w in s.lower() for w in ["punjabi","jatt","kudi","yaar"]))
    other = max(0, total - hindi - english - punjabi)
    def pct(n): return f"{(n/total*100):.0f}%" if total > 0 else "0%"
    await m.reply(f"📊 **{m.from_user.first_name}'s Genre Breakdown:**\n\n"
                  f"🇮🇳 Hindi: {hindi} ({pct(hindi)})\n🌍 English: {english} ({pct(english)})\n"
                  f"🎵 Punjabi: {punjabi} ({pct(punjabi)})\n🎶 Other: {other} ({pct(other)})\n\n"
                  f"📥 Total: {total}")

@app.on_message(filters.command("gleaderboard"))
async def gleaderboard(_, m: Message):
    if m.chat.type.name not in ("GROUP", "SUPERGROUP"):
        await m.reply("❌ Group mein use karo!")
        return
    rows = db.get_group_leaderboard(m.chat.id)
    if not rows:
        await m.reply("❌ No downloads in this group yet!")
        return
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    text = f"🏆 **{m.chat.title} Leaderboard:**\n\n"
    for i, row in enumerate(rows, 0):
        text += f"{medals[i]} **{row['user_name']}** — {row['downloads']} downloads\n"
    text += "\n🎵 Download songs to climb up!"
    await m.reply(text)

@app.on_message(filters.command("groupmood"))
async def groupmood(_, m: Message):
    if m.chat.type.name not in ("GROUP", "SUPERGROUP"):
        await m.reply("❌ Group mein use karo!")
        return
    moods = ["happy 😊", "sad 😢", "party 🎉", "romantic 💕", "chill 😌"]
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("😊 Happy", callback_data="none"),
         InlineKeyboardButton("😢 Sad", callback_data="none")],
        [InlineKeyboardButton("🎉 Party", callback_data="none"),
         InlineKeyboardButton("💕 Romantic", callback_data="none")],
        [InlineKeyboardButton("😌 Chill", callback_data="none")]
    ])
    await m.reply(f"🎭 **Group Mood Poll!**\n\nSabka mood kya hai?\nBot best playlist suggest karega!\n\n"
                  f"Vote karo neeche 👇", reply_markup=keyboard)

@app.on_message(filters.command("groupquiz"))
async def groupquiz(_, m: Message):
    if m.chat.type.name not in ("GROUP", "SUPERGROUP"):
        await m.reply("❌ Group mein use karo!")
        return
    msg = await m.reply("🎮 **Group Music Quiz Starting!**\n\nSabse pehle jawab do — winner hoga! 🏆")
    chat_id = m.chat.id
    results = search_jiosaavn_multiple("popular hindi bollywood songs", 20)
    if not results:
        await msg.edit("❌ Could not fetch!")
        return
    correct = random.choice(results)
    title, artist = correct["name"], correct["primaryArtists"]
    lyrics_text, _ = get_lyrics(f"{title} - {artist}")
    if lyrics_text:
        lines = [l.strip() for l in lyrics_text.split("\n") if len(l.strip()) > 20]
        line = random.choice(lines[:10]) if lines else f"Artist: **{artist}**"
    else:
        line = f"Artist: **{artist}**"
    active_quiz[chat_id] = {"answer": title.lower(), "title": title, "artist": artist, "type": "guess"}
    await msg.edit(f"🎮 **Group Quiz!** 👥\n\n🎵 **Lyrics:**\n_{line}_\n\n"
                   f"💭 **Sabse pehle sahi answer karega wo jitega!**\n⏱ 30 seconds!")
    await asyncio.sleep(30)
    if chat_id in active_quiz and active_quiz[chat_id].get("type") == "guess":
        del active_quiz[chat_id]
        await m.reply(f"⏱ **Time's up! Kisi ne sahi answer nahi diya!**\nAnswer: **{title}** by {artist}")

@app.on_message(filters.command("groupstats"))
async def groupstats(_, m: Message):
    if m.chat.type.name not in ("GROUP", "SUPERGROUP"):
        await m.reply("❌ Group mein use karo!")
        return
    group_id = m.chat.id
    total = db.get_group_total_downloads(group_id)
    members = db.get_group_members_count(group_id)
    top = db.get_group_leaderboard(group_id, 1)
    top_name = top[0]["user_name"] if top else "None"
    await m.reply(f"📊 **{m.chat.title} Stats:**\n\n"
                  f"👥 Active Members: {members}\n"
                  f"📥 Total Downloads: {total}\n"
                  f"🥇 Top User: {top_name}\n\n"
                  f"🏆 `/gleaderboard` — See full ranking")

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
    await msg.edit(f"🎯 **Guess The Song!**\n\n🎵 **Lyrics:**\n_{line}_\n\n"
                   f"💭 Reply with song name!\n⏱ 30 seconds!\nUse `/skip` to skip.")
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
    await m.reply(f"❓ **{BOT_NAME} Help Menu**\n\nChoose a category below 👇", reply_markup=keyboard)

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
    avg_rating, vote_count = db.get_avg_rating(song_data['name'][:25])
    album_raw = song_data.get("album", "Unknown")
    album_name = album_raw.get("name", "Unknown") if isinstance(album_raw, dict) else (album_raw or "Unknown")
    await msg.edit(f"ℹ️ **Song Info:**\n\n🎵 **Title:** {song_data['name']}\n"
                   f"👤 **Artist:** {song_data.get('artist', song_data.get('primaryArtists','Unknown'))}\n"
                   f"💿 **Album:** {album_name}\n"
                   f"📅 **Year:** {song_data.get('year', 'Unknown')}\n"
                   f"🌐 **Language:** {song_data.get('language', 'Unknown').capitalize()}\n"
                   f"⏱ **Duration:** {mins}:{secs:02d}\n"
                   f"📥 **Bot Downloads:** {g_stats.get('downloads', 0)}\n"
                   f"⭐ **Rating:** {avg_rating:.1f}/5 ({vote_count} votes)\n\n"
                   f"📥 `/download {song_data['name']}`")

@app.on_message(filters.command("invite"))
async def invite(_, m: Message):
    user_id = m.from_user.id
    db.ensure_user(user_id, m.from_user.first_name)
    await m.reply(f"🤝 **Invite Friends to {BOT_NAME}!**\n\n"
                  f"Share this bot:\n👉 {BOT_USERNAME}\n\n"
                  f"_Share the music, spread the love!_ 🎵")

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
        await msg.edit(f"❌ No karaoke found!\n💡 Try:\n📥 `/download {query} karaoke`")
        return
    text = f"🎼 **Karaoke/Instrumental: `{query}`**\n\n"
    for i, s in enumerate(unique[:6], 1):
        text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

# L

@app.on_message(filters.command("lastdownload"))
async def lastdownload(_, m: Message):
    s = db.get_last_downloaded(m.from_user.id)
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
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    text = "🏆 **Top Music Lovers:**\n\n"
    for i, u in enumerate(users[:10], 0):
        streak_text = f" 🔥{u['streak']}" if u.get("streak", 0) >= 3 else ""
        xp_text = f" ✨{u.get('xp',0)}xp"
        text += f"{medals[i]} **{u['name']}** — {u['downloads']} downloads{streak_text}{xp_text}\n"
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
    for q in [f"{query} lofi", f"{query} lo-fi", f"lofi {query}"]:
        results += search_jiosaavn_multiple(q, 3)
    seen, unique = set(), []
    for s in results:
        if s["name"] not in seen:
            seen.add(s["name"])
            unique.append(s)
    if not unique:
        await msg.edit(f"❌ No Lo-Fi found!\n💡 Try: `/download {query} lofi`")
        return
    text = f"🎵 **Lo-Fi: `{query}`**\n\n"
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

@app.on_message(filters.command("musicfact"))
async def musicfact(_, m: Message):
    await m.reply(f"🎵 **Music Fact:**\n\n{random.choice(MUSIC_FACTS)}")

@app.on_message(filters.command("musicmatch"))
async def musicmatch(_, m: Message):
    if m.chat.type.name not in ("GROUP", "SUPERGROUP"):
        await m.reply("❌ Group mein use karo!\nExample: `/musicmatch @user1 @user2`")
        return
    await m.reply("🎵 **Music Match!**\n\nDono users ke downloads compare ho rahe hain...\n\n"
                  "_(Feature coming soon — abhi apni history `/history` mein dekho!)_ 🎵")

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
    xp = user.get("xp", 0)
    level = user.get("level", 1)
    await m.reply(f"👤 **{m.from_user.first_name}'s Stats:**\n\n"
                  f"📥 Downloads: {user['downloads']}\n"
                  f"🎵 Most Downloaded: {most}\n"
                  f"📜 History: {len(db.get_history(user_id))}\n"
                  f"⭐ Favorites: {db.count_favorites(user_id)}\n"
                  f"🔥 Streak: {user.get('streak', 0)} days\n"
                  f"✨ XP: {xp} | {get_xp_bar(xp)}\n"
                  f"🎖 Level: {level} — {get_level_title(level)}\n"
                  f"🎸 Genre: {get_user_genre_from_history(user_id)}\n"
                  f"🏅 Rank: {get_level(user['downloads'])}")

@app.on_message(filters.command("mywishlist"))
async def mywishlist(_, m: Message):
    items = db.get_wishlist(m.from_user.id)
    if not items:
        await m.reply("📋 Wishlist empty!\nUse `/wishlist [song]` to add.")
        return
    text = "📋 **Your Wishlist:**\n\n"
    for i, s in enumerate(items, 1):
        text += f"{i}. {s}\n"
    text += "\n📥 `/download [song name]`"
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
    results = []
    for q in ["night songs hindi", "sad hindi songs", "chill hindi songs", "romantic night songs"]:
        results = search_jiosaavn_multiple(q, 10)
        if results:
            break
    if not results:
        await msg.edit("❌ No songs found!")
        return
    await send_song(m, random.choice(results)["name"], msg)

@app.on_message(filters.command("note"))
async def note(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or "|" not in parts[1]:
        await m.reply("❌ Format: `/note Song | Note`\nExample: `/note Tum Hi Ho | Best song ever!`")
        return
    song, note_text = parts[1].split("|", 1)
    db.save_note(m.from_user.id, song.strip(), note_text.strip())
    await m.reply(f"📝 **Note saved!**\n\n🎵 **{song.strip()}**\n💬 _{note_text.strip()}_")

# P

@app.on_message(filters.command("party"))
async def party(_, m: Message):
    if m.chat.type.name not in ("GROUP", "SUPERGROUP"):
        await m.reply("❌ Group mein use karo!")
        return
    group_id = m.chat.id
    if db.get_group_setting(group_id, "party_mode"):
        await m.reply("🎉 **Party already active!**\nAdd songs: `/addsong [song]`\nQueue: `/partyqueue`\nSkip: `/skipparty`\nStop: `/stopparty`")
        return
    db.set_group_setting(group_id, "party_mode", 1)
    db.set_group_setting(group_id, "party_host", m.from_user.id)
    db.clear_party_queue(group_id)
    await m.reply(f"🎉 **Party Mode Activated!**\n\n"
                  f"🎵 Host: **{m.from_user.first_name}**\n\n"
                  f"Add songs to the queue:\n`/addsong Tum Hi Ho`\n`/addsong Kesariya`\n\n"
                  f"📋 `/partyqueue` — See queue\n"
                  f"⏭ `/skipparty` — Skip current\n"
                  f"🛑 `/stopparty` — End party\n\n"
                  f"Let's go! 🔥🎵")

@app.on_message(filters.command("partyqueue"))
async def partyqueue(_, m: Message):
    if m.chat.type.name not in ("GROUP", "SUPERGROUP"):
        await m.reply("❌ Group mein use karo!")
        return
    queue = db.get_party_queue(m.chat.id)
    if not queue:
        await m.reply("📋 **Queue empty!**\nAdd songs: `/addsong [song]`")
        return
    text = f"📋 **Party Queue ({len(queue)} songs):**\n\n"
    for i, item in enumerate(queue, 1):
        text += f"{i}. **{item['song']}** — by {item['user_name']}\n"
    await m.reply(text)

@app.on_message(filters.command("ping"))
async def ping(_, m: Message):
    start = datetime.datetime.now()
    msg = await m.reply("🏓 **Pinging...**")
    latency = (datetime.datetime.now() - start).microseconds // 1000
    await msg.edit(f"🏓 **Pong!**\n\n⚡ Latency: **{latency}ms**\n✅ Status: Online")

@app.on_message(filters.command("play"))
async def play_vc(_, m: Message):
    await m.reply("🔜 **Coming Soon!**\n\nVoice Chat feature jald aayega!\n\nAbhi ke liye: 📥 `/download [song]`")

@app.on_message(filters.command("skip"))
async def skip_cmd(_, m: Message):
    chat_id = m.chat.id
    if chat_id not in active_quiz:
        await m.reply("❌ No active quiz!")
        return
    quiz = active_quiz.pop(chat_id)
    await m.reply(f"⏭ **Skipped!**\nAnswer: **{quiz['title']}** by {quiz['artist']}")





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
        path = download_song_file(preview_url, f"preview_{title}")
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
    xp = user.get("xp", 0)
    level = user.get("level", 1)
    songs = db.get_history(user_id, 50)
    most = max(set(songs), key=songs.count) if songs else "None"
    badge_list = get_badges(user_id)
    await m.reply(f"👤 **{m.from_user.first_name}'s Profile**\n\n"
                  f"📅 Since: {user.get('joined', 'Unknown')}\n"
                  f"📥 Downloads: {downloads}\n"
                  f"🎵 Top Song: {most}\n"
                  f"🎸 Genre: {get_user_genre_from_history(user_id)}\n"
                  f"⭐ Favorites: {db.count_favorites(user_id)}\n"
                  f"🔥 Streak: {user.get('streak', 0)} days\n"
                  f"✨ XP: {xp}\n"
                  f"{get_xp_bar(xp)}\n"
                  f"🎖 Level: {level} — {get_level_title(level)}\n"
                  f"🔔 Subscribed: {'Yes ✅' if db.is_subscribed(user_id) else 'No ❌'}\n\n"
                  f"**Badges:**\n" + "\n".join(f"• {b}" for b in badge_list))

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
    await m.reply(f"🎧 **Select Quality:**\n`{song}`\n\n128kbps — Data saver 📶\n192kbps — Balanced ⚖️\n320kbps — Best quality 🎵", reply_markup=keyboard)

@app.on_message(filters.command("quote"))
async def quote(_, m: Message):
    msg = await m.reply("💬 **Fetching quote...**")
    await msg.edit(f"💬 **Music Quote:**\n\n{fetch_quote()}")

# R

@app.on_message(filters.command("random"))
async def random_song(_, m: Message):
    keywords = ["hindi popular 2024", "bollywood hits", "top songs india", "english hits", "punjabi popular", "romantic songs"]
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
    hist = db.get_history(user_id, 1)
    if hist:
        results = search_jiosaavn_multiple(f"songs like {hist[0]}", 5)
        text = f"🎧 **Because you downloaded** `{hist[0]}`:\n\n**Recommended:**\n"
    else:
        results = search_jiosaavn_multiple("best hindi songs popular", 5)
        text = "🎯 **Recommended for You:**\n\n"
    if not results:
        await msg.edit("❌ Could not fetch!")
        return
    for i, s in enumerate(results, 1):
        text += f"• **{s['name']}** - {s['primaryArtists']}\n"
    text += "\n📥 `/download [song name]`"
    await msg.edit(text)

@app.on_message(filters.command("regional"))
async def regional(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("🌍 **Choose:**\n`/regional marathi` `/regional tamil` `/regional telugu`\n`/regional bhojpuri` `/regional bengali` `/regional gujarati`")
        return
    lang = parts[1].strip().lower()
    msg = await m.reply(f"🌍 **Fetching {lang} songs...**")
    results = apis.search_by_language(lang, 10)
    if not results:
        await msg.edit("❌ No songs found!")
        return
    text = f"🌍 **Top {lang.capitalize()} Songs:**\n\n"
    for i, s in enumerate(results[:10], 1):
        artist = s.get("artist", s.get("primaryArtists", "Unknown"))
        text += f"{i}. **{s['name']}** - {artist}\n"
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
    if db.remove_favorite(m.from_user.id, parts[1].strip()):
        await m.reply(f"🗑 **Removed:** `{parts[1].strip()}`")
    else:
        await m.reply("❌ Not in favorites!")

@app.on_message(filters.command("requestsong"))
async def requestsong(_, m: Message):
    if m.chat.type.name not in ("GROUP", "SUPERGROUP"):
        await m.reply("❌ Group mein use karo!")
        return
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await m.reply("❌ Example: `/requestsong Tum Hi Ho`")
        return
    song = parts[1].strip()
    await m.reply(f"🎵 **Song Request!**\n\n🎶 `{song}`\n👤 Requested by: **{m.from_user.first_name}**\n\n📥 `/download {song}` to download!")

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
        keyboard_row = [
            InlineKeyboardButton("📥", callback_data=f"dl_{song['name'][:30]}"),
            InlineKeyboardButton("🎤", callback_data=f"lyr_{song['name'][:35]}"),
            InlineKeyboardButton("🎵", callback_data=f"sim_{song['name'][:40]}"),
        ]
        text += f"{i}. **{song['name']}** — {song['primaryArtists']} | ⏱ {d//60}:{d%60:02d}\n"
    text += "\n📥 Tap buttons below or `/download [name]`"
    # Inline buttons for top result
    top = results[0]
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📥 Download", callback_data=f"dl_{top['name'][:30]}"),
        InlineKeyboardButton("📝 Lyrics", callback_data=f"lyr_{top['name'][:35]}"),
        InlineKeyboardButton("🎵 Similar", callback_data=f"sim_{top['name'][:40]}"),
        InlineKeyboardButton("▶️ Preview", callback_data=f"none"),
    ]])
    await msg.edit(text, reply_markup=keyboard)

@app.on_message(filters.command("secret"))
async def secret(_, m: Message):
    secrets = [
        "🔮 **Secret #1:** Type `/musicfact` for hidden music knowledge!",
        "🤫 **Secret #2:** Your streak gives you bonus XP! Try `/dailyreward`",
        "🔮 **Secret #3:** Rate songs with `/rate` to earn XP!",
        "🤫 **Secret #4:** Try `/party` in a group for the ultimate experience!",
        "🔮 **Secret #5:** `/easteregg` has more secrets hidden inside! 🥚",
    ]
    await m.reply(random.choice(secrets))

@app.on_message(filters.command("share"))
async def share(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Example: `/share Tum Hi Ho`")
        return
    query = parts[1].strip()
    msg = await m.reply("📤 **Creating share card...**")
    dl_url, title, duration, song_data = search_jiosaavn(query)
    if not song_data:
        await msg.edit("❌ Song not found!")
        return
    mins, secs = duration // 60, duration % 60
    avg_rating, _ = db.get_avg_rating(song_data['name'][:25])
    await msg.edit(f"🎵 **{song_data['name']}**\n"
                   f"👤 Artist: {song_data['primaryArtists']}\n"
                   f"💿 Album: {song_data.get('album',{}).get('name','Unknown')}\n"
                   f"⏱ Duration: {mins}:{secs:02d} | 📅 {song_data.get('year','Unknown')}\n"
                   f"⭐ Rating: {avg_rating:.1f}/5\n\n"
                   f"🎧 Download from **{BOT_NAME}**\n👉 {BOT_USERNAME}")

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
    # Use LastFM for better similar track recommendations
    artist_name = song_data.get("artist", song_data.get("primaryArtists","")).split(",")[0].strip()
    song_name = song_data.get("name", query)
    similar_tracks = apis.get_similar_tracks(artist_name, song_name)
    if similar_tracks:
        text = f"🎵 **Similar to** `{query}` (LastFM):\n\n"
        for i, t in enumerate(similar_tracks[:8], 1):
            text += f"{i}. **{t['name']}** - {t['artist']}\n"
    else:
        fallback = search_jiosaavn_multiple(f"{artist_name} songs", 6)
        text = f"🎵 **Similar to** `{query}`:\n\n"
        for i, s in enumerate(fallback, 1):
            text += f"{i}. **{s['name']}** - {s['primaryArtists']}\n"
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
    artists = apis.get_similar_artists(query)
    if not artists:
        await msg.edit("❌ No results found!")
        return
    text = f"🎤 **Artists Similar to {query}:**\n\n"
    for i, a in enumerate(artists[:8], 1):
        text += f"{i}. **{a}**\n"
    text += f"\n🎵 `/artist [name]` — See their songs\nℹ️ `/artistinfo [name]` — Artist details"
    await msg.edit(text)

@app.on_message(filters.command("skip"))
async def skip(_, m: Message):
    chat_id = m.chat.id
    if chat_id not in active_quiz:
        await m.reply("❌ No active quiz!")
        return
    quiz = active_quiz.pop(chat_id)
    await m.reply(f"⏭ **Skipped!**\nAnswer: **{quiz['title']}** by {quiz['artist']}")

@app.on_message(filters.command("skipparty"))
async def skipparty(_, m: Message):
    if m.chat.type.name not in ("GROUP", "SUPERGROUP"):
        await m.reply("❌ Group mein use karo!")
        return
    group_id = m.chat.id
    if not db.get_group_setting(group_id, "party_mode"):
        await m.reply("❌ Party mode active nahi hai!")
        return
    next_song = db.pop_party_queue(group_id)
    if not next_song:
        await m.reply("📋 **Queue empty!**\nAdd songs: `/addsong [song]`")
        return
    msg = await m.reply(f"⏭ **Playing next:**\n🎵 `{next_song['song']}`\n👤 Added by: {next_song['user_name']}")
    await send_song(m, next_song["song"], msg)

@app.on_message(filters.command("songbattle"))
async def songbattle(_, m: Message):
    if m.chat.type.name not in ("GROUP", "SUPERGROUP"):
        await m.reply("❌ Group mein use karo!")
        return
    parts = m.text.split(None, 1)
    if len(parts) < 2 or "|" not in parts[1]:
        await m.reply("❌ Format: `/songbattle Song1 | Song2`\nExample: `/songbattle Husn | Kesariya`")
        return
    songs = parts[1].split("|")
    if len(songs) != 2:
        await m.reply("❌ 2 songs likho `|` se alag karke!")
        return
    s1, s2 = songs[0].strip(), songs[1].strip()
    group_id = m.chat.id
    group_votes[group_id] = {"songs": [s1, s2], "votes": {}, "active": True}
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(f"🎵 {s1[:20]}", callback_data=f"vote_{group_id}_0"),
        InlineKeyboardButton(f"🎵 {s2[:20]}", callback_data=f"vote_{group_id}_1"),
    ]])
    msg = await m.reply(f"⚔️ **Song Battle!**\n\n🎵 **{s1}**\n  VS\n🎵 **{s2}**\n\nVote karo! ⏱ 30 seconds!", reply_markup=keyboard)
    await asyncio.sleep(30)
    if group_id in group_votes and group_votes[group_id].get("active"):
        votes = group_votes[group_id]["votes"]
        v0 = sum(1 for v in votes.values() if v == 0)
        v1 = sum(1 for v in votes.values() if v == 1)
        winner = s1 if v0 >= v1 else s2
        del group_votes[group_id]
        await m.reply(f"🏆 **Battle Result!**\n\n🎵 **{s1}**: {v0} votes\n🎵 **{s2}**: {v1} votes\n\n👑 **Winner: {winner}!**\n\n📥 `/download {winner}`")

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
    reactions = db.get_song_reactions(song_name[:25])
    await msg.edit(f"📊 **{song_name}**\n\n"
                   f"👤 {song_data['primaryArtists']}\n"
                   f"💿 {song_data.get('album',{}).get('name','Unknown')} | 📅 {song_data.get('year','Unknown')}\n\n"
                   f"📥 **Bot Downloads:** {g_stats['downloads']}\n"
                   f"⭐ **Favorites:** {g_stats['favorites']}\n"
                   f"🌟 **Rating:** {'⭐ ' + f'{avg_rating:.1f}/5 ({vote_count} votes)' if vote_count > 0 else 'Not rated yet'}\n"
                   f"👍 Likes: {reactions.get('like',0)} | 🔥 Fire: {reactions.get('fire',0)} | 💔 Sad: {reactions.get('sad',0)}\n\n"
                   f"📥 `/download {song_name}`")

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
    await m.reply(f"🎵 **Welcome to {BOT_NAME}!**\n"
                  f"Hello {m.from_user.first_name}! 👋\n\n"
                  f"🤖 Your ultimate music companion!\n\n"
                  f"━━━━━━━━━━━━━━━━━━━━\n"
                  f"🚀 **Quick Start:**\n"
                  f"📥 `/download Tum Hi Ho`\n"
                  f"🔍 `/search Arijit Singh`\n"
                  f"🎭 `/mood happy`\n"
                  f"🎮 `/guesssong`\n"
                  f"🎁 `/dailyreward` — Free XP!\n\n"
                  f"━━━━━━━━━━━━━━━━━━━━\n"
                  f"📋 **Browse commands below** 👇\n"
                  f"━━━━━━━━━━━━━━━━━━━━\n\n"
                  f"⚠️ **Bug/Issue?** Contact: {DEVELOPER}",
                  reply_markup=keyboard)

@app.on_message(filters.command("stats"))
async def bot_stats(_, m: Message):
    update_today_stats()
    uptime = datetime.datetime.now() - START_TIME
    hours = int(uptime.total_seconds() // 3600)
    mins = int((uptime.total_seconds() % 3600) // 60)
    await m.reply(f"📊 **{BOT_NAME} Statistics:**\n\n"
                  f"👥 Total Users: {db.get_total_users()}\n"
                  f"📥 Total Downloads: {db.get_total_downloads()}\n"
                  f"📅 Today: {today_downloads['count']}\n"
                  f"🔔 Subscribers: {len(db.get_subscribers())}\n"
                  f"⏰ Uptime: {hours}h {mins}m\n"
                  f"🎵 Database: JioSaavn + SQLite\n\n"
                  f"⚠️ Issues? Contact: {DEVELOPER}")

@app.on_message(filters.command("stopparty"))
async def stopparty(_, m: Message):
    if m.chat.type.name not in ("GROUP", "SUPERGROUP"):
        await m.reply("❌ Group mein use karo!")
        return
    group_id = m.chat.id
    host = db.get_group_setting(group_id, "party_host")
    if host and host != m.from_user.id:
        await m.reply("❌ Sirf party host stop kar sakta hai!")
        return
    db.set_group_setting(group_id, "party_mode", 0)
    db.clear_party_queue(group_id)
    await m.reply("🛑 **Party Mode Stopped!**\n\nThanks for the party! 🎉\nPhir milenge! 🎵")

@app.on_message(filters.command("streak"))
async def streak(_, m: Message):
    user_id = m.from_user.id
    db.ensure_user(user_id, m.from_user.first_name)
    u = db.get_user(user_id)
    current_streak = u["streak"] if u else 0
    if current_streak == 0:
        await m.reply("🔥 **Streak: 0 days**\n\nDownload a song today to start! 🎵\n🎁 `/dailyreward` — Claim free XP!")
        return
    if current_streak >= 30: emoji = "👑"
    elif current_streak >= 7: emoji = "⚡"
    elif current_streak >= 3: emoji = "🔥"
    else: emoji = "✨"
    await m.reply(f"{emoji} **{m.from_user.first_name}'s Streak:**\n\n"
                  f"🔥 **{current_streak} day streak!**\n\n"
                  f"{'👑 Legendary!' if current_streak >= 30 else '⚡ Week streak! Amazing!' if current_streak >= 7 else '🔥 3 days! Keep going!' if current_streak >= 3 else '✨ Good start!'}\n\n"
                  f"📥 Download daily to keep it going!")

@app.on_message(filters.command("subscribe"))
async def subscribe(_, m: Message):
    user_id = m.from_user.id
    if db.is_subscribed(user_id):
        await m.reply("🔔 Already subscribed!\nUse `/unsubscribe` to stop.")
        return
    db.ensure_user(user_id, m.from_user.first_name)
    db.set_subscribed(user_id, True)
    await m.reply("🔔 **Subscribed!**\n\nHar roz subah 9 AM par ek song milega!\nUse `/unsubscribe` to stop.")

# T

@app.on_message(filters.command("todaystats"))
async def todaystats(_, m: Message):
    update_today_stats()
    await m.reply(f"📅 **Today's Stats:**\n\n"
                  f"📥 Downloads Today: {today_downloads['count']}\n"
                  f"👥 Total Users: {db.get_total_users()}\n"
                  f"📊 Date: {datetime.date.today().strftime('%d %b %Y')}")

@app.on_message(filters.command("topartist"))
async def topartist(_, m: Message):
    parts = m.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or parts[1].strip().lower() in PLACEHOLDERS:
        await m.reply("❌ Example: `/topartist Arijit Singh`")
        return
    query = parts[1].strip()
    msg = await m.reply(f"🏆 **Top songs by:** `{query}`...")
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

@app.on_message(filters.command("topuser"))
async def topuser(_, m: Message):
    if m.chat.type.name not in ("GROUP", "SUPERGROUP"):
        await m.reply("❌ Group mein use karo!")
        return
    top = db.get_group_leaderboard(m.chat.id, 1)
    if not top:
        await m.reply("❌ No downloads in this group yet!")
        return
    await m.reply(f"🥇 **Top User in {m.chat.title}:**\n\n"
                  f"👤 **{top[0]['user_name']}**\n📥 Downloads: {top[0]['downloads']}\n\n"
                  f"🏆 `/gleaderboard` — Full ranking")

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
    text = "🏆 **Song Tournament!**\n\n**🎵 Contestants:**\n\n"
    for i, s in enumerate(songs, 1):
        text += f"{i}. {s}\n"
    text += "\n**Vote with the number of your favourite!** 🎵"
    await msg.edit(text)

@app.on_message(filters.command("trendingartist"))
async def trendingartist(_, m: Message):
    msg = await m.reply("🔥 **Fetching Trending Artists...**")
    results = []
    for q in ["trending hindi 2024", "popular bollywood 2024", "viral songs 2024"]:
        results += search_jiosaavn_multiple(q, 5)
    artists, seen_artists = [], set()
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
    # Try LastFM geo trending first
    tracks = apis.get_trending("india")
    if tracks:
        text = "🌍 **Trending in India (LastFM):**\n\n"
        for i, t in enumerate(tracks[:10], 1):
            text += f"{i}. **{t['name']}** - {t['artist']}\n"
        text += "\n📥 `/download [song name]`"
        await msg.edit(text)
        return
    # Fallback
    results = search_jiosaavn_multiple("trending india 2025 top hits", 5)
    results += search_jiosaavn_multiple("viral hindi songs 2025", 5)
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
    delta = datetime.datetime.now() - START_TIME
    total = int(delta.total_seconds())
    days, hours = total // 86400, (total % 86400) // 3600
    mins, secs = (total % 3600) // 60, total % 60
    await m.reply(f"⏰ **{BOT_NAME} Uptime:**\n\n🕐 **{days}d {hours}h {mins}m {secs}s**\n\n✅ Status: Online\n🤖 Bot: {BOT_USERNAME}")

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
    await msg.edit(f"🎭 **Vibe Analysis:**\n\n🎵 **{song_data['name']}**\n"
                   f"👤 {song_data['primaryArtists']}\n"
                   f"⏱ {mins}:{secs:02d} | 🌐 {song_data.get('language','Unknown').capitalize()}\n\n"
                   f"**Vibe:** {vibe_r}\n📝 {desc}")

@app.on_message(filters.command("votesong"))
async def votesong(_, m: Message):
    if m.chat.type.name not in ("GROUP", "SUPERGROUP"):
        await m.reply("❌ Group mein use karo!")
        return
    msg = await m.reply("📊 **Creating Song Vote...**")
    results = search_jiosaavn_multiple("popular hindi songs", 10)
    if not results:
        await msg.edit("❌ Could not fetch!")
        return
    songs = random.sample(results, min(4, len(results)))
    group_id = m.chat.id
    group_votes[group_id] = {"songs": [s["name"] for s in songs], "votes": {}, "active": True}
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🎵 {songs[0]['name'][:20]}", callback_data=f"vote_{group_id}_0"),
         InlineKeyboardButton(f"🎵 {songs[1]['name'][:20]}", callback_data=f"vote_{group_id}_1")],
        [InlineKeyboardButton(f"🎵 {songs[2]['name'][:20]}", callback_data=f"vote_{group_id}_2"),
         InlineKeyboardButton(f"🎵 {songs[3]['name'][:20]}", callback_data=f"vote_{group_id}_3")] if len(songs) > 3 else []
    ])
    text = "📊 **Group Song Vote!**\n\nKaunsa song download karein?\n\n"
    for i, s in enumerate(songs, 1):
        text += f"{i}. {s['name']}\n"
    text += "\n⏱ 30 seconds!"
    await msg.edit(text, reply_markup=keyboard)
    await asyncio.sleep(30)
    if group_id in group_votes and group_votes[group_id].get("active"):
        votes = group_votes[group_id]["votes"]
        song_names = group_votes[group_id]["songs"]
        counts = [sum(1 for v in votes.values() if v == i) for i in range(len(song_names))]
        winner_idx = counts.index(max(counts))
        winner = song_names[winner_idx]
        del group_votes[group_id]
        result_text = "📊 **Vote Result!**\n\n"
        for i, (s, c) in enumerate(zip(song_names, counts)):
            result_text += f"{'👑 ' if i == winner_idx else '  '}**{s}**: {c} votes\n"
        result_text += f"\n🏆 **Winner: {winner}!**\n📥 `/download {winner}`"
        await m.reply(result_text)

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
        await m.reply("❌ Valid year likho (1990-2025)!")
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
    songs_with_year = [s for s in results if str(s.get("year", "")).isdigit()]
    if not songs_with_year:
        await msg.edit("❌ Could not fetch! Try again.")
        return
    song = random.choice(songs_with_year)
    title, artist, correct_year = song["name"], song["primaryArtists"], song["year"]
    active_quiz[chat_id] = {"answer": correct_year, "title": title, "artist": artist, "type": "yeargame"}
    await msg.edit(f"📅 **Year Guess Game!**\n\n🎵 **Song:** {title}\n👤 **Artist:** {artist}\n\n"
                   f"❓ **Which year was this released?**\n\n💭 Reply with the year!\n⏱ 20 seconds!")
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
                db.ensure_user(m.from_user.id, m.from_user.first_name)
                db.add_xp(m.from_user.id, XP_REWARDS["quiz_win"])
                await m.reply(f"✅ **Correct! {m.from_user.first_name}!** 🎉\n"
                              f"🎵 **{quiz['title']}** by {quiz['artist']}\n"
                              f"✨ **+{XP_REWARDS['quiz_win']} XP earned!**\n\n"
                              f"📥 `/download {quiz['title']}`")
            else:
                await m.reply(f"❌ **Wrong!** Try again!\n💡 Starts with **{quiz['title'][0]}**")

    elif quiz_type == "fillblank":
        if user_ans == correct or correct in user_ans:
            del active_quiz[chat_id]
            db.ensure_user(m.from_user.id, m.from_user.first_name)
            db.add_xp(m.from_user.id, XP_REWARDS["quiz_win"])
            await m.reply(f"✅ **Correct! {m.from_user.first_name}!** 🎉\n"
                          f"Word: **{correct}** | Song: **{quiz['title']}**\n"
                          f"✨ **+{XP_REWARDS['quiz_win']} XP!**")
        else:
            await m.reply(f"❌ **Wrong!** Starts with **{correct[0]}**")

    elif quiz_type == "yeargame":
        if user_ans == correct:
            del active_quiz[chat_id]
            db.ensure_user(m.from_user.id, m.from_user.first_name)
            db.add_xp(m.from_user.id, XP_REWARDS["quiz_win"])
            await m.reply(f"✅ **Correct! {m.from_user.first_name}!** 🎉\nYear: **{correct}**\n✨ **+{XP_REWARDS['quiz_win']} XP!**")
        else:
            try:
                diff = abs(int(user_ans) - int(correct))
                hint = "🔥 Very close!" if diff <= 2 else "📅 Try again!"
                await m.reply(f"❌ **Wrong!** {hint}")
            except:
                await m.reply("❌ Year number likho!")

    else:  # guess
        if any(w in user_ans for w in correct.split() if len(w) > 3):
            del active_quiz[chat_id]
            db.ensure_user(m.from_user.id, m.from_user.first_name)
            db.add_xp(m.from_user.id, XP_REWARDS["quiz_win"])
            await m.reply(f"✅ **Correct! {m.from_user.first_name}!** 🎉\n"
                          f"🎵 **{quiz['title']}** by {quiz['artist']}\n"
                          f"✨ **+{XP_REWARDS['quiz_win']} XP!**\n\n"
                          f"📥 `/download {quiz['title']}`")

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
    global pytgcalls  # MUST be first line
    await app.start()
    db.init_db()
    print(f"✅ {BOT_NAME} started!")
    

    # Start userbot + pytgcalls if configured
    if userbot:
        try:
            # Register stream end handler BEFORE starting
            @pytgcalls.on_stream_end()
            async def on_stream_end(client, update):
                chat_id = update.chat_id
                if vc_queue.get(chat_id):
                    next_song = vc_queue[chat_id].pop(0)
                    await start_playing(chat_id, next_song)
                    try:
                        await app.send_message(
                            chat_id,
                            f"▶️ **Now Playing:**\n🎵 {next_song['title']}\n👤 {next_song['requested_by']}"
                        )
                    except: pass
                else:
                    
                    try:
                        await pytgcalls.leave_group_call(chat_id)
                    except: pass

            # Start userbot first
            print("[VC] Starting userbot...")
            await userbot.start()
            print("✅ Userbot started!")

            # Initialize pytgcalls NOW after userbot is connected
            from pytgcalls import PyTgCalls as _PTC
            pytgcalls = _PTC(userbot)
            print("✅ PyTgCalls created!")

            # Start pytgcalls
            await pytgcalls.start()
            print("✅ PyTgCalls started!")

        except Exception as e:
            import traceback
            print(f"⚠️ VC Error: {e}")
            print(traceback.format_exc())
    else:
        print("⚠️ USER_STRING_SESSION not set — VC disabled")

    asyncio.create_task(send_daily_songs())
    await asyncio.Event().wait()

app.run(main())
