# apis.py - BeatNova Multi-API Music System
# APIs: saavn.dev, JioSaavn fallback, iTunes, Deezer, LastFM
import requests
import random

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; BeatNovaBot/1.0)"}
TIMEOUT = 15

# ==================== JIOSAAVN (Primary - Hindi/Indian) ====================

def _saavn_dev(query, limit=10):
    """saavn.dev - newer, more stable JioSaavn API"""
    try:
        r = requests.get(
            f"https://saavn.dev/api/search/songs",
            params={"query": query, "limit": limit, "page": 1},
            headers=HEADERS, timeout=TIMEOUT
        )
        data = r.json()
        results = data.get("data", {}).get("results", [])
        out = []
        for s in results:
            dl_urls = s.get("downloadUrl", [])
            dl_url = dl_urls[-1]["url"] if dl_urls else None
            if not dl_url:
                continue
            out.append({
                "source": "jiosaavn",
                "name": s.get("name", "Unknown"),
                "artist": ", ".join(a["name"] for a in s.get("artists", {}).get("primary", [])) or "Unknown",
                "album": s.get("album", {}).get("name", "Unknown"),
                "year": s.get("year", "Unknown"),
                "duration": int(s.get("duration", 0)),
                "language": s.get("language", "hindi").capitalize(),
                "download_url": dl_url,
                "preview_url": dl_url,
                "image": s.get("image", [{}])[-1].get("url", ""),
                "id": s.get("id", ""),
                "quality": "320kbps",
            })
        return out
    except Exception as e:
        print(f"[saavn.dev] Error: {e}")
        return []

def _saavn_old(query, limit=10):
    """jiosaavn-api-privatecvc2 - old fallback"""
    try:
        r = requests.get(
            f"https://jiosaavn-api-privatecvc2.vercel.app/search/songs",
            params={"query": query, "page": 1, "limit": limit},
            headers=HEADERS, timeout=TIMEOUT
        )
        results = r.json()["data"]["results"]
        out = []
        for s in results:
            dl_urls = s.get("downloadUrl", [])
            dl_url = dl_urls[-1]["link"] if dl_urls else None
            if not dl_url:
                continue
            out.append({
                "source": "jiosaavn",
                "name": s.get("name", "Unknown"),
                "artist": s.get("primaryArtists", "Unknown"),
                "album": s.get("album", {}).get("name", "Unknown"),
                "year": s.get("year", "Unknown"),
                "duration": int(s.get("duration", 0)),
                "language": s.get("language", "hindi").capitalize(),
                "download_url": dl_url,
                "preview_url": dl_url,
                "image": "",
                "id": s.get("id", ""),
                "quality": "320kbps",
            })
        return out
    except Exception as e:
        print(f"[saavn_old] Error: {e}")
        return []

