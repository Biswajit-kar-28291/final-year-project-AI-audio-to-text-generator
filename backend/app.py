import os
from urllib.parse import urlparse, parse_qs

from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import whisper

app = Flask(__name__)
CORS(app)

DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Load Whisper model once when backend starts
# small = better quality than tiny, but slower
model = whisper.load_model("small")


def is_valid_youtube_url(url):
    try:
        parsed = urlparse(url)

        valid_domains = {
            "www.youtube.com",
            "youtube.com",
            "youtu.be",
            "www.youtu.be",
            "m.youtube.com",
        }

        if parsed.netloc not in valid_domains:
            return False

        if parsed.netloc in {"youtu.be", "www.youtu.be"}:
            video_id = parsed.path.strip("/")
            return bool(video_id)

        if parsed.path == "/watch":
            query_params = parse_qs(parsed.query)
            video_id = query_params.get("v", [""])[0]
            return bool(video_id)

        if parsed.path.startswith("/shorts/"):
            video_id = parsed.path.split("/shorts/")[-1].strip("/")
            return bool(video_id)

        return False

    except Exception:
        return False


def extract_video_id(url):
    try:
        parsed = urlparse(url)

        if parsed.netloc in {"youtu.be", "www.youtu.be"}:
            return parsed.path.strip("/")

        if parsed.path == "/watch":
            query_params = parse_qs(parsed.query)
            return query_params.get("v", [""])[0]

        if parsed.path.startswith("/shorts/"):
            return parsed.path.split("/shorts/")[-1].strip("/")

        return ""

    except Exception:
        return ""


def download_audio(youtube_link, video_id):
    output_template = os.path.join(DOWNLOAD_FOLDER, f"{video_id}.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": False,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([youtube_link])

    final_file = os.path.join(DOWNLOAD_FOLDER, f"{video_id}.mp3")
    return final_file


def transcribe_audio(audio_path):
    result = model.transcribe(audio_path)
    return result["text"].strip()


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "success",
        "message": "Flask backend is running"
    }), 200


@app.route("/api/process", methods=["POST"])
def process_video():
    try:
        data = request.get_json(silent=True)

        if not data:
            return jsonify({
                "status": "error",
                "error": "No JSON data received"
            }), 400

        youtube_link = str(data.get("youtube_link", "")).strip()

        if not youtube_link:
            return jsonify({
                "status": "error",
                "error": "YouTube link is required"
            }), 400

        if not is_valid_youtube_url(youtube_link):
            return jsonify({
                "status": "error",
                "error": "Please enter a valid YouTube link"
            }), 400

        video_id = extract_video_id(youtube_link)

        if not video_id:
            return jsonify({
                "status": "error",
                "error": "Could not extract video ID from the link"
            }), 400

        audio_file_path = download_audio(youtube_link, video_id)

        if not os.path.exists(audio_file_path):
            return jsonify({
                "status": "error",
                "error": "Audio download failed"
            }), 500

        transcript = transcribe_audio(audio_file_path)

        if not transcript:
            return jsonify({
                "status": "error",
                "error": "Transcription failed"
            }), 500

        return jsonify({
            "status": "success",
            "message": "Audio downloaded and transcribed successfully",
            "youtube_link": youtube_link,
            "video_id": video_id,
            "audio_file": audio_file_path,
            "transcript": transcript,
            "notes": [
                "Audio downloaded successfully.",
                "Real transcript generated using Whisper.",
                "Next step will convert transcript into notes and summary."
            ]
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "error": f"Server error: {str(e)}"
        }), 500


if __name__ == "__main__":
    app.run(debug=True)