import yt_dlp
import os
import shutil
import subprocess
import syncedlyrics
from audio_separator.separator import Separator

# Cloud Storage Setup (Colab vs Local)
DRIVE_PATH = "/content/drive/MyDrive/KaraokeOutput"
OUTPUT_DIR = DRIVE_PATH if os.path.exists("/content/drive") else "./output"

def apply_pitch_shift(input_file, output_file, semitones):
    if semitones == 0: return
    # FFmpeg logic: adjust speed and sample rate to shift pitch without changing tempo
    factor = 2 ** (semitones / 12)
    new_rate = int(44100 * factor)
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", input_file, 
           "-af", f"asetrate={new_rate},aresample=44100,atempo={1/factor:.4f}", output_file]
    subprocess.run(cmd)

def process_track(url, semitones, separator):
    try:
        # 1. Download Audio
        ydl_opts = {
            'format': 'bestaudio/best', 
            'outtmpl': 'temp.%(ext)s', 
            'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3'}], 
            'quiet': True
        }
        
        title = "Unknown"
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # Clean title: Remove junk like "(Official Video)" to help lyrics search
            raw_title = info['title']
            title = "".join([c for c in raw_title if c.isalnum() or c in (' ', '-', '_')]).strip()
            
            # Create a "cleaner" title for searching lyrics (removes extra punctuation)
            search_title = raw_title.replace("(Official Video)", "").replace("(Lyrics)", "").replace("(Official Audio)", "").strip()
        
        print(f"\n🎵 Processing: {title}")

        # --- SAVE ORIGINAL MP3 ---
        original_path = f"{OUTPUT_DIR}/{title}_Original.mp3"
        shutil.copy("temp.mp3", original_path)
        print(f"      💾 Saved Original MP3")

        # 2. Lyrics Search (Enhanced)
        try:
            print(f"      🔎 Searching for lyrics for '{search_title}'...")
            lrc = syncedlyrics.search(search_title, enhanced=True)
            if lrc:
                with open(f"{OUTPUT_DIR}/{title}.lrc", "w", encoding="utf-8") as f: f.write(lrc)
                print(f"      📝 Lyrics saved.")
            else:
                print(f"      ⚠️ No synced lyrics found.")
        except Exception as e:
            print(f"      ⚠️ Lyrics Error: {e}")

        # 3. Separate Vocals
        print(f"      🎻 Separating Instrumentals (this may take a moment)...")
        files = separator.separate("temp.mp3")
        
        # Find the instrumental file in the output
        inst_temp = next(f for f in files if "Instrumental" in f)
        final_inst = f"{OUTPUT_DIR}/{title}_Inst.mp3"
        
        # Move to Drive (Fixes "Cross-Device" Error)
        shutil.move(inst_temp, final_inst) 

        # 4. Pitch Shift
        if semitones != 0:
            apply_pitch_shift(final_inst, f"{OUTPUT_DIR}/{title}_Pitched.mp3", semitones)
            print(f"      🎸 Pitched version created.")
        
        print(f"✅ COMPLETE: {title}")

        # Cleanup temp file for next song
        if os.path.exists("temp.mp3"): os.remove("temp.mp3")
        
    except Exception as e:
        print(f"❌ Error with {url}: {e}")

def main():
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
    
    # 1. Input
    url = input("Paste YouTube Video or Playlist URL: ").strip()
    if not url: return

    # 2. Menu
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

    # 3. Initialize AI
    print("🚀 Initializing AI Model (UVR-HQ3)...")
    sep = Separator()
    sep.load_model(model_filename="UVR-MDX-NET-Inst_HQ_3.onnx")

    # 4. Process (Playlist vs Single)
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
