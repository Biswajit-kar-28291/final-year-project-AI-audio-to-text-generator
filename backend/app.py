import re
from urllib.parse import urlparse, parse_qs

from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


def is_valid_youtube_url(url):
    """
    Checks if the URL belongs to YouTube and contains a usable video ID.
    Supports:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://youtube.com/shorts/VIDEO_ID
    """
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

        # youtu.be/<id>
        if parsed.netloc in {"youtu.be", "www.youtu.be"}:
            video_id = parsed.path.strip("/")
            return bool(video_id)

        # youtube.com/watch?v=<id>
        if parsed.path == "/watch":
            query_params = parse_qs(parsed.query)
            video_id = query_params.get("v", [""])[0]
            return bool(video_id)

        # youtube.com/shorts/<id>
        if parsed.path.startswith("/shorts/"):
            video_id = parsed.path.split("/shorts/")[-1].strip("/")
            return bool(video_id)

        return False

    except Exception:
        return False


def extract_video_id(url):
    """
    Extract the YouTube video ID from supported URL formats.
    """
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

        # Day 2 placeholder output
        # Later we will replace this with real audio extraction + transcription + summary
        sample_transcript = (
            "This is a sample transcript for the selected YouTube video. "
            "In the next step, we will replace this with real transcript generation."
        )

        sample_notes = [
            "Validated the YouTube link successfully.",
            "Extracted the video ID from the link.",
            "Prepared backend structure for transcript and notes generation.",
            "Next step will add real video/audio processing."
        ]

        return jsonify({
            "status": "success",
            "message": "YouTube link processed successfully",
            "youtube_link": youtube_link,
            "video_id": video_id,
            "transcript": sample_transcript,
            "notes": sample_notes
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "error": f"Server error: {str(e)}"
        }), 500


if __name__ == "__main__":
    app.run(debug=True)