# =========================================
# streamlit_app.py — Azure OpenAI (AOAI) only
# Author: Lavanya Srivastava  |  Brand: "Made by Lavanya"
# Year: 2025  |  License: Personal portfolio demo
# =========================================
import os, re, json, glob, time, html, tempfile, subprocess
from pathlib import Path
from datetime import datetime

import streamlit as st
import pandas as pd

# Optional: load .env for local dev (Azure App Service will use App Settings)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

st.set_page_config(
    page_title="Video Summarizer & Quiz (Azure)",
    page_icon="🎥",
    layout="wide"
)

# ──────────────────────────────────────────────────────────────
# Helpers (system tools)
# ──────────────────────────────────────────────────────────────

def _env(name: str, default: str | None = None) -> str | None:
    """Env reader: trims quotes/spaces and normalizes endpoint trailing slash."""
    v = os.getenv(name, default)
    if v is None:
        return None
    v = v.strip().strip('"').strip("'")
    if name == "AZURE_OPENAI_ENDPOINT":
        v = v.rstrip('/')
    return v

def ensure_cmd_ok(cmd: str) -> bool:
    try:
        subprocess.run([cmd, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except Exception:
        return False

def run_ffmpeg_extract_audio(video_path: str, out_wav_path: str, sr: int = 16000):
    if not ensure_cmd_ok("ffmpeg"):
        raise RuntimeError("ffmpeg not found. Ensure ffmpeg is installed or present in PATH.")
    proc = subprocess.run(
        ["ffmpeg", "-y", "-i", video_path, "-ac", "1", "-ar", str(sr), out_wav_path],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise RuntimeError(("ffmpeg failed: " + proc.stderr.decode(errors="ignore"))[:1500])

# ──────────────────────────────────────────────────────────────
# Transcription engines
# ──────────────────────────────────────────────────────────────

@st.cache_resource
def _load_whisper_local(model_name: str = "base"):
    import whisper
    return whisper.load_model(model_name)

def transcribe_local_whisper(wav_path: str, model_name: str = "base") -> str:
    try:
        model = _load_whisper_local(model_name)
        return model.transcribe(wav_path).get("text", "").strip()
    except Exception:
        return ""

def transcribe_azure_speech(wav_path: str) -> str:
    import azure.cognitiveservices.speech as speechsdk
    key = _env("AZ_SPEECH_KEY")
    region = _env("AZ_SPEECH_REGION")
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

    def _stop(_):
        nonlocal done
        done = True

    recognizer.recognized.connect(_recognized)
    recognizer.session_stopped.connect(_stop)
    recognizer.canceled.connect(_stop)

    recognizer.start_continuous_recognition_async().get()
    t0 = time.time()
    while not done and (time.time() - t0) < 1800:
        time.sleep(0.25)
    recognizer.stop_continuous_recognition_async().get()
    return " ".join(chunks).strip()

# ──────────────────────────────────────────────────────────────
# Azure OpenAI (AOAI) client — hardened
# ──────────────────────────────────────────────────────────────

def _make_aoai_client():
    from openai import AzureOpenAI
    endpoint = _env("AZURE_OPENAI_ENDPOINT")
    key = _env("AZURE_OPENAI_API_KEY")
    version = _env("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

    if not endpoint:
        raise RuntimeError("AZURE_OPENAI_ENDPOINT not set.")
    if not key:
        raise RuntimeError("AZURE_OPENAI_API_KEY not set.")

    base = endpoint if endpoint.endswith(".azure.com") else endpoint
    return AzureOpenAI(azure_endpoint=base + "/", api_key=key, api_version=version)


def _get_deployment_or_fail() -> str:
    dep = _env("AZURE_OPENAI_DEPLOYMENT")
    if not dep:
        raise RuntimeError(
            "AZURE_OPENAI_DEPLOYMENT missing. Use your Deployment Name from Azure → OpenAI → Deployments (not the model name)."
        )
    return dep


def call_gpt_azure(prompt: str, temperature: float = 0.2) -> str:
    deployment = _get_deployment_or_fail()
    client = _make_aoai_client()
    try:
        resp = client.chat.completions.create(
            model=deployment,
            temperature=float(temperature),
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        raise RuntimeError(f"AOAI chat call failed: {e}") from e


def call_gpt_azure_json(messages: list, temperature: float = 0.1) -> str:
    deployment = _get_deployment_or_fail()
    client = _make_aoai_client()
    try:
        resp = client.chat.completions.create(
            model=deployment,
            temperature=float(temperature),
            response_format={"type": "json_object"},
            messages=messages,
        )
        return resp.choices[0].message.content
    except Exception as e:
        raise RuntimeError(f"AOAI JSON chat call failed: {e}") from e


# ──────────────────────────────────────────────────────────────
# AOAI validator (lists deployments, pinpoints common mistakes)
# ──────────────────────────────────────────────────────────────

import requests

def validate_aoai() -> dict:
    endpoint = _env("AZURE_OPENAI_ENDPOINT")
    key = _env("AZURE_OPENAI_API_KEY")
    version = _env("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
    dep = _env("AZURE_OPENAI_DEPLOYMENT")

    out = {
        "endpoint": endpoint,
        "api_version": version,
        "deployment": dep,
        "api_key_set": bool(key),
        "ok": False,
        "note": "",
    }

    if not (endpoint and key):
        out["note"] = "Endpoint or API key missing."
        return out

    try:
        url = f"{endpoint.rstrip('/')}/openai/deployments?api-version={version}"
        r = requests.get(url, headers={"api-key": key}, timeout=15)
        if r.status_code != 200:
            out["note"] = f"Deployments list failed: HTTP {r.status_code} {r.text[:300]}"
            return out
        names = [x.get("name") for x in r.json().get("data", []) if isinstance(x, dict)]
        out["deployments_available"] = names
        if dep and dep not in names:
            out["note"] = f"Deployment '{dep}' not found. Available: {names}"
            return out
        out["ok"] = True
        out["note"] = "Azure OpenAI connectivity OK."
        return out
    except Exception as e:
        out["note"] = f"Validation exception: {e}"
        return out

# ──────────────────────────────────────────────────────────────
# Quiz prompt builder
# ──────────────────────────────────────────────────────────────

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

# ──────────────────────────────────────────────────────────────
# YouTube helpers
# ──────────────────────────────────────────────────────────────

import yt_dlp, xml.etree.ElementTree as ET
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled


def _extract_video_id(url: str) -> str | None:
    m = re.search(r"(?:v=|/shorts/|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else None


def fetch_transcript_via_api_first(url: str) -> tuple[str | None, str]:
    vid = _extract_video_id(url)
    if not vid:
        return None, "Could not parse YouTube video id."
    try:
        s = YouTubeTranscriptApi.get_transcript(vid, languages=["en", "en-US", "en-GB"])
        text = "\n".join([c["text"].strip() for c in s if c.get("text")])
        return (text, "Fetched captions via youtube-transcript-api.") if text.strip() else (None, "Empty transcript.")
    except (NoTranscriptFound, TranscriptsDisabled):
        return None, "No public transcript; falling back."
    except Exception as e:
        return None, f"Transcript API error: {e}"


def _vtt_to_text(vtt_str: str) -> str:
    lines = []
    for line in vtt_str.splitlines():
        s = line.strip()
        if (not s) or s.startswith("WEBVTT") or "-->" in s or re.match(r"^\d+$", s):
            continue
        s = re.sub(r"<[^>]+>", "", s)
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


def _pick_caption_track(tracks: dict, prefer_langs=("en", "en-US", "en-GB")):
    if not tracks:
        return None
    for lang in list(prefer_langs) + list(tracks.keys()):
        if lang in tracks:
            arr = sorted(tracks[lang], key=lambda x: (x.get("ext") != "vtt", x.get("ext") != "srt"))
            return arr[0], lang
    lang = next(iter(tracks.keys()))
    return tracks[lang][0], lang


def fetch_youtube_captions_robust(url: str) -> tuple[str | None, str]:
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
        import requests as _rq
        r = _rq.get(track["url"], timeout=20)
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
        text = _vtt_to_text(r.text)

    if not text.strip():
        return None, f"Downloaded caption track ({lang}, {ext}) has no usable lines."
    return text, f"Fetched {lang} captions ({ext})."


def ytdlp_download_audio(url: str, out_dir: str) -> str:
    if not ensure_cmd_ok("ffmpeg"):
        raise RuntimeError("ffmpeg not found.")
    ydl_opts = {
        "quiet": True,
        "format": "bestaudio/best",
        "outtmpl": os.path.join(out_dir, "audio.%(ext)s"),
        "ratelimit": 2_500_000,
        "sleep_requests": 1.0,
        "retries": 3,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(url, download=True)

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

# ──────────────────────────────────────────────────────────────
# UI — Header / Brand
# ──────────────────────────────────────────────────────────────

st.markdown(
    """
    <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 12px;border-radius:10px;background:#F3F6FF;border:1px solid #E0E7FF;margin-bottom:8px;">
      <div>
        <b>Status:</b> <span style="color:#2E7D32;">App ✓</span> |
        <span style="color:#1976D2;">Speech ✓</span> |
        <span style="color:#6A1B9A;">Caption/Audio Fallback ✓</span>
      </div>
      <div style="font-weight:600;color:#111;">Made by Lavanya Srivastava</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ──────────────────────────────────────────────────────────────
# Sidebar (settings + debug)
# ──────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("⚙️ Settings")
    engine = st.selectbox("Transcription engine", ["Azure Speech", "Local Whisper (base)"])
    st.caption("Tip: keep videos ≤ 10–15 min for smooth demos.")

    # Debug panel
    if st.checkbox("🔍 Debug Azure"):
        info = validate_aoai()
        st.write({
            "endpoint": info["endpoint"],
            "api_version": info["api_version"],
            "deployment": info.get("deployment"),
            "api_key_set": info["api_key_set"],
            "deployments_available": info.get("deployments_available", []),
            "ok": info["ok"],
            "note": info["note"],
        })
        if st.button("Ping AOAI"):
            try:
                msg = call_gpt_azure("Say OK from Azure OpenAI.")
                st.success(msg)
            except Exception as e:
                st.error(str(e))

# ──────────────────────────────────────────────────────────────
# Hero + quick demo controls
# ──────────────────────────────────────────────────────────────

st.markdown("# 🎥 Video Summarizer & Quiz (Azure)")

st.info("Use a **YouTube URL** (transcript first, then captions, then audio fallback) or **upload a video** → get **Transcript → Summary → Quiz**.")

SAMPLE_PATH = Path("assets/sample.mp4")

st.subheader("⚡ Quick Demo")
_c1, _c2, _ = st.columns([1, 1, 2])
with _c1:
    if SAMPLE_PATH.exists() and st.button("Try sample video", use_container_width=True):
        st.session_state["_sample_video_bytes"] = SAMPLE_PATH.read_bytes()
        st.session_state["_sample_video_name"] = SAMPLE_PATH.name
        st.success("Sample loaded. Scroll to Upload.")
with _c2:
    open_caption_box = st.toggle("Use YouTube URL", value=True)

# ──────────────────────────────────────────────────────────────
# YouTube handler (captions/transcript first)
# ──────────────────────────────────────────────────────────────

if open_caption_box:
    yt_url = st.text_input("Paste YouTube URL:", placeholder="https://www.youtube.com/watch?v=...")
    if yt_url and st.button("Fetch transcript 🎬", use_container_width=True):
        with st.spinner("Extracting transcript..."):
            text, msg = fetch_transcript_via_api_first(yt_url.strip())
            if text:
                st.success(f"✅ {msg}")
                st.session_state["_forced_transcript_from_captions"] = text
            else:
                text2, msg2 = fetch_youtube_captions_robust(yt_url.strip())
                if text2:
                    st.success(f"✅ {msg2}")
                    st.session_state["_forced_transcript_from_captions"] = text2
                else:
                    st.warning(f"{msg2 or msg} — Captions unavailable, converting audio.")
                    try:
                        with tempfile.TemporaryDirectory() as tdir:
                            wav_path = ytdlp_download_audio(yt_url.strip(), tdir)
                            tx = (
                                transcribe_local_whisper(wav_path)
                                if engine.startswith("Local")
                                else transcribe_azure_speech(wav_path)
                            )
                        if tx.strip():
                            st.success("✅ Audio converted successfully.")
                            st.session_state["_forced_transcript_from_captions"] = tx
                        else:
                            st.error("❌ No speech detected. Try another video or upload a file.")
                    except Exception as e:
                        st.error("Audio fallback failed.")
                        st.code(str(e))

# ──────────────────────────────────────────────────────────────
# Upload / Select video
# ──────────────────────────────────────────────────────────────

st.subheader("📤 Upload")
_sample_loaded = "_sample_video_bytes" in st.session_state
video_bytes, video_name = None, None

if _sample_loaded:
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

# ──────────────────────────────────────────────────────────────
# Transcript (captions or ASR)
# ──────────────────────────────────────────────────────────────

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
            transcript = (
                transcribe_local_whisper(wav_path, "base")
                if engine.startswith("Local")
                else transcribe_azure_speech(wav_path)
            )

if not transcript or not transcript.strip():
    st.warning("No speech detected.")
    st.stop()

st.subheader("📝 Transcript")
transcript = st.text_area("Editable transcript", value=transcript, height=300)
_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
st.download_button("⬇️ Download transcript (.txt)", data=transcript, file_name=f"transcript_{_ts}.txt")

# ──────────────────────────────────────────────────────────────
# Executive Summary (AOAI)
# ──────────────────────────────────────────────────────────────

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
    st.download_button("⬇️ Download summary (.md)", data=summary, file_name=f"summary_{_ts}.md")
except Exception as e:
    st.error("Summarization failed. Check endpoint/key/deployment.")
    st.code(str(e))

# ──────────────────────────────────────────────────────────────
# QUIZ (AOAI JSON)
# ──────────────────────────────────────────────────────────────

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
        m = re.search(r"\{[\s\S]*\}", locals().get("qraw", ""), re.MULTILINE)
        if m:
            try:
                data = json.loads(m.group(0))
                if "questions" in data and isinstance(data["questions"], list):
                    st.session_state["quiz_data"] = data
                else:
                    st.error("Quiz generation failed.")
                    st.code(str(e))
            except Exception:
                st.error("Quiz generation failed.")
                st.code(str(e))
        else:
            st.error("Quiz generation failed.")
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
        _ts2 = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button("⬇️ Results (.csv)", data=df.to_csv(index=False), file_name=f"quiz_results_{_ts2}.csv")
        st.download_button("⬇️ Quiz (.json)", data=json.dumps(quiz_data, indent=2), file_name=f"quiz_{_ts2}.json")
else:
    st.caption("Click **Generate quiz** to create assessment items from the transcript.")

# ──────────────────────────────────────────────────────────────
# Footer — Authenticity tag
# ──────────────────────────────────────────────────────────────

st.markdown(
    """
    <div style="margin-top:18px;padding:10px 12px;border-radius:10px;background:#F8FAFC;border:1px solid #E5E7EB;">
      <div style="font-size:14px;color:#111;">
        © 2025 <b>Lavanya Srivastava</b> — Made with ❤️ | Authentic Build: <i>"Made by Lavanya"</i>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
