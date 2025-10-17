import os, json, openai
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from PyPDF2 import PdfReader
from docx import Document

# --- App setup ---
app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)
openai.api_key = os.getenv("OPENAI_API_KEY")

# --- Helpers ---
def extract_text(file):
    name = file.filename.lower()
    if name.endswith(".pdf"):
        reader = PdfReader(file)
        return "\n".join([p.extract_text() or "" for p in reader.pages])
    elif name.endswith(".docx"):
        doc = Document(file)
        return "\n".join([p.text for p in doc.paragraphs])
    return file.read().decode("utf-8", errors="ignore")

# --- Serve HTML/JS/CSS directly ---
@app.route("/")
def home():
    return send_from_directory(".", "index.html")

@app.route("/<path:path>")
def serve_static(path):
    return send_from_directory(".", path)

# --- API route ---
@app.route("/generate", methods=["POST"])
def generate():
    try:
        stream = request.form.get("stream") or "SEL"
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded"}), 400
        lesson_text = extract_text(request.files["file"])
        if not lesson_text.strip():
            return jsonify({"error": "Empty lesson"}), 400

        system_prompt = f"""
You are an expert instructional designer working in a bilingual military academy.

Streams:
1. SEL — English comprehension, vocabulary, communication.
2. AW — Technical/academic English (aviation, engineering, defense).

Analyze the lesson and produce JSON with:
- Four rubric domains (Understanding, Application, Communication, Behavior)
- Each domain: criterion + four measurable levels (4–1)
- Two comprehension questions (MCQ with one correct answer)

Output ONLY valid JSON:
{{
  "lesson": "Lesson title",
  "stream": "{stream}",
  "rubric": [
    {{"domain": "Understanding", "criterion": "...", "4": "...", "3": "...", "2": "...", "1": "..." }},
    {{"domain": "Application", "criterion": "...", "4": "...", "3": "...", "2": "...", "1": "..." }},
    {{"domain": "Communication", "criterion": "...", "4": "...", "3": "...", "2": "...", "1": "..." }},
    {{"domain": "Behavior", "criterion": "...", "4": "...", "3": "...", "2": "...", "1": "..." }}
  ],
  "questions": [
    {{"domain": "Understanding", "stem": "...", "options": ["A","B","C","D"], "answer": "A"}},
    {{"domain": "Application", "stem": "...", "options": ["A","B","C","D"], "answer": "B"}}
  ]
}}
        """

        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.3,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": lesson_text}
            ],
            response_format={"type": "json_object"}
        )

        return response.choices[0].message.content, 200, {"Content-Type": "application/json"}

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
