import os
import time
from dotenv import load_dotenv

# Video -> audio
from moviepy.editor import VideoFileClip

# Azure Speech
import azure.cognitiveservices.speech as speechsdk

# Azure AI Foundry (OpenAI-compatible)
from openai import OpenAI

load_dotenv()

# ------------ Audio extraction ------------
def extract_audio_from_video(video_path: str, audio_path: str) -> str | None:
    """
    Extracts audio from a video file to mp3 using moviepy.
    If FFMPEG_PATH is set in .env, moviepy will try to use it (imageio-ffmpeg respects PATH).
    """
    try:
        clip = VideoFileClip(video_path)
        clip.audio.write_audiofile(audio_path, codec="mp3")
        clip.close()
        return audio_path
    except Exception:
        return None

# ------------ Azure Speech transcription ------------
def transcribe_audio(audio_path: str) -> str | None:
    """
    Transcribe using Azure Speech-to-Text (short/medium files).
    For long files, this uses continuous recognition in-process and concatenates results.
    """
    key = os.getenv("AZ_SPEECH_KEY")
    region = os.getenv("AZ_SPEECH_REGION")
    if not key or not region:
        return None

    speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
    # You may adjust language here if needed:
    # speech_config.speech_recognition_language = "en-US"
    audio_config = speechsdk.AudioConfig(filename=audio_path)
    recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

    results = []
    done = False

    def handle_final(evt):
        if evt.result and evt.result.text:
            results.append(evt.result.text)

    def stop_cb(evt):
        nonlocal done
        done = True

    recognizer.recognized.connect(handle_final)
    recognizer.session_stopped.connect(stop_cb)
    recognizer.canceled.connect(stop_cb)

    recognizer.start_continuous_recognition()
    while not done:
        time.sleep(0.5)
    recognizer.stop_continuous_recognition()

    return " ".join(results).strip() or None

# ------------ Azure AI Foundry (summary + quiz) ------------
def _client() -> OpenAI | None:
    endpoint = os.getenv("AZ_INFERENCE_ENDPOINT")
    key = os.getenv("AZ_INFERENCE_KEY")
    if not endpoint or not key:
        return None
    return OpenAI(base_url=endpoint, api_key=key)

def create_summary(transcript_text: str) -> str:
    """
    Summarize with your Azure deployment (e.g., Phi-4-mini-instruct).
    """
    model = os.getenv("AZ_MODEL", "Phi-4-mini-instruct")
    client = _client()
    if not client:
        return "Azure AI Foundry credentials missing."

    prompt = (
        "Summarize the following transcript clearly, concisely, and factually. "
        "Use short paragraphs and bullet points where helpful.\n\n"
        f"{transcript_text}"
    )
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": "You are a helpful summarizer."},
                      {"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        return f"Summarization failed: {e}"

def create_quiz(summary_text: str, n_q: int = 5) -> str:
    """
    Generate MCQ quiz text (A/B/C/D + answers).
    Return as plain text so you can just display it.
    """
    model = os.getenv("AZ_MODEL", "Phi-4-mini-instruct")
    client = _client()
    if not client:
        return "Azure AI Foundry credentials missing."

    prompt = (
        f"Create {n_q} multiple-choice questions (A-D) based ONLY on the summary below. "
        "Each question must include four options and indicate the correct option letter.\n\n"
        f"SUMMARY:\n{summary_text}"
    )
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": "You write clear quizzes."},
                      {"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        return f"Quiz generation failed: {e}"
