import streamlit as st
import yt_dlp
import os
import shutil
import subprocess
import syncedlyrics
import re
import csv
from datetime import datetime, timedelta
from audio_separator.separator import Separator

# --- CONFIGURATION ---
DRIVE_PATH = "/content/drive/MyDrive/KaraokeOutput"
OUTPUT_DIR = DRIVE_PATH if os.path.exists("/content/drive") else "./output"
VIDEO_DIR = os.path.join(OUTPUT_DIR, "Karaoke_Videos_Final")
session_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_FILE = f"{OUTPUT_DIR}/Report_Dashboard_{session_time}.csv"

# Ensure directories exist
if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
if not os.path.exists(VIDEO_DIR): os.makedirs(VIDEO_DIR)

# --- HELPER FUNCTIONS ---

def log_to_excel(title, status, details=""):
    """Logs activity to a CSV file."""
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "Title", "Status", "Details"])
        writer.writerow([datetime.now().strftime("%H:%M:%S"), title, status, details])

def lrc_to_srt(lrc_path, srt_path):
    """Converts LRC to SRT, cleaning tags and formatting time."""
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
            # Clean <timestamps> from Enhanced LRC
            raw_text = match.group(3).strip()
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
    """Generates TV-Ready Video with Yellow Noto Sans Text."""
    # The 'Universal' Style (Yellow Text, Black Border, Noto Sans Font)
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

def apply_pitch_shift(input_file, output_file, semitones):
    if semitones == 0: return
    factor = 2 ** (semitones / 12)
    new_rate = int(44100 * factor)
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", input_file, 
           "-af", f"asetrate={new_rate},aresample=44100,atempo={1/factor:.4f}", output_file]
    subprocess.run(cmd)

# --- STREAMLIT UI ---

st.set_page_config(page_title="Karaoke Cloud", page_icon="🎤")
st.title("☁️ Karaoke Cloud Dashboard")
st.markdown("### Universal Downloader & TV Video Maker")

# Sidebar Options
st.sidebar.header("Settings")
make_video = st.sidebar.checkbox("Generate TV Video (MP4)", value=True, help="Creates a video file with lyrics for your TV.")
pitch_mode = st.sidebar.selectbox("Target Key", ["Original", "Male ➔ Female (+4)", "Female ➔ Male (-4)", "Custom"])
custom_pitch = st.sidebar.number_input("Custom Semitones", -12, 12, 0) if pitch_mode == "Custom" else 0

url = st.text_input("Paste Link (YouTube, SoundCloud, Archive.org):")

if st.button("🚀 Start Processing"):
    if not url:
        st.error("Please enter a URL first.")
    else:
        # Determine Pitch
        pitch = 4 if "Male" in pitch_mode else -4 if "Female" in pitch_mode else custom_pitch
        
        status_box = st.status("Initializing...", expanded=True)
        
        try:
            # 1. Load Model
            status_box.write("⚙️ Loading AI Model (UVR-HQ3)...")
            sep = Separator()
            sep.load_model(model_filename="UVR-MDX-NET-Inst_HQ_3.onnx")
            
            # 2. Extract Info
            status_box.write("📋 Fetching Playlist Info...")
            dl_opts = {
                'extract_flat': True, 'quiet': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'nocheckcertificate': True
            }
            
            with yt_dlp.YoutubeDL(dl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                # Handle single tracks vs playlists
                tracks = info['entries'] if 'entries' in info else [info]

            # 3. Process Loop
            progress_bar = st.progress(0)
            
            for i, track in enumerate(tracks):
                if not track: continue
                track_url = track.get('url', url)
                raw_title = track.get('title', 'Unknown Track')
                
                # Cleanup Titles
                title = "".join([c for c in raw_title if c.isalnum() or c in (' ', '-', '_')]).strip()
                clean_title = raw_title.replace("(Official Video)", "").replace(".mp3", "").replace("_", " ").strip()
                
                status_box.write(f"🎵 Processing ({i+1}/{len(tracks)}): **{title}**")
                
                # A. Download
                ydl_opts = {
                    'format': 'bestaudio/best', 
                    'outtmpl': 'temp.%(ext)s', 
                    'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3'}], 
                    'quiet': True,
                    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'nocheckcertificate': True
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.extract_info(track_url, download=True)
                
                # Save Original
                shutil.copy("temp.mp3", f"{OUTPUT_DIR}/{title}_Original.mp3")

                # B. Lyrics
                status_box.write("   🔎 Fetching Lyrics...")
                lrc = syncedlyrics.search(clean_title, enhanced=True)
                lrc_path = f"{OUTPUT_DIR}/{title}.lrc"
                has_lyrics = False
                if lrc:
                    with open(lrc_path, "w", encoding="utf-8") as f: f.write(lrc)
                    has_lyrics = True
                
                # C. Separation
                status_box.write("   🎻 Separating Vocals...")
                files = sep.separate("temp.mp3")
                inst_temp = next(f for f in files if "Instrumental" in f)
                
                final_inst = f"{OUTPUT_DIR}/{title}_Inst.mp3"
                shutil.move(inst_temp, final_inst)
                
                # D. Pitch Shift
                if pitch != 0:
                    status_box.write(f"   🎸 Shifting Pitch ({pitch} semitones)...")
                    pitched_path = f"{OUTPUT_DIR}/{title}_Pitched.mp3"
                    apply_pitch_shift(final_inst, pitched_path, pitch)
                    final_inst = pitched_path # Use pitched version for video
                
                # E. Video Generation (The New Feature!)
                if make_video and has_lyrics:
                    status_box.write("   📺 Generating TV Video (Yellow/Noto Sans)...")
                    srt_path = "temp_subs.srt"
                    video_out = f"{VIDEO_DIR}/{title}_Karaoke.mp4"
                    
                    try:
                        lrc_to_srt(lrc_path, srt_path)
                        create_video(final_inst, srt_path, video_out)
                        status_box.write(f"   ✅ Video Created: {title}_Karaoke.mp4")
                    except Exception as e:
                        st.warning(f"Video Error: {e}")
                    
                    if os.path.exists(srt_path): os.remove(srt_path)

                # Cleanup & Log
                if os.path.exists("temp.mp3"): os.remove("temp.mp3")
                log_to_excel(title, "Success", "Video Created" if make_video else "Audio Only")
                
                progress_bar.progress((i + 1) / len(tracks))

            status_box.update(label="✅ All Done! Check your Google Drive.", state="complete", expanded=False)
            st.success(f"Processed {len(tracks)} tracks. Files saved to Drive.")
            
        except Exception as e:
            st.error(f"Critical Error: {e}")
            log_to_excel("Global Error", "Failed", str(e))
