## SETTING UP
# 1. Activate the virtual environment (or create a new one)
#    source ../spotify-telegram-bot/bin/activate
# 2. Install requirements
#    pip install -r requirements.txt
# 3. Run the revamped bot
#    python main.py

import asyncio
import html
import logging
import os
import random
import re
import subprocess
import sys
import time
from threading import Timer

from dotenv import load_dotenv
from lyricsgenius import Genius
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonCommands,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Base directory so .env and .cache resolve regardless of working directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load environment variables from .env file (AI API keys intentionally disabled)
load_dotenv(os.path.join(BASE_DIR, ".env"))

# For logging purposes
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Spotify authentication
# Scope determines permissions (e.g. modifying playback state, reading/modifying playlists and library)
SCOPE = (
    "user-library-read,user-read-playback-state,user-modify-playback-state,"
    "user-read-currently-playing,user-library-modify,playlist-read-private,"
    "playlist-modify-public,playlist-modify-private"
)
sp = spotipy.Spotify(
    auth_manager=SpotifyOAuth(
        scope=SCOPE,
        cache_path=os.path.join(BASE_DIR, ".cache"),
        open_browser=False,
    )
)

# Genius API for lyrics (non-AI)
genius_token = os.getenv("GENIUS_ACCESS_TOKEN")
genius = Genius(genius_token) if genius_token else None

# Telegram Bot Token
telegram_access_token = os.getenv("TELEGRAM_ACCESS_TOKEN")

# Allowed Telegram user IDs for single-user private mode (comma-separated in .env)
allowed_ids_raw = os.getenv("ALLOWED_TELEGRAM_USER_IDS", "").strip()
ALLOWED_USER_IDS = [int(uid.strip()) for uid in allowed_ids_raw.split(",") if uid.strip().isdigit()]

# Active Party / Salon Session State (Party Code Sharing)
active_party = {
    "active": False,
    "code": "",
    "host_id": ALLOWED_USER_IDS[0] if ALLOWED_USER_IDS else 0,
    "host_chat_id": 0,
    "guests": {},  # { user_id: {"name": str, "joined_at": float} }
    "created_at": 0,
    "queue_only": False,
}


def is_host(user) -> bool:
    """Returns True if the user is the bot owner or the registered host of the active party."""
    if not user:
        return False
    if ALLOWED_USER_IDS and user.id in ALLOWED_USER_IDS:
        return True
    if active_party.get("active") and user.id == active_party.get("host_id"):
        return True
    if not ALLOWED_USER_IDS and not active_party.get("active"):
        return True
    return False


def is_user_authorized(user) -> bool:
    """Checks if the Telegram user is allowed to control this bot."""
    if not user:
        return False
    # 1. Master/Owner is always authorized
    if ALLOWED_USER_IDS and user.id in ALLOWED_USER_IDS:
        return True
    # 2. Host of current party is authorized
    if active_party.get("active") and user.id == active_party.get("host_id"):
        return True
    # 3. Accepted guest in active party session is authorized
    if active_party.get("active") and user.id in active_party.get("guests", {}):
        return True
    # 4. If ALLOWED_USER_IDS is empty and no party mode is active: open access
    if not ALLOWED_USER_IDS and not active_party.get("active"):
        return True
    return False


UNAUTHORIZED_MESSAGE = (
    "<i>Dearest Gentle Traveler,</i>\n\n"
    "<i>I am afraid this musical salon is reserved exclusively for its master and welcomed guests. "
    "If your host has provided a party passcode, kindly type <code>/join &lt;code&gt;</code> to gain entry.</i>\n\n"
    "— <b>The Baroness</b>"
)


# ==============================================================================
# GLOBAL STATE & CACHES
# ==============================================================================

# Track details for the currently selected / playing song
song_name = ""
song_id = ""
song_artist_name = ""
song_artist_id = ""
song_preview_url = None
song_url = ""
song_album = ""
song_album_uri = ""

# Secondary recommendation links (matching original structure)
song_recommendation_2_ctn = ""
song_recommendation_2_sc = ""
song_recommendation_2_hf = ""
song_recommendation_2_r = ""
song_recommendation_2_rfa = ""
song_recommendation_2_rfm = ""

# Audio feature values for mood recommendations
audio_feature_values = []

# Cache for playlist names and devices so callback_data stays well under Telegram's 64-byte limit
playlist_cache = {}   # {playlist_id: playlist_name}
device_cache = {}     # {index_str: {"id": device_id, "name": device_name}}
search_track_cache = {}   # {index_str: track_dict}
search_artist_cache = {}  # {index_str: artist_dict}
lyrics = {}

# Conversational input mode per chat so users can type with OR without ~, *, ! prefixes
# Values: None, "search_track", "search_mood", "search_artist"
chat_input_mode = {}

# Track recently sent Chart-Topping Numbers and reset every 15 minutes (900 seconds)
sent_songs_ctn = []


def clear_list():
    global sent_songs_ctn
    sent_songs_ctn = []
    start_timer()


def start_timer():
    timer = Timer(900, clear_list)
    timer.daemon = True
    timer.start()


start_timer()


# ==============================================================================
# THE BARONESS — PRE-WRITTEN REGENCY RESPONSES (NO AI API KEYS USED)
# ==============================================================================

INTRO_RESPONSES = [
    (
        "Dearest Gentle Listener,\n\n"
        "Word has reached the drawing rooms that you are in pursuit of only the most exquisite melodies "
        "this season has to offer. Allow me to serve as your devoted arbiter of musical taste—curating "
        "chart-topping sensations, hidden gems, and compositions tailored to your very spirits.\n\n"
        "Yours in harmony,\nThe Baroness"
    ),
    (
        "Dearest Gentle Listener,\n\n"
        "How delightful it is to welcome you to our private musical salon. Whether your heart yearns "
        "for a triumphant ballad, a beloved maestro's finest work, or a serendipitous discovery, "
        "every note awaits your command.\n\n"
        "Yours in harmony,\nThe Baroness"
    ),
    (
        "Dearest Gentle Listener,\n\n"
        "It has come to my attention that silence has lingered far too long in your chambers. "
        "Fear not, for I have assembled a collection of melodies worthy of the most discerning ear.\n\n"
        "Yours in harmony,\nThe Baroness"
    ),
]

CHOICE_RESPONSES = {
    "A Chart-Topping Number": (
        "An impeccable choice. Everyone in high society is whispering about the season's most celebrated "
        "sensations—pray enjoy the reigning melody that follows."
    ),
    "A Harmonious Find": (
        "A listener of refined curiosity, I see. Pray divulge the title or lyrics you seek below, "
        "and I shall summon it from the archives at once."
    ),
    "A Melody for Your Spirits": (
        "How tender the human heart can be. Share your current disposition below—or select a mood from "
        "my parlor cards—and I hope you will find solace in what is recommended."
    ),
    "Tracks from a Beloved Maestro": (
        "Devotion to a true virtuoso is ever admirable. Name your chosen artist, and prepare to revel "
        "in their finest repertoire."
    ),
    "Tracks from a Personal Collection": (
        "There is no treasure quite like one's own private library. Pray select a collection below "
        "and enjoy the tune chosen for you."
    ),
    "Serendipity's Choice": (
        "How thrilling to surrender one's ear to fortune itself! Prepare to enjoy an unexpected melody "
        "plucked from the grand catalog."
    ),
}

SONG_QUOTES = [
    '"Every note is a whispered confession that prose alone could never dare to utter."',
    '"In the hush between two chords, the heart discovers what it truly longs for."',
    '"A single melody can turn an ordinary evening into an unforgettable affair."',
    '"Music is the only scandal that grows sweeter the more it is repeated."',
    '"Let the rhythm speak where polite society demands silence."',
    '"Even the most guarded soul must eventually waltz to a familiar refrain."',
    '"Some tunes do not merely play in the room; they linger in the memory."',
]

MOOD_PRESETS = {
    "sanguine": {
        "label": "✨ Radiant & Euphoric",
        "description": "High spirits, sparkling rhythms, and jubilant melodies.",
        "values": [0.0, 0.5, 0.65, 0.98, 0.65, 0.98, 0.0, 0.2, -10.0, 0.0, 1, 0.0, 0.3, 105.0, 150.0, 0.65, 0.98],
        "genres": ["pop", "dance", "disco", "synth-pop"],
        "search_terms": ["upbeat feel good pop", "euphoric dance hit", "happy sunshine pop"],
    },
    "saudade": {
        "label": "🥀 Melancholy & Saudade",
        "description": "Wistful, bittersweet reflections for a pensive heart.",
        "values": [0.4, 0.95, 0.2, 0.6, 0.1, 0.5, 0.0, 0.4, -20.0, -5.0, 0, 0.0, 0.2, 65.0, 110.0, 0.05, 0.38],
        "genres": ["acoustic", "indie", "sad", "piano"],
        "search_terms": ["melancholy acoustic ballad", "bittersweet indie", "sad piano song"],
    },
    "amorous": {
        "label": "🌹 Romantic & Tender",
        "description": "Velvet harmonies and swooning serenades for stolen glances.",
        "values": [0.25, 0.85, 0.4, 0.75, 0.25, 0.65, 0.0, 0.25, -15.0, -3.0, 1, 0.0, 0.2, 75.0, 120.0, 0.4, 0.8],
        "genres": ["r-n-b", "romance", "soul", "pop"],
        "search_terms": ["romantic love ballad", "timeless love song", "dreamy romance"],
    },
    "serene": {
        "label": "🍵 Serene & Tranquil",
        "description": "Gentle acoustic and classical arrangements for quiet repose.",
        "values": [0.6, 0.99, 0.15, 0.55, 0.05, 0.4, 0.1, 0.9, -25.0, -6.0, 1, 0.0, 0.15, 60.0, 105.0, 0.3, 0.7],
        "genres": ["acoustic", "classical", "chill", "ambient"],
        "search_terms": ["peaceful acoustic instrumental", "calm classical piano", "serene chill"],
    },
    "tempest": {
        "label": "⚡ Fierce & Tempestuous",
        "description": "Bold, dramatic intensity and commanding energy.",
        "values": [0.0, 0.3, 0.5, 0.9, 0.75, 1.0, 0.0, 0.3, -8.0, 0.0, 0, 0.0, 0.35, 115.0, 175.0, 0.2, 0.65],
        "genres": ["rock", "alt-rock", "electronic", "pop"],
        "search_terms": ["dramatic energetic rock", "intense anthem", "powerful dark pop"],
    },
    "reverie": {
        "label": "🌙 Midnight Reverie",
        "description": "Dreamy, atmospheric nocturnes for late-hour contemplation.",
        "values": [0.3, 0.85, 0.35, 0.7, 0.2, 0.55, 0.0, 0.5, -18.0, -4.0, 0, 0.0, 0.2, 70.0, 115.0, 0.2, 0.55],
        "genres": ["indie-pop", "chill", "mandopop", "soul"],
        "search_terms": ["late night dreamy indie", "midnight chill vibes", "nocturne dream pop"],
    },
}


def generate_intro_response() -> str:
    return random.choice(INTRO_RESPONSES)


def generate_preliminary_choice_response(user_choice: str) -> str:
    return CHOICE_RESPONSES.get(
        user_choice,
        "A most intriguing selection, Dearest Gentle Listener. Allow me to prepare your musical accompaniment.",
    )


def generate_song_writeup(s_title: str, s_artist: str, s_alb: str) -> str:
    templates = [
        (
            f"From the acclaimed collection <b>{html.escape(s_alb)}</b>, "
            f"<b>{html.escape(s_title)}</b> showcases the unmistakable artistry of "
            f"<b>{html.escape(s_artist)}</b>—a composition that continues to captivate drawing rooms far and wide."
        ),
        (
            f"Crafted with poise by <b>{html.escape(s_artist)}</b> and featured on "
            f"<b>{html.escape(s_alb)}</b>, <b>{html.escape(s_title)}</b> offers a most enchanting arrangement "
            f"for listeners of refined sensibility."
        ),
        (
            f"A standout jewel from <b>{html.escape(s_alb)}</b>, this performance of "
            f"<b>{html.escape(s_title)}</b> by <b>{html.escape(s_artist)}</b> blends elegance with irresistible charm."
        ),
    ]
    return random.choice(templates)