def _saavn_quality(query, quality="320", limit=10):
    """JioSaavn with specific quality"""
    try:
        r = requests.get(
            f"https://saavn.dev/api/search/songs",
            params={"query": query, "limit": limit},
            headers=HEADERS, timeout=TIMEOUT
        )
        results = r.json().get("data", {}).get("results", [])
        if not results:
            # fallback
            r2 = requests.get(
                f"https://jiosaavn-api-privatecvc2.vercel.app/search/songs",
                params={"query": query, "page": 1, "limit": limit},
                headers=HEADERS, timeout=TIMEOUT
            )
            results_old = r2.json()["data"]["results"]
            if results_old:
                s = results_old[0]
                dl_urls = s.get("downloadUrl", [])
                q_map = {"128": 0, "192": 1, "320": -1}
                try:
                    dl_url = dl_urls[q_map.get(quality, -1)]["link"]
                except:
                    dl_url = dl_urls[-1]["link"] if dl_urls else None
                if not dl_url:
                    return None
                return {
                    "source": "jiosaavn",
                    "name": s.get("name", "Unknown"),
                    "artist": s.get("primaryArtists", "Unknown"),
                    "album": s.get("album", {}).get("name", "Unknown"),
                    "year": s.get("year", "Unknown"),
                    "duration": int(s.get("duration", 0)),
                    "language": s.get("language", "hindi").capitalize(),
                    "download_url": dl_url,
                    "preview_url": dl_url,
                    "image": "",
                    "id": s.get("id", ""),
                    "quality": f"{quality}kbps",
                }
            return None

        s = results[0]
        dl_urls = s.get("downloadUrl", [])
        q_map = {"128": 0, "192": 1, "320": -1}
        try:
            dl_url = dl_urls[q_map.get(quality, -1)]["url"]
        except:
            dl_url = dl_urls[-1]["url"] if dl_urls else None
        if not dl_url:
            return None
        return {
            "source": "jiosaavn",
            "name": s.get("name", "Unknown"),
            "artist": ", ".join(a["name"] for a in s.get("artists", {}).get("primary", [])) or "Unknown",
            "album": s.get("album", {}).get("name", "Unknown"),
            "year": s.get("year", "Unknown"),
            "duration": int(s.get("duration", 0)),
            "language": s.get("language", "hindi").capitalize(),
            "download_url": dl_url,
            "preview_url": dl_url,
            "image": s.get("image", [{}])[-1].get("url", ""),
            "id": s.get("id", ""),
            "quality": f"{quality}kbps",
        }
    except Exception as e:
        print(f"[saavn_quality] Error: {e}")
        return None

# ==================== DEEZER (International - All Languages) ====================

def _deezer_search(query, limit=10):
    """Deezer - free, no auth, all languages"""
    try:
        r = requests.get(
            "https://api.deezer.com/search",
            params={"q": query, "limit": limit},
            headers=HEADERS, timeout=TIMEOUT
        )
        results = r.json().get("data", [])
        out = []
        for s in results:
            preview = s.get("preview", "")
            out.append({
                "source": "deezer",
                "name": s.get("title", "Unknown"),
                "artist": s.get("artist", {}).get("name", "Unknown"),
                "album": s.get("album", {}).get("title", "Unknown"),
                "year": "Unknown",
                "duration": int(s.get("duration", 0)),
                "language": "Unknown",
                "download_url": preview,  # 30sec preview only
                "preview_url": preview,
                "image": s.get("album", {}).get("cover_medium", ""),
                "id": str(s.get("id", "")),
                "quality": "preview",
                "deezer_id": s.get("id"),
            })
        return out
    except Exception as e:
        print(f"[deezer] Error: {e}")
        return []

def _deezer_track(track_id):
    """Get Deezer track details"""
    try:
        r = requests.get(f"https://api.deezer.com/track/{track_id}", headers=HEADERS, timeout=TIMEOUT)
        return r.json()
    except:
        return {}

# ==================== ITUNES (Apple - All Languages, Official) ====================

def _itunes_search(query, limit=10, country="IN"):
    """iTunes Search API - completely free, official, all languages"""
    try:
        r = requests.get(
            "https://itunes.apple.com/search",
            params={
                "term": query,
                "media": "music",
                "entity": "song",
                "limit": limit,
                "country": country,
            },
            headers=HEADERS, timeout=TIMEOUT
        )
        results = r.json().get("results", [])
        out = []
        for s in results:
            preview = s.get("previewUrl", "")
            duration_ms = s.get("trackTimeMillis", 0)
            out.append({
                "source": "itunes",
                "name": s.get("trackName", "Unknown"),
                "artist": s.get("artistName", "Unknown"),
                "album": s.get("collectionName", "Unknown"),
                "year": s.get("releaseDate", "")[:4] if s.get("releaseDate") else "Unknown",
                "duration": duration_ms // 1000,
                "language": s.get("primaryGenreName", "Unknown"),
                "download_url": preview,  # 30sec preview
                "preview_url": preview,
                "image": s.get("artworkUrl100", "").replace("100x100", "600x600"),
                "id": str(s.get("trackId", "")),
                "quality": "preview",
                "genre": s.get("primaryGenreName", ""),
                "explicit": s.get("trackExplicitness", "") == "explicit",
            })
        return out
    except Exception as e:
        print(f"[itunes] Error: {e}")
        return []

