import streamlit as st
import yt_dlp
import os
import syncedlyrics
import subprocess
from audio_separator.separator import Separator

# Drive Setup
DRIVE_PATH = "/content/drive/MyDrive/KaraokeOutput"
OUTPUT_DIR = DRIVE_PATH if os.path.exists("/content/drive") else "./output"
if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)

st.title("☁️ Cloud Karaoke Maker")
url = st.text_input("YouTube Playlist or Video URL:")
pitch_mode = st.selectbox("Target Key:", ["Original", "Male ➔ Female (+4)", "Female ➔ Male (-4)", "Custom"])
custom_pitch = st.number_input("Custom Semitones:", -12, 12, 0) if pitch_mode == "Custom" else 0

def apply_pitch_shift(input_file, output_file, semitones):
    if semitones == 0: return
    factor = 2 ** (semitones / 12)
    new_rate = int(44100 * factor)
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", input_file, 
           "-af", f"asetrate={new_rate},aresample=44100,atempo={1/factor:.4f}", output_file]
    subprocess.run(cmd)

if st.button("🚀 START"):
    pitch = 4 if "Male" in pitch_mode else -4 if "Female" in pitch_mode else custom_pitch
    
    status = st.empty()
    bar = st.progress(0)
    
    # Init Model
    sep = Separator()
    sep.load_model(model_filename="UVR-MDX-NET-Inst_HQ_3.onnx")
    
    with yt_dlp.YoutubeDL({'extract_flat': True, 'quiet': True}) as ydl:
        info = ydl.extract_info(url, download=False)
        tracks = info['entries'] if 'entries' in info else [info]

    for i, track in enumerate(tracks):
        title = track.get('title', 'Unknown')
        status.write(f"Processing ({i+1}/{len(tracks)}): {title}")
        
        # Download logic
        ydl_opts = {'format': 'bestaudio/best', 'outtmpl': 'temp.%(ext)s', 'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3'}], 'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.extract_info(track['url'], download=True)
        
        # Lyrics & Separation
        lrc = syncedlyrics.search(title)
        if lrc: 
            with open(f"{OUTPUT_DIR}/{title}.lrc", "w") as f: f.write(lrc)
            
        files = sep.separate("temp.mp3")
        inst_temp = next(f for f in files if "Instrumental" in f)
        final_inst = f"{OUTPUT_DIR}/{title}_Inst.mp3"
        os.rename(inst_temp, final_inst)
        
        if pitch != 0:
            apply_pitch_shift(final_inst, f"{OUTPUT_DIR}/{title}_Pitched.mp3", pitch)
            
        bar.progress((i + 1) / len(tracks))

    st.success("✅ Playlist Complete! Check Google Drive.")