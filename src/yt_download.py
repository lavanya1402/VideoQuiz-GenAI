import os
import re
import json
import subprocess
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple

import streamlit as st
from yt_dlp import YoutubeDL
from dotenv import load_dotenv

# Optional transcript extractor
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api.formatters import TextFormatter
    YT_TRANSCRIPT_OK = True
except Exception:
    YT_TRANSCRIPT_OK = False

from openai import OpenAI


# =========================
# UI / Styling (PASTEL)
# =========================
def inject_css():
    st.markdown(
        """
        <style>
          :root{
            /* Pastel palette */
            --bg1: #f7f8ff;
            --bg2: #ffffff;

            --panel: rgba(255,255,255,0.92);
            --panel2: rgba(255,255,255,0.78);

            --text: #0f172a;     /* slate-900 */
            --muted: rgba(15,23,42,0.62);

            --accent: #7c83ff;   /* lavender-blue */
            --accent2:#9ae6ff;   /* baby-cyan */
            --accent3:#ffd6e7;   /* baby-pink */
            --accent4:#c9f2d1;   /* mint */

            --border: rgba(15,23,42,0.10);
          }

          .block-container { max-width: 1200px; padding-top: 1.6rem; padding-bottom: 2.0rem; }
          header[data-testid="stHeader"] { background: transparent; }

          /* Main background */
          .stApp{
            background:
              radial-gradient(900px 520px at 12% 8%, rgba(124,131,255,0.18), transparent 45%),
              radial-gradient(850px 520px at 92% 12%, rgba(154,230,255,0.18), transparent 48%),
              radial-gradient(750px 520px at 80% 92%, rgba(255,214,231,0.16), transparent 46%),
              linear-gradient(180deg, var(--bg1) 0%, var(--bg2) 55%, #ffffff 100%);
          }

          /* Sidebar pastel */
          section[data-testid="stSidebar"]{
            background:
              radial-gradient(600px 420px at 10% 10%, rgba(124,131,255,0.16), transparent 55%),
              radial-gradient(600px 420px at 90% 30%, rgba(154,230,255,0.14), transparent 58%),
              linear-gradient(180deg, rgba(255,255,255,0.85) 0%, rgba(255,255,255,0.78) 100%);
            border-right: 1px solid rgba(15,23,42,0.08);
          }
          section[data-testid="stSidebar"] * { color: rgba(15,23,42,0.86) !important; }
          section[data-testid="stSidebar"] input,
          section[data-testid="stSidebar"] textarea,
          section[data-testid="stSidebar"] .stSelectbox > div,
          section[data-testid="stSidebar"] .stFileUploader label + div{
            background: rgba(255,255,255,0.85) !important;
            border: 1px solid rgba(15,23,42,0.10) !important;
            border-radius: 12px !important;
          }

          /* Top brand row */
          .topbar{
            display:flex; align-items:center; justify-content:space-between;
            margin: 6px 0 12px 0;
          }
          .brand-left{ display:flex; flex-direction:column; gap:3px; }
          .brand-title{
            font-size: 18px; font-weight: 780; letter-spacing:-0.3px;
            margin:0; color: var(--text);
          }
          .brand-sub{ font-size: 12.5px; margin:0; color: var(--muted); }
          .brand-pill{
            font-size: 12.5px; font-weight: 700;
            color: rgba(15,23,42,0.78);
            padding: 8px 12px;
            border-radius: 999px;
            background: rgba(255,255,255,0.82);
            border: 1px solid rgba(15,23,42,0.12);
            box-shadow: 0 8px 18px rgba(15,23,42,0.08);
          }

          /* Hero pastel (no black) */
          .hero{
            background:
              radial-gradient(900px 420px at 14% 18%, rgba(124,131,255,0.26), transparent 55%),
              radial-gradient(900px 420px at 92% 18%, rgba(154,230,255,0.26), transparent 55%),
              linear-gradient(135deg, rgba(255,255,255,0.92) 0%, rgba(255,255,255,0.80) 100%);
            border: 1px solid rgba(15,23,42,0.10);
            border-radius: 22px;
            padding: 22px 22px;
            box-shadow: 0 18px 45px rgba(15,23,42,0.10);
            color: var(--text);
          }
          .hero h1{
            margin: 0;
            font-size: 32px;
            letter-spacing: -0.6px;
          }
          .hero p{
            margin: 8px 0 0 0;
            color: var(--muted);
            font-size: 13.5px;
          }

          /* Chips (pastel) */
          .chips{ margin-top: 12px; }
          .chip{
            display:inline-block;
            padding: 7px 11px;
            margin-right: 8px;
            border-radius: 999px;
            border: 1px solid rgba(15,23,42,0.10);
            background: rgba(255,255,255,0.85);
            color: rgba(15,23,42,0.78);
            font-size: 12px;
            font-weight: 700;
            box-shadow: 0 10px 22px rgba(15,23,42,0.06);
          }

          /* Cards */
          .card{
            background: var(--panel);
            border: 1px solid rgba(15,23,42,0.10);
            border-radius: 18px;
            padding: 16px 16px;
            box-shadow: 0 12px 28px rgba(15,23,42,0.06);
          }
          .subtle{
            background: var(--panel2);
            border: 1px solid rgba(15,23,42,0.10);
            border-radius: 18px;
            padding: 14px 14px;
          }
          .muted{ color: var(--muted); font-size: 13px; }

          /* Buttons pastel */
          div.stButton > button{
            background: linear-gradient(90deg, var(--accent) 0%, var(--accent2) 100%) !important;
            color: rgba(15,23,42,0.88) !important;
            border: 1px solid rgba(15,23,42,0.10) !important;
            border-radius: 14px !important;
            padding: 0.72rem 1.10rem !important;
            font-weight: 800 !important;
            box-shadow: 0 14px 26px rgba(124,131,255,0.18) !important;
          }
          div.stButton > button:hover{ filter: brightness(1.02); }
          div.stButton > button:disabled{
            background: rgba(255,255,255,0.72) !important;
            color: rgba(15,23,42,0.45) !important;
            box-shadow: none !important;
          }

          /* Tabs */
          button[data-baseweb="tab"]{ font-weight: 700; }

          /* Footer */
          .footer{
            margin-top: 18px;
            padding-top: 14px;
            border-top: 1px solid rgba(15,23,42,0.10);
            color: rgba(15,23,42,0.55);
            font-size: 13px;
            text-align: center;
            font-weight: 700;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


# =========================
# Helpers
# =========================
def sanitize_filename(s: str) -> str:
    s = re.sub(r"[^\w\-_\. ]", "_", s)
    return s.strip()[:180]


def run_cmd(cmd: List[str]) -> Tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, check=False)
        out = (p.stdout or "") + "\n" + (p.stderr or "")
        return p.returncode, out.strip()
    except Exception as e:
        return 999, str(e)


def ensure_ffmpeg_available(ffmpeg_path: Optional[str] = None) -> str:
    if ffmpeg_path:
        ffmpeg_path = ffmpeg_path.strip().strip('"').strip("'")

        if os.path.isdir(ffmpeg_path):
            ffmpeg_path = os.path.join(ffmpeg_path, "ffmpeg.exe")

        if os.path.isfile(ffmpeg_path) and ffmpeg_path.lower().endswith("ffmpeg.exe"):
            code, out = run_cmd([ffmpeg_path, "-version"])
            if code == 0:
                return ffmpeg_path
            raise RuntimeError(f"FFmpeg exe found but not runnable.\n{out}")

        raise RuntimeError("FFmpeg path invalid. Provide ...\\bin or ...\\bin\\ffmpeg.exe")

    code, _ = run_cmd(["ffmpeg", "-version"])
    if code == 0:
        return "ffmpeg"

    raise RuntimeError("FFmpeg not found. Install FFmpeg or provide ffmpeg.exe path.")


def extract_video_id(url: str) -> Optional[str]:
    patterns = [
        r"v=([A-Za-z0-9_-]{11})",
        r"youtu\.be/([A-Za-z0-9_-]{11})",
        r"/shorts/([A-Za-z0-9_-]{11})",
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None


@dataclass
class DownloadResult:
    ok: bool
    audio_path: Optional[str] = None
    title: Optional[str] = None
    video_id: Optional[str] = None
    error: Optional[str] = None


def download_audio_yt_dlp(
    url: str,
    output_dir: str,
    cookies_txt_path: Optional[str] = None,
    cookies_from_browser: Optional[str] = None,
    ffmpeg_path: Optional[str] = None,
) -> DownloadResult:
    os.makedirs(output_dir, exist_ok=True)

    ffmpeg_exec = ensure_ffmpeg_available(ffmpeg_path)
    outtmpl = os.path.join(output_dir, "%(id)s.%(ext)s")

    base_opts: Dict[str, Any] = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": True,
        "retries": 10,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": 1,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "ffmpeg_location": ffmpeg_exec if ffmpeg_exec != "ffmpeg" else None,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
        ],
    }

    if cookies_txt_path:
        base_opts["cookiefile"] = cookies_txt_path
    elif cookies_from_browser and cookies_from_browser.lower() != "none":
        base_opts["cookiesfrombrowser"] = (cookies_from_browser.lower(),)

    strategies = [
        {"extractor_args": {"youtube": {"player_client": ["web"]}}},
        {"extractor_args": {"youtube": {"player_client": ["ios"]}}},
        {"extractor_args": {"youtube": {"player_client": ["tv_embedded"]}}},
    ]

    last_err = None
    for extra in strategies:
        opts = dict(base_opts)
        opts.update(extra)
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                vid = info.get("id")
                title = info.get("title")

            mp3_path = os.path.join(output_dir, f"{vid}.mp3")
            if os.path.exists(mp3_path):
                return DownloadResult(ok=True, audio_path=mp3_path, title=title, video_id=vid)

            last_err = "Audio downloaded but mp3 not found. Check ffmpeg settings."
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"

    return DownloadResult(ok=False, error=last_err or "Unknown yt-dlp error")


def try_youtube_transcript(video_id: str) -> Optional[str]:
    if not YT_TRANSCRIPT_OK:
        return None
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "hi", "en-US", "en-GB"])
        formatter = TextFormatter()
        return formatter.format_transcript(transcript)
    except Exception:
        return None


def whisper_transcribe(client: OpenAI, audio_path: str) -> str:
    with open(audio_path, "rb") as f:
        tr = client.audio.transcriptions.create(model="whisper-1", file=f)
    return tr.text


def llm_summarize(client: OpenAI, transcript: str) -> str:
    prompt = f"""
Summarize the following transcript in a structured way:
- Key takeaways (5 bullets)
- Short summary (6-8 lines)
- Important terms / concepts (bullets)

Transcript:
{transcript}
""".strip()

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Write a crisp, professional summary. No emojis. No fluff."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip()


def llm_generate_quiz_5q_3opt(client: OpenAI, transcript: str, max_tries: int = 3) -> Dict[str, Any]:
    system = (
        "Return ONLY valid JSON. "
        "Top-level key: questions (exactly 5). "
        "Each item must include: q, options (len=3), answer_index (0-2), explanation."
    )
    user = f"""
Create a quiz from the transcript.
Rules:
- EXACTLY 5 questions
- EXACTLY 3 options each
- answer_index must be 0,1,2
- 1-2 line explanation
Return ONLY JSON.

Transcript:
{transcript}
""".strip()

    last = ""
    for _ in range(max_tries):
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        last = resp.choices[0].message.content or ""
        data = json.loads(last)

        qs = data.get("questions") or []
        if len(qs) != 5:
            continue

        ok = True
        for q in qs:
            opts = q.get("options") or []
            ai = q.get("answer_index")
            if not isinstance(opts, list) or len(opts) != 3:
                ok = False
                break
            if ai not in [0, 1, 2]:
                ok = False
                break
            if not q.get("q"):
                ok = False
                break

        if ok:
            return data

    raise ValueError("Quiz generation failed. Please click Run Pipeline again.")


def score_quiz(quiz: Dict[str, Any], user_answers: List[int]) -> Dict[str, Any]:
    qs = quiz.get("questions") or []
    total = len(qs)
    correct = 0
    details = []

    for i, q in enumerate(qs):
        ans = q.get("answer_index")
        ua = user_answers[i] if i < len(user_answers) else None
        is_ok = (ua == ans)
        if is_ok:
            correct += 1
        details.append(
            {
                "q": q.get("q"),
                "options": q.get("options"),
                "your": ua,
                "correct": ans,
                "explanation": q.get("explanation", ""),
                "ok": is_ok,
            }
        )

    pct = (correct / total * 100.0) if total else 0.0
    return {"total": total, "correct": correct, "percent": pct, "details": details}


# =========================
# App State (prevents re-running pipeline on quiz clicks)
# =========================
def init_state():
    st.session_state.setdefault("pipeline_done", False)
    st.session_state.setdefault("running", False)

    st.session_state.setdefault("title", None)
    st.session_state.setdefault("audio_path", None)
    st.session_state.setdefault("transcript", None)
    st.session_state.setdefault("summary", None)
    st.session_state.setdefault("quiz", None)
    st.session_state.setdefault("files", None)

    st.session_state.setdefault("quiz_answers", [])
    st.session_state.setdefault("quiz_scored", None)


def reset_results():
    st.session_state["pipeline_done"] = False
    st.session_state["title"] = None
    st.session_state["audio_path"] = None
    st.session_state["transcript"] = None
    st.session_state["summary"] = None
    st.session_state["quiz"] = None
    st.session_state["files"] = None
    st.session_state["quiz_answers"] = []
    st.session_state["quiz_scored"] = None


# =========================
# Streamlit UI
# =========================
st.set_page_config(page_title="YouTube Transcript Summary Quiz", layout="wide")
inject_css()

load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

init_state()

# Sidebar
st.sidebar.markdown("## Settings")
output_dir = st.sidebar.text_input("Output folder", value=os.path.join(os.getcwd(), "downloads"))
ffmpeg_path = st.sidebar.text_input("FFmpeg path (folder OR exe)", value="")
st.sidebar.markdown("## Cookies (optional)")
cookies_txt = st.sidebar.file_uploader("Upload cookies.txt", type=["txt"])
cookies_from_browser = st.sidebar.selectbox(
    "Or cookies from browser", options=["None", "chrome", "edge", "firefox"], index=0
)

# Top brand row (visible)
st.markdown(
    """
    <div class="topbar">
      <div class="brand-left">
        <p class="brand-title">YouTube Transcript Suite</p>
        <p class="brand-sub">Download, Transcribe, Summarize, and Assess Understanding</p>
      </div>
      <div class="brand-pill">Made by Lavanya Srivastava</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Header (pastel hero)
st.markdown(
    """
    <div class="hero">
      <div class="chips">
        <span class="chip">Download</span>
        <span class="chip">Transcribe</span>
        <span class="chip">Summarize</span>
        <span class="chip">Quiz</span>
      </div>
      <h1>YouTube Transcript Summary Quiz</h1>
      <p>Use only for content you own or have permission to download.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.write("")

top = st.container()
with top:
    c1, c2 = st.columns([2.4, 1], gap="large")
    with c1:
        url = st.text_input("YouTube URL", placeholder="https://youtu.be/....")
    with c2:
        st.write("")
        run_btn = st.button("Run Pipeline", disabled=(not url) or st.session_state["running"])

# If URL changes, reset old results (so quiz doesn't mix with new URL)
if "last_url" not in st.session_state:
    st.session_state["last_url"] = ""
if url != st.session_state["last_url"]:
    st.session_state["last_url"] = url
    reset_results()

# Run pipeline ONLY on button click
if run_btn:
    if not API_KEY:
        st.error("OPENAI_API_KEY not found in .env. Put it in .env and restart Streamlit.")
        st.stop()

    st.session_state["running"] = True
    reset_results()

    os.makedirs(output_dir, exist_ok=True)
    client = OpenAI(api_key=API_KEY)

    cookies_path = None
    if cookies_txt is not None:
        cookies_path = os.path.join(output_dir, "cookies.txt")
        with open(cookies_path, "wb") as f:
            f.write(cookies_txt.read())

    prog = st.progress(0)
    status = st.empty()

    try:
        status.info("Step 1 of 4: Downloading audio")
        prog.progress(10)

        dl = download_audio_yt_dlp(
            url=url,
            output_dir=output_dir,
            cookies_txt_path=cookies_path,
            cookies_from_browser=cookies_from_browser if cookies_from_browser != "None" else None,
            ffmpeg_path=ffmpeg_path.strip() or None,
        )
        if not dl.ok:
            st.error(f"Download failed: {dl.error}")
            st.session_state["running"] = False
            st.stop()

        prog.progress(30)

        status.info("Step 2 of 4: Creating transcript")
        vid = dl.video_id or extract_video_id(url)
        transcript = try_youtube_transcript(vid) if vid else None
        transcript_source = "YouTube captions" if transcript else "Whisper"

        if not transcript:
            transcript = whisper_transcribe(client, dl.audio_path)

        prog.progress(55)

        status.info("Step 3 of 4: Creating summary")
        summary = llm_summarize(client, transcript)
        prog.progress(75)

        status.info("Step 4 of 4: Creating quiz")
        quiz = llm_generate_quiz_5q_3opt(client, transcript, max_tries=3)
        prog.progress(95)

        safe_title = sanitize_filename(dl.title or "video")

        transcript_path = os.path.join(output_dir, f"{safe_title}_transcript.txt")
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(transcript)

        summary_path = os.path.join(output_dir, f"{safe_title}_summary.txt")
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(summary)

        quiz_path = os.path.join(output_dir, f"{safe_title}_quiz.json")
        with open(quiz_path, "w", encoding="utf-8") as f:
            json.dump(quiz, f, ensure_ascii=False, indent=2)

        st.session_state["title"] = dl.title
        st.session_state["audio_path"] = dl.audio_path
        st.session_state["transcript"] = transcript
        st.session_state["summary"] = summary
        st.session_state["quiz"] = quiz
        st.session_state["files"] = {
            "output_dir": output_dir,
            "audio": dl.audio_path,
            "transcript": transcript_path,
            "summary": summary_path,
            "quiz": quiz_path,
            "transcript_source": transcript_source,
        }

        qs = quiz.get("questions") or []
        st.session_state["quiz_answers"] = [0] * len(qs)

        st.session_state["pipeline_done"] = True
        prog.progress(100)
        status.success("Done")

    finally:
        st.session_state["running"] = False

# Show results if available (and do NOT rerun pipeline on quiz clicks)
if st.session_state["pipeline_done"]:
    files = st.session_state["files"] or {}

    st.write("")
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Result")
    st.write(f"Title: {st.session_state['title'] or 'N/A'}")
    st.write(f"Transcript source: {files.get('transcript_source', 'N/A')}")
    st.write(f"Saved in: {files.get('output_dir', '')}")
    st.markdown("</div>", unsafe_allow_html=True)

    st.write("")
    tab1, tab2, tab3, tab4 = st.tabs(["Transcript", "Summary", "Quiz", "Files"])

    with tab1:
        st.markdown('<div class="subtle">', unsafe_allow_html=True)
        st.text_area("Transcript", st.session_state["transcript"] or "", height=380)
        st.markdown("</div>", unsafe_allow_html=True)

    with tab2:
        st.markdown('<div class="subtle">', unsafe_allow_html=True)
        st.markdown(st.session_state["summary"] or "")
        st.markdown("</div>", unsafe_allow_html=True)

    with tab3:
        quiz = st.session_state["quiz"] or {}
        qs = quiz.get("questions") or []

        st.markdown('<div class="subtle">', unsafe_allow_html=True)
        st.subheader("Quiz (5 questions, 3 options)")

        for i, q in enumerate(qs):
            st.markdown(f"**Q{i+1}. {q['q']}**")
            opts = q["options"]

            chosen = st.radio(
                label=f"Select answer for Q{i+1}",
                options=[0, 1, 2],
                format_func=lambda x: opts[x],
                index=st.session_state["quiz_answers"][i],
                key=f"q_{i}",
            )
            st.session_state["quiz_answers"][i] = chosen
            st.divider()

        colS1, colS2 = st.columns([1, 2])
        with colS1:
            if st.button("Submit"):
                scored = score_quiz(quiz, st.session_state["quiz_answers"])
                st.session_state["quiz_scored"] = scored

        if st.session_state["quiz_scored"]:
            scored = st.session_state["quiz_scored"]
            st.success(f"Score: {scored['correct']}/{scored['total']} ({scored['percent']:.1f}%)")

            wrong = [d for d in scored["details"] if not d["ok"]]
            if wrong:
                st.markdown("Incorrect questions")
                for d in wrong:
                    opts = d["options"]
                    st.markdown(f"**{d['q']}**")
                    st.write(f"Your answer: {opts[d['your']]}")
                    st.write(f"Correct answer: {opts[d['correct']]}")
                    if d["explanation"]:
                        st.caption(d["explanation"])
                    st.divider()

        st.markdown("</div>", unsafe_allow_html=True)

    with tab4:
        st.markdown('<div class="subtle">', unsafe_allow_html=True)
        st.json(files)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="footer">Made by Lavanya Srivastava</div>', unsafe_allow_html=True)

else:
    st.write("")
    st.markdown(
        '<div class="card"><span class="muted">Enter a YouTube URL and click "Run Pipeline". Results will appear here.</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="footer">Made by Lavanya Srivastava</div>', unsafe_allow_html=True)
