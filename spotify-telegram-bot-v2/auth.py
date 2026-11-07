"""
Spotify Authentication Helper for spotify-telegram-bot-v2.
Run this script once to log in to your Spotify account:
    python auth.py
"""

import os
import sys
import webbrowser
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

SCOPE = (
    "user-library-read,user-read-playback-state,user-modify-playback-state,"
    "user-read-currently-playing,user-library-modify,playlist-read-private,"
    "playlist-modify-public,playlist-modify-private"
)


def authenticate():
    cache_path = os.path.join(BASE_DIR, ".cache")
    auth_manager = SpotifyOAuth(
        scope=SCOPE,
        cache_path=cache_path,
        open_browser=False,  # Prevents port 8888 binding collisions and IPv6 localhost errors
    )

    auth_url = auth_manager.get_authorize_url()
    print("=" * 68)
    print("🌹 The Baroness — Spotify Authorization")
    print("=" * 68)
    print("\n1. Opening Spotify login in your browser...")
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    print("\nIf your browser did not open automatically, visit this URL:\n")
    print(auth_url)
    print("\n" + "=" * 68)
    print("2. Log in and click 'Agree'.")
    print("3. Your browser will redirect to a URL starting with:")
    print("   http://localhost:8888/callback?code=...")
    print("   (Even if the page says 'Unable to connect' or 'Site can't be reached',")
    print("    the URL in your browser's address bar is what we need!)")
    print("=" * 68)

    try:
        redirected = input("\n👉 Paste the full redirect URL (or just the code) here: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nAborted.")
        return

    if not redirected:
        print("❌ No URL provided. Aborting.")
        return

    try:
        code = auth_manager.parse_response_code(redirected)
        token_info = auth_manager.get_access_token(code=code, as_dict=True)
        if token_info:
            sp = spotipy.Spotify(auth_manager=auth_manager)
            user = sp.current_user()
            print(f"\n🎉 Successfully authenticated as: {user.get('display_name')}!")
            print(f"✅ Credentials successfully saved to: {cache_path}")
            print("\nYou can now start the bot:\n   python main.py\n")
        else:
            print("❌ Could not obtain token from the provided URL. Please try again.")
    except Exception as e:
        print(f"\n❌ Error during token exchange: {e}")
        print("Please run 'python auth.py' again and ensure the full redirected URL is copied.")


if __name__ == "__main__":
    authenticate()
