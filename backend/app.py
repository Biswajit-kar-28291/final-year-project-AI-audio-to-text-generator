import os
import re
from collections import Counter
from urllib.parse import urlparse, parse_qs

from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import whisper

app = Flask(__name__)
CORS(app)

DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Load Whisper model once
model = whisper.load_model("small")

STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "than", "so", "because",
    "as", "of", "at", "by", "for", "with", "about", "into", "through", "during",
    "before", "after", "above", "below", "to", "from", "up", "down", "in", "out",
    "on", "off", "over", "under", "again", "further", "once", "here", "there",
    "when", "where", "why", "how", "all", "any", "both", "each", "few", "more",
    "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same",
    "very", "can", "will", "just", "do", "does", "did", "is", "am", "are", "was",
    "were", "be", "been", "being", "have", "has", "had", "having", "this", "that",
    "these", "those", "he", "she", "it", "they", "them", "his", "her", "their",
    "you", "your", "yours", "we", "our", "ours", "i", "me", "my", "mine"
}


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
            return bool(parsed.path.strip("/"))

        if parsed.path == "/watch":
            query_params = parse_qs(parsed.query)
            return bool(query_params.get("v", [""])[0])

        if parsed.path.startswith("/shorts/"):
            return bool(parsed.path.split("/shorts/")[-1].strip("/"))

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

    return os.path.join(DOWNLOAD_FOLDER, f"{video_id}.mp3")


def transcribe_audio(audio_path):
    result = model.transcribe(audio_path)
    return result["text"].strip()


def split_sentences(text):
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    return sentences


def extract_keywords(text, top_n=8):
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    filtered_words = [word for word in words if word not in STOP_WORDS]
    word_counts = Counter(filtered_words)
    return [word for word, _ in word_counts.most_common(top_n)]


def score_sentences(sentences, keywords):
    scored = []
    keyword_set = set(keywords)

    for sentence in sentences:
        words = re.findall(r"\b[a-zA-Z]{3,}\b", sentence.lower())
        score = sum(1 for word in words if word in keyword_set)
        scored.append((sentence, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def generate_summary_and_notes(transcript):
    sentences = split_sentences(transcript)

    if not sentences:
        return {
            "summary": "No summary could be generated.",
            "important_points": [],
            "keywords": []
        }

    keywords = extract_keywords(transcript, top_n=8)
    scored_sentences = score_sentences(sentences, keywords)

    top_summary_sentences = [sentence for sentence, score in scored_sentences[:3] if score > 0]
    if not top_summary_sentences:
        top_summary_sentences = sentences[:2]

    summary = " ".join(top_summary_sentences)

    important_points = [sentence for sentence, score in scored_sentences[:5] if score > 0]
    if not important_points:
        important_points = sentences[:5]

    return {
        "summary": summary,
        "important_points": important_points,
        "keywords": keywords
    }


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

        notes_data = generate_summary_and_notes(transcript)

        return jsonify({
            "status": "success",
            "message": "Audio downloaded, transcribed, and notes generated successfully",
            "youtube_link": youtube_link,
            "video_id": video_id,
            "audio_file": audio_file_path,
            "transcript": transcript,
            "summary": notes_data["summary"],
            "important_points": notes_data["important_points"],
            "keywords": notes_data["keywords"]
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "error": f"Server error: {str(e)}"
        }), 500


if __name__ == "__main__":
    app.run(debug=True)