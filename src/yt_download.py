import os
from yt_dlp import YoutubeDL

def download_youtube_audio(url: str, output_dir: str, cookies_path: str | None = None, ffmpeg_path: str | None = None):
    """
    Downloads audio for a YouTube URL using yt-dlp.
    Returns (audio_path, error_message). If success, error_message is None.

    IMPORTANT:
    - 2025 YouTube often requires cookies for restricted videos.
    - Upload/export a cookies.txt (Netscape format) from your logged-in browser.
    """
    os.makedirs(output_dir, exist_ok=True)

    base_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(output_dir, "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "retries": 10,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": 1,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "160"},
        ],
    }
    if ffmpeg_path:
        base_opts["ffmpeg_location"] = ffmpeg_path

    strategies = []
    if cookies_path:
        strategies.append({"cookiefile": cookies_path, "extractor_args": {"youtube": {"player_client": ["web"]}}})

    # Try several client profiles (without cookies)
    strategies += [
        {"extractor_args": {"youtube": {"player_client": ["web"]}}},
        {"extractor_args": {"youtube": {"player_client": ["ios"]}}},
        {"extractor_args": {"youtube": {"player_client": ["tv_embedded"]}}},
    ]

    last_err = None
    for i, extra in enumerate(strategies, 1):
        opts = base_opts | extra
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                audio_path = os.path.join(output_dir, f"{info['id']}.mp3")
            return audio_path, None
        except Exception as e:
            last_err = f"[try {i}/{len(strategies)}] {type(e).__name__}: {e}"

    return None, last_err or "Unknown yt-dlp error"
