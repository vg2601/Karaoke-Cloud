import yt_dlp as universal_dl  # <--- Renamed Import
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
session_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_FILE = f"{OUTPUT_DIR}/Report_Audio_{session_time}.csv"

def log_to_excel(title, pitch, lyrics_found, orig_path, inst_path, status="Success"):
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "Title", "Status", "Pitch", "Lyrics", "Original File", "Inst File"])
        writer.writerow([datetime.now().strftime("%H:%M:%S"), title, status, f"{pitch}", "Yes" if lyrics_found else "No", orig_path, inst_path])

def apply_pitch_shift(input_file, output_file, semitones):
    if semitones == 0: return
    factor = 2 ** (semitones / 12)
    new_rate = int(44100 * factor)
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", input_file, 
           "-af", f"asetrate={new_rate},aresample=44100,atempo={1/factor:.4f}", output_file]
    subprocess.run(cmd)

def get_lyrics(clean_title):
    print(f"      🔎 Searching lyrics database for '{clean_title}'...")
    try:
        lrc = syncedlyrics.search(clean_title, enhanced=True)
        if lrc: return lrc
    except:
        pass
    
    print(f"      ⚠️ Automatic search failed.")
    print(f"      👉 Enter 'Artist - Song Name' manually (or press Enter to skip):")
    manual_query = input("      > ").strip()
    if manual_query:
        print(f"      🔎 Retrying with '{manual_query}'...")
        return syncedlyrics.search(manual_query, enhanced=True)
    return None

def process_track(url, semitones, separator):
    title = "Unknown"
    lyrics_found = False
    
    try:
        # Generic Downloader Config
        dl_opts = {
            'format': 'bestaudio/best', 
            'outtmpl': 'temp.%(ext)s', 
            'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3'}], 
            'quiet': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'nocheckcertificate': True,
        }
        
        with universal_dl.YoutubeDL(dl_opts) as downloader:
            info = downloader.extract_info(url, download=True)
            raw_title = info.get('title', 'Unknown Track')
            title = "".join([c for c in raw_title if c.isalnum() or c in (' ', '-', '_')]).strip()
            # Clean title for metadata search
            clean_title = raw_title.replace("(Official Video)", "").replace(".mp3", "").replace("_", " ").strip()
        
        print(f"\n🎵 Processing Track: {title}")

        original_path = f"{OUTPUT_DIR}/{title}_Original.mp3"
        shutil.copy("temp.mp3", original_path)

        lrc = get_lyrics(clean_title)
        if lrc:
            with open(f"{OUTPUT_DIR}/{title}.lrc", "w", encoding="utf-8") as f: f.write(lrc)
            lyrics_found = True
            print(f"      📝 Lyrics found and saved.")
        else:
            print(f"      ⚠️ No lyrics found in database.")

        print(f"      🎻 Separating stems...")
        files = separator.separate("temp.mp3")
        inst_temp = next(f for f in files if "Instrumental" in f)
        final_inst = f"{OUTPUT_DIR}/{title}_Inst.mp3"
        shutil.move(inst_temp, final_inst) 

        if semitones != 0:
            apply_pitch_shift(final_inst, f"{OUTPUT_DIR}/{title}_Pitched.mp3", semitones)
            final_inst = f"{OUTPUT_DIR}/{title}_Pitched.mp3"
            print(f"      🎸 Pitched version created.")
        
        print(f"✅ Finished: {title}")
        log_to_excel(title, semitones, lyrics_found, original_path, final_inst, status="Success")

        if os.path.exists("temp.mp3"): os.remove("temp.mp3")
        
    except Exception as e:
        print(f"❌ Error processing source: {e}")
        log_to_excel(title, semitones, False, "N/A", "N/A", status=f"Error: {str(e)}")

def main():
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
    
    print("\n🔗 Universal Audio Downloader")
    print("   (Supports Direct Links, Archive.org, SoundCloud, etc.)")
    url = input("Paste Source URL: ").strip()
    if not url: return

    print("\nSelect Output Key:")
    print("1. Original Key (0)")
    print("2. Male ➔ Female (+4)")
    print("3. Female ➔ Male (-4)")
    
    choice = input("Enter choice (1-3): ").strip()
    semitones = 4 if choice == "2" else -4 if choice == "3" else 0

    print("🚀 Initializing AI Engine...")
    sep = Separator()
    sep.load_model(model_filename="UVR-MDX-NET-Inst_HQ_3.onnx")

    dl_list_opts = {
        'extract_flat': True, 'quiet': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    # Check for lists/sets
    with universal_dl.YoutubeDL(dl_list_opts) as downloader:
        try:
            info = downloader.extract_info(url, download=False)
            if 'entries' in info:
                print(f"📋 Collection Detected: {len(info['entries'])} tracks.")
                for entry in info['entries']:
                    if entry: process_track(entry['url'], semitones, sep)
            else:
                process_track(url, semitones, sep)
        except:
            process_track(url, semitones, sep)

if __name__ == "__main__": main()
