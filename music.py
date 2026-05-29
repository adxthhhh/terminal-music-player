import os
import curses
import json
import time
import threading
import vlc
from pathlib import Path
from ytmusicapi import YTMusic
import yt_dlp
from tinytag import TinyTag

# --- 1. CONFIGURATION & STATE ---
CONFIG_DIR = Path.home() / ".config" / "life_os" / "music"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

HISTORY_FILE = CONFIG_DIR / "history.json"
PLAYLISTS_FILE = CONFIG_DIR / "playlists.json"
SETTINGS_FILE = CONFIG_DIR / "settings.json"

# Global APIs & Players
ytmusic = YTMusic()
vlc_instance = vlc.Instance('--no-video', '--quiet')
player = vlc_instance.media_player_new()

# Event flag for auto-advance
song_finished_event = threading.Event()

def vlc_end_callback(event):
    """Triggers when VLC finishes playing a file/stream."""
    song_finished_event.set()

# Attach the callback to VLC's event manager
vlc_events = player.event_manager()
vlc_events.event_attach(vlc.EventType.MediaPlayerEndReached, vlc_end_callback)

def load_json(filepath, default_state):
    """Safely loads JSON data."""
    if filepath.exists():
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception:
            return default_state
    return default_state

def save_json(filepath, data):
    """Safely saves JSON data."""
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)

# --- 2. BACKEND LOGIC ---
def sanitize_query(query):
    """Prevents path traversal vulnerabilities."""
    return query.replace("/", "").replace("\\", "").replace(".", "")

def search_local_directory(directory_path, query):
    """Performs a safe, case-insensitive local file search."""
    clean_query = sanitize_query(query).lower()
    if not clean_query: 
        return None
        
    music_path = Path(directory_path)
    if not music_path.exists() or not music_path.is_dir(): 
        return None
        
    extensions = {'.mp3', '.m4a', '.flac', '.wav'}
    
    try:
        # Recursively search all files, checking extensions and substrings case-insensitively
        for filepath in music_path.rglob('*'):
            if filepath.suffix.lower() in extensions:
                if clean_query in filepath.name.lower():
                    return str(filepath)
    except Exception:
        pass
    return None

def search_youtube(query, stdscr):
    """Fetches metadata and video ID, but NOT the expiring stream URL."""
    safe_addstr(stdscr, curses.LINES - 3, 0, f"[*] Not found locally. Searching web for '{query}'...", curses.A_BOLD)
    stdscr.refresh()
    
    try:
        search_results = ytmusic.search(query, filter="songs")
        if not search_results:
            return None
            
        top_result = search_results[0]
        video_id = top_result.get('videoId')
        if not video_id: return None
        
        # Safely extract metadata with fallbacks to prevent IndexErrors
        artist = top_result.get('artists', [{'name': 'Unknown Artist'}])[0]['name']
        duration_sec = top_result.get('duration_seconds', 0)
        duration_str = f"{duration_sec // 60}:{duration_sec % 60:02d}"
            
        return {
            "title": top_result.get('title', 'Unknown Title'),
            "artist": artist, 
            "duration": duration_str,
            "source_type": "youtube",
            "source_id": video_id
        }
    except Exception:
        return None

