import os
import re
import ast
import json
import operator
import requests
from collections import Counter
from urllib.parse import urlparse, parse_qs

from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import whisper

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)
CORS(app)

DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Change to "base" if your PC is slow
model = whisper.load_model("small")

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.1:8b"

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
    "you", "your", "yours", "we", "our", "ours", "i", "me", "my", "mine",
    "hello", "welcome", "today", "video", "guys", "okay", "right", "yeah"
}

SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.Mod: operator.mod
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
    return [s.strip() for s in sentences if s.strip()]


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


def generate_auto_qa(keywords, important_points):
    qa_list = []

    for i, point in enumerate(important_points[:3]):
        keyword = keywords[i] if i < len(keywords) else "topic"
        qa_list.append({
            "question": f"What does the video explain about {keyword}?",
            "answer": point
        })

    return qa_list


def generate_summary_and_notes_rule_based(transcript):
    sentences = split_sentences(transcript)

    if not sentences:
        return {
            "summary": "No summary could be generated.",
            "important_points": [],
            "keywords": [],
            "auto_qa": []
        }

    keywords = extract_keywords(transcript, top_n=8)
    scored_sentences = score_sentences(sentences, keywords)

    top_summary_sentences = [sentence for sentence, score in scored_sentences[:3] if score > 0]
    if not top_summary_sentences:
        top_summary_sentences = sentences[:3]

    important_points = [sentence for sentence, score in scored_sentences[:5] if score > 0]
    if not important_points:
        important_points = sentences[:5]

    auto_qa = generate_auto_qa(keywords, important_points)

    return {
        "summary": " ".join(top_summary_sentences),
        "important_points": important_points,
        "keywords": keywords,
        "auto_qa": auto_qa
    }


def ask_ollama(prompt):
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False
            },
            timeout=120
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "").strip()
    except Exception:
        return ""


def clean_json_text(text):
    text = text.strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def generate_summary_and_notes_llm(transcript):
    prompt = f"""
You are a helpful study assistant.

Read the transcript and return ONLY valid JSON in this exact format:

{{
  "summary": "short easy summary",
  "important_points": ["point 1", "point 2", "point 3", "point 4", "point 5"],
  "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5", "keyword6"],
  "auto_qa": [
    {{"question": "question 1", "answer": "answer 1"}},
    {{"question": "question 2", "answer": "answer 2"}},
    {{"question": "question 3", "answer": "answer 3"}}
  ]
}}

Return only JSON. Do not write markdown.

Transcript:
{transcript}
"""
    raw = ask_ollama(prompt)
    if not raw:
        return generate_summary_and_notes_rule_based(transcript)

    try:
        cleaned = clean_json_text(raw)
        parsed = json.loads(cleaned)
        return {
            "summary": parsed.get("summary", "No summary generated."),
            "important_points": parsed.get("important_points", []),
            "keywords": parsed.get("keywords", []),
            "auto_qa": parsed.get("auto_qa", [])
        }
    except Exception:
        return generate_summary_and_notes_rule_based(transcript)


def eval_math_expr(expr):
    def _eval(node):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("Invalid constant")

        if isinstance(node, ast.Num):
            return node.n

        if isinstance(node, ast.BinOp):
            left = _eval(node.left)
            right = _eval(node.right)
            op_type = type(node.op)
            if op_type in SAFE_OPERATORS:
                return SAFE_OPERATORS[op_type](left, right)
            raise ValueError("Unsupported operator")

        if isinstance(node, ast.UnaryOp):
            operand = _eval(node.operand)
            op_type = type(node.op)
            if op_type in SAFE_OPERATORS:
                return SAFE_OPERATORS[op_type](operand)
            raise ValueError("Unsupported unary operator")

        raise ValueError("Invalid expression")

    parsed = ast.parse(expr, mode="eval")
    return _eval(parsed.body)


