import yt_dlp as universal_dl
import os
import shutil
import subprocess
import syncedlyrics
import csv
import re
from datetime import datetime, timedelta
from audio_separator.separator import Separator

# Cloud Storage Setup
DRIVE_PATH = "/content/drive/MyDrive/KaraokeOutput"
OUTPUT_DIR = DRIVE_PATH if os.path.exists("/content/drive") else "./output"
VIDEO_DIR = os.path.join(OUTPUT_DIR, "Karaoke_Videos_Final")
session_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_FILE = f"{OUTPUT_DIR}/Report_Audio_{session_time}.csv"

if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
if not os.path.exists(VIDEO_DIR): os.makedirs(VIDEO_DIR)

# --- FEATURE 1: HTML PLAYER GENERATOR ---
def create_flashcard_player():
    """Generates the Ultimate HTML Player with Group Sync & Tap-to-Catch-Up."""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Group Karaoke Player</title>
    <style>
        body { background-color: #000; color: #fff; font-family: 'Arial', sans-serif; margin: 0; height: 100vh; display: flex; flex-direction: column; overflow: hidden; text-align: center; }
        #controls { position: absolute; top: 10px; width: 100%; z-index: 100; text-align: center; opacity: 0.5; transition: opacity 0.3s; display: flex; justify-content: center; gap: 10px; }
        #controls:hover { opacity: 1; }
        .btn { background: #333; color: #fff; border: 1px solid #555; padding: 10px 20px; border-radius: 20px; font-size: 14px; cursor: pointer; text-decoration: none; user-select: none; }
        .btn-green { background: #006400; border-color: #008000; }
        input[type="file"] { display: none; }
        #lyrics-container { flex: 1; display: flex; flex-direction: column; align-items: center; overflow-y: auto; scroll-behavior: smooth; padding-top: 50vh; padding-bottom: 50vh; cursor: grab; }
        #lyrics-container::-webkit-scrollbar { display: none; } 
        .line { padding: 15px 20px; opacity: 0.3; font-size: 22px; transition: all 0.3s ease; max-width: 90%; margin: 5px 0; border-radius: 10px; cursor: pointer; }
        .line:active { background: rgba(255, 255, 255, 0.1); } 
        .active { opacity: 1; font-size: 40px; font-weight: bold; color: #00FFFF; text-shadow: 0px 0px 10px rgba(0,255,255,0.5); transform: scale(1.05); }
        #countdown { position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); display: none; justify-content: center; align-items: center; font-size: 150px; font-weight: bold; color: #00FF00; z-index: 200; }
        audio { position: absolute; bottom: 20px; left: 5%; width: 90%; filter: invert(1); opacity: 0.8; }
        #toast { position: absolute; bottom: 80px; left: 50%; transform: translateX(-50%); background: rgba(0,0,0,0.8); padding: 10px 20px; border-radius: 20px; display: none; border: 1px solid #555; }
    </style>
</head>
<body>
    <div id="controls">
        <label class="btn">📂 Load <input type="file" id="fileInput" multiple accept=".mp3,.lrc,.txt"></label>
        <div class="btn btn-green" onclick="startCountdown()">⏱ Sync Start</div>
    </div>
    <div id="countdown">3</div>
    <div id="toast">Synced!</div>
    <div id="lyrics-container">
        <div class="line">1. Load Song 📂</div>
        <div class="line">2. Wait for Group</div>
        <div class="line">3. Tap 'Sync Start' ⏱</div>
        <div class="line" style="color: #ffff00">Tip: Tap any line to jump there!</div>
    </div>
    <audio id="audioPlayer" controls></audio>
    <script>
        const fileInput = document.getElementById('fileInput'), audioPlayer = document.getElementById('audioPlayer'), container = document.getElementById('lyrics-container'), countdownEl = document.getElementById('countdown'), toast = document.getElementById('toast');
        let lyrics = [], isUserScrolling = false, scrollTimeout;
        container.addEventListener('touchstart', () => { isUserScrolling = true; });
        container.addEventListener('touchend', () => { clearTimeout(scrollTimeout); scrollTimeout = setTimeout(() => { isUserScrolling = false; }, 2000); });
        container.addEventListener('mousedown', () => { isUserScrolling = true; });
        container.addEventListener('mouseup', () => { clearTimeout(scrollTimeout); scrollTimeout = setTimeout(() => { isUserScrolling = false; }, 2000); });
        fileInput.addEventListener('change', (e) => {
            for (let file of e.target.files) {
                if (file.name.match(/\.(mp3|wav|m4a)$/i)) audioPlayer.src = URL.createObjectURL(file);
                else if (file.name.endsWith('.lrc')) readFile(file, parseLRC);
                else if (file.name.endsWith('.txt')) readFile(file, parseTXT);
            }
        });
        function readFile(file, parser) { const r = new FileReader(); r.onload = (e) => parser(e.target.result); r.readAsText(file); }
        function startCountdown() {
            countdownEl.style.display = 'flex'; let count = 3; countdownEl.innerText = count;
            const timer = setInterval(() => { count--; if (count > 0) countdownEl.innerText = count; else if (count === 0) countdownEl.innerText = "GO!"; else { clearInterval(timer); countdownEl.style.display = 'none'; audioPlayer.play(); } }, 1000);
        }
        function seekTo(index) {
            if (lyrics[index].time !== -1) { audioPlayer.currentTime = lyrics[index].time; audioPlayer.play(); showToast("Synced!"); }
            document.querySelectorAll('.line').forEach(d => d.classList.remove('active'));
            const el = document.getElementById(`line-${index}`); if(el) el.classList.add('active');
        }
        function showToast(msg) { toast.innerText = msg; toast.style.display = 'block'; setTimeout(() => toast.style.display = 'none', 1500); }
        function parseLRC(text) {
            lyrics = []; text.split('\\n').forEach(line => {
                const match = line.match(/\[(\d{2}):(\d{2})\.(\d{2,3})\]/);
                if (match) {
                    const time = parseInt(match[1]) * 60 + parseInt(match[2]) + parseInt(match[3]) / 100;
                    let cleanText = line.replace(/\[.*?\]/g, '').replace(/<[^>]*>/g, '').trim();
                    if (cleanText) lyrics.push({ time, text: cleanText });
                }
            }); renderLyrics();
        }
        function parseTXT(text) { lyrics = []; text.split('\\n').forEach(line => { if(line.trim()) lyrics.push({ time: -1, text: line.trim() }); }); renderLyrics(); }
        function renderLyrics() {
            container.innerHTML = ''; lyrics.forEach((line, i) => {
                const div = document.createElement('div'); div.className = 'line'; div.id = `line-${i}`; div.innerText = line.text; div.onclick = () => seekTo(i); container.appendChild(div);
            }); const pad = document.createElement('div'); pad.style.height = "50vh"; container.appendChild(pad);
        }
        audioPlayer.addEventListener('timeupdate', () => {
            if (isUserScrolling) return; 
            let activeIndex = -1; for (let i = 0; i < lyrics.length; i++) if (audioPlayer.currentTime >= lyrics[i].time) activeIndex = i; else break;
            if (activeIndex !== -1) {
                document.querySelectorAll('.line').forEach(d => d.classList.remove('active'));
                const a = document.getElementById(`line-${activeIndex}`); if (a) { a.classList.add('active'); a.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
            }
        });
    </script>
</body>
</html>"""
    player_path = f"{OUTPUT_DIR}/Player.html"
    if not os.path.exists(player_path):
        with open(player_path, "w", encoding="utf-8") as f: f.write(html_content)
        print(f"📱 Web Player Created: {player_path}")

# --- FEATURE 2: VIDEO GENERATOR HELPERS ---
def lrc_to_srt(lrc_path, srt_path):
    with open(lrc_path, 'r', encoding='utf-8') as f: lines = f.readlines()
    srt_lines = []
    counter = 1
    pattern = re.compile(r'\[(\d+):(\d+\.?\d*)\](.*)')
    parsed_lines = []
    for line in lines:
        match = pattern.match(line)
        if match:
            minutes = int(match.group(1))
            seconds = float(match.group(2))
            clean_text = re.sub(r'<[^>]+>', '', match.group(3).strip()).strip()
            start_time = timedelta(minutes=minutes, seconds=seconds)
            parsed_lines.append((start_time, clean_text))

    for i in range(len(parsed_lines)):
        start = parsed_lines[i][0]
        text = parsed_lines[i][1]
        end = parsed_lines[i+1][0] if i < len(parsed_lines) - 1 else start + timedelta(seconds=5)
        def fmt_time(td):
            total_sec = int(td.total_seconds())
            ms = int(td.microseconds / 1000)
            return f"{total_sec // 3600:02}:{(total_sec % 3600) // 60:02}:{total_sec % 60:02},{ms:03}"
        if text:
            srt_lines.append(f"{counter}\n{fmt_time(start)} --> {fmt_time(end)}\n{text}\n\n")
            counter += 1
    with open(srt_path, 'w', encoding='utf-8') as f: f.writelines(srt_lines)

def create_video(audio_path, srt_path, output_path):
    style = "Fontname=Noto Sans,Fontsize=60,PrimaryColour=&H00FFFF,Outline=3,MarginV=50,Alignment=2"
    cmd = ["ffmpeg", "-y", "-v", "quiet", "-stats", "-f", "lavfi", "-i", "color=c=black:s=1920x1080:r=24", "-i", audio_path, "-vf", f"subtitles={srt_path}:force_style='{style}'", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast", output_path]
    subprocess.run(cmd)

# --- CORE LOGIC ---
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
    except: pass
    print(f"      ⚠️ Automatic search failed.")
    manual_query = input("      👉 Enter 'Artist - Song Name' (or Enter to skip): ").strip()
    if manual_query:
        print(f"      🔎 Retrying with '{manual_query}'...")
        return syncedlyrics.search(manual_query, enhanced=True)
    return None

def process_track(url, semitones, separator, generate_video):
    title = "Unknown"
    lyrics_found = False
    try:
        dl_opts = {'format': 'bestaudio/best', 'outtmpl': 'temp.%(ext)s', 'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3'}], 'quiet': True, 'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36', 'nocheckcertificate': True}
        
        with universal_dl.YoutubeDL(dl_opts) as downloader:
            info = downloader.extract_info(url, download=True)
            raw_title = info.get('title', 'Unknown Track')
            title = "".join([c for c in raw_title if c.isalnum() or c in (' ', '-', '_')]).strip()
            clean_title = raw_title.replace("(Official Video)", "").replace(".mp3", "").replace("_", " ").strip()
        
        print(f"\n🎵 Processing: {title}")
        original_path = f"{OUTPUT_DIR}/{title}_Original.mp3"
        shutil.copy("temp.mp3", original_path)

        lrc = get_lyrics(clean_title)
        lrc_path = f"{OUTPUT_DIR}/{title}.lrc"
        if lrc:
            with open(lrc_path, "w", encoding="utf-8") as f: f.write(lrc)
            lyrics_found = True
            print(f"      📝 Lyrics saved.")
        else:
            print(f"      ⚠️ No lyrics found.")

        print(f"      🎻 Separating stems...")
        files = separator.separate("temp.mp3")
        inst_temp = next(f for f in files if "Instrumental" in f)
        final_inst = f"{OUTPUT_DIR}/{title}_Inst.mp3"
        shutil.move(inst_temp, final_inst) 

        if semitones != 0:
            apply_pitch_shift(final_inst, f"{OUTPUT_DIR}/{title}_Pitched.mp3", semitones)
            final_inst = f"{OUTPUT_DIR}/{title}_Pitched.mp3"
            print(f"      🎸 Pitched version created.")
        
        # --- VIDEO GENERATION ---
        if generate_video and lyrics_found:
            print(f"      📺 Generating TV Video...")
            srt_path = "temp_subs.srt"
            video_out = f"{VIDEO_DIR}/{title}_Karaoke.mp4"
            try:
                lrc_to_srt(lrc_path, srt_path)
                create_video(final_inst, srt_path, video_out)
                print(f"      ✅ Video Created: {title}_Karaoke.mp4")
            except Exception as e:
                print(f"      ⚠️ Video Error: {e}")
            if os.path.exists(srt_path): os.remove(srt_path)

        print(f"✅ Finished: {title}")
        log_to_excel(title, semitones, lyrics_found, original_path, final_inst, status="Success")
        if os.path.exists("temp.mp3"): os.remove("temp.mp3")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        log_to_excel(title, semitones, False, "N/A", "N/A", status=f"Error: {str(e)}")

def main():
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
    create_flashcard_player()
    
    print("\n🔗 Universal Audio Downloader")
    url = input("Paste Source URL: ").strip()
    if not url: return

    print("\nSelect Output Key:")
    print("1. Original Key (0)")
    print("2. Male ➔ Female (+4)")
    print("3. Female ➔ Male (-4)")
    choice = input("Enter choice (1-3): ").strip()
    semitones = 4 if choice == "2" else -4 if choice == "3" else 0

    vid_choice = input("\nGenerate TV Video (MP4)? (y/n): ").strip().lower()
    generate_video = vid_choice == 'y'

    print("🚀 Initializing AI Engine...")
    sep = Separator()
    sep.load_model(model_filename="UVR_MDXNET_KARA_2.onnx")
    dl_list_opts = {'extract_flat': True, 'quiet': True, 'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    with universal_dl.YoutubeDL(dl_list_opts) as downloader:
        try:
            info = downloader.extract_info(url, download=False)
            if 'entries' in info:
                print(f"📋 Collection Detected: {len(info['entries'])} tracks.")
                for entry in info['entries']:
                    if entry: process_track(entry['url'], semitones, sep, generate_video)
            else:
                process_track(url, semitones, sep, generate_video)
        except:
            process_track(url, semitones, sep, generate_video)


if __name__ == "__main__": main()