def generate_song_quote(s_title: str = "", s_artist: str = "") -> str:
    return random.choice(SONG_QUOTES)


def generate_mood_response(user_mood: str) -> str:
    escaped = html.escape(user_mood.strip())
    return (
        f"Dearest Gentle Listener, to feel <b>{escaped}</b> is the mark of a richly lived spirit. "
        f"Take comfort and allow the coming melody to accompany your thoughts."
    )


def generate_audio_feature_values(user_mood: str) -> list:
    mood_lower = user_mood.lower().strip()
    if mood_lower in MOOD_PRESETS:
        return MOOD_PRESETS[mood_lower]["values"]

    if any(w in mood_lower for w in ["sad", "melanchol", "saudade", "lonely", "cry", "heartbreak", "blue", "grief"]):
        return MOOD_PRESETS["saudade"]["values"]
    if any(w in mood_lower for w in ["happy", "joy", "excited", "euphor", "party", "dance", "cheer", "good", "energetic"]):
        return MOOD_PRESETS["sanguine"]["values"]
    if any(w in mood_lower for w in ["love", "roman", "crush", "tender", "sweet", "affection", "yearn"]):
        return MOOD_PRESETS["amorous"]["values"]
    if any(w in mood_lower for w in ["calm", "peace", "relax", "chill", "study", "quiet", "serene", "tranquil", "sleep"]):
        return MOOD_PRESETS["serene"]["values"]
    if any(w in mood_lower for w in ["angry", "fierce", "workout", "hype", "intense", "bold", "power", "storm"]):
        return MOOD_PRESETS["tempest"]["values"]
    return MOOD_PRESETS["reverie"]["values"]


def generate_artist_response(user_chosen_artist: str) -> str:
    titled = html.escape(user_chosen_artist.strip().title())
    return (
        f"Dearest Gentle Listener, what a splendid inclination! The evocative repertoire of "
        f"<b>{titled}</b> never fails to stir the soul—pray enjoy the performance that awaits."
    )


