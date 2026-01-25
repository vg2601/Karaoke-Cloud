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
    """Appends the processing result to a CSV file (Opens in Excel)."""
    file_exists = os.path.isfile(LOG_FILE)
    
    with open(LOG_FILE, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # Write Header if new file
        if not file_exists:
            writer.writerow(["Date", "Song Title", "Status", "Pitch Change", "Lyrics Found", "Original File", "Instrumental File"])
        
        # Write Data
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            title,
            status,
            f"{pitch} semitones",
            "Yes" if lyrics_found else "No",
            orig_path,
            inst_path
        ])

def apply_pitch_shift(input_file, output_file, semitones):
    if semitones == 0: return
    factor = 2 ** (semitones / 12)
    new_rate = int(44100 * factor)
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", input_file, 
           "-af", f"asetrate={new_rate},aresample=44100,atempo={1/factor:.4f}", output_file]
    subprocess.run(cmd)

def process_track(url, semitones, separator):
    title = "Unknown"
    lyrics_found = False
    final_inst = "N/A"
    original_path = "N/A"
    
    try:
        # 1. Download
        ydl_opts = {
            'format': 'bestaudio/best', 
            'outtmpl': 'temp.%(ext)s', 
            'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3'}], 
            'quiet': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            raw_title = info['title']
            title = "".join([c for c in raw_title if c.isalnum() or c in (' ', '-', '_')]).strip()
            search_title = raw_title.replace("(Official Video)", "").replace("(Lyrics)", "").replace("(Official Audio)", "").strip()
        
        print(f"\n🎵 Processing: {title}")

        # Save Original
        original_path = f"{OUTPUT_DIR}/{title}_Original.mp3"
        shutil.copy("temp.mp3", original_path)
        print(f"      💾 Saved Original MP3")

        # 2. Lyrics
        try:
            print(f"      🔎 Searching for lyrics...")
            lrc = syncedlyrics.search(search_title, enhanced=True)
            if lrc:
                with open(f"{OUTPUT_DIR}/{title}.lrc", "w", encoding="utf-8") as f: f.write(lrc)
                lyrics_found = True
                print(f"      📝 Lyrics saved.")
            else:
                print(f"      ⚠️ No synced lyrics found.")
        except Exception as e:
            print(f"      ⚠️ Lyrics Error: {e}")

        # 3. Separate
        print(f"      🎻 Separating Instrumentals...")
        files = separator.separate("temp.mp3")
        inst_temp = next(f for f in files if "Instrumental" in f)
        final_inst = f"{OUTPUT_DIR}/{title}_Inst.mp3"
        shutil.move(inst_temp, final_inst) 

        # 4. Pitch Shift
        if semitones != 0:
            apply_pitch_shift(final_inst, f"{OUTPUT_DIR}/{title}_Pitched.mp3", semitones)
            final_inst = f"{OUTPUT_DIR}/{title}_Pitched.mp3" # Update log to point to pitched version
            print(f"      🎸 Pitched version created.")
        
        print(f"✅ COMPLETE: {title}")
        
        # LOG SUCCESS
        log_to_excel(title, semitones, lyrics_found, original_path, final_inst, status="Success")

        # Cleanup
        if os.path.exists("temp.mp3"): os.remove("temp.mp3")
        
    except Exception as e:
        print(f"❌ Error with {url}: {e}")
        # LOG FAILURE
        log_to_excel(title, semitones, False, "N/A", "N/A", status=f"Error: {str(e)}")

def main():
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
    
    url = input("Paste YouTube Video or Playlist URL: ").strip()
    if not url: return

    print("\nSelect Output Key for ALL tracks:")
    print("1. Original Key Only (0)")
    print("2. Male ➔ Female (+4)")
    print("3. Female ➔ Male (-4)")
    print("4. Custom Value")
    
    choice = input("Enter choice (1-4): ").strip()
    
    semitones = 0
    if choice == "2": semitones = 4
    elif choice == "3": semitones = -4
    elif choice == "4":
        try: semitones = int(input("Enter custom semitones: "))
        except: semitones = 0

    print("🚀 Initializing AI Model (UVR-HQ3)...")
    sep = Separator()
    sep.load_model(model_filename="UVR-MDX-NET-Inst_HQ_3.onnx")

    ydl_list = {'extract_flat': True, 'quiet': True}
    with yt_dlp.YoutubeDL(ydl_list) as ydl:
        info = ydl.extract_info(url, download=False)
        
        if 'entries' in info:
            print(f"📋 Playlist Detected: {len(info['entries'])} tracks.")
            for i, entry in enumerate(info['entries']):
                print(f"--- Track {i+1}/{len(info['entries'])} ---")
                process_track(entry['url'], semitones, sep)
        else:
            process_track(url, semitones, sep)

if __name__ == "__main__": main()
