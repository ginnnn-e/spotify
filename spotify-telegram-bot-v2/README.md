# 🌹 The Baroness — Spotify Curation Concierge & Remote Control Bot (v2)

> **Executive Summary:** **The Baroness** is a full-featured Spotify music discovery engine, 15-button remote control deck, and instant lyrics reader built inside Telegram (`python-telegram-bot`, `spotipy`). Designed with a theatrical Regency (*Bridgerton* / *Lady Whistledown*) persona, it lets you discover music by mood, charts, artist, or random serendipity, manage your Spotify library and playlists, switch playback devices, and read ad-free lyrics—all without leaving Telegram. Built on a **100% deterministic, zero-AI architecture ($0/mo)**, it works seamlessly as your **personal daily Spotify companion** and also includes an optional **Listening Party Mode** (`/host`) when you want friends to join in.

---

## 📑 Table of Contents

### Part I — Overview, Features & Quick Start
1. [🌟 What Makes This App Special & Stand Out](#-what-makes-this-app-special--stand-out)
2. [🏗 How the Whole Application Works (System Architecture)](#-how-the-whole-application-works-system-architecture)
3. [✨ Core Features](#-core-features)
   - [Seven Curation & Discovery Modes (`/select`)](#1-seven-curation--discovery-modes-select)
   - [15-Button Playback Control Deck (`/controls`)](#2-custom-telegram-playback-control-deck-controls)
   - [Immediate Auto-Playback & Atomic Sync](#3-immediate-auto-playback-on-recommendation--discovery)
   - [Optional: Live Listening Party Mode (`/host` & `/join`)](#4-live-listening-party-mode--room-code-sharing-host--join)
4. [💬 Bot Commands & Direct Text Shortcuts](#-bot-commands--shortcuts)
5. [📸 Demo & Interface Walkthrough](#-demo--interface-walkthrough)
6. [🚀 Getting Started & Installation](#-getting-started)
7. [⚖️ Ethical & Open-Source Libraries](#️-ethical--open-source-libraries)
8. [📜 Changelog & Version History](#-changelog--version-history)

### Part II — Technical Deep Dives & Engineering Logs
9. [🔍 Deep Dive: Spotify API Search & Retrieval Mechanics](#-deep-dive-spotify-api-search--retrieval-mechanics)
10. [📖 Architecture & Function-by-Function Reference](#-architecture--function-reference)
11. [🔮 Future Work & Multi-Tenant SaaS Scaling Roadmap](#-future-work--multi-tenant-saas-scaling-roadmap)
12. [🛠 Engineering Post-Mortems & Troubleshooting Log (Items 1–11)](#-troubleshooting--bug-fixes-log)

---

# Part I — Overview, Features & Quick Start

## 🌟 What Makes This App Special & Stand Out

Most music bots are basic command-line wrappers (`!play url`) or slow, expensive wrappers around paid LLM APIs. **The Baroness** is a complete musical companion that combines curation, library management, hardware-style controls, and lyrics in one place:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   WHY THE BARONESS STANDS OUT                                    │
├─────────────────────────┬───────────────────────────────────┬────────────────────────────────────┤
│ Capability              │ Standard Music Bots               │ The Baroness (v2)                  │
├─────────────────────────┼───────────────────────────────────┼────────────────────────────────────┤
│ Music Discovery         │ Manual song search only           │ 7 modes (Moods, Charts, Random...) │
│ Player Interface        │ Text-only commands                │ Full 15-button hardware deck in UI │
│ Library Management      │ Cannot edit your Spotify library  │ Save to Liked Songs & Playlists    │
│ Lyrics Delivery         │ Broken by Cloudflare 403 blocks   │ 3-Tier REST engine (~300ms, $0)    │
│ Persona & AI Cost       │ Generic robot or $20/mo LLM fees  │ Zero-AI Regency persona ($0, <5ms) │
│ Playback Stability      │ Slices bare URIs & wipes queue    │ Album context + offset preservation│
│ Social Mode (Optional)  │ Every guest needs Spotify Premium │ 1-click Telegram PIN party mode    │
└─────────────────────────┴───────────────────────────────────┴────────────────────────────────────┘
```

1. **7-in-1 Personal Music Concierge & Discovery Engine**:
   - Whether you want a *Chart-Topping Hit*, a song tailored to your current *Mood* (via 6 interactive parlor mood cards or custom keywords), a deep dive into a *Beloved Maestro*, your own *Personal Playlists*, or a *Random Serendipity* pick, the bot curates and plays music immediately.
2. **Hardware-Grade 15-Button Remote Control & Library Deck**:
   - Replaces switching apps with an inline remote inside Telegram: Play/Pause, Skip/Prev, Volume (`±10%`), Shuffle, 3-state Repeat cycling, Add to Queue, Save/Remove from Liked Songs, Add to Personal Playlists (with duplicate checking), and Switch Active Device (Mac, Phone, Web Player, Speaker).
3. **Zero-AI, Zero-Latency Regency Persona**:
   - Built with deterministic Regency prose generators and acoustic keyword mapping. You get rich *Bridgerton* / *Lady Whistledown* commentary on every song, mood, and artist with **zero token fees, zero rate limits, and sub-5ms response times**.
4. **Resilient 3-Tier REST Lyrics Engine**:
   - When Genius blocked HTML scrapers with Cloudflare 403 errors, this bot introduced an open REST failover pipeline (LRCLIB $\rightarrow$ Lyrics.ovh $\rightarrow$ Genius) that delivers clean, formatted lyrics in ~300ms with zero API keys required.
5. **Context-Preserving Playback & Local Mac Fallback**:
   - Starts tracks inside their album context using offsets (`context_uri` + `offset`) so your Spotify Desktop queue buffer is never wiped, backed by a native macOS AppleScript (`osascript`) bridge if the cloud device is asleep.
6. **Optional 1-Click Listening Party Mode (`/host`)**:
   - Works privately for you by default, and whenever you have friends over, type `/host` to generate a 4-digit PIN / 1-click link so guests can queue and control music from Telegram without needing Spotify Premium.

---

## 🏗 How the Whole Application Works (System Architecture)

Here is how the entire application is structured—from your input in Telegram, through the 4 core engines inside [`main.py`](main.py), out to your Spotify player and lyrics databases:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                THE BARONESS — FULL SYSTEM ARCHITECTURE                              │
└─────────────────────────────────────────────────────────────────────────────────────────────────────┘

                                   ┌─────────────────────────────────┐
                                   │       📱 TELEGRAM INTERFACE     │
                                   │  • Solo Owner Mode (Default)    │
                                   │  • Party Guest Mode (Optional)  │
                                   └────────────────┬────────────────┘
                                                    │
                                    Taps Menu / Controls / Types ~ * !
                                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   🤖 THE BARONESS CORE (main.py)                                    │
│                                                                                                     │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐  ┌─────────────────┐  │
│  │ 1. CURATION ENGINE   │  │ 2. 15-BTN REMOTE DECK│  │ 3. LYRICS PIPELINE   │  │ 4. PERSONA &    │  │
│  │ • Global Charts      │  │ • Play / Pause / Skip│  │ • Title Sanitizer    │  │    ACCESS GATE  │  │
│  │ • 6 Mood Cards + NLP │  │ • Volume ±10%        │  │ • Paragraph Chunker  │  │ • Zero-AI Prose │  │
│  │ • Song & Artist Find │  │ • Shuffle & Repeat   │  │ • 3-Tier Failover    │  │ • Owner Lock &  │  │
│  │ • Random Serendipity │  │ • Queue & Liked Songs│  │   Dispatcher         │  │   Optional PIN  │  │
│  │ • Similar / Maestro  │  │ • Playlist & Devices │  │                      │  │   Party Manager │  │
│  └──────────┬───────────┘  └──────────┬───────────┘  └──────────┬───────────┘  └─────────────────┘  │
└─────────────┼─────────────────────────┼─────────────────────────┼───────────────────────────────────┘
              │                         │                         │
              └────────────┬────────────┘                         │
                           ▼                                      ▼
        ┌─────────────────────────────────────┐    ┌─────────────────────────────────────┐
        │     🎵 SPOTIFY PLAYBACK & CLOUD     │    │    📜 3-TIER LYRICS DATABASES       │
        │  • Spotify Web API (OAuth / Spotipy)│    │  Tier 1: LRCLIB Open REST API       │
        │  • Atomic Track-Change Poller       │    │  Tier 2: Lyrics.ovh REST API        │
        │  • macOS AppleScript Local Fallback │    │  Tier 3: Genius Scraper Fallback    │
        └──────────────────┬──────────────────┘    └─────────────────────────────────────┘
                           ▼
        ┌─────────────────────────────────────┐
        │   🔊 YOUR ACTIVE SPOTIFY DEVICE     │
        │   (Mac / iPhone / Web / Speakers)   │
        └─────────────────────────────────────┘
```

```mermaid
flowchart TB
    User["📱 You on Telegram<br/>(Solo Daily Use or Optional Party Mode)"] -->|"Slash Commands (/select, /controls)<br/>Text Shortcuts (~song, *mood, !artist)<br/>or 15-Button Inline Deck"| Core

    subgraph Core["🤖 The Baroness Core Application (main.py)"]
        direction LR
        Persona["🎭 Zero-AI Regency Persona<br/>(Instant Bridgerton commentary)"]
        Discovery["🔍 7-Mode Curation Engine<br/>(Charts · Moods · Search · Artist · Playlists · Random)"]
        Controls["🎛 15-Button Remote & Library<br/>(Transport · Vol · Queue · Liked Songs · Playlists · Devices)"]
        LyricsEng["📜 Lyrics Sanitizer & Chunker<br/>(Regex title cleaner + HTML-safe paragraphs)"]
    end

    Discovery & Controls -->|"Spotipy Web API<br/>(Album Context + Offset)"| SpotifyAPI["🎵 Spotify Cloud API"]
    SpotifyAPI -.->|"If desktop app asleep"| MacIPC["💻 macOS AppleScript Bridge"]
    SpotifyAPI & MacIPC --> Speaker["🔊 Your Active Spotify Player<br/>(Mac, Phone, or Speaker)"]

    LyricsEng -->|"1st Try (~300ms)"| Tier1["🌐 LRCLIB REST API"]
    Tier1 -.->|"2nd Try"| Tier2["🌐 Lyrics.ovh REST API"]
    Tier2 -.->|"3rd Try"| Tier3["🌐 Genius Fallback"]
```

### How It Works as a Whole:
1. **Your Input in Telegram:** You interact with the bot using slash commands (`/select`, `/controls`, `/nowplaying`, `/devices`), quick text prefixes (`~song`, `*mood`, `!artist`), or the 15-button remote control deck.
2. **Four Core Engines in [`main.py`](main.py):**
   - **Curation Engine:** Searches Spotify's catalog using genre taxonomies, live chart playlists, wildcard sampling, or your personal playlists to pick a playable song.
   - **Remote & Library Controller:** Adjusts transport (Play/Pause/Next/Prev), volume (`±10%`), shuffle/repeat, adds to your queue, saves tracks to your Liked Songs or playlists, and switches active devices.
   - **Zero-AI Regency Persona:** Wraps every recommendation and status card in custom *Bridgerton*-style commentary generated deterministically in under 5ms.
   - **3-Tier Lyrics Pipeline:** Cleans messy song titles (stripping *"Remastered"* or *"Taylor's Version"*) and fetches lyrics from LRCLIB $\rightarrow$ Lyrics.ovh $\rightarrow$ Genius.
3. **Output to Your Spotify Player:** Commands your active Spotify device via the Spotify Web API (with a native macOS AppleScript fallback if your desktop app is idle) and waits until the track change is confirmed before updating your chat card.
4. **Solo by Default, Social When You Want:** By default, the bot is locked to your personal Telegram ID (`ALLOWED_TELEGRAM_USER_IDS`). Whenever you want friends to join, `/host` opens a temporary PIN session and `/endparty` closes it.

---

## ✨ Core Features

### 1. Seven Curation & Discovery Modes (`/select`)
- **A Chart-Topping Number ♭** — Curates a random hit from global/top charts without repeating recently sent tracks (resets every 15 minutes).
- **A Harmonious Find ♯** — Search for any song on Spotify (type directly after selecting, or prefix anytime with `~Song Name`). Includes quick-select buttons for alternative matches.
- **A Melody for Your Spirits ♮** — Pick from 6 interactive parlor mood cards (*Radiant & Euphoric*, *Melancholy & Saudade*, *Romantic & Tender*, *Serene & Tranquil*, *Fierce & Tempestuous*, *Midnight Reverie*) or type your mood with `*mood` to curate tracks matching those audio characteristics.
- **Tracks from a Beloved Maestro ♪** — Search and play tracks from a specific artist (type directly after selecting, or prefix anytime with `!Artist Name`), prioritizing exact artist name matches.
- **Tracks from a Personal Collection 𝄢** — Browse your own Spotify playlists and start playback directly from Telegram.
- **Serendipity's Choice ☾** — Discover a completely random playable track from Spotify's catalog.
- **In the Spotlight ✧** — View a live Now Playing card with playback status, progress timestamp, active device, volume, shuffle, and repeat state.

---

### 2. Custom Telegram Playback Control Deck (`/controls`)

| Row | Controls | Description |
| :--- | :--- | :--- |
| **Row 1: Transport** | `⏮ Prev` · `⏯ Play / Pause` · `⏭ Next` | Resume or pause active playback without wiping the queue, or skip tracks. |
| **Row 2: Modes & Volume** | `🔀 Shuffle` · `🔁 Repeat` · `🔉 -10%` · `🔊 +10%` | Toggle shuffle on/off, cycle repeat mode (`off` → `context` → `track`), and adjust device volume. |
| **Row 3: Queue & Library** | `>> Queue` · `❥ Save/Unsave` · `+ Playlist` | Add the track to your queue, save/remove from Liked Songs, or add to any of your personal playlists (with duplicate detection). |
| **Row 4: Discovery & Lyrics** | `✿ Similar Tune` · `❀ Maestro's Best` · `𝛂 Lyrics` | Get a similar song recommendation, another top track by the same artist, or fetch formatted lyrics in ~300ms. |
| **Row 5: Navigation** | `✧ Spotlight` · `📱 Devices` · `📜 Menu` | Refresh the Now Playing card, switch active playback between your phone/desktop/web player, or return to the main menu. |

---

### 3. Immediate Auto-Playback on Recommendation & Discovery
Whenever you choose or request any track (*Serendipity's Choice*, *✿ Similar Tune*, *❀ Maestro's Best*, *A Chart-Topping Number*, *A Melody for Your Spirits*, *A Harmonious Find*, or alternative track selections):
- **Immediate Playback**: The bot immediately commands Spotify to start streaming that exact track on your active player, replacing the active track without requiring extra button presses.
- **Atomic Cloud Sync**: Waits for Spotify's cloud player to acknowledge the change before outputting metadata.
- **Rich Card & Controls**: Presents The Baroness's Regency writeup alongside the live Now Playing card and the full 15-button playback deck.

---

### 4. Live Listening Party Mode & Room Code Sharing (`/host` & `/join`)

Instead of manually editing `.env` with friends' Telegram numeric IDs and restarting the server whenever guests visit, the bot features a dynamic **Listening Party ("Musical Salon")** engine:

```mermaid
flowchart TD
    Host["👑 Host (Owner)<br/>Runs /host"] -->|"Generates ephemeral code<br/>e.g. 7492 + 1-Click Link"| Bot["🤖 Telegram Bot"]
    Guest1["👤 Guest A<br/>Taps link or /join 7492"] -->|"Authorized for active session"| Bot
    Guest2["👤 Guest B<br/>Taps link or /join 7492"] -->|"Authorized for active session"| Bot
    Bot -->|"Commands playback via Web API"| Spotify["🎵 Host's Spotify Player<br/>(Mac / Speaker / Phone)"]
    Bot -.->|"Real-Time Broadcast Alerts<br/>'@danbury queued Anti-Hero'"| HostChat["💬 Host's Private Telegram Chat"]
```

1. **Host Commands (`/host`, `/party`, `/endparty`)**:
   - `/host` — Generates a temporary 4-digit passcode (e.g., `7492`) and an instant 1-click invite link (`https://t.me/Bot?start=7492`).
   - `/party` — Displays session duration and real-time roster of connected guests.
   - `/endparty` — Concludes the gathering, revokes all guest sessions, notifies guests, and restores private master mode.
2. **Guest Onboarding (`/join <code>`, `/leave`, or 1-Click Link)**:
   - **One-Click Deep Linking:** Guests tap `https://t.me/YourBot?start=7492` to authenticate and join instantly without manual code entry.
   - **Manual Code:** Guests can also message the bot `/join 7492`.
   - `/leave` — Guests can exit the gathering voluntarily at any point.
3. **Live Host Activity Broadcast Feed**:
   - Whenever any guest selects or controls playback (skips, pauses, resumes, changes volume, queues tracks, saves to Liked Songs, or plays playlists/artists), the bot sends an immediate alert to the host's private chat attributing the action to `@username` or guest ID.
   - **Self-Echo Suppression:** Actions taken by the host themselves are automatically suppressed from the broadcast feed to avoid redundant chat echoes.
4. **Privacy & Security Guarantees**:
   - Guests never log into Spotify and never see the host's Spotify credentials.
   - Telegram hides user phone numbers from bots by default, and guests cannot see each other's private chats or Telegram IDs.

---

## 💬 Bot Commands & Shortcuts

### Slash Commands
- `/start` — Greeted by The Baroness + opens the main selection menu (or 1-click joins a party via invite link)
- `/select` — Open The Baroness's musical selection menu
- `/controls` — Summon the custom 15-button Spotify Playback Controls deck
- `/nowplaying` — Show the currently playing track, progress bar, and device status
- `/devices` — View and switch active Spotify playback devices
- `/host` — Convene a party session with an ephemeral 4-digit PIN and 1-click invite link *(Host only)*
- `/join <code>` — Join an active musical salon party using a 4-digit passcode
- `/party` — View current party status, room code, session duration, and connected guests
- `/leave` — Exit the active party gathering voluntarily
- `/endparty` — Conclude the party session and revoke all guest access *(Host only)*
- `/help` — View the complete compendium of commands and text shortcuts

### Direct Text Shortcuts
You can type these at any time in the chat (or simply type without a prefix right after clicking the corresponding menu button):
- `~Cruel Summer Taylor Swift` — Search for a specific song (*A Harmonious Find*)
- `*saudade` — Curate a track for your mood (*A Melody for Your Spirits*)
- `!Laufey` — Play music by a specific artist (*Tracks from a Beloved Maestro*)

---

## 📸 Demo & Interface Walkthrough

Below is a live walkthrough and labeled interface showcase of **The Baroness (`@thebaroness_bot`)** in action inside Telegram:

### 1. Bot Identity & Persona (`@thebaroness_bot`)
<p align="center">
  <img src="assets/01_bot_profile.png" alt="01 - The Baroness Bot Profile" width="440" />
</p>

---

### 2. End-to-End Live Walkthrough (Animated GIF)
> *Watch The Baroness greet the listener, curate a track from the global charts, stream it immediately to Spotify Desktop, render the 15-button playback control deck, and fetch full lyrics in real time:*

<p align="center">
  <img src="assets/00_live_demo_walkthrough.gif" alt="00 - Live Demo Walkthrough GIF" width="380" />
</p>

---

### 3. Labeled Interface Screenshots (Step-by-Step)

| **Step 1: Regency Greeting & Main Menu (`/start`)** | **Step 2: Now Playing Card & 15-Button Control Deck** | **Step 3: Instant Lyrics View (`𝛂 Lyrics`)** |
| :---: | :---: | :---: |
| <img src="assets/02_welcome_and_main_menu.jpg" alt="02 - Welcome & Main Curation Menu" width="270" /> | <img src="assets/03_now_playing_and_control_deck.jpg" alt="03 - Now Playing Card & 15-Button Control Deck" width="270" /> | <img src="assets/04_instant_lyrics_display.jpg" alt="04 - Instant Formatted Lyrics View" width="270" /> |
| *The Baroness welcomes you with a custom Regency letter and presents all 7 curation modes plus quick access to the Control Deck.* | *Selecting a mode immediately starts playback on your active Spotify device, displays live progress/device/volume metadata, and summons the 15-button remote.* | *Tapping `𝛂 Lyrics` retrieves clean, paragraph-chunked lyrics in ~300ms via the 3-tier REST pipeline.* |

| **Step 4: Personal Playlist Collection (`Tracks from a Personal Collection 𝄢`)** | **Step 5: Artist Discovery & Direct Text Shortcut (`!ive`)** |
| :---: | :---: |
| <img src="assets/05_personal_playlist_collection.jpg" alt="05 - Tracks from a Personal Collection" width="270" /> | <img src="assets/06_beloved_maestro_artist_playback.jpg" alt="06 - Beloved Maestro Artist Search & Playback" width="270" /> |
| *Fetches your own Spotify playlists dynamically and renders them as interactive inline buttons so you can spin a random track from any personal collection.* | *Using `Tracks from a Beloved Maestro ♪` or the `!artist` shortcut (`!ive`) delivers a Regency commentary, high-res artist portrait card, and immediate playback of a standout track.* |

### Typical 30-Second Workflow:
1. **Pick a Vibe or Search:** Tap `A Chart-Topping Number ♭` or `A Melody for Your Spirits ♮` (or type `~Cruel Summer`).
2. **Music Plays Immediately:** Your Spotify Desktop/Phone player switches to the curated track right away while preserving your queue buffer.
3. **Control Everything Inline:** Use the 15-button deck to adjust volume (`🔉 -10%` / `🔊 +10%`), save to Liked Songs (`❥`), add to a personal playlist, or pull up full lyrics (`𝛂 Lyrics`) in ~300ms.
4. **Host a Gathering (Optional):** Type `/host` to generate a 4-digit PIN and 1-click invite link so friends can queue songs from their own phones.

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10+
- An active **Spotify Premium** account (required by Spotify's Web API for remote playback controls)
- A **Spotify Developer App** ([Spotify Developer Dashboard](https://developer.spotify.com/dashboard)) with Redirect URI set to `http://127.0.0.1:8888/callback`
- A **Telegram Bot Token** from [@BotFather](https://t.me/BotFather)
- *(Optional)* A **Genius API Client Access Token** ([Genius API Clients](https://genius.com/api-clients)) as a Tier-3 lyrics fallback (Tier 1 & Tier 2 work out-of-the-box with zero keys)

### 2. Installation

```bash
git clone https://github.com/ginnnn-e/spotify.git
cd spotify/spotify-telegram-bot-v2

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Environment Variables (`.env`)

Copy [`.env.example`](.env.example) to `.env` in `spotify-telegram-bot-v2/` and fill in your credentials:

```env
SPOTIPY_CLIENT_ID=your_spotify_client_id
SPOTIPY_CLIENT_SECRET=your_spotify_client_secret
SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
TELEGRAM_ACCESS_TOKEN=your_telegram_bot_token

# Single-user private mode & default Party Host (your personal numeric Telegram user ID)
ALLOWED_TELEGRAM_USER_IDS=123456789

# Optional Tier-3 fallback (LRCLIB & Lyrics.ovh require no keys)
GENIUS_ACCESS_TOKEN=
```

### 4. Spotify Authorization (`auth.py`)

Before starting the bot for the first time (or whenever your Spotify session expires), run the headless authentication helper:

```bash
python auth.py
```

1. Your browser will open Spotify's login and authorization page.
2. Click **Agree** to authorize playback control and library scopes.
3. Your browser will redirect to `http://127.0.0.1:8888/callback?code=...`.
4. Copy that full URL from your browser's address bar, paste it into the terminal prompt, and press Enter.
5. The script exchanges the code for a fresh Spotify token and saves it to `.cache`.

### 5. Run the Bot

```bash
python main.py
```

---

## ⚖️ Ethical & Open-Source Libraries

All dependencies and APIs used in this project are **100% free, open-source, and ethical**:

| Component | License / Type | Role |
| :--- | :--- | :--- |
| **`python-telegram-bot`** | LGPLv3 (Open Source) | Official async framework for the Telegram Bot API |
| **`spotipy`** | MIT License (Open Source) | Official Python client for the Spotify Web API |
| **`LRCLIB` (`lrclib.net`)** | MIT / Public REST API | Community-driven, keyless REST API built for open-source audio players |
| **`Lyrics.ovh`** | Free Public REST API | Lightweight JSON REST endpoint for secondary lyrics failover |
| **`python-dotenv` & `requests`** | BSD-3 / Apache 2.0 | Standard Python environment & HTTP libraries |

---

## 📜 Changelog & Version History

### [v2.3.1] — November 7, 2026
- **Real-Time Host Activity Broadcasts**:
  - Whenever any guest or listener performs an action involving choosing or controlling a song (skipping tracks, pausing, resuming, adjusting volume, queueing tracks, saving to Liked Songs, toggling shuffle, changing repeat mode, or playing playlists/artists), the bot immediately broadcasts a live activity notification card directly to the host's private Telegram chat.
  - **Self-Echo Suppression**: Actions performed by the host themselves are suppressed from the broadcast feed, preventing redundant notification clutter in the host's personal chat.
  - **Dynamic Actor Attribution**: Clearly highlights the actor's Telegram handle (e.g. `@username`), full name, or guest ID in each notification (e.g. `👑 Salon Activity: @danbury queued Cruel Summer by Taylor Swift`).
  - **Party Mode & Multi-User Whitelist Parity**: Works seamlessly during active Party Mode sessions (`/host`), and falls back to the designated bot owner (`ALLOWED_TELEGRAM_USER_IDS[0]`) in multi-user whitelist deployments.
- **Comprehensive `/help` Compendium Overhaul**:
  - Upgraded the `/help` guide to comprehensively enumerate every single menu command categorized into *Melodic Curation & Playback Deck*, *Salon Party Mode*, and *General & Assistance*, alongside instant direct text shortcuts (`~`, `*`, `!`).
- **Repository Cleanup & Security Hardening**:
  - Removed unused legacy prototype `server.py` and `Flask` dependency; added [`.env.example`](.env.example).

### [v2.3.0] — November 7, 2026
- **Live Party Mode (`/host`, `/join`, `/party`, `/leave`, `/endparty`)**:
  - Implemented dynamic salon room codes allowing the host to run `/host` and generate a temporary 4-digit PIN with a 1-click invite link (`t.me/YourBot?start=7492`).
  - Guests join dynamically without needing Spotify accounts, Spotify apps, or `.env` configuration updates.
  - Added real-time host notifications when guests join or leave.
  - Added `/party` to view connected guests and session duration.
  - Added `/endparty` to immediately conclude the gathering and revoke all guest access.
- **Plain-English Deep Dive Clarifications**:
  - Added simple, non-technical *"In Plain English"* explanations at the top of every discovery engine in the architecture reference.

### [v2.2.0] — November 7, 2026
- **Multi-Tiered REST Lyrics Engine**:
  - Integrated **LRCLIB** (`https://lrclib.net`) as Tier 1 primary lyrics provider: 100% free, open-source REST API built for audio players that bypasses Cloudflare 403 anti-bot gates entirely.
  - Integrated **Lyrics.ovh** as Tier 2 high-availability fallback REST API.
  - Retained Genius as Tier 3 scraper fallback.
  - Decoupled from Genius API key: the bot now delivers lyrics out of the box even without a `GENIUS_ACCESS_TOKEN`.
- **Title Sanitization & Unicode Apostrophe Normalization**:
  - Upgraded `clean_song_title` to preserve legitimate hyphenated titles (*"Can't Feel My Face"*, *"T-Shirt"*, *"Spider-Man"*, *"A-O-K"*) while cleanly stripping edition tags (*"- Taylor's Version"*, *"- Remastered"*, *"- From The Vault"*, *"(feat. ...)"*).
  - Resolved straight (`'`) vs. curly (`’`) apostrophe mismatches across all lyrical search providers.
- **Paragraph-Safe Chunking & HTML Protection**:
  - Implemented `chunk_lyrics_for_telegram` which splits oversized lyrics along paragraph boundaries (`\n\n`) so HTML styling tags are never truncated across chunk limits.
  - Added automatic plain-text fallbacks to guarantee messages are always delivered even if special entity parsing conflicts occur.
- **Instant Lyrics Delivery**:
  - Lyrics now display immediately upon tapping `𝛂 Lyrics` in ~300ms, eliminating the redundant 2-step selection menu.

### [v2.1.0] — November 7, 2026
- **Immediate Auto-Playback on Recommendation**:
  - Unified playback dispatcher (`play_and_display_track`) across all 6 curation/discovery flows (*Serendipity's Choice*, *A Chart-Topping Number*, *A Melody for Your Spirits*, *A Harmonious Find*, *✿ Similar Tune*, and *❀ Maestro's Best*).
  - Replaces the current track immediately upon selection without requiring secondary button presses.
- **Desktop Buffer Wipe Fix**:
  - Changed playback initiation to use album context and track offset (`context_uri=target_album, offset={"uri": track_uri}`), preventing Spotify Desktop from wiping its active queue and pausing.
- **Playability & Region Licensing Filter**:
  - Added `market="from_token"` and `is_playable: True` filters to `serendipitys_choice()`, preventing unplayable region-locked discoveries.
- **Multi-User Access & Visibility Architecture**:
  - Documented open access configuration (`ALLOWED_TELEGRAM_USER_IDS=`) and two-sided visibility mechanics (Spotify real-time audio sync vs. Telegram private chat separation vs. shared group chats).
  - Designed the Party Room Code architecture roadmap (`/host`, `/join CODE`, `/leave`, `/endparty`).
- **Comprehensive API Search Mechanics Reference**:
  - Added deep-dive architectural section explaining exact endpoints, search syntax, wildcards, and deduplication logic for each curation function.

### [v2.0.0] — November 6, 2026
- **Zero-AI Regency Transformation**:
  - Replaced all OpenAI and external LLM dependencies with 100% deterministic, high-variety Bridgerton/Lady Whistledown Regency prose templates.
  - Zero API subscription costs, zero token latency, zero quota limits.
- **Revamped 15-Button Playback Control Deck**:
  - Added dedicated controls for transport (prev/pause/next), modes (shuffle, repeat cycle), volume adjustments (±10%), queue management, Liked Songs toggle, playlist picker with duplicate detection, lyrics, and device switching.
- **Directory Isolation**:
  - Created standalone `spotify-telegram-bot-v2/` workspace, keeping legacy v1 code completely intact.

---
---

# Part II — Technical Deep Dives & Engineering Logs

## 🔍 Deep Dive: Spotify API Search & Retrieval Mechanics

This section details the exact queries, filters, API endpoints, deduplication strategies, and fallbacks used by each curation function to discover and stream music.

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 SPOTIFY API DISCOVERY FLOW                                   │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
  1. A Chart-Topping Number   ──► sp.search(q="Top 50 Global", type="playlist") ─► sp.playlist_items()
  2. Serendipity's Choice     ──► sp.search(q="%<char>%", offset=0..50, market="from_token")
  3. A Harmonious Find        ──► sp.search(q="<query>", type="track", limit=5)
  4. A Melody for Your Spirits──► sp.search(q='genre:"<mood_genre>"', type="track", limit=30)
  5. Beloved Maestro          ──► sp.search(q="<artist>", type="artist") ─► context_uri="spotify:artist:id"
  6. Similar Tune             ──► sp.artist(id) ─► sp.search(q='genre:"<tag>"', type="track")
  7. Maestro's Best           ──► sp.artist_top_tracks(id) ─► Filter out current song
  8. Personal Collection      ──► sp.current_user_playlists(limit=50) ─► Filter owner == user
```

---

### 1. `chart_topping_number()` — "A Chart-Topping Number ♭"
> **In Plain English:** The bot checks Spotify's live global charts (like *Top 50 Global* and *Today's Top Hits*) and instantly plays a popular trending hit you haven't heard yet in this session.

- **Spotify API Endpoints:**
  - `sp.search(q=query, type="playlist", limit=5)`
  - `sp.playlist_items(playlist_id, limit=30)`
  - `sp.current_user_top_tracks(limit=30, time_range="short_term")` *(Fallback 1)*
  - `sp.search(q="hit", limit=30, type="track")` *(Fallback 2)*
- **Search Strategy:**
  - Iterates over dynamic chart query terms: `["Top 50 Global", "Today's Top Hits", "Top Hits 2026", "Viral 50 Global"]`.
  - Retrieves the top matching playlist and extracts up to 30 track items.
  - Builds a pool of at least 15 trending tracks.
- **Filtering & Deduplication:**
  - Tracks previously played songs in memory via `sent_songs_ctn`.
  - Filters `tracks_pool` against `sent_songs_ctn` so you never hear the same song twice in a session.
  - When the entire pool has been exhausted, `sent_songs_ctn.clear()` resets history automatically so music never stops.
- **Immediate Playback:**
  - Hands the chosen track to `play_and_display_track()`, starting playback via `sp.start_playback(context_uri=album_uri, offset={"uri": track_uri})`.

---

### 2. `serendipitys_choice()` — "Serendipity's Choice ☾"
> **In Plain English:** The bot picks a surprise mystery song out of Spotify's 100-million-track library at random, verifies that it's licensed and playable in your region, and plays it immediately.

- **Spotify API Endpoints:**
  - `sp.search(q=random_query, offset=random_offset, limit=10, type="track", market="from_token")`
  - `sp.search(q="a", offset=0, limit=20, type="track", market="from_token")` *(Fallback)*
- **Search Strategy:**
  - Generates wildcard search patterns across the alphabet: `"%a"`, `"%a%"`, `"a%"`, etc.
  - Randomly selects one query string and pairs it with a random offset between 0 and 50: `random.randint(0, 50)`.
- **Licensing & Region Filtering:**
  - Passes `market="from_token"`: guarantees Spotify checks licensing against your actual account region.
  - Inspects results and discards unplayable tracks: `[t for t in items if t and t.get("is_playable", True)]`.
- **Immediate Playback:**
  - Selects a random playable candidate and streams it via `play_and_display_track()`.

---

### 3. `harmonious_find(search)` — "A Harmonious Find ♯" (`~query`)
> **In Plain English:** Type any song name or lyrics (e.g. `~Cruel Summer`), and the bot finds the exact track on Spotify and plays it instantly, while giving you buttons to switch to alternative versions (like acoustic or live cuts).

- **Spotify API Endpoints:**
  - `sp.search(q=query_str, offset=0, limit=5, type="track")`
- **Search Strategy:**
  - Strips any leading `~` prefix and whitespace from user input.
  - Queries Spotify's catalog for top matching tracks (limit 5).
- **Result Caching & Alternative Buttons:**
  - Automatically streams the #1 top match immediately (`items[0]`).
  - Simultaneously stores items 1–4 into `search_track_cache`.
  - Attaches quick-switch interactive buttons (`TRK:1`, `TRK:2`, `TRK:3`) directly to the Telegram message so you can switch to an alternate version with a single tap if the first wasn't your intended mix.

---

### 4. `recommender_from_mood(mood_key_or_text)` — "A Melody for Your Spirits ♮" (`*mood`)
> **In Plain English:** Tap a parlor mood card (like *Radiant*, *Romantic*, or *Melancholy*) or type how you feel (e.g. `*calm`), and the bot finds a song tailored to that emotional vibe and starts playing it.

- **Spotify API Endpoints:**
  - `sp.search(q=query, type="track", limit=30)`
  - `sp.search(q="acoustic pop", type="track", limit=20)` *(Fallback)*
- **Search Strategy:**
  - **Preset Match:** If matching one of the 6 parlor presets (*Radiant*, *Melancholy*, *Romantic*, *Serene*, *Tempestuous*, *Midnight*):
    - Retrieves preset search terms (e.g., `"euphoric dance"`, `"lo-fi chill"`, `"rainy day acoustic"`) and genre tags (e.g., `genre:"indie"`, `genre:"pop"`, `genre:"r-b"`).
    - Selects a random query variant to ensure diversity on every tap.
  - **Freeform Text Match:** If user inputs custom text (e.g., `*heartbreak` or `*studying`):
    - Analyzes keywords using `generate_audio_feature_values()` to map to the closest emotional profile, or queries `f"{mood_key_or_text} music"`.
- **Candidate Pool Sampling:**
  - Fetches 30 candidate tracks matching the mood genre.
  - Selects a track at random via `random.choice(candidates)` and immediately streams it.

---

### 5. `play_artist_selection()` — "Tracks from a Beloved Maestro ♪" (`!artist`)
> **In Plain English:** Type any artist's name (e.g. `!Laufey` or `!The Weeknd`), and the bot finds their official artist discography on Spotify and begins playing their music through your speakers.

- **Spotify API Endpoints:**
  - `sp.search(q=query_val, limit=10, type="artist")`
  - `sp.start_playback(context_uri=f"spotify:artist:{artist_id}")`
  - `sp.artist_top_tracks(artist_id)` *(Fallback if Spotify player is sleeping)*
- **Search Strategy:**
  - Queries Spotify's artist catalog with `limit=10`.
  - **Exact Match Prioritization:** Iterates through results to find an exact case-insensitive name match (`a["name"].lower() == query.lower()`). This prevents substring or collaborative collisions (e.g., typing `"milet"` returning `"Aimer"` because of collaborative releases).
- **Immediate Playback:**
  - Launches full artist context playback directly on your Spotify device.
  - Asynchronously polls `wait_for_track_change(match_artist_id=artist_id)` until the player confirms music is streaming from this artist.

---

### 6. `recommender(artist_id, url)` — "✿ Similar Tune"
> **In Plain English:** Tap this while a song is playing to discover a fresh track by a similar artist that shares the same musical style and genre, playing it immediately.

- **Spotify API Endpoints:**
  - `sp.artist(artist_id)`
  - `sp.search(q='genre:"<genre>"', type="track", limit=30)`
  - `recommender_from_artist(artist_id, song_id, song_name)` *(Fallback)*
- **Search Strategy:**
  - Calls `sp.artist(artist_id)` to extract Spotify's official genre taxonomy tags for the artist.
  - Constructs a targeted query: `genre:"<primary_genre>"`. If no genre tag is assigned by Spotify, searches by artist name in quotes: `"<artist_name>"`.
- **Deduplication:**
  - Pulls 30 candidates and explicitly filters out the current track: `t["id"] != song_id`.
  - Randomly selects from candidates and auto-plays via `play_and_display_track()`.

---

### 7. `recommender_from_artist(a_id, s_id, s_name)` — "❀ Maestro's Best"
> **In Plain English:** Tap this to immediately play another one of the greatest hits by the artist you're currently listening to (without repeating the song currently playing).

- **Spotify API Endpoints:**
  - `sp.artist_top_tracks(artist_id)`
- **Search Strategy:**
  - Pulls the top 10 most popular tracks for the specified artist.
- **Deduplication:**
  - Filters out the song currently playing: `candidate["id"] != song_id and candidate["name"] != song_name`.
  - Randomly picks from the remaining top tracks and immediately streams it.

---

### 8. `Tracks from a Personal Collection 𝄢` (`PPID:`)
> **In Plain English:** Shows you an interactive menu of your own personal Spotify playlists so you can tap one and instantly start playing your own collection directly from Telegram.

- **Spotify API Endpoints:**
  - `sp.current_user()`
  - `sp.current_user_playlists(limit=50)`
  - `sp.start_playback(context_uri=f"spotify:playlist:{playlist_id}")`
- **Search Strategy:**
  - Fetches the authenticated user's `display_name`.
  - Queries all library playlists and filters: `playlist["owner"]["display_name"] == current_user_display`. This ensures only playlists *created* by you are shown, excluding public curated or followed playlists.
- **Immediate Playback:**
  - Displays each playlist as an interactive button (`PPID:<id>`).
  - When clicked, immediately streams the playlist via `context_uri=f"spotify:playlist:{playlist_id}"`.

---

## 📖 Architecture & Function Reference

A concise reference guide to every core function implemented in [`main.py`](main.py):

### 1. Security, Party Auth & Lifecycle
- `is_host(user)` — Returns `True` if the Telegram user is the master bot owner (`ALLOWED_USER_IDS`) or the designated host of the active party.
- `is_user_authorized(user)` — Validates if a user is permitted to control the bot (checks `ALLOWED_USER_IDS`, active party host, or authenticated party guests).
- `get_actor_label(user)` — Returns a readable label (`@username`, full name, or `Guest <id>`) for activity notifications.
- `broadcast_to_host(context, message_text, sender_user_id)` — Dispatches real-time salon activity notifications to the host's private chat while suppressing self-echoes when the host acts themselves.
- `clear_list()` — Clears recently sent chart song IDs (`sent_songs_ctn`) to reset the 15-minute anti-repetition memory.
- `start_timer()` — Spawns a daemon `threading.Timer` that fires `clear_list()` every 900 seconds (15 minutes).

### 2. Regency Persona & Lyrics Engines (Zero-AI)
- `generate_intro_response()` — Randomly selects an opening Bridgerton/Lady Whistledown greeting letter for `/start`.
- `generate_preliminary_choice_response(user_choice)` — Returns tailored Regency commentary acknowledging the chosen salon menu option.
- `generate_song_writeup(s_title, s_artist, s_alb)` — Dynamically injects live track title, artist name, and album into rotating Regency commentary templates.
- `generate_song_quote(s_title, s_artist)` — Randomly selects one of 7 Regency musical epigrams displayed inside spoiler tags.
- `generate_mood_response(user_mood)` — Crafts an empathetic Regency reflection validating the user's chosen mood.
- `generate_audio_feature_values(user_mood)` — Maps user mood input to acoustic target values for fallback filtering.
- `generate_artist_response(user_chosen_artist)` — Composes a personalized Regency compliment for the requested maestro.
- `clean_song_title(input_song_name)` — Removes extraneous edition tags (e.g. `(Live)`, `- Remastered`, `- Taylor's Version`) while preserving hyphenated words (`Can't Feel My Face`, `T-Shirt`).
- `format_song_name(input_song_name)` — Backwards-compatible alias for `clean_song_title`.
- `clean_raw_lyrics(raw_lyrics)` — Cleans raw scraped lyrics by removing Genius headers, embed counters, and redundant whitespace.
- `chunk_lyrics_for_telegram(title, lyrics_body)` — Formats lyrics with Regency headers and chunks text along paragraph breaks (`\n\n`) to prevent HTML entity truncation.
- `fetch_lrclib_lyrics(title, artist)` — Tier 1 REST lyrics retrieval via `https://lrclib.net/api`.
- `fetch_ovh_lyrics(title, artist)` — Tier 2 REST lyrics retrieval via `https://api.lyrics.ovh`.
- `fetch_best_lyrics(title, artist_str)` — Multi-tiered REST + Genius failover lyrics engine.
- `format_ms(ms)` — Converts millisecond durations to standard `M:SS` format.
- `format_now_playing_card(playback, header_note)` — Compiles live playback details (title, artist, album, progress, device, volume, shuffle, repeat, quote) into an HTML card that is never blank.

### 3. Keyboards & Navigation
- `menu_keyboard()` — Builds the 6-button main salon discovery menu.
- `mood_preset_keyboard()` — Builds the 6 interactive parlor mood cards (*Radiant*, *Melancholy*, *Romantic*, *Serene*, *Tempestuous*, *Midnight*).
- `playback_keyboard()` — Builds the custom 15-button Spotify playback control deck (transport, volume, modes, queue, save, lyrics, devices, menu).

### 4. Spotify Track Helpers
- `s_name(path)` / `s_id(path)` / `s_artist_name(path)` / `s_artist_id(path)` / `s_preview_url(path)` / `s_url(path)` / `s_album(path)` — Extractors for Spotify track dictionaries.
- `set_global_song_from_track(track_obj)` — Synchronizes global song variables and returns formatted recommendation strings (`rec_1`, `rec_2`).

### 5. Playback & Device Control
- `ensure_device_id()` — Returns the active Spotify player ID, or falls back to the first available connected player.
- `macos_spotify_cmd(action, uri)` — Controls the local macOS Spotify desktop application directly via AppleScript (`osascript`) as an instant fallback.
- `wait_for_track_change(prev_track_id, target_track_id, match_artist_id, match_artist_name)` — Asynchronously polls Spotify until cloud status confirms the track ID has changed or matches the target before rendering status messages.
- `play_and_display_track(...)` — Central auto-playback dispatcher: commands Spotify to stream a new track within its album context, renders the live card with the playback controls deck, and notifies the host.
- `play_artist_selection(target_message, chosen_artist, context, actor_user)` — Initiates playback for an artist catalog context, waits for track confirmation, displays controls, and broadcasts to the host.

### 6. Discovery & Curation Engines
- `chart_topping_number()` / `serendipitys_choice()` / `harmonious_find(search)` / `recommender(artist_id, url)` / `recommender_from_artist(a_id, s_id, s_name)` / `recommender_from_mood(mood_key_or_text)` / `current_song()` — Core curation functions detailed in the Deep Dive section above.

### 7. Telegram Bot Commands & Callbacks
- `post_init(application)` — Registers bot commands and sets the Telegram UI menu button at startup.
- `process_join(update, context, code)` — Authenticates a guest passcode and adds them to `active_party["guests"]`.
- `start` / `host_command` / `join_command` / `party_command` / `leave_command` / `endparty_command` / `select` / `controls_command` / `nowplaying_command` / `devices_command` / `help_command` — Slash command handlers.
- `send_devices_menu(...)` — Renders available Spotify devices with active status badges (`🟢`/`⚪`) and transfer buttons.
- `handle_text_callback(update, context)` — Routes incoming text messages based on prefixes (`~song`, `*mood`, `!artist`) or active conversation mode.
- `handle_button_callback(update, context)` — Central callback query router handling all inline button actions and triggering host activity broadcasts.

---

## 🔮 Future Work & Multi-Tenant SaaS Scaling Roadmap

### 1. How Multi-User Control Works Today
Currently, the bot is linked to your **Spotify Premium account** via OAuth. When access is opened (via `/host` Party Mode or listing friend Telegram IDs):
- **On Your Spotify App (Real-time Sync):**
  - **Yes, it shows on your side immediately.** Because the bot commands your Spotify account directly via the Spotify Web API, any change a friend makes (skipping a track, choosing a mood, adjusting volume, pausing) instantly updates the Spotify app on your Mac, iPhone, or connected smart speaker in real-time.
- **On Your Telegram Chat (Interface Separation + Host Broadcasts):**
  - **In 1-on-1 Private Chats:** Telegram private chats are isolated so a guest's menu clicks stay in their own chat window, while the **Host Activity Broadcast Feed** sends a clean one-line notification to your private chat whenever a guest selects or controls a song.
  - **In a Telegram Group Chat:** If you add the bot to a shared group chat, **everyone sees all commands, search results, and playback cards together** in real-time.

### 2. Planned Party Mode Enhancements
- **`/kick @username`**: Remove an individual disruptive guest without ending the whole party for everyone else.
- **Collaborative Queue-Only Mode ("Jukebox Mode")**: Option to route all guest song selections to `sp.add_to_queue()` so guests never cut off a currently playing track mid-song.
- **Democratic Skip Voting**: Require 50%+ of connected guests to tap `⏭ Next` before skipping a track.
- **Session Auto-Expiry & Cooldowns**: Auto-expire room codes after 6–12 hours and add per-user rate limits against button spamming.

### 3. Scaling to a Multi-Tenant SaaS Platform (Multiple Hosts & Independent Parties)

To transition from a personal party bot to a hosted SaaS platform supporting hundreds of simultaneous independent parties:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                               MULTI-TENANT PARTY SCALING FLOW                                   │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
   Host 1 (Alice)   ──► Web OAuth /login ──► Generates Code "1024" ──► Friends join Alice's Speaker
   Host 2 (Bob)     ──► Web OAuth /login ──► Generates Code "5599" ──► Friends join Bob's Speaker
   Host 3 (Charlie) ──► Web OAuth /login ──► Generates Code "8821" ──► Friends join Charlie's Speaker
                                                    │
                                                    ▼
                     Central SQLite / PostgreSQL Database ("sessions" table)
                     [room_code | host_id | refresh_token | guest_ids | expires_at]
```

1. **Database-Backed Session Storage (Replacing `.cache`)**:
   - Migrate from the local file `.cache` to an encrypted SQLite / PostgreSQL `sessions` table.
   - Key each party session by `room_code` storing the host's encrypted Spotify OAuth refresh token, host Telegram ID, and guest list.
   - Dynamic client instantiation: When any guest sends an instruction, look up their active `room_code` and execute commands via `spotipy.Spotify(auth=session["refresh_token"])`.
2. **Web OAuth Onboarding for Multiple Hosts**:
   - Host runs `/host` in Telegram ➔ bot returns a unique authorization URL: `https://your-domain.com/login?tg_id=<id>`.
   - Host taps the link and authorizes with Spotify in their mobile browser.
   - The web server callback saves the refresh token, generates a 4-digit PIN (e.g., `7492`), and notifies the host in Telegram with their room code and invite link.
3. **Containerized Deployment & Horizontal Scaling**:
   - Package with Docker and deploy on cloud hosting (Railway, Fly.io, or VPS).
   - Use Redis for sub-millisecond room-code routing and ephemeral guest state caching.

---

## 🛠 Troubleshooting & Bug Fixes Log

A complete engineering record of issues diagnosed, investigated, and resolved during development:

### 1. Telegram Polling Conflict (`telegram.error.Conflict`)
- **Symptom**: `telegram.error.Conflict: terminated by other getUpdates request; make sure that only one bot instance is running`.
- **Cause**: Telegram Bot API only allows one active polling connection per bot token at any given moment. A background process was running simultaneously with the terminal instance.
- **Fix**: Terminated duplicate background tasks (`manage_task kill`) and ensured only a single bot process polls at a time.

---

### 2. Expired / Revoked Spotify Token (`invalid_grant`)
- **Symptom**: `spotipy.oauth2.SpotifyOauthError: error: invalid_grant, error_description: Refresh token revoked` causing `A chart-topping tune could not be retrieved right now`.
- **Cause**: The `.cache` file copied from the older repository contained an expired/revoked session token from an earlier year. Spotipy crashed when attempting to refresh an invalid grant.
- **Fix**: Removed stale `.cache`, created the [`auth.py`](auth.py) authentication helper to generate fresh credentials with full playback scopes, and added error trapping with helpful prompts in `main.py`.

---

### 3. Port 8888 Collision & IPv6 Connection Refused
- **Symptom**: `OSError: [Errno 48] Address already in use` or browser displaying *"This site can’t be reached (localhost refused to connect)"*.
- **Cause**: Spotipy's default `open_browser=True` launches an internal `HTTPServer` on port `8888`. If port 8888 was lingering from a previous script, it crashed with `Errno 48`. When browsers attempted to connect via IPv6 `[::1]:8888`, the connection was refused.
- **Fix**: Re-architected [`auth.py`](auth.py) with `open_browser=False` to eliminate port binding entirely. Instead, the script opens the browser to Spotify's login page and prompts you to copy/paste the redirected address bar URL directly into the terminal, parsing the authorization code cleanly.

---

### 4. Redirect URI Mismatch & Security Whitelist
- **Symptom**: `redirect_uri: Not matching configuration` or `This redirect URI is not secure`.
- **Cause**: Spotify OAuth 2.0 strictly enforces exact string matching against the Redirect URIs configured in the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard). Furthermore, Spotify updated its security policy (per RFC 8252) to disallow plain `http://localhost` over HTTP.
- **Fix**: Standardized on the permitted loopback IP literal `http://127.0.0.1:8888/callback` across `.env`, `README.md`, and the Spotify Developer Dashboard settings.

---

### 5. Spotify API 404 Deprecations (Playlists & Recommendations)
- **Symptom**: Spotipy logging `HTTP Error 404` for playlist items and `https://api.spotify.com/v1/recommendations returned 404`.
- **Cause**:
  1. The legacy Today's Top Hits playlist ID (`37i9dQZF1DXcBWIGoYBM5M`) was retired by Spotify, returning `404: Resource not found`.
  2. In late November 2024, Spotify officially deprecated and disabled the `/v1/recommendations` and audio-features endpoints for standard developer apps.
- **Fix**:
  1. Rewrote `chart_topping_number()` to dynamically search top global playlists (`Top 50 Global`, `Today's Top Hits`, `Billboard Hot 100`) and extract live tracks.
  2. Replaced `sp.recommendations(...)` in `recommender()` and `recommender_from_mood()` with Spotify catalog genre and artist search queries, completely eliminating 404 logs.

---

### 6. Queue Overwriting & Blank Now Playing Cards
- **Symptom**: Clicking Play reset the currently playing song back to 0:00, replaced the playback queue with 30 artist tracks, or showed a blank card (`<b></b> by Album:`).
- **Cause**:
  1. The original `play_song` implementation called `sp.start_playback(uris=..., offset={"position": 0})`, which forcefully discarded the user's active queue and restarted from the beginning.
  2. `format_now_playing_card` relied on global variables that were empty strings `""` when no track had been curated in chat.
  3. `toggle_play_pause` checked `current_song()` after only `0.4s` before Spotify cloud synced (which takes ~`0.8s`), raising an uncaught `ValueError`.
- **Fix**:
  1. Consolidated transport into a non-destructive `⏯ Play / Pause` toggle that calls `sp.start_playback(device_id=dev_id)` without `uris`, resuming your existing track from its exact position without resetting.
  2. Updated `format_now_playing_card` to extract track, artist, album, and duration directly from Spotify's live playback object so it is never blank.
  3. Increased sync polling delay to `0.8s` with graceful fallback handling.

---

### 7. Playback Failing to Start (`Application isn’t running. (-600)`)
- **Symptom**: Clicking Play showed successful API calls, but no music played through speakers.
- **Cause**: Spotify's cloud API reported `"My MacBook"` as a registered device from a previous session, but the Spotify desktop application (`/Applications/Spotify.app`) was completely closed on macOS.
- **Fix**:
  1. Verified that the Spotify desktop application must be open to receive audio output.
  2. Integrated a native macOS AppleScript bridge (`macos_spotify_cmd`) inside `main.py` as an immediate local fallback to command Spotify directly on macOS (`tell application "Spotify" to play...`) alongside cloud Web API calls.

---

### 8. Playback Hijacking & Bot Security (`ALLOWED_TELEGRAM_USER_IDS`)
- **Symptom / Security Inquiry**: *"Can anyone who has access to the bot link use the bot? Will it overlap with mine?"*
- **Risk**: In Telegram, bots with public `@username` handles accept messages from anyone who opens a chat with them. Because the bot server is authenticated to your single personal Spotify account via OAuth, any stranger with the bot handle could send commands to change your songs, adjust volume, or modify your saved playlists.
- **Fix**:
  1. Implemented a strict authorization guard via `ALLOWED_TELEGRAM_USER_IDS` in `.env` (configured with your personal numeric Telegram ID, e.g. `123456789`).
  2. Guarded all Telegram entry points (`/start`, `/select`, `/controls`, `/nowplaying`, `/devices`, `/help`), direct text handlers (`~`, `*`, `!`), and inline button clicks (`handle_button_callback`) using `is_user_authorized()`.
  3. Any unauthorized user who messages the bot is rejected with a Bridgerton-themed notice (*"Dearest Gentle Traveler, I am afraid this private musical salon is reserved exclusively for its master..."*) and their commands are dropped before touching Spotify.

---

### 9. Song Metadata Race Condition on Artist Search (`!artist`)
- **Symptom**: *"For the song logs, it's not logging it correctly. When I type `![artist]` and it starts playing a song from them, the message shows the previous song."*
- **Cause**: Spotify's Web API is an asynchronous cloud service. When the bot triggers `sp.start_playback(context_uri=f"spotify:artist:{artist_id}")`, Spotify starts streaming the new artist on your device, but `sp.current_playback()` continues to return the previous track's cached metadata for 0.8s – 1.5s. Querying playback immediately captured the old track before Spotify's cloud synced.
- **Fix**:
  1. Implemented an asynchronous polling helper `wait_for_track_change(prev_track_id=old_id, match_artist_id=artist_id, match_artist_name=artist_name)` with exponential polling (up to 4s, checking every 0.5s).
  2. `play_artist_selection` captures the active track ID (`old_id`) prior to sending the play command.
  3. `wait_for_track_change` rejects any cached response where the track ID is still `old_id` or where the artist does not match the chosen maestro, returning only once Spotify confirms the new track is actively playing.
  4. Applied the same atomic change detector to `⏮ Prev` (`play_previous_song`), `⏭ Next` (`play_next_song`), and personal playlist playback (`PPID:`).

---

### 10. Immediate Auto-Playback & Desktop Queue Wipe Fix
- **Symptom**: *"When I clicked on Serendipity's Choice, it stopped playing the current song and removed all playback. It didn't play the new song."*
- **Cause**:
  1. **Bare Track URIs wiping playback buffer**: On Spotify Desktop and Spotify Connect, invoking `sp.start_playback(uris=["spotify:track:..."])` without album context while shuffle or repeat is active destroys the player's active queue buffer, causing Spotify to clear all playback (`item: None`, `is_playing: False`).
  2. **Unplayable / Region-Locked Searches**: Random query searches (`%a%`) without `market="from_token"` could occasionally return tracks not licensed for streaming in the user's country.
- **Fix**:
  1. Updated [`play_and_display_track`](main.py#L1055-L1135) to stream tracks with their album context and track offset: `context_uri=target_album, offset={"uri": track_uri}`. This preserves the player's buffer, starts the target song immediately, and keeps `is_playing: True`.
  2. Updated `serendipitys_choice()` to search with `market="from_token"` and filter only playable items (`is_playable: True`).
  3. Integrated `wait_for_track_change(target_track_id=track_id)` for atomic verification before sending the live Now Playing card and controls deck.

---

### 11. Cloudflare 403 Anti-Bot Gate on Genius Web & Multi-Tiered REST Lyrics Engine
- **Symptom**: *"Unfortunately, lyrics for Blank Space are not available, or it may be an instrumental track. It says this for every song now."*
- **Root Cause**:
  1. **Genius.com Cloudflare 403 Blocking**: The official Genius JSON API (`api.genius.com`) only returns metadata and song search results; it intentionally excludes lyrics text due to publisher licensing agreements. The `lyricsgenius` Python library works by scraping `https://genius.com/*-lyrics` via web requests. Genius recently deployed strict Cloudflare Turnstile anti-bot checks across `genius.com`, returning `403 Forbidden` to all automated web-scraping requests (`requests.exceptions.HTTPError: 403 Client Error: Forbidden`).
  2. **Process Running Old Code in Memory**: Python processes keep code in RAM once started. After code modifications, the bot process must be restarted to load updated handlers.
- **Fix**:
  1. **Architected a Multi-Tiered REST Lyrics Engine (`fetch_best_lyrics`)**:
     - **Tier 1 (LRCLIB REST API — `fetch_lrclib_lyrics`)**: Direct query to `https://lrclib.net/api/get` and `/api/search`. Free, open-source, official REST endpoint designed for audio players with zero scraping, no Cloudflare gates, and sub-second response times (~300ms).
     - **Tier 2 (Lyrics.ovh REST API — `fetch_ovh_lyrics`)**: High-availability secondary REST API (`https://api.lyrics.ovh/v1/{artist}/{title}`).
     - **Tier 3 (Genius API Fallback)**: Official search and scraper fallback if unblocked.
  2. **Decoupled from Genius Token Dependency**: The bot no longer aborts if `GENIUS_ACCESS_TOKEN` is unset or failing; Tier 1 and Tier 2 provide pristine lyrics text completely keyless.
  3. **Paragraph-Safe Chunking & HTML Protection (`chunk_lyrics_for_telegram`)**: Chunks text along paragraph breaks (`\n\n`) to prevent splitting HTML tags, with automatic fallback to plain text if Telegram entity parsing ever encounters special characters.