def clean_song_title(input_song_name: str) -> str:
    """Removes remastered, feat, live, and version suffixes without destroying hyphenated titles like 'Can't Feel My Face' or 'T-Shirt'."""
    cleaned = re.sub(
        r"\s*[\(\[](feat\.|ft\.|featuring|remaster|live|version|edit|remix|deluxe|bonus|anniversary|from the vault).*?[\)\]]",
        "",
        input_song_name,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\s*-\s*(remastered|live|radio edit|remix|acoustic|bonus track|single version|deluxe|taylor's version|from the vault).*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s*[\(\[].*?[\)\]]", "", cleaned)
    cleaned = cleaned.strip()
    return cleaned if cleaned else input_song_name


def format_song_name(input_song_name: str) -> str:
    """Backwards-compatible alias for clean_song_title."""
    return clean_song_title(input_song_name)


def clean_raw_lyrics(raw_lyrics: str) -> str:
    """Strips metadata headers, embed footers, and redundant whitespace."""
    if not raw_lyrics:
        return ""
    lines = raw_lyrics.splitlines()
    if lines and "lyrics" in lines[0].lower():
        lines = lines[1:]
    text = "\n".join(lines)
    text = re.sub(r"\d*Embed$", "", text)
    text = re.sub(r"You might also like", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def chunk_lyrics_for_telegram(title: str, lyrics_body: str, max_chunk_size: int = 3500) -> list:
    """Safely chunks lyrics along paragraph breaks so HTML entities and styling tags are never split."""
    escaped_title = html.escape(title)
    header = f"✦✦✦ <b>{escaped_title} lyrics</b> ✦✦✦\n\n"
    footer = "\n\n<i>Lyrics provided via musical archives.</i>"

    escaped_lyrics = html.escape(lyrics_body)
    formatted_lyrics = re.sub(r"\[(.*?)\]", r"<b>[\1]</b>", escaped_lyrics)

    paragraphs = formatted_lyrics.split("\n\n")
    chunks = []
    current_chunk = header

    for p in paragraphs:
        if len(current_chunk) + len(p) + 2 > max_chunk_size:
            chunks.append(current_chunk.strip())
            current_chunk = p + "\n\n"
        else:
            current_chunk += p + "\n\n"

    if current_chunk:
        current_chunk += footer
        chunks.append(current_chunk.strip())
    elif chunks:
        chunks[-1] += footer

    return chunks


def fetch_lrclib_lyrics(title: str, artist: str):
    """Retrieves lyrics from LRCLIB's official open REST API (fast, clean, no Cloudflare blocks)."""
    cleaned_t = clean_song_title(title)
    first_artist = artist.split(",")[0].split("&")[0].strip()
    headers = {"User-Agent": "BaronessSpotifyBot/2.0 (musical-salon-telegram)"}

    # 1. Direct match endpoint
    try:
        r = requests.get(
            "https://lrclib.net/api/get",
            params={"track_name": cleaned_t, "artist_name": first_artist},
            headers=headers,
            timeout=5,
        )
        if r.status_code == 200:
            data = r.json()
            plain = data.get("plainLyrics")
            if plain and len(plain.strip()) > 30:
                return data.get("trackName", cleaned_t), plain
    except Exception as e:
        logger.debug(f"LRCLIB get error: {e}")

    # 2. Search fallback
    try:
        r = requests.get(
            "https://lrclib.net/api/search",
            params={"q": f"{cleaned_t} {first_artist}"},
            headers=headers,
            timeout=5,
        )
        if r.status_code == 200:
            items = r.json()
            if isinstance(items, list):
                for item in items[:4]:
                    plain = item.get("plainLyrics")
                    if plain and len(plain.strip()) > 30:
                        return item.get("trackName", cleaned_t), plain
    except Exception as e:
        logger.debug(f"LRCLIB search error: {e}")

    return None, None


def fetch_ovh_lyrics(title: str, artist: str):
    """Retrieves lyrics from Lyrics.ovh REST API."""
    cleaned_t = clean_song_title(title)
    first_artist = artist.split(",")[0].split("&")[0].strip()
    try:
        url = f"https://api.lyrics.ovh/v1/{requests.utils.quote(first_artist)}/{requests.utils.quote(cleaned_t)}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            lyr = r.json().get("lyrics")
            if lyr and len(lyr.strip()) > 30:
                return cleaned_t, lyr
    except Exception as e:
        logger.debug(f"Lyrics.ovh error: {e}")
    return None, None


def fetch_best_lyrics(title: str, artist_str: str):
    """Multi-tiered search engine querying LRCLIB, Lyrics.ovh, and Genius."""
    cleaned_t = clean_song_title(title)
    first_artist = artist_str.split(",")[0].split("&")[0].strip()

    # Tier 1: LRCLIB (Direct REST API, fast, 0 Cloudflare blocks)
    try:
        t, lyr = fetch_lrclib_lyrics(cleaned_t, first_artist)
        if lyr:
            return t, clean_raw_lyrics(lyr)
    except Exception as e:
        logger.warning(f"Lyrics Tier 1 (LRCLIB) failed: {e}")

    # Tier 2: Lyrics.ovh (Secondary high-availability REST API)
    try:
        t, lyr = fetch_ovh_lyrics(cleaned_t, first_artist)
        if lyr:
            return t, clean_raw_lyrics(lyr)
    except Exception as e:
        logger.warning(f"Lyrics Tier 2 (Lyrics.ovh) failed: {e}")

    # Tier 3: Genius API (Scraper fallback)
    if genius:
        try:
            song = genius.search_song(title=cleaned_t, artist=first_artist)
            if song and song.lyrics and len(song.lyrics.strip()) > 30:
                return song.title, clean_raw_lyrics(song.lyrics)
        except Exception as e:
            logger.warning(f"Lyrics Tier 3 (Genius search_song) failed: {e}")

        try:
            res = genius.search_songs(f"{cleaned_t} {first_artist}")
            for hit in res.get("hits", [])[:3]:
                r = hit.get("result", {})
                url = r.get("url")
                full_t = r.get("full_title", "")
                if not url or "translation" in full_t.lower() or "tracklist" in full_t.lower():
                    continue
                lyr = genius.lyrics(song_url=url)
                if lyr and len(lyr.strip()) > 30:
                    cut_idx = full_t.find(" by")
                    clean_t = full_t[:cut_idx] if cut_idx != -1 else r.get("title", cleaned_t)
                    return clean_t, clean_raw_lyrics(lyr)
        except Exception as e:
            logger.warning(f"Lyrics Tier 3 (Genius search_songs) failed: {e}")

    return None, None


# ==============================================================================
# KEYBOARDS & CUSTOM TELEGRAM CONTROLS
# ==============================================================================

def menu_keyboard():
    return [
        [InlineKeyboardButton("A Chart-Topping Number ♭", callback_data="A Chart-Topping Number")],
        [InlineKeyboardButton("A Harmonious Find ♯", callback_data="A Harmonious Find")],
        [InlineKeyboardButton("A Melody for Your Spirits ♮", callback_data="A Melody for Your Spirits")],
        [InlineKeyboardButton("Tracks from a Beloved Maestro ♪", callback_data="Tracks from a Beloved Maestro")],
        [InlineKeyboardButton("Tracks from a Personal Collection 𝄢", callback_data="Tracks from a Personal Collection")],
        [InlineKeyboardButton("Serendipity's Choice ☾", callback_data="Serendipity's Choice")],
        [
            InlineKeyboardButton("In the Spotlight ✧", callback_data="get_current_song"),
            InlineKeyboardButton("Control Deck 🎛", callback_data="open_controls"),
        ],
    ]


def mood_preset_keyboard():
    return [
        [
            InlineKeyboardButton("✨ Radiant & Euphoric", callback_data="MOOD:sanguine"),
            InlineKeyboardButton("🥀 Melancholy & Saudade", callback_data="MOOD:saudade"),
        ],
        [
            InlineKeyboardButton("🌹 Romantic & Tender", callback_data="MOOD:amorous"),
            InlineKeyboardButton("🍵 Serene & Tranquil", callback_data="MOOD:serene"),
        ],
        [
            InlineKeyboardButton("⚡ Fierce & Tempestuous", callback_data="MOOD:tempest"),
            InlineKeyboardButton("🌙 Midnight Reverie", callback_data="MOOD:reverie"),
        ],
        [InlineKeyboardButton("📜 Back to Salon Menu", callback_data="main_menu")],
    ]


def playback_keyboard():
    """Revamped custom control panel on Telegram."""
    return [
        # Row 1: Core Transport
        [
            InlineKeyboardButton("⏮ Prev", callback_data="play_previous_song"),
            InlineKeyboardButton("⏯ Play / Pause", callback_data="toggle_play_pause"),
            InlineKeyboardButton("⏭ Next", callback_data="play_next_song"),
        ],
        # Row 2: Custom Playback Modes & Volume
        [
            InlineKeyboardButton("🔀 Shuffle", callback_data="toggle_shuffle"),
            InlineKeyboardButton("🔁 Repeat", callback_data="cycle_repeat"),
            InlineKeyboardButton("🔉 -10%", callback_data="vol_down"),
            InlineKeyboardButton("🔊 +10%", callback_data="vol_up"),
        ],
        # Row 3: Queue & Library Management
        [
            InlineKeyboardButton(">> Queue", callback_data="confirm_add_to_queue"),
            InlineKeyboardButton("❥ Save/Unsave", callback_data="add_to_saved_tracks"),
            InlineKeyboardButton("+ Playlist", callback_data="add_to_playlist"),
        ],
        # Row 4: Discovery & Lyrics
        [
            InlineKeyboardButton("✿ Similar Tune", callback_data="recommend_song"),
            InlineKeyboardButton("❀ Maestro's Best", callback_data="recommend_song_from_artist"),
            InlineKeyboardButton("𝛂 Lyrics", callback_data="get_song_lyrics"),
        ],
        # Row 5: Spotlight, Devices & Salon Menu
        [
            InlineKeyboardButton("✧ Spotlight", callback_data="get_current_song"),
            InlineKeyboardButton("📱 Devices", callback_data="list_devices"),
            InlineKeyboardButton("📜 Menu", callback_data="main_menu"),
        ],
    ]


# ==============================================================================
# SPOTIFY TRACK HELPERS
# ==============================================================================

def s_name(path):
    return path["name"]


def s_id(path):
    return path["id"]


def s_artist_name(path):
    artists = [artist["name"] for artist in path.get("artists", [])]
    return ", ".join(artists) if artists else "Unknown Artist"


def s_artist_id(path):
    artists = path.get("artists", [])
    return artists[0]["id"] if artists else ""


def s_preview_url(path):
    return path.get("preview_url")


def s_url(path):
    return path.get("external_urls", {}).get("spotify", "https://open.spotify.com")


def s_album(path):
    return path.get("album", {}).get("name", "Single")


def set_global_song_from_track(track_obj):
    """Populates global song variables from a Spotify track object and returns formatted strings."""
    global song_name, song_id, song_artist_name, song_artist_id, song_preview_url, song_url, song_album, song_album_uri
    song_name = s_name(track_obj)
    song_id = s_id(track_obj)
    song_artist_name = s_artist_name(track_obj)
    song_artist_id = s_artist_id(track_obj)
    song_preview_url = s_preview_url(track_obj)
    song_url = s_url(track_obj)
    song_album = s_album(track_obj)
    song_album_uri = track_obj.get("album", {}).get("uri", "")

    preview_section = (
        f"\n\n<b><a href='{song_preview_url}'>Enjoy a glimpse of the tune</a></b>"
        if song_preview_url
        else ""
    )
    rec_1 = (
        f"<b>{html.escape(song_name)}</b>\n"
        f"by {html.escape(song_artist_name)}\n\n"
        f"<i>{generate_song_writeup(song_name, song_artist_name, song_album)}</i>"
        f"{preview_section}"
    )
    rec_2 = f"<b><a href='{song_url}'>Indulge in the full melody on Spotify</a></b>"
    return rec_1, rec_2


def format_ms(ms: int) -> str:
    if not ms:
        return "0:00"
    total_sec = int(ms // 1000)
    return f"{total_sec // 60}:{total_sec % 60:02d}"


# ==============================================================================
# SPOTIFY CURATION & DISCOVERY FUNCTIONS
# ==============================================================================

def macos_spotify_cmd(action: str, uri: str = None) -> bool:
    """Controls Spotify desktop locally on macOS via AppleScript as an instant fallback."""
    if sys.platform != "darwin":
        return False
    try:
        if action == "play" and uri:
            script = f'tell application "Spotify" to play track "{uri}"'
        elif action == "play":
            script = 'tell application "Spotify" to play'
        elif action == "pause":
            script = 'tell application "Spotify" to pause'
        elif action == "playpause":
            script = 'tell application "Spotify" to playpause'
        elif action == "next":
            script = 'tell application "Spotify" to next track'
        elif action == "previous":
            script = 'tell application "Spotify" to previous track'
        else:
            return False
        subprocess.run(["osascript", "-e", script], check=False, capture_output=True, timeout=2)
        return True
    except Exception:
        return False


def ensure_device_id():
    """Returns an active Spotify device ID or the first available device if none is active."""
    try:
        devs = sp.devices().get("devices", [])
        if not devs:
            return None
        for d in devs:
            if d.get("is_active"):
                return d["id"]
        return devs[0]["id"]
    except Exception:
        return None


def chart_topping_number():
    global song_recommendation_2_ctn
    tracks_pool = []

    # Dynamically search top global and trending playlists instead of dead hardcoded IDs
    for query in ["Top 50 Global", "Today's Top Hits", "Top Hits 2026", "Viral 50 Global"]:
        try:
            res = sp.search(q=query, type="playlist", limit=5)
            for pl in res.get("playlists", {}).get("items", []):
                if not pl:
                    continue
                items = sp.playlist_items(pl["id"], limit=30).get("items", [])
                for it in items:
                    t = it.get("track") if it else None
                    if t and t.get("id"):
                        tracks_pool.append(t)
                if len(tracks_pool) >= 15:
                    break
            if tracks_pool:
                break
        except Exception:
            continue

    if not tracks_pool:
        try:
            top = sp.current_user_top_tracks(limit=30, time_range="short_term")
            tracks_pool = [t for t in top.get("items", []) if t and t.get("id")]
        except Exception:
            pass

    if not tracks_pool:
        res = sp.search(q="hit", limit=30, type="track")
        tracks_pool = [t for t in res.get("tracks", {}).get("items", []) if t and t.get("id")]

    unsent = [t for t in tracks_pool if t["id"] not in sent_songs_ctn]
    if not unsent:
        sent_songs_ctn.clear()
        unsent = tracks_pool

    chosen = random.choice(unsent)
    sent_songs_ctn.append(chosen["id"])

    rec_1, rec_2 = set_global_song_from_track(chosen)
    song_recommendation_2_ctn = rec_2
    return rec_1


def serendipitys_choice():
    global song_recommendation_2_sc
    search_queries = []
    for char in "abcdefghijklmnopqrstuvwxyz":
        search_queries.extend([f"%{char}", f"%{char}%", f"{char}%"])

    random_query = random.choice(search_queries)
    random_offset = random.randint(0, 50)
    try:
        results = sp.search(q=random_query, offset=random_offset, limit=10, type="track", market="from_token")
    except Exception:
        results = sp.search(q=random_query, offset=random_offset, limit=10, type="track")

    items = results.get("tracks", {}).get("items", [])
    playable_items = [t for t in items if t and t.get("id") and t.get("is_playable", True)]
    if not playable_items:
        try:
            results = sp.search(q="a", offset=0, limit=20, type="track", market="from_token")
        except Exception:
            results = sp.search(q="a", offset=0, limit=20, type="track")
        items = results.get("tracks", {}).get("items", [])
        playable_items = [t for t in items if t and t.get("id") and t.get("is_playable", True)]

    default_path = random.choice(playable_items) if playable_items else (items[0] if items else None)
    if not default_path:
        raise ValueError("Could not discover a random melody")

    rec_1, rec_2 = set_global_song_from_track(default_path)
    song_recommendation_2_sc = rec_2
    return rec_1


def harmonious_find(search: str):
    global song_recommendation_2_hf
    query_str = search.lstrip("~").strip()
    results = sp.search(q=query_str, offset=0, limit=5, type="track")
    items = results.get("tracks", {}).get("items", [])
    if not items:
        raise ValueError("No tracks found")

    # Cache top 5 tracks so user can also switch between matches if desired
    search_track_cache.clear()
    for idx, t in enumerate(items[:5]):
        search_track_cache[str(idx)] = t

    default_path = items[0]
    rec_1, rec_2 = set_global_song_from_track(default_path)
    song_recommendation_2_hf = rec_2
    return rec_1


def recommender(artist_id: str, url: str):
    global song_recommendation_2_r
    chosen_track = None
    try:
        artist_obj = sp.artist(artist_id)
        genres = artist_obj.get("genres", [])
        artist_name = artist_obj.get("name", "")

        # Find similar tracks by searching artist's genre or name
        q_str = f'genre:"{genres[0]}"' if genres else f'"{artist_name}"'
        res = sp.search(q=q_str, type="track", limit=30)
        candidates = [
            t for t in res.get("tracks", {}).get("items", [])
            if t and t.get("id") and t["id"] != song_id
        ]
        if candidates:
            chosen_track = random.choice(candidates)
    except Exception as e:
        logger.warning(f"Recommender fallback search: {e}")

    if not chosen_track:
        return recommender_from_artist(artist_id, song_id, song_name)

    rec_1, rec_2 = set_global_song_from_track(chosen_track)
    song_recommendation_2_r = rec_2
    return rec_1


def recommender_from_artist(a_id: str, s__id: str, s__name: str):
    global song_recommendation_2_rfa
    top_tracks = sp.artist_top_tracks(a_id).get("tracks", [])
    if not top_tracks:
        raise ValueError("No top tracks available for artist")

    candidates = [t for t in top_tracks if t["id"] != s__id and t["name"] != s__name]
    selected_song = random.choice(candidates) if candidates else random.choice(top_tracks)

    rec_1, rec_2 = set_global_song_from_track(selected_song)
    song_recommendation_2_rfa = rec_2
    return rec_1


def recommender_from_mood(mood_key_or_text: str = ""):
    global song_recommendation_2_rfm
    chosen_track = None
    preset = MOOD_PRESETS.get(mood_key_or_text.lower().strip())

    if preset:
        queries = preset.get("search_terms", []) + [f'genre:"{g}"' for g in preset.get("genres", [])]
        query = random.choice(queries)
    else:
        query = f"{mood_key_or_text} music"

    try:
        res = sp.search(q=query, type="track", limit=30)
        candidates = [t for t in res.get("tracks", {}).get("items", []) if t and t.get("id")]
        if candidates:
            chosen_track = random.choice(candidates)
    except Exception as e:
        logger.warning(f"Mood search error: {e}")

    if not chosen_track:
        fallback_res = sp.search(q="acoustic pop", type="track", limit=20)
        candidates = [t for t in fallback_res.get("tracks", {}).get("items", []) if t and t.get("id")]
        chosen_track = random.choice(candidates) if candidates else None

    if not chosen_track:
        raise ValueError("Could not curate a track for this mood")

    rec_1, rec_2 = set_global_song_from_track(chosen_track)
    song_recommendation_2_rfm = rec_2
    return rec_1


async def wait_for_track_change(
    prev_track_id: str = None,
    target_track_id: str = None,
    match_artist_id: str = None,
    match_artist_name: str = None,
    max_attempts: int = 8,
    delay: float = 0.5,
) -> dict:
    """Polls Spotify playback until the track updates from prev_track_id, matches target_track_id, or matches the target artist."""
    last_pb = None
    for _ in range(max_attempts):
        await asyncio.sleep(delay)
        pb = sp.current_playback()
        if not pb or not pb.get("item"):
            continue
        last_pb = pb
        item = pb["item"]
        cur_id = item.get("id")

        # If waiting for a specific target track:
        if target_track_id:
            if cur_id == target_track_id:
                set_global_song_from_track(item)
                return pb
            continue

        # If matching a target artist:
        if match_artist_id or match_artist_name:
            if prev_track_id and cur_id == prev_track_id:
                continue  # still playing previous track
            artists = item.get("artists", [])
            a_ids = [a.get("id") for a in artists]
            a_names = [a.get("name", "").lower() for a in artists]
            if match_artist_id and match_artist_id in a_ids:
                set_global_song_from_track(item)
                return pb
            if match_artist_name and any(match_artist_name.lower() in an for an in a_names):
                set_global_song_from_track(item)
                return pb
            continue  # still playing previous track

        # If waiting for track to change from prev_track_id:
        if prev_track_id and cur_id and cur_id != prev_track_id:
            set_global_song_from_track(item)
            return pb
        elif not prev_track_id and cur_id:
            set_global_song_from_track(item)
            return pb

    if last_pb and last_pb.get("item"):
        set_global_song_from_track(last_pb["item"])
        return last_pb

    try:
        return current_song()
    except Exception:
        return last_pb or {}


def current_song():
    """Fetches current playback details and updates global song state."""
    global song_name, song_id, song_artist_name, song_artist_id, song_preview_url, song_url, song_album
    playback = sp.current_playback(additional_types=["track", "episode"])
    if not playback or not playback.get("item"):
        raise ValueError("No active playback found")

    current_song_path = playback["item"]
    song_name = s_name(current_song_path)
    song_id = s_id(current_song_path)
    song_artist_name = s_artist_name(current_song_path)
    song_artist_id = s_artist_id(current_song_path)
    song_preview_url = s_preview_url(current_song_path)
    song_url = s_url(current_song_path)
    song_album = s_album(current_song_path)
    return playback


def format_now_playing_card(playback: dict, header_note: str = "is currently playing.") -> str:
    if not playback:
        playback = {}

    is_playing = playback.get("is_playing", False)
    status_icon = "▶️ Playing" if is_playing else "⏸ Paused"
    progress = format_ms(playback.get("progress_ms", 0))
    item = playback.get("item") or {}
    duration = format_ms(item.get("duration_ms", 0))
    device = playback.get("device", {})
    device_name = device.get("name", "Spotify")
    volume = device.get("volume_percent")
    vol_str = f" • 🔊 {volume}%" if volume is not None else ""
    shuffle_str = "🔀 On" if playback.get("shuffle_state") else "🔀 Off"
    repeat_str = f"🔁 {playback.get('repeat_state', 'off').capitalize()}"

    # Extract info directly from Spotify's live playback object so it is NEVER blank!
    if item and item.get("name"):
        c_name = item["name"]
        c_artist = ", ".join([a["name"] for a in item.get("artists", [])]) or "Spotify Artist"
        c_album = item.get("album", {}).get("name", "Single")
    elif song_name:
        c_name = song_name
        c_artist = song_artist_name
        c_album = song_album
    else:
        c_name = "Spotify Melody"
        c_artist = "Spotify"
        c_album = "Spotify Session"

    return (
        f"<i>Dearest Gentle Listener,</i>\n\n"
        f"<i>✦ ✦ ✦</i>\n"
        f"<b>{html.escape(c_name)}</b>\n"
        f"by {html.escape(c_artist)}\n"
        f"<i>Album: {html.escape(c_album)}</i>\n"
        f"<i>✦ ✦ ✦</i>\n\n"
        f"<i>{header_note}</i>\n"
        f"<code>{status_icon} [{progress} / {duration}]</code>\n"
        f"<code>📱 {html.escape(device_name)}{vol_str} • {shuffle_str} • {repeat_str}</code>\n\n"
        f"<i><span class=\"tg-spoiler\">{generate_song_quote(c_name, c_artist)}</span></i>"
    )


def get_actor_label(user) -> str:
    """Returns a readable name for the user performing the action."""
    if not user:
        return "A listener"
    if getattr(user, "username", None):
        return f"@{user.username}"
    first = getattr(user, "first_name", "") or ""
    last = getattr(user, "last_name", "") or ""
    full = f"{first} {last}".strip()
    return full or f"Guest {getattr(user, 'id', 'User')}"


async def broadcast_to_host(
    context: ContextTypes.DEFAULT_TYPE,
    message_text: str,
    sender_user_id: int = None,
):
    """Sends an unobtrusive notification to the host's private chat whenever anyone performs an action."""
    host_chat = active_party.get("host_chat_id") or (ALLOWED_USER_IDS[0] if ALLOWED_USER_IDS else None)
    if not host_chat:
        return

    # Never echo back to the host if they performed the action themselves
    if sender_user_id and str(sender_user_id) == str(host_chat):
        return

    try:
        await context.bot.send_message(
            chat_id=host_chat,
            text=message_text,
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.debug(f"Host broadcast failed: {e}")


async def play_and_display_track(
    target_message,
    track_id: str,
    context: ContextTypes.DEFAULT_TYPE,
    header_writeup: str = "",
    status_msg=None,
    extra_buttons: list = None,
    album_uri: str = None,
    actor_user=None,
):
    """Immediately commands Spotify to replace the active playback with this track and display the controls."""
    chat_id = target_message.chat_id
    dev_id = ensure_device_id()
    old_id = (sp.current_playback() or {}).get("item", {}).get("id")
    track_uri = f"spotify:track:{track_id}"
    target_album = album_uri or song_album_uri

    if not target_album:
        try:
            t_obj = sp.track(track_id)
            target_album = t_obj.get("album", {}).get("uri")
        except Exception:
            target_album = None

    try:
        if dev_id:
            try:
                # Prefer playing with album context and offset so Spotify Desktop maintains queue and stream state
                if target_album:
                    sp.start_playback(context_uri=target_album, offset={"uri": track_uri}, device_id=dev_id)
                else:
                    sp.start_playback(uris=[track_uri], device_id=dev_id)
            except Exception as e:
                logger.warning(f"Context playback failed ({e}), falling back to uris: {track_uri}")
                try:
                    sp.start_playback(uris=[track_uri], device_id=dev_id)
                except Exception:
                    macos_spotify_cmd("play", track_uri)
        else:
            macos_spotify_cmd("play", track_uri)
    except Exception as e:
        logger.warning(f"Error starting playback: {e}")
        macos_spotify_cmd("play", track_uri)

    playback = await wait_for_track_change(prev_track_id=old_id, target_track_id=track_id)

    card = format_now_playing_card(playback, "is now playing.")
    display_text = f"{header_writeup}\n\n{card}" if header_writeup else card

    kb = playback_keyboard()
    if extra_buttons:
        kb = extra_buttons + kb

    if status_msg:
        try:
            await status_msg.edit_text(text=display_text, parse_mode=ParseMode.HTML)
        except Exception:
            await target_message.reply_text(text=display_text, parse_mode=ParseMode.HTML)
    else:
        await target_message.reply_text(text=display_text, parse_mode=ParseMode.HTML)

    await target_message.reply_text(
        "<b>🎛 Spotify Playback Controls</b>",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode=ParseMode.HTML,
    )

    actor_label = get_actor_label(actor_user)
    actor_id = getattr(actor_user, "id", None) if actor_user else chat_id
    await broadcast_to_host(
        context,
        f"👑 <i>Salon Activity:</i> <b>{html.escape(actor_label)}</b> selected <b>{html.escape(song_name)}</b> by {html.escape(song_artist_name)}.",
        sender_user_id=actor_id,
    )


# ==============================================================================
# TELEGRAM COMMAND HANDLERS
# ==============================================================================


async def post_init(application: Application) -> None:
    """Sets the Telegram command menu and MenuButton properly inside the async event loop."""
    commands = [
        BotCommand("start", "Introduction by The Baroness herself"),
        BotCommand("select", "Open The Baroness's musical selection menu"),
        BotCommand("controls", "Open the custom Spotify Playback Controls deck"),
        BotCommand("nowplaying", "Inspect the song currently in the spotlight"),
        BotCommand("devices", "Switch active Spotify playback device"),
        BotCommand("host", "Convene a party session with a passcode & link"),
        BotCommand("join", "Join a party session with a passcode"),
        BotCommand("party", "View current salon party status & guests"),
        BotCommand("leave", "Exit the active salon gathering"),
        BotCommand("endparty", "Conclude the gathering & revoke guest access"),
        BotCommand("help", "How to converse with The Baroness"),
    ]
    try:
        await application.bot.set_my_commands(commands)
        await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    except Exception as e:
        logger.warning(f"Could not set menu button: {e}")


async def process_join(update: Update, context: ContextTypes.DEFAULT_TYPE, code: str):
    """Authenticates a guest and adds them to the active party session."""
    user = update.effective_user
    chat_id = update.effective_chat.id

    if not active_party.get("active"):
        await update.message.reply_text(
            "<i>Dearest Traveler, no musical salon gathering is presently convened. Pray ask your host to initiate one via <code>/host</code>.</i>",
            parse_mode=ParseMode.HTML,
        )
        return

    expected_code = str(active_party.get("code", "")).strip().lower()
    provided_code = code.strip().lower()

    if provided_code != expected_code:
        await update.message.reply_text(
            f"<i>Dearest Traveler, the passcode <code>{html.escape(code)}</code> was not recognized in the salon archives. Kindly verify the code with your host.</i>",
            parse_mode=ParseMode.HTML,
        )
        return

    # Add guest to active session
    display_name = user.full_name or user.username or f"Guest {user.id}"
    active_party["guests"][user.id] = {
        "name": display_name,
        "username": user.username or "",
        "joined_at": time.time(),
        "chat_id": chat_id,
    }

    welcome_msg = (
        f"✨ <b>WELCOME TO THE MUSICAL SALON, {html.escape(display_name).upper()}!</b> ✨\n\n"
        "<i>Your invitation has been gracefully accepted. You now hold the freedom to explore moods, "
        "search tunes, and command the melodies streaming through the salon's player!</i>\n\n"
        "<b>Commands available to you:</b>\n"
        "• /select — Open the curation menu\n"
        "• /controls — Open the playback deck\n"
        "• /nowplaying — Inspect what is playing\n"
        "• /leave — Exit the gathering"
    )
    await update.message.reply_text(welcome_msg, parse_mode=ParseMode.HTML)

    reply_markup = InlineKeyboardMarkup(menu_keyboard())
    await update.message.reply_text(
        "<b>Your melodic journey awaits! Indulge us with your selection.</b>",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
    )

    # Notify Host
    await broadcast_to_host(
        context,
        f"👑 <i>Salon Notice:</i> <b>{html.escape(display_name)}</b> <i>has joined your musical gathering!</i>",
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Support 1-click deep linking: /start <code> or /start join_<code>
    if context.args:
        raw_arg = context.args[0].replace("join_", "").strip()
        if raw_arg:
            await process_join(update, context, raw_arg)
            return

    if not is_user_authorized(update.effective_user):
        await update.message.reply_text(UNAUTHORIZED_MESSAGE, parse_mode=ParseMode.HTML)
        return

    chat_id = update.effective_chat.id
    chat_input_mode[chat_id] = None
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"<i>{generate_intro_response()}</i>",
        parse_mode=ParseMode.HTML,
    )

    reply_markup = InlineKeyboardMarkup(menu_keyboard())
    await update.message.reply_text(
        "<b>Your melodic journey awaits! Indulge us with your selection.</b>",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
    )


async def host_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Convenes a party session and generates a 4-digit passcode + 1-click invite link."""
    user = update.effective_user
    chat_id = update.effective_chat.id

    if not is_host(user):
        await update.message.reply_text(
            "<i>Dearest Listener, only the designated master of this salon holds authority to convene a party session.</i>",
            parse_mode=ParseMode.HTML,
        )
        return

    code = f"{random.randint(1000, 9999)}"
    active_party["active"] = True
    active_party["code"] = code
    active_party["host_id"] = user.id
    active_party["host_chat_id"] = chat_id
    active_party["guests"] = {}
    active_party["created_at"] = time.time()

    bot_user = await context.bot.get_me()
    bot_username = bot_user.username or "BaronessBot"
    deep_link = f"https://t.me/{bot_username}?start={code}"

    host_msg = (
        "👑 <b>THE MUSICAL SALON HAS BEEN CONVENED</b> 👑\n\n"
        f"Dearest Host <b>{html.escape(user.first_name)}</b>, your gathering has been officially assembled!\n\n"
        f"🎟 <b>Party Passcode:</b> <code>{code}</code>\n"
        f"🔗 <b>One-Click Guest Link:</b> <a href=\"{deep_link}\">{deep_link}</a>\n\n"
        "<i>Share the passcode or link with your companions. Once joined, they may freely request, "
        "curate, and enjoy melodies streaming through your Spotify player!</i>\n\n"
        "<b>Salon Management:</b>\n"
        "• /party — View connected guests\n"
        "• /endparty — Conclude gathering & revoke guest access"
    )
    await update.message.reply_text(host_msg, parse_mode=ParseMode.HTML)


async def join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /join <code>."""
    if not context.args:
        await update.message.reply_text(
            "<i>Kindly provide the 4-digit salon passcode, e.g. <code>/join 7492</code>.</i>",
            parse_mode=ParseMode.HTML,
        )
        return
    code = context.args[0].strip()
    await process_join(update, context, code)


async def party_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays active party status, room code, and connected guests."""
    if not is_user_authorized(update.effective_user):
        await update.message.reply_text(UNAUTHORIZED_MESSAGE, parse_mode=ParseMode.HTML)
        return

    if not active_party.get("active"):
        await update.message.reply_text(
            "<i>No musical salon gathering is presently convened. Type <code>/host</code> to convene one!</i>",
            parse_mode=ParseMode.HTML,
        )
        return

    code = active_party.get("code")
    guests = active_party.get("guests", {})
    elapsed = int((time.time() - active_party.get("created_at", time.time())) // 60)

    guest_list_str = ""
    if guests:
        for idx, (gid, ginfo) in enumerate(guests.items(), 1):
            handle = f" (@{ginfo['username']})" if ginfo.get("username") else ""
            guest_list_str += f"\n  {idx}. <b>{html.escape(ginfo['name'])}</b>{handle}"
    else:
        guest_list_str = "\n  <i>No guests have joined yet.</i>"

    bot_user = await context.bot.get_me()
    bot_username = bot_user.username or "BaronessBot"
    deep_link = f"https://t.me/{bot_username}?start={code}"

    party_text = (
        "🌹 <b>CURRENT MUSICAL SALON GATHERING</b> 🌹\n\n"
        f"🎟 <b>Party Passcode:</b> <code>{code}</code>\n"
        f"⏳ <b>Session Duration:</b> {elapsed} minute(s)\n"
        f"🔗 <b>Invite Link:</b> <a href=\"{deep_link}\">{deep_link}</a>\n\n"
        f"👥 <b>Connected Guests ({len(guests)}):</b>{guest_list_str}"
    )
    await update.message.reply_text(party_text, parse_mode=ParseMode.HTML)


async def leave_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allows a guest to voluntarily exit the party."""
    user = update.effective_user
    if active_party.get("active") and user.id in active_party.get("guests", {}):
        gname = active_party["guests"][user.id].get("name", "A guest")
        del active_party["guests"][user.id]
        await update.message.reply_text(
            "<i>You have gracefully taken your leave from the musical salon. Safe travels!</i>",
            parse_mode=ParseMode.HTML,
        )
        await broadcast_to_host(
            context,
            f"👑 <i>Salon Notice:</i> <b>{html.escape(gname)}</b> <i>has departed the gathering.</i>",
        )
    else:
        await update.message.reply_text(
            "<i>You are not currently part of an active salon party.</i>",
            parse_mode=ParseMode.HTML,
        )


async def endparty_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Concludes the active party session (Host only)."""
    user = update.effective_user
    if not is_host(user):
        await update.message.reply_text(
            "<i>Only the host holds authority to conclude the musical gathering.</i>",
            parse_mode=ParseMode.HTML,
        )
        return

    if not active_party.get("active"):
        await update.message.reply_text(
            "<i>There is no active musical salon gathering to conclude.</i>",
            parse_mode=ParseMode.HTML,
        )
        return

    # Notify connected guests
    guests = dict(active_party.get("guests", {}))
    for gid, ginfo in guests.items():
        try:
            await context.bot.send_message(
                chat_id=ginfo["chat_id"],
                text="<i>Dearest Listener, the host has officially concluded this evening's musical salon. Thank you for your companionship!</i>",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass

    active_party["active"] = False
    active_party["code"] = ""
    active_party["guests"].clear()

    await update.message.reply_text(
        "👑 <b>THE MUSICAL SALON HAS CONCLUDED</b> 👑\n\n"
        "<i>All guest sessions have been gracefully revoked, and private master control has been restored.</i>",
        parse_mode=ParseMode.HTML,
    )


async def select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_user_authorized(update.effective_user):
        await update.message.reply_text(UNAUTHORIZED_MESSAGE, parse_mode=ParseMode.HTML)
        return
    chat_id = update.effective_chat.id
    chat_input_mode[chat_id] = None
    reply_markup = InlineKeyboardMarkup(menu_keyboard())
    await update.message.reply_text(
        "<b>Your melodic journey awaits! Indulge us with your selection.</b>",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
    )


async def controls_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_user_authorized(update.effective_user):
        await update.message.reply_text(UNAUTHORIZED_MESSAGE, parse_mode=ParseMode.HTML)
        return
    reply_markup = InlineKeyboardMarkup(playback_keyboard())
    await update.message.reply_text(
        "<b>🎛 Spotify Playback Controls</b>",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
    )


async def nowplaying_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_user_authorized(update.effective_user):
        await update.message.reply_text(UNAUTHORIZED_MESSAGE, parse_mode=ParseMode.HTML)
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    msg = await update.message.reply_text("<i>Fetching the current song...</i>", parse_mode=ParseMode.HTML)
    try:
        playback = current_song()
        await msg.edit_text(
            text=format_now_playing_card(playback, "is currently playing."),
            parse_mode=ParseMode.HTML,
        )
        await update.message.reply_text(
            "<b>🎛 Spotify Playback Controls</b>",
            reply_markup=InlineKeyboardMarkup(playback_keyboard()),
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        await msg.edit_text(
            "<i>No active song could be found. Kindly ensure that your Spotify app is actively playing and try again.</i>",
            parse_mode=ParseMode.HTML,
        )


async def devices_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_user_authorized(update.effective_user):
        await update.message.reply_text(UNAUTHORIZED_MESSAGE, parse_mode=ParseMode.HTML)
        return
    await send_devices_menu(update.message, context)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_user_authorized(update.effective_user):
        await update.message.reply_text(UNAUTHORIZED_MESSAGE, parse_mode=ParseMode.HTML)
        return
    help_text = (
        "<b>🌹 The Baroness's Musical Salon — Compendium of Commands</b>\n\n"
        "<b>Melodic Curation & Playback Deck:</b>\n"
        "• /start — Introduction by The Baroness herself\n"
        "• /select — Open the main musical selection menu\n"
        "• /controls — Summon the custom Spotify Playback Controls deck\n"
        "• /nowplaying — View the currently playing song, album, progress & status\n"
        "• /devices — Switch playback between computer, phone, or web player\n\n"
        "<b>Salon Party Mode (Shared Listening & Queueing):</b>\n"
        "• /host — Convene a party session with a passcode & 1-click invite link <i>(Host only)</i>\n"
        "• /join <code>&lt;code&gt;</code> — Join an active salon gathering with a 4-digit passcode\n"
        "• /party — View active party status, room code & connected guests\n"
        "• /leave — Gracefully exit the active salon gathering\n"
        "• /endparty — Conclude gathering & revoke guest access <i>(Host only)</i>\n\n"
        "<b>General & Assistance:</b>\n"
        "• /help — Display this compendium of commands\n\n"
        "<b>Direct Text Shortcuts (anytime):</b>\n"
        "• <code>~Song Title</code> — Instant track search (<i>A Harmonious Find</i>)\n"
        "• <code>*Mood</code> — Curate a song by disposition (<i>A Melody for Your Spirits</i>)\n"
        "• <code>!Artist Name</code> — Play tracks by an artist (<i>Tracks from a Beloved Maestro</i>)\n\n"
        "<i>Tip: When you select a search button in the menu, you may also type your query directly without any prefix!</i>"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)


async def send_devices_menu(target_message, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=target_message.chat_id, action="typing")
    status_msg = await target_message.reply_text("<i>Inspecting your available Spotify devices...</i>", parse_mode=ParseMode.HTML)
    try:
        devices = sp.devices().get("devices", [])
        if not devices:
            await status_msg.edit_text(
                "<i>No active Spotify devices were detected. Kindly open Spotify on your phone, desktop, or web player first.</i>",
                parse_mode=ParseMode.HTML,
            )
            return

        device_cache.clear()
        keyboard = []
        for idx, dev in enumerate(devices):
            key = str(idx)
            device_cache[key] = {"id": dev["id"], "name": dev["name"]}
            active_badge = "🟢 " if dev.get("is_active") else "⚪ "
            label = f"{active_badge}{dev['name']} ({dev.get('type', 'Device')})"
            keyboard.append([InlineKeyboardButton(label, callback_data=f"DEV:{key}")])

        keyboard.append([InlineKeyboardButton("📜 Back to Controls", callback_data="open_controls")])
        await status_msg.edit_text(
            "<b>📱 Select the Spotify device you wish to command:</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        await status_msg.edit_text(
            "<i>Could not retrieve your Spotify devices at this moment.</i>",
            parse_mode=ParseMode.HTML,
        )


# ==============================================================================
# TEXT SEARCH HANDLER (~song, *mood, !artist, OR STATEFUL INPUT)
# ==============================================================================

async def handle_text_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    if not is_user_authorized(update.effective_user):
        await update.message.reply_text(UNAUTHORIZED_MESSAGE, parse_mode=ParseMode.HTML)
        return

    chat_id = update.effective_chat.id
    raw_text = update.message.text.strip()
    if not raw_text:
        return

    mode = chat_input_mode.get(chat_id)

    # Determine intent from prefix (~, *, !) or active chat_input_mode
    if raw_text.startswith("~"):
        intent = "search_track"
        query_val = raw_text[1:].strip()
    elif raw_text.startswith("*"):
        intent = "search_mood"
        query_val = raw_text[1:].strip()
    elif raw_text.startswith("!"):
        intent = "search_artist"
        query_val = raw_text[1:].strip()
    elif mode in ("search_track", "search_mood", "search_artist"):
        intent = mode
        query_val = raw_text
    else:
        # Default fallback if user types plain text without prefix: treat as song search
        intent = "search_track"
        query_val = raw_text

    chat_input_mode[chat_id] = None

    # 1. A HARMONIOUS FIND (Song Search)
    if intent == "search_track":
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        await update.message.reply_text(
            f"<i>You wish to search for</i> <b>{html.escape(query_val)}</b><i>.</i>",
            parse_mode=ParseMode.HTML,
        )
        searching = await update.message.reply_text("<i>Searching...</i>", parse_mode=ParseMode.HTML)
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")

        try:
            rec_text = harmonious_find(query_val)
            # Also attach quick-switch buttons if multiple results were cached
            alt_buttons = []
            if len(search_track_cache) > 1:
                for idx_str, t_obj in list(search_track_cache.items())[1:4]:
                    btn_label = f"🎵 {t_obj['name']} — {s_artist_name(t_obj)}"[:45]
                    alt_buttons.append([InlineKeyboardButton(btn_label, callback_data=f"TRK:{idx_str}")])

            await play_and_display_track(
                target_message=update.message,
                track_id=song_id,
                context=context,
                header_writeup=rec_text,
                status_msg=searching,
                extra_buttons=alt_buttons,
                actor_user=update.effective_user,
            )
        except Exception:
            await searching.edit_text(
                text="<i>Spotify could not return any results. Try another search.</i>",
                parse_mode=ParseMode.HTML,
            )
        return

    # 2. A MELODY FOR YOUR SPIRITS (Mood Curation)
    if intent == "search_mood":
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        await update.message.reply_text(
            f"<i>Your mood entry: </i><b>{html.escape(query_val)}</b>\n\n<i>{generate_mood_response(query_val)}</i>",
            parse_mode=ParseMode.HTML,
        )
        curation = await update.message.reply_text(
            "<i>Please be patient during the curation process...</i>",
            parse_mode=ParseMode.HTML,
        )
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        global audio_feature_values
        audio_feature_values = generate_audio_feature_values(query_val)

        try:
            rec_1 = recommender_from_mood(query_val)
            await play_and_display_track(
                target_message=update.message,
                track_id=song_id,
                context=context,
                header_writeup=rec_1,
                status_msg=curation,
                actor_user=update.effective_user,
            )
        except Exception:
            await curation.edit_text(
                text="<i>Spotify could not return any results. Try another search.</i>",
                parse_mode=ParseMode.HTML,
            )
        return

    # 3. TRACKS FROM A BELOVED MAESTRO (Artist Playback)
    if intent == "search_artist":
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        await update.message.reply_text(
            f"<i>You wish to listen to: </i><b>{html.escape(query_val)}</b>\n\n<i>{generate_artist_response(query_val)}</i>",
            parse_mode=ParseMode.HTML,
        )

        try:
            search_res = sp.search(q=query_val, limit=10, type="artist")
            artists = search_res.get("artists", {}).get("items", [])
            if not artists:
                await update.message.reply_text(
                    "<i>No artist by that name could be found in the archives.</i>",
                    parse_mode=ParseMode.HTML,
                )
                return

            # Prefer exact case-insensitive name match first (fixes 'milet' returning 'Aimer')
            chosen_artist = next(
                (a for a in artists if a["name"].lower() == query_val.lower()),
                artists[0],
            )

            search_artist_cache.clear()
            for idx, a_obj in enumerate(artists[:5]):
                search_artist_cache[str(idx)] = a_obj

            await play_artist_selection(update.message, chosen_artist, context=context, actor_user=update.effective_user)
        except Exception:
            await update.message.reply_text(
                "<i>The artist could not be retrieved. Please try another name.</i>",
                parse_mode=ParseMode.HTML,
            )
        return


async def play_artist_selection(
    target_message,
    chosen_artist: dict,
    context: ContextTypes.DEFAULT_TYPE = None,
    actor_user=None,
):
    artist_name = chosen_artist["name"]
    artist_id = chosen_artist["id"]
    images = chosen_artist.get("images", [])
    artist_pic = images[-1]["url"] if images else "https://open.spotify.com"

    playing = await target_message.reply_text(
        f"<i>Playing songs by </i><b>{html.escape(artist_name)}</b><i>...</i>",
        parse_mode=ParseMode.HTML,
    )
    await target_message.reply_text(
        f'<b><a href="{artist_pic}">[◉°] {html.escape(artist_name)}</a></b>',
        parse_mode=ParseMode.HTML,
    )

    try:
        old_id = (sp.current_playback() or {}).get("item", {}).get("id")
        dev_id = ensure_device_id()
        try:
            sp.start_playback(context_uri=f"spotify:artist:{artist_id}", device_id=dev_id)
        except Exception:
            macos_spotify_cmd("play", f"spotify:artist:{artist_id}")

        await playing.edit_text(
            f"🌹 <b>NOW PLAYING ARTIST: {html.escape(artist_name)}</b> 🌹",
            parse_mode=ParseMode.HTML,
        )

        # Poll until Spotify actually updates its playback to this chosen artist!
        playback = await wait_for_track_change(prev_track_id=old_id, match_artist_id=artist_id, match_artist_name=artist_name)
        await target_message.reply_text(
            text=format_now_playing_card(playback, "is now playing."),
            parse_mode=ParseMode.HTML,
        )
        await target_message.reply_text(
            "<b>🎛 Spotify Playback Controls</b>",
            reply_markup=InlineKeyboardMarkup(playback_keyboard()),
            parse_mode=ParseMode.HTML,
        )
        if context:
            actor_label = get_actor_label(actor_user)
            actor_id = getattr(actor_user, "id", None) if actor_user else (target_message.chat_id if target_message else None)
            await broadcast_to_host(
                context,
                f"🌹 <i>Salon Activity:</i> <b>{html.escape(actor_label)}</b> started playing Maestro <b>{html.escape(artist_name)}</b>.",
                sender_user_id=actor_id,
            )
    except Exception:
        # Even if active playback fails (e.g. Spotify app closed), showcase top track by artist so user can still browse/save
        try:
            rec_1 = recommender_from_artist(artist_id, "", "")
            await playing.edit_text(
                text=(
                    f"<i>Your Spotify player appears to be resting, so I have prepared a top selection by "
                    f"<b>{html.escape(artist_name)}</b> for your inspection:</i>\n\n{rec_1}"
                ),
                parse_mode=ParseMode.HTML,
            )
            await target_message.reply_text(
                "<b>🎛 Spotify Playback Controls</b>",
                reply_markup=InlineKeyboardMarkup(playback_keyboard()),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            await playing.edit_text(
                text="<i>The song could not be played. Kindly ensure that your Spotify app is running and try again.</i>",
                parse_mode=ParseMode.HTML,
            )


# ==============================================================================
# BUTTON CALLBACK HANDLER
# ==============================================================================

async def handle_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not is_user_authorized(update.effective_user):
        await query.answer("Private musical salon: Access restricted to authorized listeners.", show_alert=True)
        return
    await query.answer()
    chat_id = update.effective_chat.id
    actor = get_actor_label(update.effective_user)
    actor_id = update.effective_user.id if update.effective_user else chat_id
    data = query.data

    # Navigation shortcuts
    if data == "main_menu":
        chat_input_mode[chat_id] = None
        await query.message.reply_text(
            "<b>Your melodic journey awaits! Indulge us with your selection.</b>",
            reply_markup=InlineKeyboardMarkup(menu_keyboard()),
            parse_mode=ParseMode.HTML,
        )
        return

    if data == "open_controls":
        await query.message.reply_text(
            "<b>🎛 Spotify Playback Controls</b>",
            reply_markup=InlineKeyboardMarkup(playback_keyboard()),
            parse_mode=ParseMode.HTML,
        )
        return

    if data == "list_devices":
        await send_devices_menu(query.message, context)
        return

    if data.startswith("DEV:"):
        dev_key = data[4:]
        dev_info = device_cache.get(dev_key)
        if not dev_info:
            await query.message.reply_text("<i>Device list expired. Please tap Devices again.</i>", parse_mode=ParseMode.HTML)
            return
        try:
            sp.transfer_playback(device_id=dev_info["id"], force_play=True)
            await query.message.reply_text(
                f"📱 <i>Playback has been gracefully transferred to </i><b>{html.escape(dev_info['name'])}</b><i>.</i>",
                parse_mode=ParseMode.HTML,
            )
            await broadcast_to_host(
                context,
                f"📱 <i>Salon Activity:</i> <b>{html.escape(actor)}</b> transferred playback to <b>{html.escape(dev_info['name'])}</b>.",
                sender_user_id=actor_id,
            )
        except Exception:
            await query.message.reply_text(
                f"<i>Could not transfer playback to <b>{html.escape(dev_info['name'])}</b>. Ensure the device is awake.</i>",
                parse_mode=ParseMode.HTML,
            )
        return

    # Alternative search track selection
    if data.startswith("TRK:"):
        idx_str = data[4:]
        t_obj = search_track_cache.get(idx_str)
        if t_obj:
            rec_1, rec_2 = set_global_song_from_track(t_obj)
            await play_and_display_track(
                target_message=query.message,
                track_id=song_id,
                context=context,
                header_writeup=rec_1,
                actor_user=update.effective_user,
            )
        return

    # Mood preset button callback
    if data.startswith("MOOD:"):
        mood_key = data[5:]
        preset = MOOD_PRESETS.get(mood_key)
        mood_label = preset["label"] if preset else mood_key
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        await query.message.reply_text(
            f"<i>Your chosen disposition: </i><b>{html.escape(mood_label)}</b>\n\n"
            f"<i>{generate_mood_response(mood_label)}</i>",
            parse_mode=ParseMode.HTML,
        )
        curation = await query.message.reply_text(
            "<i>Please be patient during the curation process...</i>",
            parse_mode=ParseMode.HTML,
        )
        global audio_feature_values
        audio_feature_values = generate_audio_feature_values(mood_key)
        try:
            rec_1 = recommender_from_mood(mood_key)
            await play_and_display_track(
                target_message=query.message,
                track_id=song_id,
                context=context,
                header_writeup=rec_1,
                status_msg=curation,
                actor_user=update.effective_user,
            )
        except Exception:
            await curation.edit_text(
                text="<i>Spotify could not return any results. Try another mood selection.</i>",
                parse_mode=ParseMode.HTML,
            )
        return

    # MAIN SALON MENU OPTIONS
    if data in [
        "A Chart-Topping Number",
        "A Harmonious Find",
        "A Melody for Your Spirits",
        "Tracks from a Beloved Maestro",
        "Tracks from a Personal Collection",
        "Serendipity's Choice",
    ]:
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        await query.message.reply_text(
            text=(
                f"<i>Dearest Gentle Listener, you have selected</i>\n\n"
                f"<b>{data}</b>\n\n"
                f"<i>{generate_preliminary_choice_response(data)}</i>"
            ),
            parse_mode=ParseMode.HTML,
        )

        if data == "A Chart-Topping Number":
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
            curation = await query.message.reply_text(
                "<i>Please be patient during the curation process...</i>",
                parse_mode=ParseMode.HTML,
            )
            try:
                rec_1 = chart_topping_number()
                await play_and_display_track(
                    target_message=query.message,
                    track_id=song_id,
                    context=context,
                    header_writeup=rec_1,
                    status_msg=curation,
                    actor_user=update.effective_user,
                )
            except Exception as e:
                logger.error("Error in A Chart-Topping Number: %s", e, exc_info=True)
                err_str = str(e).lower()
                if "invalid_grant" in err_str or "revoked" in err_str or "token" in err_str:
                    await curation.edit_text(
                        "<i>Your Spotify authorization has expired. Kindly run <code>python auth.py</code> in your terminal to log in.</i>",
                        parse_mode=ParseMode.HTML,
                    )
                else:
                    await curation.edit_text(
                        text="<i>A chart-topping tune could not be retrieved right now. Please try again.</i>",
                        parse_mode=ParseMode.HTML,
                    )
            return

        if data == "A Harmonious Find":
            chat_input_mode[chat_id] = "search_track"
            await query.message.reply_text(
                text=(
                    "<i>For the finest accuracy, may I ask you be as specific as possible in your search. "
                    "Simply reply with your search below (or precede it with a tilde, e.g. </i>"
                    "<b>~Cruel Summer Taylor Swift</b><i>).</i>"
                ),
                parse_mode=ParseMode.HTML,
            )
            return

        if data == "A Melody for Your Spirits":
            chat_input_mode[chat_id] = "search_mood"
            await query.message.reply_text(
                text=(
                    "<i>Pray, tell me, what are you feeling today? Select one of the parlor mood cards below, "
                    "or type your disposition beginning with an asterisk, e.g. </i><b>*saudade</b><i>.</i>"
                ),
                reply_markup=InlineKeyboardMarkup(mood_preset_keyboard()),
                parse_mode=ParseMode.HTML,
            )
            return

        if data == "Tracks from a Beloved Maestro":
            chat_input_mode[chat_id] = "search_artist"
            await query.message.reply_text(
                text=(
                    "<i>I would be delighted to know which artist graces your thoughts today. "
                    "Kindly type the artist's name below (or precede it with an exclamation mark, e.g. </i>"
                    "<b>!Laufey</b><i>).</i>"
                ),
                parse_mode=ParseMode.HTML,
            )
            return

        if data == "Tracks from a Personal Collection":
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
            retrieve = await query.message.reply_text(
                text="<i>Retrieving your playlists...</i>",
                parse_mode=ParseMode.HTML,
            )
            keyboard = []
            try:
                current_user_display = sp.current_user().get("display_name")
                playlists = sp.current_user_playlists(limit=50).get("items", [])
                playlist_cache.clear()
                for playlist in playlists:
                    if not playlist:
                        continue
                    if playlist.get("owner", {}).get("display_name") == current_user_display:
                        pid = playlist["id"]
                        pname = playlist["name"]
                        playlist_cache[pid] = pname
                        keyboard.append([InlineKeyboardButton(pname, callback_data=f"PPID:{pid}")])

                if not keyboard:
                    await retrieve.edit_text(
                        "<i>No personal playlists were found in your account.</i>",
                        parse_mode=ParseMode.HTML,
                    )
                    return

                await retrieve.edit_text(
                    "<b>Kindly select the playlist you wish to play from. A song from your collection will begin.</b>",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                await retrieve.edit_text(
                    "<i>Your playlists could not be retrieved at this moment. Please try again.</i>",
                    parse_mode=ParseMode.HTML,
                )
            return

        if data == "Serendipity's Choice":
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
            curation = await query.message.reply_text(
                "<i>Please be patient during the curation process...</i>",
                parse_mode=ParseMode.HTML,
            )
            try:
                rec_1 = serendipitys_choice()
                await play_and_display_track(
                    target_message=query.message,
                    track_id=song_id,
                    context=context,
                    header_writeup=rec_1,
                    status_msg=curation,
                    actor_user=update.effective_user,
                )
            except Exception:
                await curation.edit_text(
                    text="<i>A song could not be found. Please try again.</i>",
                    parse_mode=ParseMode.HTML,
                )
            return

    # PLAY FROM PERSONAL PLAYLIST CALLBACK
    if data.startswith("PPID:"):
        p_id = data[5:]
        p_name = playlist_cache.get(p_id)
        if not p_name:
            try:
                p_name = sp.playlist(playlist_id=p_id).get("name", "Personal Collection")
            except Exception:
                p_name = "Personal Collection"

        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        play = await query.message.reply_text(
            text=f"<i>Playing from </i><b>{html.escape(p_name)}</b><i>...</i>",
            parse_mode=ParseMode.HTML,
        )
        try:
            pl_info = sp.playlist(playlist_id=p_id)
            images = pl_info.get("images", [])
            if images:
                await query.message.reply_text(
                    text=f"<a href='{images[0]['url']}'>[◉°] <b>{html.escape(p_name)}</b></a>",
                    parse_mode=ParseMode.HTML,
                )

            old_id = (sp.current_playback() or {}).get("item", {}).get("id")
            dev_id = ensure_device_id()
            try:
                sp.start_playback(context_uri=f"spotify:playlist:{p_id}", device_id=dev_id)
            except Exception:
                macos_spotify_cmd("play", f"spotify:playlist:{p_id}")

            await play.edit_text(
                text=f"🌺 <b>NOW PLAYING PLAYLIST: {html.escape(p_name)}</b> 🌺",
                parse_mode=ParseMode.HTML,
            )
            playback = await wait_for_track_change(prev_track_id=old_id)
            await query.message.reply_text(
                text=format_now_playing_card(playback, f"is now playing from <b>{html.escape(p_name)}</b>."),
                parse_mode=ParseMode.HTML,
            )
            await query.message.reply_text(
                "<b>🎛 Spotify Playback Controls</b>",
                reply_markup=InlineKeyboardMarkup(playback_keyboard()),
                parse_mode=ParseMode.HTML,
            )
            await broadcast_to_host(
                context,
                f"🌺 <i>Salon Activity:</i> <b>{html.escape(actor)}</b> started playlist <b>{html.escape(p_name)}</b>.",
                sender_user_id=actor_id,
            )
        except Exception:
            await play.edit_text(
                text="<i>The playlist could not be played. Kindly ensure that your Spotify app is running and try again.</i>",
                parse_mode=ParseMode.HTML,
            )
        return

    # CUSTOM PLAYBACK CONTROLS DECK: PLAY / PAUSE TOGGLE
    if data in ("toggle_play_pause", "play_song"):
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        status_msg = await query.message.reply_text("<i>Updating playback...</i>", parse_mode=ParseMode.HTML)
        try:
            dev_id = ensure_device_id()
            if not dev_id:
                await status_msg.edit_text(
                    "<i>No active Spotify device was found. Kindly open Spotify on your Mac or phone first.</i>",
                    parse_mode=ParseMode.HTML,
                )
                return

            playback = sp.current_playback()

            # 1. If music is already playing: Pause it
            if playback and playback.get("is_playing"):
                try:
                    sp.pause_playback(device_id=dev_id)
                except Exception:
                    macos_spotify_cmd("pause")
                await status_msg.edit_text("⏸ <i>Playback has been gracefully paused.</i>", parse_mode=ParseMode.HTML)
                await broadcast_to_host(
                    context,
                    f"⏸ <i>Salon Activity:</i> <b>{html.escape(actor)}</b> paused playback.",
                    sender_user_id=actor_id,
                )
                return

            # 2. If Spotify has a paused track in queue: Resume it without resetting position or queue
            if playback and playback.get("item"):
                try:
                    sp.start_playback(device_id=dev_id)
                except Exception:
                    macos_spotify_cmd("play")
            # 3. If Spotify is idle/empty, but a track was curated in the chat: Play that curated track
            elif song_id:
                try:
                    sp.start_playback(uris=[f"spotify:track:{song_id}"], device_id=dev_id)
                except Exception:
                    macos_spotify_cmd("play", f"spotify:track:{song_id}")
            # 4. Fallback: ask Spotify to resume whatever it last held
            else:
                try:
                    sp.start_playback(device_id=dev_id)
                except Exception:
                    if not macos_spotify_cmd("play"):
                        await status_msg.edit_text(
                            "<i>No song is currently queued in Spotify. Select a melody from the menu to begin!</i>",
                            parse_mode=ParseMode.HTML,
                        )
                        return

            # Wait briefly for Spotify cloud status to refresh
            await asyncio.sleep(0.8)
            pb_after = sp.current_playback()
            await status_msg.edit_text(
                text=format_now_playing_card(pb_after, "is now playing."),
                parse_mode=ParseMode.HTML,
            )
            await query.message.reply_text(
                "<b>🎛 Spotify Playback Controls</b>",
                reply_markup=InlineKeyboardMarkup(playback_keyboard()),
                parse_mode=ParseMode.HTML,
            )
            await broadcast_to_host(
                context,
                f"▶️ <i>Salon Activity:</i> <b>{html.escape(actor)}</b> resumed playback.",
                sender_user_id=actor_id,
            )
        except Exception as e:
            logger.error("Error in play/pause: %s", e, exc_info=True)
            await status_msg.edit_text(
                "<i>Could not control playback. Kindly ensure that your Spotify app is open on your Mac or phone.</i>",
                parse_mode=ParseMode.HTML,
            )
        return

    if data == "play_previous_song":
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        add = await query.message.reply_text(text="<i>Playing the previous song...</i>", parse_mode=ParseMode.HTML)
        try:
            old_id = (sp.current_playback() or {}).get("item", {}).get("id")
            dev_id = ensure_device_id()
            try:
                sp.previous_track(device_id=dev_id)
            except Exception:
                macos_spotify_cmd("previous")
            pb = await wait_for_track_change(prev_track_id=old_id)
            await add.edit_text(
                text=format_now_playing_card(pb, "is now playing."),
                parse_mode=ParseMode.HTML,
            )
            await query.message.reply_text(
                "<b>🎛 Spotify Playback Controls</b>",
                reply_markup=InlineKeyboardMarkup(playback_keyboard()),
                parse_mode=ParseMode.HTML,
            )
            await broadcast_to_host(
                context,
                f"⏮ <i>Salon Activity:</i> <b>{html.escape(actor)}</b> skipped to previous track.",
                sender_user_id=actor_id,
            )
        except Exception as e:
            logger.error("Error in play_previous_song: %s", e, exc_info=True)
            await add.edit_text(
                text="<i>The previous song could not be played. Kindly ensure that your Spotify app is running and try again.</i>",
                parse_mode=ParseMode.HTML,
            )
        return

    if data == "play_next_song":
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        add = await query.message.reply_text(text="<i>Playing the next song...</i>", parse_mode=ParseMode.HTML)
        try:
            old_id = (sp.current_playback() or {}).get("item", {}).get("id")
            dev_id = ensure_device_id()
            try:
                sp.next_track(device_id=dev_id)
            except Exception:
                macos_spotify_cmd("next")
            pb = await wait_for_track_change(prev_track_id=old_id)
            await add.edit_text(
                text=format_now_playing_card(pb, "is now playing."),
                parse_mode=ParseMode.HTML,
            )
            await query.message.reply_text(
                "<b>🎛 Spotify Playback Controls</b>",
                reply_markup=InlineKeyboardMarkup(playback_keyboard()),
                parse_mode=ParseMode.HTML,
            )
            await broadcast_to_host(
                context,
                f"⏭ <i>Salon Activity:</i> <b>{html.escape(actor)}</b> skipped to next track.",
                sender_user_id=actor_id,
            )
        except Exception as e:
            logger.error("Error in play_next_song: %s", e, exc_info=True)
            await add.edit_text(
                text="<i>The next song could not be played. Kindly ensure that your Spotify app is running and try again.</i>",
                parse_mode=ParseMode.HTML,
            )
        return

    if data == "toggle_shuffle":
        try:
            playback = sp.current_playback()
            new_state = not bool(playback and playback.get("shuffle_state"))
            sp.shuffle(new_state)
            state_label = "enabled 🔀" if new_state else "disabled ➡️"
            await query.message.reply_text(
                f"<i>Dearest Gentle Listener, shuffle mode is now <b>{state_label}</b>.</i>",
                parse_mode=ParseMode.HTML,
            )
            await broadcast_to_host(
                context,
                f"🔀 <i>Salon Activity:</i> <b>{html.escape(actor)}</b> turned shuffle <b>{state_label}</b>.",
                sender_user_id=actor_id,
            )
        except Exception:
            await query.message.reply_text(
                "<i>Shuffle mode could not be changed. Kindly ensure Spotify is actively playing.</i>",
                parse_mode=ParseMode.HTML,
            )
        return

    if data == "cycle_repeat":
        try:
            playback = sp.current_playback()
            current_rep = (playback or {}).get("repeat_state", "off")
            next_map = {"off": "context", "context": "track", "track": "off"}
            next_rep = next_map.get(current_rep, "context")
            sp.repeat(next_rep)
            rep_labels = {
                "off": "Off ➡️",
                "context": "Repeat Context / Playlist 🔁",
                "track": "Repeat Current Track 🔂",
            }
            await query.message.reply_text(
                f"<i>Dearest Gentle Listener, repeat mode is now set to <b>{rep_labels[next_rep]}</b>.</i>",
                parse_mode=ParseMode.HTML,
            )
            await broadcast_to_host(
                context,
                f"🔁 <i>Salon Activity:</i> <b>{html.escape(actor)}</b> set repeat to <b>{rep_labels[next_rep]}</b>.",
                sender_user_id=actor_id,
            )
        except Exception:
            await query.message.reply_text(
                "<i>Repeat mode could not be changed. Kindly ensure Spotify is actively playing.</i>",
                parse_mode=ParseMode.HTML,
            )
        return

    if data in ("vol_down", "vol_up"):
        try:
            playback = sp.current_playback()
            cur_vol = (playback or {}).get("device", {}).get("volume_percent", 50)
            delta = -10 if data == "vol_down" else 10
            new_vol = max(0, min(100, cur_vol + delta))
            sp.volume(new_vol)
            await query.message.reply_text(
                f"🔊 <i>Volume adjusted to <b>{new_vol}%</b>.</i>",
                parse_mode=ParseMode.HTML,
            )
            await broadcast_to_host(
                context,
                f"🔊 <i>Salon Activity:</i> <b>{html.escape(actor)}</b> changed volume to <b>{new_vol}%</b>.",
                sender_user_id=actor_id,
            )
        except Exception:
            await query.message.reply_text(
                "<i>Volume could not be adjusted on the current Spotify device.</i>",
                parse_mode=ParseMode.HTML,
            )
        return

    if data == "confirm_add_to_queue":
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        add = await query.message.reply_text(text="<i>Adding to your queue...</i>", parse_mode=ParseMode.HTML)
        try:
            if not song_url:
                current_song()
            sp.add_to_queue(song_url)
            await add.edit_text(
                text=(
                    f"<i>Dearest Gentle Listener,</i>\n\n"
                    f"<b>{html.escape(song_name)}</b>\nby {html.escape(song_artist_name)}\n\n"
                    f"<i>has been added to the queue.</i>\n\n"
                    f"<i><span class=\"tg-spoiler\">{generate_song_quote(song_name, song_artist_name)}</span></i>"
                ),
                parse_mode=ParseMode.HTML,
            )
            await broadcast_to_host(
                context,
                f"🎵 <i>Salon Activity:</i> <b>{html.escape(actor)}</b> queued <b>{html.escape(song_name)}</b> by {html.escape(song_artist_name)}.",
                sender_user_id=actor_id,
            )
        except Exception:
            await add.edit_text(
                text="<i>The song could not be added to the queue. Kindly ensure that your Spotify app is running and try again.</i>",
                parse_mode=ParseMode.HTML,
            )
        return

    if data == "add_to_saved_tracks":
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        add = await query.message.reply_text(text="<i>Checking your saved tracks...</i>", parse_mode=ParseMode.HTML)
        try:
            if not song_id:
                current_song()
            if sp.current_user_saved_tracks_contains([song_id]) == [True]:
                keyboard = [[InlineKeyboardButton("💔 Remove from Saved Tracks", callback_data="remove_saved_track")]]
                await add.edit_text(
                    text=f"<b>{html.escape(song_name)}</b> <i>already resides in your saved tracks.</i>",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.HTML,
                )
                return

            sp.current_user_saved_tracks_add([song_id])
            await add.edit_text(
                text=(
                    f"<i>Dearest Gentle Listener,</i>\n\n"
                    f"<b>{html.escape(song_name)}</b>\nby {html.escape(song_artist_name)}\n\n"
                    f"<i>has been added to your saved tracks.</i>\n\n"
                    f"<i><span class=\"tg-spoiler\">{generate_song_quote(song_name, song_artist_name)}</span></i>"
                ),
                parse_mode=ParseMode.HTML,
            )
            await broadcast_to_host(
                context,
                f"❥ <i>Salon Activity:</i> <b>{html.escape(actor)}</b> saved <b>{html.escape(song_name)}</b> to Liked Songs.",
                sender_user_id=actor_id,
            )
        except Exception:
            await add.edit_text(
                text="<i>The song could not be added to your saved tracks. Kindly try again.</i>",
                parse_mode=ParseMode.HTML,
            )
        return

    if data == "remove_saved_track":
        try:
            if song_id:
                sp.current_user_saved_tracks_delete([song_id])
                await query.message.edit_text(
                    f"<i><b>{html.escape(song_name)}</b> has been removed from your saved tracks.</i>",
                    parse_mode=ParseMode.HTML,
                )
                await broadcast_to_host(
                    context,
                    f"💔 <i>Salon Activity:</i> <b>{html.escape(actor)}</b> removed <b>{html.escape(song_name)}</b> from Liked Songs.",
                    sender_user_id=actor_id,
                )
        except Exception:
            await query.message.reply_text(
                "<i>Could not remove the song from your saved tracks.</i>",
                parse_mode=ParseMode.HTML,
            )
        return

    if data == "add_to_playlist":
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        retrieve = await query.message.reply_text(text="<i>Retrieving your playlists...</i>", parse_mode=ParseMode.HTML)
        keyboard = []
        try:
            if not song_id:
                current_song()
            current_user_display = sp.current_user().get("display_name")
            for playlist in sp.current_user_playlists(limit=50).get("items", []):
                if not playlist:
                    continue
                if playlist.get("owner", {}).get("display_name") == current_user_display:
                    pid = playlist["id"]
                    pname = playlist["name"]
                    playlist_cache[pid] = pname
                    keyboard.append([InlineKeyboardButton(pname, callback_data=f"PID:{pid}")])

            await retrieve.edit_text(
                "<b>Kindly select the playlist you wish to add to.</b>",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            await retrieve.edit_text(
                "<i>Your playlists could not be retrieved at this moment.</i>",
                parse_mode=ParseMode.HTML,
            )
        return

    if data.startswith("PID:"):
        p_id = data[4:]
        p_name = playlist_cache.get(p_id)
        if not p_name:
            try:
                p_name = sp.playlist(playlist_id=p_id).get("name", "Playlist")
            except Exception:
                p_name = "Playlist"

        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        add = await query.message.reply_text(
            f"<i>Checking if the song</i> <b>{html.escape(song_name)}</b>"
            f"<i> exists in the playlist</i> <b>{html.escape(p_name)}</b><i>...</i>",
            parse_mode=ParseMode.HTML,
        )
        try:
            offset_index = 0
            sid_list = []
            while True:
                page = sp.playlist_items(playlist_id=p_id, limit=100, offset=offset_index).get("items", [])
                for item in page:
                    trk = item.get("track") if item else None
                    if trk and trk.get("id"):
                        sid_list.append(trk["id"])
                    if len(page) < 100:
                        break
                offset_index += 100

            if song_id in sid_list:
                await add.edit_text(
                    f"<i>The song </i><b>{html.escape(song_name)}</b>"
                    f"<i> already exists in the playlist </i><b>{html.escape(p_name)}</b><i>.</i>",
                    parse_mode=ParseMode.HTML,
                )
                return

            await add.edit_text("<i>Adding to playlist...</i>", parse_mode=ParseMode.HTML)
            sp.playlist_add_items(playlist_id=p_id, items=[song_url])
            await add.edit_text(
                text=(
                    f"<i>Dearest Gentle Listener,</i>\n\n"
                    f"<b>{html.escape(song_name)}</b>\nby {html.escape(song_artist_name)}\n\n"
                    f"<i>has been added to the playlist</i> <b>{html.escape(p_name)}</b><i>.</i>\n\n"
                    f"<i><span class=\"tg-spoiler\">{generate_song_quote(song_name, song_artist_name)}</span></i>"
                ),
                parse_mode=ParseMode.HTML,
            )
            await broadcast_to_host(
                context,
                f"📑 <i>Salon Activity:</i> <b>{html.escape(actor)}</b> added <b>{html.escape(song_name)}</b> to playlist <b>{html.escape(p_name)}</b>.",
                sender_user_id=actor_id,
            )
        except Exception:
            await add.edit_text(
                text=f"<i>The song could not be added to the playlist <b>{html.escape(p_name)}</b>. Kindly try again.</i>",
                parse_mode=ParseMode.HTML,
            )
        return

    if data == "recommend_song":
        if not song_id:
            try:
                current_song()
            except Exception:
                await query.message.reply_text(
                    "<i>Kindly select or play a song first so I may recommend a similar tune.</i>",
                    parse_mode=ParseMode.HTML,
                )
                return

        curation = await query.message.reply_text(
            f"<i>Recommending a track based on</i> <b>{html.escape(song_name)}</b> "
            f"<i>by</i> {html.escape(song_artist_name)}<i>...</i>",
            parse_mode=ParseMode.HTML,
        )
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        try:
            rec_1 = recommender(song_artist_id, song_url)
            await play_and_display_track(
                target_message=query.message,
                track_id=song_id,
                context=context,
                header_writeup=rec_1,
                status_msg=curation,
                actor_user=update.effective_user,
            )
        except Exception:
            await curation.edit_text(
                text="<i>The recommendation was unsuccessful. May I suggest selecting a different tune?</i>",
                parse_mode=ParseMode.HTML,
            )
        return

    if data == "recommend_song_from_artist":
        if not song_artist_id:
            try:
                current_song()
            except Exception:
                await query.message.reply_text(
                    "<i>Kindly select or play a song first so I know which Maestro to feature.</i>",
                    parse_mode=ParseMode.HTML,
                )
                return

        first_artist = song_artist_name.split(", ")[0]
        curation = await query.message.reply_text(
            f"<i>Recommending another track by</i> {html.escape(first_artist)}<i>...</i>",
            parse_mode=ParseMode.HTML,
        )
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        try:
            rec_1 = recommender_from_artist(song_artist_id, song_id, song_name)
            await play_and_display_track(
                target_message=query.message,
                track_id=song_id,
                context=context,
                header_writeup=rec_1,
                status_msg=curation,
                actor_user=update.effective_user,
            )
        except Exception:
            await curation.edit_text(
                text="<i>The recommendation was unsuccessful. May I suggest selecting a different tune?</i>",
                parse_mode=ParseMode.HTML,
            )
        return

    if data == "get_song_lyrics":
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        retrieving = await query.message.reply_text(
            "<i>Retrieving song lyrics, kindly be patient as this may take a moment...</i>",
            parse_mode=ParseMode.HTML,
        )

        # Always refresh active playback so lyrics match what is currently playing
        try:
            current_song()
        except Exception:
            pass

        if not song_name:
            await retrieving.edit_text(
                "<i>Kindly select or play a song first before requesting lyrics.</i>",
                parse_mode=ParseMode.HTML,
            )
            return

        try:
            best_title, lyrics_body = fetch_best_lyrics(song_name, song_artist_name)

            if not lyrics_body:
                await retrieving.edit_text(
                    f"<i>Unfortunately, lyrics for </i><b>{html.escape(song_name)}</b>"
                    f"<i> are not available, or it may be an instrumental track.</i>",
                    parse_mode=ParseMode.HTML,
                )
                return

            # Safely chunk along paragraphs so HTML tags are never truncated
            chunks = chunk_lyrics_for_telegram(best_title or song_name, lyrics_body)

            # Edit first chunk into status message
            first_chunk = chunks[0]
            try:
                await retrieving.edit_text(first_chunk, parse_mode=ParseMode.HTML)
            except Exception:
                # Fallback to plain text if HTML tags ever conflict
                clean_text = re.sub(r"<[^>]+>", "", first_chunk)
                await retrieving.edit_text(clean_text)

            # Send remaining chunks if song is exceptionally long
            for subsequent_chunk in chunks[1:]:
                try:
                    await query.message.reply_text(subsequent_chunk, parse_mode=ParseMode.HTML)
                except Exception:
                    clean_sub = re.sub(r"<[^>]+>", "", subsequent_chunk)
                    await query.message.reply_text(clean_sub)

        except Exception as e:
            logger.error(f"Error retrieving lyrics: {e}", exc_info=True)
            await retrieving.edit_text(
                "<i>Lyrics could not be retrieved at this moment. Please try again.</i>",
                parse_mode=ParseMode.HTML,
            )
        return

    if data.startswith("LYR:"):
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        lyr_idx = int(data[4:])
        entry = lyrics.get(lyr_idx)
        if not entry:
            await query.message.reply_text("<i>Lyrics selection expired. Please request lyrics again.</i>", parse_mode=ParseMode.HTML)
            return

        try:
            chunks = chunk_lyrics_for_telegram(entry["title"], entry["lyrics"])
            for chunk in chunks:
                try:
                    await query.message.reply_text(chunk, parse_mode=ParseMode.HTML)
                except Exception:
                    clean_chunk = re.sub(r"<[^>]+>", "", chunk)
                    await query.message.reply_text(clean_chunk)
        except Exception as e:
            logger.error(f"Error delivering selected lyrics: {e}")
            await query.message.reply_text("<i>Could not deliver lyrics for this selection.</i>", parse_mode=ParseMode.HTML)
        return

    if data == "get_current_song":
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        add = await query.message.reply_text(text="<i>Fetching the current song...</i>", parse_mode=ParseMode.HTML)
        try:
            playback = sp.current_playback()
            if not playback or not playback.get("item"):
                if not song_name:
                    await add.edit_text(
                        "<i>No music is currently playing or queued in Spotify. Select a melody from the menu to begin!</i>",
                        parse_mode=ParseMode.HTML,
                    )
                    return

            await add.edit_text(
                text=format_now_playing_card(playback, "is in the spotlight."),
                parse_mode=ParseMode.HTML,
            )
            await query.message.reply_text(
                "<b>🎛 Spotify Playback Controls</b>",
                reply_markup=InlineKeyboardMarkup(playback_keyboard()),
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            logger.error("Error in get_current_song: %s", e, exc_info=True)
            await add.edit_text(
                text="<i>No active playback was detected. Kindly ensure that your Spotify app is running.</i>",
                parse_mode=ParseMode.HTML,
            )
        return


# ==============================================================================
# RUN THE APP
# ==============================================================================

if __name__ == "__main__":
    # Check if a valid Spotify token exists
    try:
        cached_tok = sp.auth_manager.cache_handler.get_cached_token()
        if not cached_tok or not sp.auth_manager.validate_token(cached_tok):
            logger.warning(
                "⚠️  No valid Spotify token found in .cache.\n"
                "   Please run 'python auth.py' in your terminal to authenticate with Spotify."
            )
    except Exception as e:
        logger.warning(f"Spotify token check: {e}")

    app = ApplicationBuilder().token(telegram_access_token).post_init(post_init).build()

    # Command Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("select", select))
    app.add_handler(CommandHandler("controls", controls_command))
    app.add_handler(CommandHandler("nowplaying", nowplaying_command))
    app.add_handler(CommandHandler("devices", devices_command))
    app.add_handler(CommandHandler("host", host_command))
    app.add_handler(CommandHandler("join", join_command))
    app.add_handler(CommandHandler("party", party_command))
    app.add_handler(CommandHandler("leave", leave_command))
    app.add_handler(CommandHandler("endparty", endparty_command))
    app.add_handler(CommandHandler("help", help_command))

    # Callback Query Handler for all inline buttons
    app.add_handler(CallbackQueryHandler(handle_button_callback))

    # Message Handler for user text searches (supports both ~, *, ! prefixes and direct replies)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_callback))

    logger.info("The Baroness's Revamped Spotify Telegram Bot is now polling...")
    app.run_polling()
