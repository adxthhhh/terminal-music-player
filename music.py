import curses
import json
import os
import glob
import time
import vlc
from pathlib import Path
from ytmusicapi import YTMusic
import yt_dlp
from tinytag import TinyTag

# --- 1. CONFIGURATION & STATE ---
CONFIG_DIR = Path.home() / ".config" / "life_os" / "music"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_FILE = CONFIG_DIR / "history.json"

# Initialize global APIs and Engines
ytmusic = YTMusic()
vlc_instance = vlc.Instance('--no-video', '--quiet')
player = vlc_instance.media_player_new()

def load_history():
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_history(history):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=4)

# --- 2. BACKEND LOGIC ---
def search_local_directory(directory, query):
    """Scans for local mp3/m4a/flac files matching the query."""
    extensions = ['mp3', 'm4a', 'flac', 'wav']
    for ext in extensions:
        pattern = f"{directory}/**/*{query}*.{ext}"
        # case-insensitive search via glob is tricky, so we check lowercase matches manually if needed, 
        # but this simple glob works for exact substring matches.
        results = glob.glob(pattern, recursive=True)
        if results:
            return results[0]
    return None

def fetch_from_youtube(query, stdscr):
    """Scrapes YT Music and extracts the raw audio stream."""
    stdscr.addstr(curses.LINES - 3, 0, f"[*] Not found locally. Searching web for '{query}'...", curses.A_BOLD)
    stdscr.refresh()
    
    search_results = ytmusic.search(query, filter="songs")
    if not search_results:
        return None
        
    top_result = search_results[0]
    video_id = top_result['videoId']
    
    ydl_opts = {'format': 'bestaudio/best', 'quiet': True, 'no_warnings': True, 'extract_flat': 'in_playlist'}
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
        stream_url = info['url']
        
    # Format duration from seconds to M:SS
    duration_sec = top_result.get('duration_seconds', 0)
    duration_str = f"{duration_sec // 60}:{duration_sec % 60:02d}"
        
    return {
        "title": top_result['title'],
        "artist": top_result['artists'][0]['name'], 
        "duration": duration_str,
        "url": stream_url
    }

def play_audio(source):
    """Stops current audio and plays the new source."""
    player.stop()
    media = vlc_instance.media_new(source)
    player.set_media(media)
    player.play()

# --- 3. FRONTEND / UI LOOP ---
def main(stdscr):
    curses.echo()
    curses.curs_set(1) # Show cursor
    
    # Initial Directory Prompt
    stdscr.clear()
    stdscr.addstr(0, 0, "Enter music directory path (Leave blank for ~/Music): ", curses.A_BOLD)
    stdscr.refresh()
    
    dir_input = stdscr.getstr(0, 54, 100).decode('utf-8').strip()
    music_dir = dir_input if os.path.isdir(dir_input) else str(Path.home() / "Music")
    
    history = load_history()
    
    # Main Application Loop
    while True:
        stdscr.clear()
        curses.noecho()
        
        # Sort history by plays (descending) and get top 10
        sorted_songs = sorted(history.values(), key=lambda x: x['plays'], reverse=True)[:10]
        
        # Render Header
        stdscr.addstr(0, 0, " TOP 10 PLAYED ", curses.A_REVERSE | curses.A_BOLD)
        stdscr.addstr(1, 0, "=" * 60)
        
        # Render List
        for i, song in enumerate(sorted_songs, 1):
            row = f"{i}. {song['title']} - {song['artist']} [{song['duration']}] ({song['plays']})"
            stdscr.addstr(i + 1, 0, row)
            
        # Render Input Prompt
        prompt_y = max(13, len(sorted_songs) + 3)
        stdscr.addstr(prompt_y, 0, "> Enter number (1-10) to play, or type a song name to search: ", curses.A_BOLD)
        stdscr.refresh()
        
        curses.echo()
        user_input = stdscr.getstr(prompt_y + 1, 0, 100).decode('utf-8').strip()
        
        if not user_input:
            continue
            
        # Handle Input
        if user_input.isdigit() and 1 <= int(user_input) <= len(sorted_songs):
            # Play from history list
            target = sorted_songs[int(user_input) - 1]
            stdscr.addstr(prompt_y + 3, 0, f"[*] Playing: {target['title']}", curses.A_BOLD)
            stdscr.refresh()
            play_audio(target['source_path'])
            
            key = f"{target['title']} - {target['artist']}"
            history[key]['plays'] += 1
            
        else:
            # Search new song
            stdscr.addstr(prompt_y + 3, 0, f"[*] Searching local directory for '{user_input}'...", curses.A_BOLD)
            stdscr.refresh()
            
            local_path = search_local_directory(music_dir, user_input)
            
            if local_path:
                play_audio(local_path)
                try:
                    tag = TinyTag.get(local_path)
                    title = tag.title or user_input
                    artist = tag.artist or "Unknown Artist"
                    duration = f"{int(tag.duration) // 60}:{int(tag.duration) % 60:02d}" if tag.duration else "0:00"
                except:
                    title, artist, duration = user_input, "Local File", "0:00"
                
                new_key = f"{title} - {artist}"
                if new_key not in history:
                    history[new_key] = {"title": title, "artist": artist, "duration": duration, "plays": 1, "source_path": local_path}
                else:
                    history[new_key]['plays'] += 1
            else:
                yt_data = fetch_from_youtube(user_input, stdscr)
                if yt_data:
                    play_audio(yt_data['url'])
                    new_key = f"{yt_data['title']} - {yt_data['artist']}"
                    if new_key not in history:
                        history[new_key] = {"title": yt_data['title'], "artist": yt_data['artist'], "duration": yt_data['duration'], "plays": 1, "source_path": yt_data['url']}
                    else:
                        history[new_key]['plays'] += 1
                else:
                    stdscr.addstr(prompt_y + 4, 0, "[!] Song not found anywhere.", curses.A_BOLD)
                    stdscr.refresh()
                    time.sleep(2)
                    continue

        save_history(history)
        time.sleep(1) # Brief pause to let user see status before UI refresh

if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        print("\nExiting Music Player...")
