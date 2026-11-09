# 📜 Changelog & Version History

All notable technical updates, architecture migrations, and version releases for **The Baroness (v2)**.

---

### [v2.3.1] — November 7, 2026
- **Real-Time Host Activity Broadcasts**:
  - Whenever any guest selects or controls playback (skips, pauses, volume adjustments, queueing, saving to Liked Songs, repeat/shuffle toggles, or playing playlists/artists), the bot sends an immediate alert to the host's private Telegram chat.
  - **Self-Echo Suppression**: Actions taken by the host themselves are filtered out to prevent redundant chat notifications.
  - **Dynamic Actor Attribution**: Clearly attributes the action to `@username`, full name, or guest ID (e.g., `👑 Salon Activity: @danbury queued Cruel Summer by Taylor Swift`).
  - **Multi-User Whitelist Parity**: Works during active Party Mode sessions (`/host`) and falls back to the master owner (`ALLOWED_TELEGRAM_USER_IDS[0]`).
- **Comprehensive `/help` Compendium Overhaul**:
  - Reorganized all bot commands into categorized groupings (*Melodic Curation & Playback Deck*, *Salon Party Mode*, and *General & Assistance*) alongside text shortcuts (`~`, `*`, `!`).
- **Repository Cleanup & Security Hardening**:
  - Removed unused legacy prototype `server.py` and `Flask` dependency; added `.env.example`.

---

### [v2.3.0] — November 7, 2026
- **Live Party Mode (`/host`, `/join`, `/party`, `/leave`, `/endparty`)**:
  - Generates dynamic 4-digit PINs with 1-click deep links (`t.me/YourBot?start=CODE`) allowing guests to control music without needing Spotify Premium.
  - Added real-time host notifications when guests join or leave.
  - Added `/party` to inspect active session duration and connected guests.
  - Added `/endparty` to conclude the session and revoke all guest access immediately.

---

### [v2.2.0] — November 7, 2026
- **Multi-Tiered REST Lyrics Engine**:
  - Integrated **LRCLIB** (`https://lrclib.net`) as Tier 1 primary lyrics provider: 100% keyless REST API bypassing Cloudflare 403 anti-bot gates (~300ms latency).
  - Integrated **Lyrics.ovh** as Tier 2 high-availability fallback REST API.
  - Retained Genius as Tier 3 scraper fallback.
  - Decoupled from Genius API key: delivers lyrics out of the box with zero required tokens.
- **Title Sanitization & Unicode Apostrophe Normalization**:
  - Cleanly strips edition tags (*"- Taylor's Version"*, *"- Remastered"*, *"(feat. ...)"*) while preserving hyphenated words (*"Can't Feel My Face"*, *"T-Shirt"*).
  - Normalizes curly vs. straight apostrophes across lyrical providers.
- **Paragraph-Safe Chunking & HTML Protection**:
  - Chunks oversized lyrics along paragraph boundaries (`\n\n`) to prevent breaking Telegram HTML entity tags.
- **Instant Lyrics Delivery**:
  - Lyrics now display immediately upon tapping `𝛂 Lyrics` in ~300ms without intermediate menus.

---

### [v2.1.0] — November 7, 2026
- **Immediate Auto-Playback on Recommendation**:
  - Unified playback dispatcher (`play_and_display_track`) across all curation flows to stream the selected track instantly without secondary confirmation taps.
- **Desktop Buffer Wipe Fix**:
  - Configured playback initiation via album context and track offset (`context_uri=target_album, offset={"uri": track_uri}`), preventing Spotify Desktop from wiping its active queue buffer.
- **Playability & Region Licensing Filter**:
  - Added `market="from_token"` and `is_playable: True` filters to `serendipitys_choice()`, preventing region-locked tracks.

---

### [v2.0.0] — November 6, 2026
- **Zero-AI Regency Transformation**:
  - Replaced paid LLM dependencies with 100% deterministic, high-variety Bridgerton/Lady Whistledown prose templates ($0 token fees, <5ms latency).
- **Revamped 15-Button Playback Control Deck**:
  - Added dedicated controls for transport, volume ($\pm$10%), modes (shuffle/repeat), queueing, Liked Songs toggle, playlist picker with duplicate detection, lyrics, and device switching.
- **Directory Isolation**:
  - Isolated standalone `spotify-telegram-bot-v2/` workspace, keeping legacy v1 code untouched.
