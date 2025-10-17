import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
from PyPDF2 import PdfReader
from docx import Document

# ------------------------------------------------------------
# APP SETUP
# ------------------------------------------------------------
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ------------------------------------------------------------
# UTILITIES
# ------------------------------------------------------------
def extract_text(file):
    """Extracts text from .pdf, .docx, or .txt files."""
    name = file.filename.lower()
    if name.endswith(".pdf"):
        reader = PdfReader(file)
        return "\n".join([p.extract_text() or "" for p in reader.pages])
    elif name.endswith(".docx"):
        doc = Document(file)
        return "\n".join([p.text for p in doc.paragraphs])
    else:
        return file.read().decode("utf-8", errors="ignore")

# ------------------------------------------------------------
# MAIN ROUTE
# ------------------------------------------------------------
@app.route("/generate", methods=["POST"])
def generate():
    try:
        stream = request.form.get("stream") or request.json.get("stream") or "SEL"
        lesson_text = ""

        if "file" in request.files:
            lesson_text = extract_text(request.files["file"])
        elif request.is_json:
            lesson_text = request.json.get("lesson_text", "")
        else:
            return jsonify({"error": "No lesson provided"}), 400

        if not lesson_text.strip():
            return jsonify({"error": "Empty lesson"}), 400

        system_prompt = f"""
You are an expert instructional designer working in a bilingual military academy.
You create lesson-specific rubrics and comprehension questions for two streams:

1. SEL (School of English Language) — English comprehension, vocabulary, communication.
2. AW (Academic Wing) — technical or academic English (aviation, engineering, defense).

🎯 TASK
Analyze the lesson text and return structured JSON:

- 4 domains: Understanding, Application, Communication, Behavior.
- Each domain: criterion + 4,3,2,1 performance levels.
- Add two comprehension questions (multiple-choice with one correct answer).

📦 OUTPUT FORMAT
Return ONLY valid JSON:
{{
  "lesson": "<lesson title>",
  "stream": "{stream}",
  "rubric": [
    {{"domain": "Understanding", "criterion": "...", "4": "...", "3": "...", "2": "...", "1": "..."}},
    {{"domain": "Application", "criterion": "...", "4": "...", "3": "...", "2": "...", "1": "..."}},
    {{"domain": "Communication", "criterion": "...", "4": "...", "3": "...", "2": "...", "1": "..."}},
    {{"domain": "Behavior", "criterion": "...", "4": "...", "3": "...", "2": "...", "1": "..."}}
  ],
  "questions": [
    {{"domain": "Understanding", "stem": "...", "options": ["A","B","C","D"], "answer": "..."}},
    {{"domain": "Application", "stem": "...", "options": ["A","B","C","D"], "answer": "..."}}
  ]
}}
⚠️ Output ONLY JSON — no explanations.
        """

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.3,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": lesson_text}
            ]
        )

        output = completion.choices[0].message.content
        json.loads(output)  # validate
        return output, 200, {"Content-Type": "application/json"}

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/")
def home():
    return jsonify({"status": "✅ AI Rubric Generator (GPT-4o-mini) running!"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
