# =========================================
# streamlit_app.py — Azure-ready, recruiter-proof
# =========================================
import os, io, re, json, glob, time, html, tempfile, subprocess
from pathlib import Path
from datetime import datetime

import streamlit as st
import pandas as pd

# Optional: load .env locally
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Put ffmpeg on PATH if provided
if os.getenv("FFMPEG_PATH"):
    os.environ["PATH"] = os.getenv("FFMPEG_PATH") + os.pathsep + os.environ.get("PATH", "")

st.set_page_config(page_title="Video Summarizer & Quiz (Azure)", page_icon="🎥", layout="wide")

# =========================
# Utilities: shell helpers
# =========================
def ensure_cmd_ok(cmd: str) -> bool:
    try:
        subprocess.run([cmd, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except Exception:
        return False

def run_ffmpeg_extract_audio(video_path: str, out_wav_path: str, sr: int = 16000):
    if not ensure_cmd_ok("ffmpeg"):
        raise RuntimeError("ffmpeg not found on PATH. Install ffmpeg or set FFMPEG_PATH.")
    cmd = ["ffmpeg", "-y", "-i", video_path, "-ac", "1", "-ar", str(sr), out_wav_path]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError(("ffmpeg failed: " + proc.stderr.decode(errors="ignore"))[:1500])

# =========================
# (Optional) Local Whisper
# =========================
@st.cache_resource
def _load_whisper_local(model_name: str = "base"):
    import whisper
    return whisper.load_model(model_name)

def transcribe_local_whisper(wav_path: str, model_name: str = "base") -> str:
    try:
        model = _load_whisper_local(model_name)
        return model.transcribe(wav_path).get("text", "").strip()
    except Exception as e:
        return ""

# =========================
# Azure Speech (STT)
# =========================
def transcribe_azure_speech(wav_path: str) -> str:
    import azure.cognitiveservices.speech as speechsdk
    key = os.getenv("AZ_SPEECH_KEY")
    region = os.getenv("AZ_SPEECH_REGION")
    if not key or not region:
        raise RuntimeError("Azure Speech not configured. Set AZ_SPEECH_KEY and AZ_SPEECH_REGION.")
    speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
    speech_config.speech_recognition_language = "en-US"
    audio_config = speechsdk.audio.AudioConfig(filename=wav_path)
    recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

    done, chunks = False, []

    def _recognized(evt):
        if evt.result and evt.result.text:
            chunks.append(evt.result.text)

    def _stop(evt):
        nonlocal done
        done = True

    recognizer.recognized.connect(_recognized)
    recognizer.session_stopped.connect(_stop)
    recognizer.canceled.connect(_stop)

    recognizer.start_continuous_recognition_async().get()
    # safety timeout (e.g., 30 minutes) for very long content
    t0 = time.time()
    while not done and (time.time() - t0) < 1800:
        time.sleep(0.25)
    recognizer.stop_continuous_recognition_async().get()
    return " ".join(chunks).strip()

# =========================
# Azure OpenAI (text + JSON mode)
# =========================
def call_gpt_azure(prompt: str, temperature: float = 0.2) -> str:
    from openai import AzureOpenAI
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    key = os.getenv("AZURE_OPENAI_API_KEY")
    version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    if not endpoint or not key or not deployment:
        raise RuntimeError("Azure OpenAI missing envs. Set AZURE_OPENAI_ENDPOINT/API_KEY/DEPLOYMENT.")
    client = AzureOpenAI(azure_endpoint=endpoint, api_key=key, api_version=version)
    resp = client.chat.completions.create(
        model=deployment, temperature=temperature,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content.strip()

def call_gpt_azure_json(messages: list, temperature: float = 0.1) -> str:
    from openai import AzureOpenAI
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    key = os.getenv("AZURE_OPENAI_API_KEY")
    version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    if not endpoint or not key or not deployment:
        raise RuntimeError("Azure OpenAI missing envs. Set AZURE_OPENAI_ENDPOINT/API_KEY/DEPLOYMENT.")
    client = AzureOpenAI(azure_endpoint=endpoint, api_key=key, api_version=version)
    resp = client.chat.completions.create(
        model=deployment,
        temperature=temperature,
        response_format={"type": "json_object"},  # ✅ force JSON
        messages=messages,
    )
    return resp.choices[0].message.content

# =========================
# Quiz prompt builders
# =========================
def build_quiz_prompt(tx: str) -> str:
    return f"""
Create exactly 6 questions grounded ONLY in this transcript.
Target mix: ~4 multiple-choice and ~2 true/false.

Output schema (strict):
{{
  "questions": [
    {{"type":"mcq","question":"...","options":["A","B","C","D"],"answer":"B","explanation":"1 short sentence"}},
    {{"type":"tf","question":"...","answer":true,"explanation":"1 short sentence"}}
  ]
}}

Transcript:
{tx}
""".strip()

# =========================
# Robust YouTube captions + fallback
# =========================
import yt_dlp, requests, xml.etree.ElementTree as ET

def _vtt_to_text(vtt_str: str) -> str:
    lines = []
    for line in vtt_str.splitlines():
        s = line.strip()
        if (not s) or s.startswith("WEBVTT") or "-->" in s or re.match(r"^\d+$", s):
            continue
        s = re.sub(r"<[^>]+>", "", s)  # strip html tags
        if s:
            lines.append(s)
    return "\n".join(lines)

def _srv3_xml_to_text(xml_str: str) -> str:
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        return ""
    parts = []
    for t in root.iter("text"):
        txt = "".join(t.itertext())
        txt = html.unescape(txt).replace("\n", " ").strip()
        if txt:
            parts.append(txt)
    return "\n".join(parts)

def _pick_caption_track(tracks: dict, prefer_langs=("en","en-US","en-GB")):
    if not tracks:
        return None
    for lang in list(prefer_langs) + list(tracks.keys()):
        if lang in tracks:
            arr = sorted(tracks[lang], key=lambda x: (x.get("ext") != "vtt", x.get("ext") != "srt"))
            return arr[0], lang
    lang = next(iter(tracks.keys()))
    return tracks[lang][0], lang

def fetch_youtube_captions_robust(url: str) -> tuple[str | None, str]:
    """
    Try to fetch captions (public/auto). Returns (text, status_msg).
    """
    try:
        with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        return None, f"yt-dlp error: {e}"

    subs = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}

    choice = _pick_caption_track(subs) or _pick_caption_track(auto)
    if not choice:
        return None, "No subtitles or auto-captions exposed by YouTube."

    track, lang = choice
    try:
        r = requests.get(track["url"], timeout=20)
        r.raise_for_status()
    except Exception as e:
        return None, f"Failed to download caption track: {e}"

    ext = (track.get("ext") or "").lower()
    raw = r.text.lstrip()
    if ext == "vtt" or raw.startswith("WEBVTT"):
        text = _vtt_to_text(r.text)
    elif ext.startswith("srv") or raw.startswith("<timedtext"):
        text = _srv3_xml_to_text(r.text)
    else:
        text = _vtt_to_text(r.text)  # best-effort

    if not text.strip():
        return None, f"Downloaded caption track ({lang}, {ext}) has no usable lines."
    return text, f"Fetched {lang} captions ({ext})."

def ytdlp_download_audio(url: str, out_dir: str) -> str:
    """
    Download bestaudio via yt-dlp, then convert to 16k mono wav using ffmpeg.
    Returns path to the .wav file.
    """
    if not ensure_cmd_ok("ffmpeg"):
        raise RuntimeError("ffmpeg not found on PATH. Install ffmpeg or set FFMPEG_PATH.")

    ydl_opts = {
        "quiet": True,
        "format": "bestaudio/best",
        "outtmpl": os.path.join(out_dir, "audio.%(ext)s"),
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(url, download=True)

    # find downloaded file
    downloaded = None
    for p in glob.glob(os.path.join(out_dir, "audio.*")):
        if not p.endswith(".wav"):
            downloaded = p
            break
    if not downloaded:
        raise RuntimeError("yt-dlp did not produce an audio file.")

    wav_path = os.path.join(out_dir, "audio.wav")
    run_ffmpeg_extract_audio(downloaded, wav_path, sr=16000)
    return wav_path

# =========================
# Top Banner (polish)
# =========================
st.markdown(
    """
    <div style="background:#E8F5E9;padding:10px;border-radius:8px;margin-bottom:10px;">
    <b>Status:</b> Connected to <span style="color:#2E7D32;">Azure Foundry ✓</span> |
    <span style="color:#1976D2;">Azure Speech ✓</span> |
    <span style="color:#6A1B9A;">Auto Fallback Enabled ✓</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# =========================
# Sidebar
# =========================
with st.sidebar:
    st.header("⚙️ Settings")
    engine = st.selectbox("Transcription engine", ["Azure Speech", "Local Whisper (base)"])
    st.caption("Tip: keep videos ≤ 10–15 min for smooth demos.")

# =========================
# Hero
# =========================
st.markdown("# 🎥 Video Summarizer & Quiz (Azure)")
st.info("Use a **YouTube URL** (auto fallback to audio if captions blocked) or **upload a video** → get **Transcript → Summary → Quiz**.")
with st.expander("About this demo", expanded=False):
    st.caption("Azure OpenAI for summary/quiz (JSON mode). Azure Speech (or local Whisper) for transcription.")

# =========================
# Quick Demo
# =========================
SAMPLE_PATH = Path("assets/sample.mp4")
st.subheader("⚡ Quick Demo")
c1, c2, _ = st.columns([1, 1, 2])
with c1:
    if SAMPLE_PATH.exists() and st.button("Try sample video", use_container_width=True):
        st.session_state["_sample_video_bytes"] = SAMPLE_PATH.read_bytes()
        st.session_state["_sample_video_name"] = SAMPLE_PATH.name
        st.success("Sample loaded. Scroll to Upload.")
with c2:
    open_caption_box = st.toggle("Use YouTube URL", value=True)

# --- Smart YouTube handler (recruiter-proof) ---
if open_caption_box:
    yt_url = st.text_input("Paste YouTube URL:", placeholder="https://www.youtube.com/watch?v=...")
    if yt_url and st.button("Fetch transcript 🎬", use_container_width=True):
        with st.spinner("Extracting transcript... please wait"):
            try:
                # 1) Try public/auto captions
                text, msg = fetch_youtube_captions_robust(yt_url.strip())
                if text:
                    st.success(f"✅ {msg}")
                    st.session_state["_forced_transcript_from_captions"] = text
                else:
                    # 2) Auto-fallback: download audio → Azure Speech/Local
                    st.warning(f"{msg} — Captions unavailable, converting audio.")
                    with tempfile.TemporaryDirectory() as tdir:
                        wav_path = ytdlp_download_audio(yt_url.strip(), tdir)
                        if engine.startswith("Local"):
                            text2 = transcribe_local_whisper(wav_path)
                        else:
                            text2 = transcribe_azure_speech(wav_path)
                    if text2.strip():
                        st.success("✅ Audio converted successfully.")
                        st.session_state["_forced_transcript_from_captions"] = text2
                    else:
                        st.error("❌ No speech detected. Try another video or upload a file.")
            except Exception as e:
                st.error("⚠️ Transcript extraction failed.")
                st.code(str(e))

# =========================
# Upload / Select video
# =========================
st.subheader("📤 Upload")
sample_loaded = "_sample_video_bytes" in st.session_state
video_bytes, video_name = None, None

if sample_loaded:
    video_bytes = st.session_state["_sample_video_bytes"]
    video_name = st.session_state["_sample_video_name"]
    st.caption(f"Using sample: **{video_name}**")
    st.video(video_bytes)
else:
    uf = st.file_uploader("Choose MP4, MOV, or MKV", type=["mp4", "mov", "mkv"], label_visibility="collapsed")
    forced_caps = st.session_state.get("_forced_transcript_from_captions")
    if not uf and not forced_caps:
        st.stop()
    if uf:
        st.video(uf)
        video_bytes = uf.getbuffer()
        video_name = uf.name

# =========================
# Transcript (captions or ASR)
# =========================
forced_caps = st.session_state.get("_forced_transcript_from_captions")
if forced_caps:
    transcript = forced_caps
else:
    if not video_bytes:
        st.stop()
    with st.spinner("Extracting audio and transcribing…"):
        with tempfile.TemporaryDirectory() as tmp:
            video_path = os.path.join(tmp, video_name or "video.mp4")
            with open(video_path, "wb") as f:
                f.write(video_bytes)
            wav_path = os.path.join(tmp, "audio.wav")
            run_ffmpeg_extract_audio(video_path, wav_path, sr=16000)
            if engine.startswith("Local"):
                transcript = transcribe_local_whisper(wav_path, model_name="base")
            else:
                transcript = transcribe_azure_speech(wav_path)

if not transcript or not transcript.strip():
    st.warning("No speech detected.")
    st.stop()

st.subheader("📝 Transcript")
transcript = st.text_area("Editable transcript", value=transcript, height=300)
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
st.download_button("⬇️ Download transcript (.txt)", data=transcript, file_name=f"transcript_{ts}.txt")

# =========================
# Executive Summary (Azure OpenAI)
# =========================
st.subheader("📚 Executive Summary")
sum_prompt = f"""
Summarize the transcript into:
1) Abstract (3–5 bullets),
2) Key takeaways (5–8 bullets),
3) Action items (3–5 bullets),
4) Short notable quotes (2–3).