# ==================== LASTFM (Info & Discovery) ====================

LASTFM_KEY = "c9b16bfc1f90c14d1e3b20a5d7c2fead"  # Public demo key - works for search

def _lastfm_search(query, limit=10):
    """LastFM - great for artist/track info and similar tracks"""
    try:
        r = requests.get(
            "https://ws.audioscrobbler.com/2.0/",
            params={
                "method": "track.search",
                "track": query,
                "api_key": LASTFM_KEY,
                "format": "json",
                "limit": limit,
            },
            headers=HEADERS, timeout=TIMEOUT
        )
        tracks = r.json().get("results", {}).get("trackmatches", {}).get("track", [])
        out = []
        for s in tracks:
            out.append({
                "source": "lastfm",
                "name": s.get("name", "Unknown"),
                "artist": s.get("artist", "Unknown"),
                "album": "Unknown",
                "year": "Unknown",
                "duration": 0,
                "language": "Unknown",
                "download_url": None,
                "preview_url": None,
                "image": s.get("image", [{}])[-1].get("#text", ""),
                "id": s.get("mbid", ""),
                "quality": "info_only",
            })
        return out
    except Exception as e:
        print(f"[lastfm] Error: {e}")
        return []

def _lastfm_similar(artist, track, limit=10):
    """Get similar tracks from LastFM"""
    try:
        r = requests.get(
            "https://ws.audioscrobbler.com/2.0/",
            params={
                "method": "track.getSimilar",
                "artist": artist,
                "track": track,
                "api_key": LASTFM_KEY,
                "format": "json",
                "limit": limit,
            },
            headers=HEADERS, timeout=TIMEOUT
        )
        tracks = r.json().get("similartracks", {}).get("track", [])
        return [{"name": t["name"], "artist": t["artist"]["name"]} for t in tracks]
    except:
        return []

def _lastfm_artist_info(artist):
    """Get artist info from LastFM"""
    try:
        r = requests.get(
            "https://ws.audioscrobbler.com/2.0/",
            params={
                "method": "artist.getInfo",
                "artist": artist,
                "api_key": LASTFM_KEY,
                "format": "json",
            },
            headers=HEADERS, timeout=TIMEOUT
        )
        data = r.json().get("artist", {})
        return {
            "name": data.get("name", artist),
            "listeners": data.get("stats", {}).get("listeners", "Unknown"),
            "playcount": data.get("stats", {}).get("playcount", "Unknown"),
            "bio": data.get("bio", {}).get("summary", "").split("<a")[0].strip()[:300],
            "similar": [a["name"] for a in data.get("similar", {}).get("artist", [])[:5]],
            "tags": [t["name"] for t in data.get("tags", {}).get("tag", [])[:5]],
        }
    except:
        return {}

def _lastfm_top_tracks(artist, limit=10):
    """Get artist top tracks"""
    try:
        r = requests.get(
            "https://ws.audioscrobbler.com/2.0/",
            params={
                "method": "artist.getTopTracks",
                "artist": artist,
                "api_key": LASTFM_KEY,
                "format": "json",
                "limit": limit,
            },
            headers=HEADERS, timeout=TIMEOUT
        )
        tracks = r.json().get("toptracks", {}).get("track", [])
        return [{"name": t["name"], "playcount": t.get("playcount", 0)} for t in tracks]
    except:
        return []

def _lastfm_trending(country="india", limit=10):
    """Get trending tracks by country"""
    try:
        r = requests.get(
            "https://ws.audioscrobbler.com/2.0/",
            params={
                "method": "geo.getTopTracks",
                "country": country,
                "api_key": LASTFM_KEY,
                "format": "json",
                "limit": limit,
            },
            headers=HEADERS, timeout=TIMEOUT
        )
        tracks = r.json().get("tracks", {}).get("track", [])
        return [{"name": t["name"], "artist": t["artist"]["name"]} for t in tracks]
    except:
        return []