def resolve_stream(video_id):
    """Automatically tests common browsers to find valid YouTube cookies."""
    
    # List of browsers yt-dlp supports. It will try them in this order.
    browsers_to_try = ['firefox', 'chrome', 'edge', 'brave', 'opera', 'safari']
    
    for browser in browsers_to_try:
        print(f"[*] Attempting to use cookies from: {browser}...")
        
        ydl_opts = {
            'format': 'bestaudio/best', 
            'quiet': True, 
            'no_warnings': True,
            'cookiesfrombrowser': (browser, ) 
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                print(f"[+] Success! Connected to YouTube using {browser}.")
                return info['url']
                
        except Exception as e:
            # If the browser isn't installed, is locked, or isn't logged into YT, it fails silently and loops to the next.
            error_msg = str(e).lower()
            if "sign in to confirm" in error_msg:
                print(f"[-] {browser} found, but it is not logged into YouTube.")
            elif "locked" in error_msg:
                print(f"[-] {browser} database is locked (Browser might need to be closed).")
            else:
                print(f"[-] Failed to use {browser}.")
            continue 

    print("[!] ERROR: Could not find any valid YouTube cookies on this machine.")
    print("[!] Please ensure you are logged into YouTube on one of your web browsers.")
    return None

def play_audio(source_type, source_id, stdscr):
    """Prepares and plays the media securely."""
    player.stop()
    song_finished_event.clear() # Reset the auto-advance flag
    
    if source_type == "local":
        media_url = source_id
    elif source_type == "youtube":
        safe_addstr(stdscr, curses.LINES - 2, 0, "[*] Resolving fresh stream URL...", curses.A_DIM)
        stdscr.refresh()
        media_url = resolve_stream(source_id)
        if not media_url:
            safe_addstr(stdscr, curses.LINES - 2, 0, "[!] Failed to resolve stream.    ", curses.A_BOLD)
            stdscr.refresh()
            time.sleep(1.5)
            return False
            
    media = vlc_instance.media_new(media_url)
    player.set_media(media)
    player.play()
    return True

# --- 3. UI HELPERS ---
def safe_addstr(stdscr, y, x, text, attr=0):
    """Prevents fatal crashes when resizing terminals."""
    try:
        max_y, max_x = stdscr.getmaxyx()
        if 0 <= y < max_y and 0 <= x < max_x:
            stdscr.addstr(y, x, text[:max_x - x - 1], attr)
    except curses.error:
        pass

def get_input_with_events(stdscr, prompt_y, prompt_x):
    """Non-blocking input loop that returns early if VLC triggers auto-advance."""
    stdscr.timeout(200) # Check events every 200ms
    curses.noecho()
    input_str = ""
    
    while True:
        # Check if the song finished playing naturally
        if song_finished_event.is_set():
            stdscr.timeout(-1)
            return "EVENT_NEXT"
            
        try:
            char = stdscr.getch()
            if char == -1:
                continue
            if char in (10, 13): # Enter key
                break
            elif char in (8, 127, curses.KEY_BACKSPACE):
                input_str = input_str[:-1]
            elif 32 <= char <= 126: # Standard printable characters
                input_str += chr(char)
                
            # Render the typing dynamically
            stdscr.move(prompt_y, prompt_x)
            stdscr.clrtoeol()
            safe_addstr(stdscr, prompt_y, prompt_x, input_str)
            
        except curses.error:
            pass
            
    stdscr.timeout(-1)
    return input_str.strip()

# --- 4. MAIN LOOP ---
def main_app(stdscr):
    curses.curs_set(1)
    
    settings = load_json(SETTINGS_FILE, {"music_dir": str(Path.home() / "Music")})
    history = load_json(HISTORY_FILE, {})
    playlists = load_json(PLAYLISTS_FILE, {})
    
    try:
        while True:
            stdscr.clear()
            curses.noecho()
            music_dir = settings.get("music_dir")
            
            safe_addstr(stdscr, 0, 0, " TERMINAL MUSIC PLAYER ", curses.A_REVERSE | curses.A_BOLD)
            safe_addstr(stdscr, 1, 0, "=" * 60)
            safe_addstr(stdscr, 3, 0, "1. Start Music Player")
            safe_addstr(stdscr, 4, 0, "2. Create Playlist")
            safe_addstr(stdscr, 5, 0, "3. Play Playlist")
            safe_addstr(stdscr, 6, 0, f"4. Change Music Directory (Current: {music_dir})")
            safe_addstr(stdscr, 7, 0, "5. Exit")
            
            safe_addstr(stdscr, 9, 0, "> Choose an option (1-5): ", curses.A_BOLD)
            stdscr.refresh()
            
            choice = get_input_with_events(stdscr, 9, 26)
            
            if choice == '1':
                while True:
                    stdscr.clear()
                    sorted_songs = sorted(history.values(), key=lambda x: x['plays'], reverse=True)[:10]
                    
                    safe_addstr(stdscr, 0, 0, " TOP 10 PLAYED ", curses.A_REVERSE | curses.A_BOLD)
                    safe_addstr(stdscr, 1, 0, "=" * 60)
                    
                    for i, song in enumerate(sorted_songs, 1):
                        row = f"{i}. {song['title']} - {song['artist']} - {song['duration']} - {song['plays']}"
                        safe_addstr(stdscr, i + 1, 0, row)
                        
                    prompt_y = min(max(13, len(sorted_songs) + 3), curses.LINES - 6)
                    safe_addstr(stdscr, prompt_y, 0, "> Play (1-10), search song, 'p' pause, 'b' back: ", curses.A_BOLD)
                    stdscr.refresh()
                    
                    user_input = get_input_with_events(stdscr, prompt_y, 49)
                    
                    if not user_input or user_input == "EVENT_NEXT": continue
                    if user_input.lower() in ['b', 'back', 'q', 'quit']: break
                    if user_input.lower() in ['p', 'pause']:
                        player.pause()
                        continue
                        
                    if user_input.isdigit() and 1 <= int(user_input) <= len(sorted_songs):
                        target = sorted_songs[int(user_input) - 1]
                        
                        # Legacy data safeguard
                        if 'source_type' not in target:
                            old_path = target.get('source_path', '')
                            target['source_type'] = "youtube" if old_path.startswith("http") else "local"
                            target['source_id'] = old_path

                        safe_addstr(stdscr, prompt_y + 3, 0, f"[*] Playing: {target['title']}", curses.A_BOLD)
                        play_audio(target['source_type'], target['source_id'], stdscr)
                        
                        key = f"{target['title']} - {target['artist']}"
                        history[key]['plays'] += 1
                        
                    else:
                        safe_addstr(stdscr, prompt_y + 3, 0, f"[*] Searching local directory for '{user_input}'...", curses.A_BOLD)
                        stdscr.refresh()
                        local_path = search_local_directory(music_dir, user_input)
                        
                        if local_path:
                            play_audio("local", local_path, stdscr)
                            try:
                                tag = TinyTag.get(local_path)
                                title = tag.title or user_input
                                artist = tag.artist or "Unknown Artist"
                                duration = f"{int(tag.duration) // 60}:{int(tag.duration) % 60:02d}" if tag.duration else "0:00"
                            except Exception:
                                title, artist, duration = user_input, "Local File", "0:00"
                                
                            source_data = {"source_type": "local", "source_id": local_path}
                            
                        else:
                            yt_data = search_youtube(user_input, stdscr)
                            if yt_data:
                                play_audio(yt_data['source_type'], yt_data['source_id'], stdscr)
                                title, artist, duration = yt_data['title'], yt_data['artist'], yt_data['duration']
                                source_data = {"source_type": yt_data['source_type'], "source_id": yt_data['source_id']}
                            else:
                                safe_addstr(stdscr, prompt_y + 4, 0, "[!] Song not found.", curses.A_BOLD)
                                stdscr.refresh()
                                time.sleep(1.5)
                                continue
                                
                        new_key = f"{title} - {artist}"
                        if new_key not in history:
                            history[new_key] = {"title": title, "artist": artist, "duration": duration, "plays": 1, **source_data}
                        else:
                            history[new_key]['plays'] += 1
                            
                    save_json(HISTORY_FILE, history)
                    
            elif choice == '2':
                stdscr.clear()
                safe_addstr(stdscr, 0, 0, "Enter new or existing playlist name: ", curses.A_BOLD)
                playlist_name = get_input_with_events(stdscr, 0, 37)
                
                if playlist_name and playlist_name != "EVENT_NEXT":
                    if playlist_name not in playlists:
                        playlists[playlist_name] = []
                        
                    # Playlist Population Loop
                    while True:
                        stdscr.clear()
                        safe_addstr(stdscr, 0, 0, f" EDITING PLAYLIST: {playlist_name} ", curses.A_REVERSE | curses.A_BOLD)
                        safe_addstr(stdscr, 1, 0, "=" * 60)
                        
                        # Show current songs in the playlist
                        for i, song in enumerate(playlists[playlist_name], 1):
                            row = f"{i}. {song['title']} - {song['artist']}"
                            safe_addstr(stdscr, i + 1, 0, row)
                            
                        prompt_y = min(max(10, len(playlists[playlist_name]) + 3), curses.LINES - 6)
                        safe_addstr(stdscr, prompt_y, 0, "> Enter song to search and add, or 'd' to finish: ", curses.A_BOLD)
                        stdscr.refresh()
                        
                        query = get_input_with_events(stdscr, prompt_y, 52)
                        
                        if not query or query == "EVENT_NEXT": continue
                        if query.lower() in ['d', 'done', 'q', 'quit', 'b', 'back']:
                            break
                            
                        safe_addstr(stdscr, prompt_y + 2, 0, f"[*] Searching for '{query}'...", curses.A_BOLD)
                        stdscr.refresh()
                        
                        local_path = search_local_directory(music_dir, query)
                        
                        if local_path:
                            try:
                                tag = TinyTag.get(local_path)
                                title = tag.title or query
                                artist = tag.artist or "Unknown Artist"
                                duration = f"{int(tag.duration) // 60}:{int(tag.duration) % 60:02d}" if tag.duration else "0:00"
                            except Exception:
                                title, artist, duration = query, "Local File", "0:00"
                                
                            song_data = {"title": title, "artist": artist, "duration": duration, "source_type": "local", "source_id": local_path}
                            playlists[playlist_name].append(song_data)
                            
                        else:
                            yt_data = search_youtube(query, stdscr)
                            if yt_data:
                                song_data = {"title": yt_data['title'], "artist": yt_data['artist'], "duration": yt_data['duration'], "source_type": yt_data['source_type'], "source_id": yt_data['source_id']}
                                playlists[playlist_name].append(song_data)
                                title = yt_data['title']
                            else:
                                safe_addstr(stdscr, prompt_y + 3, 0, "[!] Song not found anywhere.", curses.A_BOLD)
                                stdscr.refresh()
                                time.sleep(1.5)
                                continue
                                
                        save_json(PLAYLISTS_FILE, playlists)
                        safe_addstr(stdscr, prompt_y + 3, 0, f"[*] Added '{title}' to playlist!", curses.A_BOLD)
                        stdscr.refresh()
                        time.sleep(1)
                        
            elif choice == '3':
                if not playlists:
                    stdscr.clear()
                    safe_addstr(stdscr, 0, 0, "[!] No playlists found. Create one first.", curses.A_BOLD)
                    stdscr.refresh()
                    time.sleep(1.5)
                    continue
                    
                stdscr.clear()
                safe_addstr(stdscr, 0, 0, " AVAILABLE PLAYLISTS ", curses.A_REVERSE | curses.A_BOLD)
                
                playlist_names = list(playlists.keys())
                for i, name in enumerate(playlist_names, 1):
                    safe_addstr(stdscr, i + 1, 0, f"{i}. {name} ({len(playlists[name])} songs)")
                    
                prompt_y = min(max(10, len(playlist_names) + 3), curses.LINES - 6)
                safe_addstr(stdscr, prompt_y, 0, "> Enter playlist number to open: ", curses.A_BOLD)
                stdscr.refresh()
                
                p_choice = get_input_with_events(stdscr, prompt_y, 33)
                
                if p_choice.isdigit() and 1 <= int(p_choice) <= len(playlist_names):
                    selected_playlist = playlist_names[int(p_choice) - 1]
                    songs = playlists[selected_playlist]
                    
                    stdscr.clear()
                    safe_addstr(stdscr, 0, 0, f" PLAYLIST: {selected_playlist} ", curses.A_REVERSE | curses.A_BOLD)
                    for i, song in enumerate(songs, 1):
                        safe_addstr(stdscr, i + 1, 0, f"{i}. {song['title']} - {song['artist']}")
                        
                    safe_addstr(stdscr, prompt_y, 0, "> Enter song number to start playing from: ", curses.A_BOLD)
                    stdscr.refresh()
                    s_choice = get_input_with_events(stdscr, prompt_y, 43)
                    
                    if s_choice.isdigit() and 1 <= int(s_choice) <= len(songs):
                        current_idx = int(s_choice) - 1
                        
                        # Auto-Advance Playlist Loop
                        while 0 <= current_idx < len(songs):
                            stdscr.clear()
                            target = songs[current_idx]
                            
                            # Legacy data safeguard for playlists
                            if 'source_type' not in target:
                                old_path = target.get('source_path', '')
                                target['source_type'] = "youtube" if old_path.startswith("http") else "local"
                                target['source_id'] = old_path

                            safe_addstr(stdscr, 0, 0, f" NOW PLAYING: {target['title']} ", curses.A_REVERSE | curses.A_BOLD)
                            
                            success = play_audio(target['source_type'], target['source_id'], stdscr)
                            if not success:
                                current_idx += 1
                                continue
                                
                            safe_addstr(stdscr, 3, 0, "> [n] Next Track | [p] Pause | [b] Back to Menu: ", curses.A_BOLD)
                            stdscr.refresh()
                            
                            cmd = get_input_with_events(stdscr, 3, 49).lower()
                            
                            if cmd == "EVENT_NEXT" or cmd == 'n':
                                current_idx += 1
                            elif cmd == 'p':
                                player.pause()
                            elif cmd == 'b' or cmd == 'q':
                                player.stop()
                                break
                                
            elif choice == '4':
                stdscr.clear()
                safe_addstr(stdscr, 0, 0, "Enter new music directory path: ", curses.A_BOLD)
                dir_input = get_input_with_events(stdscr, 0, 32)
                if dir_input and dir_input != "EVENT_NEXT" and os.path.isdir(dir_input):
                    settings["music_dir"] = dir_input
                    save_json(SETTINGS_FILE, settings)
                    safe_addstr(stdscr, 2, 0, f"[*] Directory updated to: {dir_input}", curses.A_BOLD)
                else:
                    safe_addstr(stdscr, 2, 0, "[!] Invalid directory.", curses.A_BOLD)
                stdscr.refresh()
                time.sleep(1.5)
                
            elif choice == '5':
                break
                
    finally:
        # ENSURES SAFE SHUTDOWN & KILLS ZOMBIE AUDIO
        player.stop()
        vlc_instance.release()

if __name__ == "__main__":
    try:
        curses.wrapper(main_app)
    except KeyboardInterrupt:
        print("\nExiting Music Player...")
