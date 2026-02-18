# test_speech.py
from dotenv import load_dotenv; load_dotenv()
import os, azure.cognitiveservices.speech as speechsdk

cfg = speechsdk.SpeechConfig(
    subscription=os.getenv("AZ_SPEECH_KEY"),
    region=os.getenv("AZ_SPEECH_REGION")
)
cfg.speech_recognition_language = "en-US"
audio = speechsdk.AudioConfig(use_default_microphone=True)
rec = speechsdk.SpeechRecognizer(speech_config=cfg, audio_config=audio)
print("Speak something...")
result = rec.recognize_once()
print("Text:", result.text)