def _lastfm_similar_artists(artist, limit=8):
    """Get similar artists"""
    try:
        r = requests.get(
            "https://ws.audioscrobbler.com/2.0/",
            params={
                "method": "artist.getSimilar",
                "artist": artist,
                "api_key": LASTFM_KEY,
                "format": "json",
                "limit": limit,
            },
            headers=HEADERS, timeout=TIMEOUT
        )
        artists = r.json().get("similarartists", {}).get("artist", [])
        return [a["name"] for a in artists]
    except:
        return []

# ==================== UNIFIED SEARCH FUNCTIONS ====================

def detect_language(query):
    """Detect if query is Hindi/Indian or English/International"""
    hindi_chars = set("अआइईउऊएऐओऔकखगघचछजझटठडढणतथदधनपफबभमयरलवशषसह")
    if any(c in hindi_chars for c in query):
        return "hindi"
    hindi_words = ["tum", "dil", "pyar", "ishq", "tera", "mera", "yaar", "aaj", "kal",
                   "raat", "din", "phir", "kuch", "main", "hum", "hai", "ho", "kar",
                   "mere", "teri", "mohabbat", "zindagi", "duniya", "woh", "aur"]
    q_lower = query.lower()
    if any(w in q_lower.split() for w in hindi_words):
        return "hindi"
    return "international"

def search_songs(query, limit=10):
    """
    Smart multi-API search:
    - Hindi/Indian → JioSaavn primary, Deezer fallback
    - English/International → Deezer + iTunes primary, JioSaavn fallback
    - Always returns best results from available source
    """
    lang = detect_language(query)
    results = []

    if lang == "hindi":
        # Try saavn.dev first
        results = _saavn_dev(query, limit)
        if not results:
            results = _saavn_old(query, limit)
        if not results:
            # Fallback to Deezer
            deezer = _deezer_search(query, limit)
            results = deezer
    else:
        # International: Deezer + iTunes
        results = _deezer_search(query, limit)
        if len(results) < 3:
            itunes = _itunes_search(query, limit)
            results = results + itunes
        # Also try JioSaavn for any Indian content
        if len(results) < 5:
            saavn = _saavn_dev(query, 5)
            if not saavn:
                saavn = _saavn_old(query, 5)
            results = results + saavn

    return results[:limit]

def search_song_download(query, quality="320"):
    """
    Get best downloadable song:
    - JioSaavn for full quality (320kbps)
    - iTunes/Deezer for preview if JioSaavn fails
    """
    # Always try JioSaavn first for full quality
    song = _saavn_quality(query, quality)
    if song:
        return song

    # Fallback: Deezer preview
    deezer = _deezer_search(query, 3)
    if deezer:
        s = deezer[0]
        if s["download_url"]:
            s["quality"] = "preview (30sec)"
            return s

    # Fallback: iTunes preview
    itunes = _itunes_search(query, 3)
    if itunes:
        s = itunes[0]
        if s["download_url"]:
            s["quality"] = "preview (30sec)"
            return s

    return None

def get_similar_tracks(artist, track, query_fallback=""):
    """Get similar tracks using LastFM + JioSaavn"""
    similar = _lastfm_similar(artist, track, 10)
    if similar:
        return similar
    # Fallback: search based on artist
    results = search_songs(f"{artist} songs", 8)
    return [{"name": r["name"], "artist": r["artist"]} for r in results]

def get_trending(country="india"):
    """Get trending tracks for a country"""
    tracks = _lastfm_trending(country, 10)
    if tracks:
        return tracks
    # Fallback
    if country.lower() in ["india", "hindi"]:
        results = search_songs("trending hindi bollywood 2025", 10)
    else:
        results = search_songs(f"trending {country} 2025", 10)
    return [{"name": r["name"], "artist": r["artist"]} for r in results]

def get_artist_info(artist_name):
    """Get full artist info from LastFM"""
    return _lastfm_artist_info(artist_name)