def solve_math_question(question):
    clean = question.lower().replace("?", "").replace("=", "").strip()
    clean = clean.replace("plus", "+")
    clean = clean.replace("minus", "-")
    clean = clean.replace("into", "*")
    clean = clean.replace("times", "*")
    clean = clean.replace("multiplied by", "*")
    clean = clean.replace("divided by", "/")
    clean = clean.replace("mod", "%")

    clean = re.sub(r"[^0-9\+\-\*\/\%\.\(\)\s]", "", clean)

    if not clean or not re.search(r"\d", clean):
        return None

    try:
        result = eval_math_expr(clean)
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        return f"The answer is {result}."
    except Exception:
        return None


def answer_from_transcript_advanced(transcript, question, threshold=0.15):
    sentences = split_sentences(transcript)
    if not sentences:
        return None

    try:
        corpus = sentences + [question]
        vectorizer = TfidfVectorizer(stop_words="english")
        tfidf_matrix = vectorizer.fit_transform(corpus)

        question_vector = tfidf_matrix[-1]
        sentence_vectors = tfidf_matrix[:-1]

        similarities = cosine_similarity(question_vector, sentence_vectors).flatten()

        if len(similarities) == 0:
            return None

        best_index = similarities.argmax()
        best_score = similarities[best_index]

        if best_score < threshold:
            return None

        top_indices = similarities.argsort()[::-1][:3]
        top_sentences = [sentences[i] for i in top_indices if similarities[i] >= threshold]

        if not top_sentences:
            return None

        return " ".join(top_sentences)
    except Exception:
        return None


def answer_question_hybrid(transcript, question):
    math_answer = solve_math_question(question)
    if math_answer:
        return {
            "answer": math_answer,
            "source": "math_solver",
            "in_transcript": False
        }

    transcript_answer = answer_from_transcript_advanced(transcript, question)
    if transcript_answer:
        return {
            "answer": transcript_answer,
            "source": "transcript",
            "in_transcript": True
        }

    prompt = f"""
You are a helpful tutor.

Answer the user's question simply and clearly.
If the answer is not present in the transcript, you may still answer using general knowledge.

Transcript:
{transcript}

Question:
{question}

Return only the answer text.
"""
    llm_answer = ask_ollama(prompt)
    if llm_answer:
        return {
            "answer": llm_answer,
            "source": "ollama",
            "in_transcript": False
        }

    return {
        "answer": "The answer is not available in the transcript, and no fallback answer could be generated.",
        "source": "none",
        "in_transcript": False
    }


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "success",
        "message": "Backend is running"
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

        notes_data = generate_summary_and_notes_llm(transcript)

        return jsonify({
            "status": "success",
            "message": "Audio downloaded, transcribed, and Ollama AI notes generated successfully",
            "youtube_link": youtube_link,
            "video_id": video_id,
            "audio_file": audio_file_path,
            "transcript": transcript,
            "summary": notes_data["summary"],
            "important_points": notes_data["important_points"],
            "keywords": notes_data["keywords"],
            "auto_qa": notes_data["auto_qa"],
            "ai_mode": "ollama llama3.1:8b"
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "error": f"Server error: {str(e)}"
        }), 500


@app.route("/api/ask", methods=["POST"])
def ask_question():
    try:
        data = request.get_json(silent=True)

        if not data:
            return jsonify({"error": "No JSON data received"}), 400

        transcript = str(data.get("transcript", "")).strip()
        question = str(data.get("question", "")).strip()

        if not transcript:
            return jsonify({"error": "Transcript is required"}), 400

        if not question:
            return jsonify({"error": "Question is required"}), 400

        result = answer_question_hybrid(transcript, question)

        return jsonify({
            "status": "success",
            "answer": result["answer"],
            "source": result["source"],
            "in_transcript": result["in_transcript"]
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "error": f"Question answering failed: {str(e)}"
        }), 500


if __name__ == "__main__":
    app.run(debug=True)