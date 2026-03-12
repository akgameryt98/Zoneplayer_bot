import sqlite3
import datetime
import json
import os

DB_PATH = "beatnova.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()

    # Users table
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            joined TEXT,
            downloads INTEGER DEFAULT 0,
            streak INTEGER DEFAULT 0,
            last_active TEXT,
            subscribed INTEGER DEFAULT 0,
            invite_points INTEGER DEFAULT 0
        )
    """)

    # Songs history per user
    c.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            song TEXT,
            downloaded_at TEXT
        )
    """)

    # Favorites per user
    c.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            song TEXT,
            UNIQUE(user_id, song)
        )
    """)

    # Wishlist per user
    c.execute("""
        CREATE TABLE IF NOT EXISTS wishlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            song TEXT,
            UNIQUE(user_id, song)
        )
    """)

    # Song notes per user
    c.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            song TEXT,
            note TEXT,
            UNIQUE(user_id, song)
        )
    """)

    # Song ratings
    c.execute("""
        CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            song TEXT,
            rating INTEGER,
            UNIQUE(user_id, song)
        )
    """)

    # Global song stats
    c.execute("""
        CREATE TABLE IF NOT EXISTS song_stats (
            song TEXT PRIMARY KEY,
            downloads INTEGER DEFAULT 0,
            favorites INTEGER DEFAULT 0
        )
    """)

    # Bot-wide stats
    c.execute("""
        CREATE TABLE IF NOT EXISTS bot_stats (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Last downloaded per user
    c.execute("""
        CREATE TABLE IF NOT EXISTS last_downloaded (
            user_id INTEGER PRIMARY KEY,
            title TEXT,
            duration TEXT,
            by_name TEXT
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Database initialized!")

# ========== USER FUNCTIONS ==========

def get_user(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def ensure_user(user_id, name):
    conn = get_conn()
    c = conn.cursor()
    today = datetime.date.today().isoformat()
    now = datetime.datetime.now().strftime("%d %b %Y")
    c.execute("""
        INSERT INTO users (user_id, name, joined, downloads, streak, last_active)
        VALUES (?, ?, ?, 0, 0, ?)
        ON CONFLICT(user_id) DO UPDATE SET name = excluded.name
    """, (user_id, name, now, today))
    conn.commit()
    conn.close()

def update_streak(user_id):
    conn = get_conn()
    c = conn.cursor()
    today = datetime.date.today().isoformat()
    c.execute("SELECT last_active, streak FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if row:
        last = row["last_active"]
        streak = row["streak"] or 0
        if last:
            diff = (datetime.date.today() - datetime.date.fromisoformat(last)).days
            if diff == 1:
                streak += 1
            elif diff > 1:
                streak = 1
        else:
            streak = 1
        c.execute("UPDATE users SET streak = ?, last_active = ? WHERE user_id = ?", (streak, today, user_id))
    conn.commit()
    conn.close()

def increment_downloads(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET downloads = downloads + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_all_users():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users ORDER BY downloads DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_subscribers():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE subscribed = 1")
    rows = c.fetchall()
    conn.close()
    return [r["user_id"] for r in rows]

def set_subscribed(user_id, value):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET subscribed = ? WHERE user_id = ?", (1 if value else 0, user_id))
    conn.commit()
    conn.close()

def is_subscribed(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT subscribed FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return bool(row and row["subscribed"])

# ========== HISTORY ==========

def add_history(user_id, song):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.datetime.now().isoformat()
    c.execute("INSERT INTO history (user_id, song, downloaded_at) VALUES (?, ?, ?)", (user_id, song, now))
    conn.commit()
    conn.close()

def get_history(user_id, limit=10):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT song FROM history WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))
    rows = c.fetchall()
    conn.close()
    return [r["song"] for r in rows]

# ========== FAVORITES ==========

def add_favorite(user_id, song):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO favorites (user_id, song) VALUES (?, ?)", (user_id, song))
        conn.commit()
        result = True
    except sqlite3.IntegrityError:
        result = False
    conn.close()
    return result

def remove_favorite(user_id, song):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM favorites WHERE user_id = ? AND song = ?", (user_id, song))
    changed = c.rowcount > 0
    conn.commit()
    conn.close()
    return changed

def get_favorites(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT song FROM favorites WHERE user_id = ?", (user_id,))
    rows = c.fetchall()
    conn.close()
    return [r["song"] for r in rows]

def count_favorites(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as cnt FROM favorites WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row["cnt"] if row else 0

def is_favorite(user_id, song):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT 1 FROM favorites WHERE user_id = ? AND song = ?", (user_id, song))
    result = c.fetchone() is not None
    conn.close()
    return result

# ========== WISHLIST ==========

def add_wishlist(user_id, song):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO wishlist (user_id, song) VALUES (?, ?)", (user_id, song))
        conn.commit()
        result = True
    except sqlite3.IntegrityError:
        result = False
    conn.close()
    return result

def get_wishlist(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT song FROM wishlist WHERE user_id = ?", (user_id,))
    rows = c.fetchall()
    conn.close()
    return [r["song"] for r in rows]

# ========== NOTES ==========

def save_note(user_id, song, note):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO notes (user_id, song, note) VALUES (?, ?, ?)
        ON CONFLICT(user_id, song) DO UPDATE SET note = excluded.note
    """, (user_id, song, note))
    conn.commit()
    conn.close()

# ========== RATINGS ==========

def save_rating(user_id, song, rating):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO ratings (user_id, song, rating) VALUES (?, ?, ?)
        ON CONFLICT(user_id, song) DO UPDATE SET rating = excluded.rating
    """, (user_id, song, rating))
    conn.commit()
    conn.close()

def get_song_ratings(song):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT rating FROM ratings WHERE song = ?", (song,))
    rows = c.fetchall()
    conn.close()
    return [r["rating"] for r in rows]

def get_avg_rating(song):
    ratings = get_song_ratings(song)
    if not ratings: return 0, 0
    return sum(ratings) / len(ratings), len(ratings)

def get_top_rated_songs(limit=10):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT song, AVG(rating) as avg_r, COUNT(*) as cnt
        FROM ratings GROUP BY song
        ORDER BY avg_r DESC LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def user_rated_count(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as cnt FROM ratings WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row["cnt"] if row else 0

# ========== SONG GLOBAL STATS ==========

def increment_song_downloads(song):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO song_stats (song, downloads, favorites) VALUES (?, 1, 0)
        ON CONFLICT(song) DO UPDATE SET downloads = downloads + 1
    """, (song,))
    conn.commit()
    conn.close()

def increment_song_favorites(song):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO song_stats (song, downloads, favorites) VALUES (?, 0, 1)
        ON CONFLICT(song) DO UPDATE SET favorites = favorites + 1
    """, (song,))
    conn.commit()
    conn.close()

def get_song_global_stats(song):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM song_stats WHERE song = ?", (song,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else {"song": song, "downloads": 0, "favorites": 0}

# ========== BOT STATS ==========

def get_bot_stat(key, default="0"):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT value FROM bot_stats WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row["value"] if row else default

def set_bot_stat(key, value):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO bot_stats (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (key, str(value)))
    conn.commit()
    conn.close()

def increment_bot_stat(key):
    conn = get_conn()
    c = conn.cursor()
    current = int(get_bot_stat(key, "0"))
    new_val = current + 1
    c.execute("""
        INSERT INTO bot_stats (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (key, str(new_val)))
    conn.commit()
    conn.close()
    return new_val

def get_total_users():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as cnt FROM users")
    row = c.fetchone()
    conn.close()
    return row["cnt"] if row else 0

def get_total_downloads():
    return int(get_bot_stat("total_downloads", "0"))

# ========== LAST DOWNLOADED ==========

def save_last_downloaded(user_id, title, duration, by_name):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO last_downloaded (user_id, title, duration, by_name) VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET title=excluded.title, duration=excluded.duration, by_name=excluded.by_name
    """, (user_id, title, duration, by_name))
    conn.commit()
    conn.close()

def get_last_downloaded(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM last_downloaded WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None