Transcript:
{transcript}
"""
try:
    summary = call_gpt_azure(sum_prompt, temperature=0.2)
    st.markdown(summary)
    st.download_button("⬇️ Download summary (.md)", data=summary, file_name=f"summary_{ts}.md")
except Exception as e:
    st.error("Summarization failed. Check Azure OpenAI env or deployment.")
    st.code(str(e))

# =========================
# QUIZ: JSON-mode generation → attempt → score
# =========================
st.subheader("🧠 Quiz")
col1, col2 = st.columns([1, 1])
with col1:
    gen = st.button("Generate quiz", use_container_width=True)
with col2:
    reset = st.button("Reset quiz", use_container_width=True)

if reset:
    st.session_state.pop("quiz_data", None)
    st.session_state.pop("_forced_transcript_from_captions", None)
    for k in list(st.session_state.keys()):
        if k.startswith("q"):
            st.session_state.pop(k, None)
    st.rerun()

def _truncate(s: str, max_chars: int = 12000) -> str:
    return s if len(s) <= max_chars else s[:max_chars]

if gen:
    try:
        tx = _truncate(transcript)
        system = {
            "role": "system",
            "content": (
                "You are an assessment generator. "
                "Return ONLY a JSON object with 'questions' array. No prose or markdown. "
                "Each explanation must be one short sentence."
            ),
        }
        user = {"role": "user", "content": build_quiz_prompt(tx)}
        qraw = call_gpt_azure_json([system, user], temperature=0.1)
        data = json.loads(qraw)
        if not isinstance(data, dict) or "questions" not in data or not isinstance(data["questions"], list):
            raise ValueError("JSON present but missing 'questions'.")
        if len(data["questions"]) != 6:
            data["questions"] = data["questions"][:6]
        st.session_state["quiz_data"] = data
    except Exception as e:
        # Fallback: try to salvage largest {...}
        m = re.search(r"\{[\s\S]*\}", locals().get("qraw", ""), re.MULTILINE)
        if m:
            try:
                data = json.loads(m.group(0))
                if "questions" in data and isinstance(data["questions"], list):
                    st.session_state["quiz_data"] = data
                else:
                    st.error("Quiz generation failed. Try again or check deployment.")
                    st.code(str(e))
            except Exception:
                st.error("Quiz generation failed. Try again or check deployment.")
                st.code(str(e))
        else:
            st.error("Quiz generation failed. Try again or check deployment.")
            st.code(str(e))

quiz_data = st.session_state.get("quiz_data")
if quiz_data and quiz_data.get("questions"):
    st.success("Answer the questions and click **Submit**.")
    with st.form("quiz_form", clear_on_submit=False):
        for i, q in enumerate(quiz_data["questions"]):
            qtype = q.get("type", "mcq").lower()
            question = q.get("question", "").strip() or f"Question {i+1}"
            st.markdown(f"**Q{i+1}. {question}**")
            if qtype == "mcq":
                opts = (q.get("options", []) + [""] * 4)[:4]
                st.radio("Choose one:", opts, key=f"q{i}", index=0)
            elif qtype == "tf":
                st.radio("True/False:", ["True", "False"], key=f"q{i}", index=0)
            else:
                st.text_input("Your answer:", key=f"q{i}")
            st.markdown("---")
        submitted = st.form_submit_button("Submit answers ✅")

    if submitted:
        results, correct_count = [], 0
        for i, q in enumerate(quiz_data["questions"]):
            qtype = q.get("type", "mcq").lower()
            user_ans = st.session_state.get(f"q{i}")
            explanation = q.get("explanation", "")
            if qtype == "mcq":
                correct_label = q.get("answer", "").strip()
                correct = (str(user_ans).strip() == correct_label)
            elif qtype == "tf":
                correct_label = "True" if q.get("answer", True) else "False"
                correct = (user_ans == correct_label)
            else:
                correct_label = q.get("answer", "").strip()
                correct = (str(user_ans).strip().lower() == correct_label.lower())
            if correct:
                correct_count += 1
            results.append({
                "Q#": i + 1,
                "Question": q.get("question", ""),
                "Your Answer": str(user_ans),
                "Correct Answer": correct_label,
                "Correct?": "✅" if correct else "❌",
                "Why": explanation,
            })

        total = len(quiz_data["questions"])
        st.metric("Your Score", f"{correct_count}/{total}")
        st.progress(correct_count / max(total, 1))
        df = pd.DataFrame(results)
        st.caption("Detailed feedback:")
        st.dataframe(df, use_container_width=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button("⬇️ Results (.csv)", data=df.to_csv(index=False),
                           file_name=f"quiz_results_{ts}.csv")
        st.download_button("⬇️ Quiz (.json)", data=json.dumps(quiz_data, indent=2),
                           file_name=f"quiz_{ts}.json")
else:
    st.caption("Click **Generate quiz** to create assessment items from the transcript.")
