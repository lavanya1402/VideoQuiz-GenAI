# Video Summarization and Quiz Generation with OpenAI

This project allows you to upload long-form videos (lectures, podcasts), transcribe them using Whisper, summarize the content, and generate quizzes using OpenAI.

## Setup

- Create a virtual environment
- Install dependencies with `pip install -r requirements.txt`
- Install FFmpeg (required for video/audio processing)
- Set your OpenAI API key in `src/utils.py` environment variable

## Run

- Run Flask app: `python app.py`
- Run Streamlit app: `streamlit run streamlit_app.py`

Upload your videos and enjoy summarization and quizzes!
