import yt_dlp
import os
import shutil
import subprocess
import syncedlyrics
import csv
from datetime import datetime
from audio_separator.separator import Separator

# Cloud Storage Setup
DRIVE_PATH = "/content/drive/MyDrive/KaraokeOutput"
OUTPUT_DIR = DRIVE_PATH if os.path.exists("/content/drive") else "./output"
LOG_FILE = f"{OUTPUT_DIR}/Karaoke_Report.csv"

def log_to_excel(title, pitch, lyrics_found, orig_path, inst_path, status="Success"):
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Date", "Song Title", "Status", "Pitch", "Lyrics Found", "Original File", "Instrumental File"])
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M"), title, status, f"{pitch}", "Yes" if lyrics_found else "No", orig_path, inst_path])

def apply_pitch_shift(input_file, output_file, semitones):
    if semitones == 0: return
    factor = 2 ** (semitones / 12)
    new_rate = int(44100 * factor)
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", input_file, 
           "-af", f"asetrate={new_rate},aresample=44100,atempo={1/factor:.4f}", output_file]
    subprocess.run(cmd)

def get_lyrics(clean_title):
    """Attempts to find lyrics, asks user for help if failed."""
    print(f"      🔎 Searching lyrics for '{clean_title}'...")
    try:
        lrc = syncedlyrics.search(clean_title, enhanced=True)
        if lrc: return lrc
    except:
        pass
    
    # If automatic search fails, ask user for manual input
    print(f"      ⚠️ Automatic search failed for '{clean_title}'.")
    print(f"      👉 Enter strict 'Artist - Song Name' manually (or press Enter to skip):")
    manual_query = input("      > ").strip()
    if manual_query:
        print(f"      🔎 Retrying with '{manual_query}'...")
        return syncedlyrics.search(manual_query, enhanced=True)
    return None

def process_track(url, semitones, separator):
    title = "Unknown"
    lyrics_found = False
    final_inst = "N/A"
    original_path = "N/A"
    
    try:
        # 1. Download (Universal Configuration)
        ydl_opts = {
            'format': 'bestaudio/best', 
            'outtmpl': 'temp.%(ext)s', 
            'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3'}], 
            'quiet': True,
            # This 'User-Agent' line is the key to making SoundCloud/Archive.org work!
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'nocheckcertificate': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            raw_title = info.get('title', 'Unknown Track')
            
            # Clean up filename
            title = "".join([c for c in raw_title if c.isalnum() or c in (' ', '-', '_')]).strip()
            
            # Smart Title Cleaning for Lyrics Search
            # Removes "Official Video", file extensions, and common junk
            clean_title = raw_title.replace("(Official Video)", "").replace(".mp3", "").replace(".wav", "").replace("_", " ").strip()
        
        print(f"\n🎵 Processing: {title}")

        # Save Original
        original_path = f"{OUTPUT_DIR}/{title}_Original.mp3"
        shutil.copy("temp.mp3", original_path)

        # 2. Lyrics (With Manual Fallback)
        lrc = get_lyrics(clean_title)
        if lrc:
            with open(f"{OUTPUT_DIR}/{title}.lrc", "w", encoding="utf-8") as f: f.write(lrc)
            lyrics_found = True
            print(f"      📝 Lyrics saved.")
        else:
            print(f"      ⚠️ No lyrics found.")

        # 3. Separate
        print(f"      🎻 Separating Instrumentals...")
        files = separator.separate("temp.mp3")
        inst_temp = next(f for f in files if "Instrumental" in f)
        final_inst = f"{OUTPUT_DIR}/{title}_Inst.mp3"
        shutil.move(inst_temp, final_inst) 

        # 4. Pitch Shift
        if semitones != 0:
            apply_pitch_shift(final_inst, f"{OUTPUT_DIR}/{title}_Pitched.mp3", semitones)
            final_inst = f"{OUTPUT_DIR}/{title}_Pitched.mp3"
            print(f"      🎸 Pitched version created.")
        
        print(f"✅ COMPLETE: {title}")
        log_to_excel(title, semitones, lyrics_found, original_path, final_inst, status="Success")

        if os.path.exists("temp.mp3"): os.remove("temp.mp3")
        
    except Exception as e:
        print(f"❌ Error with {url}: {e}")
        log_to_excel(title, semitones, False, "N/A", "N/A", status=f"Error: {str(e)}")

def main():
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
    
    print("\n🔗 Universal Downloader Ready")
    print("   Supported: YouTube, SoundCloud, Bandcamp, Internet Archive, Mixcloud")
    url = input("Paste URL: ").strip()
    if not url: return

    print("\nSelect Output Key:")
    print("1. Original Key (0)")
    print("2. Male ➔ Female (+4)")
    print("3. Female ➔ Male (-4)")
    
    choice = input("Enter choice (1-3): ").strip()
    semitones = 4 if choice == "2" else -4 if choice == "3" else 0

    print("🚀 Initializing AI Model...")
    sep = Separator()
    sep.load_model(model_filename="UVR-MDX-NET-Inst_HQ_3.onnx")

    # Universal Playlist Logic
    ydl_list = {
        'extract_flat': True, 
        'quiet': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    with yt_dlp.YoutubeDL(ydl_list) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            
            # Check if it's a playlist (works for SoundCloud sets too)
            if 'entries' in info:
                print(f"📋 Collection Detected: {len(info['entries'])} tracks.")
                for entry in info['entries']:
                    if entry: # Sometimes entries are None
                        process_track(entry['url'], semitones, sep)
            else:
                process_track(url, semitones, sep)
        except Exception as e:
            # Fallback for direct file links (like Archive.org mp3 links)
            process_track(url, semitones, sep)

if __name__ == "__main__": main()