def get_artist_top_tracks(artist_name, limit=10):
    """Get artist's top tracks with download links"""
    # Get track names from LastFM
    tracks = _lastfm_top_tracks(artist_name, limit)
    if tracks:
        return [{"name": t["name"], "artist": artist_name, "playcount": t["playcount"]} for t in tracks]
    # Fallback to JioSaavn
    results = search_songs(f"best of {artist_name}", limit)
    return [{"name": r["name"], "artist": r["artist"], "playcount": 0} for r in results]

def get_similar_artists(artist_name):
    """Get similar artists from LastFM"""
    similar = _lastfm_similar_artists(artist_name, 8)
    if similar:
        return similar
    # Fallback: search
    results = search_songs(f"artists like {artist_name}", 8)
    seen = set()
    artists = []
    for r in results:
        a = r["artist"].split(",")[0].strip()
        if a not in seen and a.lower() != artist_name.lower():
            seen.add(a)
            artists.append(a)
    return artists[:6]

def search_by_language(language, limit=10):
    """Search songs by specific language"""
    lang_queries = {
        # Indian
        "hindi": "hindi popular songs 2024",
        "punjabi": "punjabi top hits 2024",
        "tamil": "tamil top songs 2024",
        "telugu": "telugu hits 2024",
        "marathi": "marathi songs popular",
        "bengali": "bengali songs popular",
        "gujarati": "gujarati songs popular",
        "bhojpuri": "bhojpuri songs hits",
        "kannada": "kannada songs popular",
        "malayalam": "malayalam songs hits",
        "rajasthani": "rajasthani folk songs",
        "odia": "odia songs popular",
        # International
        "english": "top english hits 2024",
        "spanish": "top spanish songs 2024",
        "french": "top french songs 2024",
        "korean": "kpop hits 2024",
        "japanese": "jpop anime songs 2024",
        "arabic": "arabic songs popular",
        "portuguese": "portuguese brazilian songs",
        "italian": "italian songs popular",
        "german": "german songs popular",
        "turkish": "turkish songs popular",
        "russian": "russian songs popular",
        "persian": "persian iranian songs",
        "urdu": "urdu ghazal songs",
        "nepali": "nepali songs popular",
        "sinhala": "sinhala songs popular",
    }
    query = lang_queries.get(language.lower(), f"{language} songs popular")
    return search_songs(query, limit)

def search_genre(genre, limit=10):
    """Search by music genre"""
    genre_queries = {
        "rock": "rock songs hits",
        "pop": "pop hits 2024",
        "jazz": "jazz music classic",
        "classical": "classical music instrumental",
        "rap": "rap hip hop hits",
        "indie": "indie songs 2024",
        "sufi": "sufi songs qawwali",
        "folk": "folk music traditional",
        "electronic": "electronic edm music",
        "blues": "blues music classic",
        "reggae": "reggae songs popular",
        "country": "country music hits",
        "metal": "metal rock songs",
        "rnb": "r&b soul music hits",
        "lofi": "lofi hip hop chill",
        "kpop": "kpop bts blackpink hits",
        "ghazal": "ghazal urdu hindi songs",
        "devotional": "bhajan aarti devotional songs",
        "qawwali": "qawwali nusrat fateh songs",
        "classical_indian": "raag classical indian music",
    }
    query = genre_queries.get(genre.lower(), f"{genre} songs")
    return search_songs(query, limit)

def format_song_info(song):
    """Format song dict to display string"""
    if not song:
        return "Unknown Song"
    duration = song.get("duration", 0)
    mins, secs = duration // 60, duration % 60
    source_emoji = {"jiosaavn": "🎵", "deezer": "🎧", "itunes": "🍎", "lastfm": "🎼"}.get(song.get("source", ""), "🎵")
    return (f"{source_emoji} **{song['name']}**\n"
            f"👤 {song['artist']}\n"
            f"💿 {song.get('album', 'Unknown')} | 📅 {song.get('year', '?')}\n"
            f"⏱ {mins}:{secs:02d} | 🌐 {song.get('language', '?')} | 🎧 {song.get('quality', '?')}")
