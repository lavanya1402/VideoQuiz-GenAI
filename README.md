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

%% EXPERIENCE
subgraph E["Experience Layer (Workspace UI)"]
UI["Transcript Workspace<br/>Paste URL → Run → View Transcript → Summary + Quiz"]
end

%% INGESTION
subgraph U["Ingestion Layer (Video → Text)"]
U1["YouTube Downloader (yt-dlp)"]
U2["Audio Extraction (FFmpeg)"]
U3["Speech to Text (Whisper)"]
end

%% INTELLIGENCE
subgraph I["Intelligence Layer"]
I1["Transcript Cleaner"]
I2["Summarization Engine"]
I3["Quiz Generator"]
end

%% OUTPUT
subgraph C["Output Layer"]
C1["Transcript File"]
C2["Summary File"]
C3["Quiz File"]
end

%% ENGINE
subgraph D["LLM Decision Engine"]
LLM["OpenAI LLM"]
end

%% FLOW
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
```


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
src/yt_download.py
scripts/check_azure_openai.py
scripts/check_azure_speech.py
.env.example
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

## Checking your API keys

`scripts/check_azure_openai.py` and `scripts/check_azure_speech.py` make one live call each to confirm your Azure keys work. Run them after filling in `.env`.

## License

MIT, see [LICENSE](LICENSE). Built by [Lavanya Srivastava](https://github.com/lavanya1402), Lavanya AI Consultancy.
