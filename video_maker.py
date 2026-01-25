import os
import subprocess
import re
import csv
from datetime import timedelta, datetime
from google.colab import drive

# --- CONFIGURATION ---
ROOT_DIR = "/content/drive/MyDrive/KaraokeOutput"
VIDEO_OUTPUT_DIR = os.path.join(ROOT_DIR, "Karaoke_Videos_Final")
session_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_FILE = f"{ROOT_DIR}/Report_Video_{session_time}.csv"

# SET THIS TO TRUE to generate the "Full Vocal" video alongside the Karaoke one
GENERATE_FULL_VOCAL_VIDEO = True 

def log_to_excel(video_name, status, details=""):
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "Video File", "Status", "Details"])
        writer.writerow([datetime.now().strftime("%H:%M:%S"), video_name, status, details])

def setup_drive():
    if not os.path.exists('/content/drive'):
        drive.mount('/content/drive')

def lrc_to_srt(lrc_path, srt_path):
    with open(lrc_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    srt_lines = []
    counter = 1
    pattern = re.compile(r'\[(\d+):(\d+\.?\d*)\](.*)')
    
    parsed_lines = []
    for line in lines:
        match = pattern.match(line)
        if match:
            minutes = int(match.group(1))
            seconds = float(match.group(2))
            raw_text = match.group(3).strip()
            # Clean <timestamps> from Enhanced LRC
            clean_text = re.sub(r'<[^>]+>', '', raw_text).strip()
            start_time = timedelta(minutes=minutes, seconds=seconds)
            parsed_lines.append((start_time, clean_text))

    for i in range(len(parsed_lines)):
        start = parsed_lines[i][0]
        text = parsed_lines[i][1]
        if i < len(parsed_lines) - 1:
            end = parsed_lines[i+1][0]
        else:
            end = start + timedelta(seconds=5)

        def fmt_time(td):
            total_sec = int(td.total_seconds())
            ms = int(td.microseconds / 1000)
            h = total_sec // 3600
            m = (total_sec % 3600) // 60
            s = total_sec % 60
            return f"{h:02}:{m:02}:{s:02},{ms:03}"

        if text:
            srt_lines.append(f"{counter}\n{fmt_time(start)} --> {fmt_time(end)}\n{text}\n\n")
            counter += 1

    with open(srt_path, 'w', encoding='utf-8') as f:
        f.writelines(srt_lines)

def create_video(audio_path, srt_path, output_path):
    # TV Style: Yellow Text, Noto Sans Font
    style = "Fontname=Noto Sans,Fontsize=60,PrimaryColour=&H00FFFF,Outline=3,MarginV=50,Alignment=2"

    cmd = [
        "ffmpeg", "-y", "-v", "quiet", "-stats",
        "-f", "lavfi", "-i", "color=c=black:s=1920x1080:r=24",
        "-i", audio_path,
        "-vf", f"subtitles={srt_path}:force_style='{style}'",
        "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
        output_path
    ]
    subprocess.run(cmd)

def main():
    setup_drive()
    if not os.path.exists(ROOT_DIR):
        print(f"❌ Error: {ROOT_DIR} not found.")
        return
    if not os.path.exists(VIDEO_OUTPUT_DIR):
        os.makedirs(VIDEO_OUTPUT_DIR)
        
    print(f"📄 Video Log: {os.path.basename(LOG_FILE)}")
    
    files = os.listdir(ROOT_DIR)
    # Find all instrumental tracks as the base for processing
    audio_files = [f for f in files if (f.endswith('_Inst.mp3') or f.endswith('_Pitched.mp3'))]
    
    print(f"📂 Found {len(audio_files)} tracks to process...")
    
    count = 0
    for audio_file in audio_files:
        # Identify filenames
        base_title = audio_file.replace("_Inst.mp3", "").replace("_Pitched.mp3", "")
        lrc_file = f"{base_title}.lrc"
        original_audio = f"{base_title}_Original.mp3"
        
        # Paths
        path_inst = os.path.join(ROOT_DIR, audio_file)
        path_orig = os.path.join(ROOT_DIR, original_audio)
        path_lrc = os.path.join(ROOT_DIR, lrc_file)
        temp_srt = "temp_subs.srt"
        
        # Output Paths
        video_karaoke = os.path.join(VIDEO_OUTPUT_DIR, f"{base_title}_Karaoke.mp4")
        video_full = os.path.join(VIDEO_OUTPUT_DIR, f"{base_title}_FullVocals.mp4")

        if os.path.exists(path_lrc):
            print(f"🎬 Processing: {base_title}")
            try:
                lrc_to_srt(path_lrc, temp_srt)
                
                # 1. Create KARAOKE Video (Instrumental)
                if not os.path.exists(video_karaoke):
                    create_video(path_inst, temp_srt, video_karaoke)
                    print(f"   ✅ Created Karaoke (Inst)")
                    log_to_excel(os.path.basename(video_karaoke), "Success")
                    count += 1
                
                # 2. Create FULL VOCAL Video (Original)
                if GENERATE_FULL_VOCAL_VIDEO and os.path.exists(path_orig):
                    if not os.path.exists(video_full):
                        create_video(path_orig, temp_srt, video_full)
                        print(f"   ✅ Created Full Vocal Video")
                        log_to_excel(os.path.basename(video_full), "Success")
                        count += 1
                        
            except Exception as e:
                print(f"   ⚠️ Error: {e}")
                log_to_excel(base_title, "Failed", str(e))
                
            if os.path.exists(temp_srt): os.remove(temp_srt)
            
    print(f"\n🎉 Finished! Created {count} new videos.")

if __name__ == "__main__": main()
