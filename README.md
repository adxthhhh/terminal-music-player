# terminal-music-player




*(Download and install VLC directly from their official website).*
**For Linux Users:**
```bash
# Arch Linux
sudo pacman -S vlc

# Ubuntu/Debian
sudo apt install vlc

```
**--- OR ---**
**For Android (Termux) Users:**
*Note: Termux users may experience audio routing issues with VLC. MPV is recommended as an alternative if VLC fails to produce sound. Will provide updated code for that.*
```bash
pkg install vlc

```
### 2. Install Python Dependencies
**For Windows Users:**
```powershell
pip install python-vlc ytmusicapi yt-dlp tinytag

```
**--- OR ---**
**For Linux Users:**
```bash
pip install python-vlc ytmusicapi yt-dlp tinytag

```
*(Note: Depending on your distribution, you may need to use pip3 or install within a venv).*
**--- OR ---**
**For Android (Termux) Users:**
```bash
pip install python-vlc ytmusicapi yt-dlp tinytag

```
*(If you pivoted to MPV on step 1, run pip install python-mpv ytmusicapi yt-dlp tinytag instead).*
## 🚀 How to Use
 1. Clone or download the music_player.py script.
 2. Launch the application from your terminal:
**For Windows Users:**
```powershell
python music_player.py

```
**--- OR ---**
**For Linux & Android (Termux) Users:**
```bash
python3 music_player.py

```
 3. **Setup:** On the first prompt, provide the path to your local music directory.
   * **Windows Example:** C:\\Users\\YourName\\Music
   * **Linux Example:** /home/username/Music
   * **Termux Example:** /storage/emulated/0/Music
     *(Leave it blank to default to your standard OS Music folder).*
 4. **Playback:** * Type a song name (e.g., "Starboy") and hit Enter to search and play.
   * To play a song from your generated Top 10 list, simply type its corresponding number (1-10) and hit Enter.
 5. **Exit:** Press Ctrl+C to close the application and stop playback.
## ⚖️ Pros and Cons
### Pros
 * **Extremely Lightweight:** Uses negligible RAM and CPU compared to GUI applications like Spotify or Apple Music.
 * **No Authentication Required:** Scrapes YouTube Music streams directly without needing a Google account, OAuth, or paid developer API keys.
 * **Keyboard-Centric:** Entirely navigable without a mouse, making it perfect for tiling window managers or mobile terminal emulators.
 * **Data Privacy:** Keeps all listening history strictly local on your machine.
### Cons
 * **Single-Track Playback:** Currently lacks a queue system or playlist support; plays one song at a time.
 * **Dependency Fragility:** Relies on yt-dlp and ytmusicapi to scrape web data. If YouTube significantly changes its frontend architecture or cipher logic, these packages will need to be updated to maintain web functionality.
 * **Terminal Dependent:** Requires an active terminal window to stay open during playback.
   """
with open("README-v2.md", "w", encoding="utf-8") as f:
f.write(readme_content)
print("README-v2.md generated successfully.")

