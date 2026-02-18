# YouTube Transcript Suite — Download • Transcribe • Summarize • Quiz

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![UI](https://img.shields.io/badge/UI-Streamlit-red)
![Whisper](https://img.shields.io/badge/Transcription-Whisper-green)
![GPT](https://img.shields.io/badge/Summarization-GPT--4o-purple)
![License](https://img.shields.io/badge/License-MIT-yellow)

An end-to-end **AI pipeline** that downloads YouTube audio, transcribes speech, generates summaries, and creates interactive quizzes to assess understanding.

Built for **learning, education, and knowledge extraction**.

> Download → Transcribe → Summarize → Learn

---

## Screenshots

<p align="center">
  <img src="./assets/screenshot-01-home.png" width="30%">
  <img src="./assets/screenshot-02-upload.png" width="30%">
  <img src="./assets/screenshot-03-analysis.png" width="30%">
</p>

<p align="center">
  <img src="./assets/screenshot-04-results.png" width="30%">
  <img src="./assets/screenshot-05-suggestions.png" width="30%">
  <img src="./assets/screenshot-06-report.png" width="30%">
</p>

---

## What It Does

### Download Pipeline
- Accepts YouTube URL
- Downloads audio safely
- Supports cookies (optional)
- Uses FFmpeg for audio processing

### Speech Transcription
- Whisper-based transcription
- Converts speech → text
- Saves transcripts locally
- Handles long videos

### AI Summary Engine
- GPT-powered summarization
- Key takeaways extraction
- Structured summaries
- Important terms & concepts

### Interactive Quiz Generator
- Auto-generated questions
- Multiple choice answers
- Instant scoring
- Feedback with explanations

---

## Architecture

```mermaid
graph TB

%% ================= EXPERIENCE =================
subgraph E["🎛️ Experience Layer (One Smart Workspace)"]
UI["🖥️ Transcript Workspace<br/>📥 Paste YouTube URL<br/>▶ Run Pipeline<br/>📄 View Transcript<br/>🧠 Summary + Quiz<br/>💾 Download Files"]
end

%% ================= INGESTION =================
subgraph U["📥 Ingestion Layer (Video → Text)"]
U1["🔗 YouTube Downloader<br/>yt-dlp"]
U2["🎧 Audio Extraction<br/>FFmpeg"]
U3["🗣️ Speech → Text<br/>Whisper Transcription"]
end

%% ================= INTELLIGENCE =================
subgraph I["🧠 Intelligence Layer (Understanding Engine)"]
I1["📄 Transcript Cleaner<br/>Noise removal"]
I2["🧠 Summarization Engine<br/>LLM Summary"]
I3["❓ Quiz Generator<br/>Auto Q&A"]
end

%% ================= CONTINUITY =================
subgraph C["💾 Output Layer (Learning Assets)"]
C1["📝 Transcript File"]
C2["📌 Summary File"]
C3["🧪 Quiz File"]
end

%% ================= DECISION ENGINE =================
subgraph D["🚀 Decision Engine"]
LLM["🤖 OpenAI LLM<br/>Reasoning + Content Generation"]
end

%% ================= FLOW =================
UI --> U1 --> U2 --> U3
U3 --> I1 --> I2 --> I3
I2 --> LLM --> I2
I3 --> LLM --> I3

I1 --> C1
I2 --> C2
I3 --> C3

C1 --> UI
C2 --> UI
C3 --> UI

%% ================= COLORS =================
classDef exp fill:#dbeafe,stroke:#1e40af,stroke-width:3px,color:#000;
classDef ingest fill:#dcfce7,stroke:#166534,stroke-width:3px,color:#000;
classDef intel fill:#fef3c7,stroke:#92400e,stroke-width:3px,color:#000;
classDef cont fill:#fce7f3,stroke:#9d174d,stroke-width:3px,color:#000;
classDef engine fill:#fff7ed,stroke:#c2410c,stroke-width:3px,color:#000;

class UI exp;
class U1,U2,U3 ingest;
class I1,I2,I3 intel;
class C1,C2,C3 cont;
class LLM engine;


---

## Tech Stack

- Python
- Streamlit UI
- OpenAI Whisper
- GPT-4o
- FFmpeg
- yt-dlp
- Prompt Engineering

---

## Quick Start

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

---

## Files

```
streamlit_app.py
test_openai.py
test_speech.py
requirements.txt
Dockerfile
README.md
assets/
```

---

## Use Cases

- Study YouTube lectures
- Summarize tutorials
- Create learning quizzes
- Auto note generation

---

## License

MIT
