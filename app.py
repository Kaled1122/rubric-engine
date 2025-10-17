import os, json, openai
from flask import Flask, request, jsonify
from flask_cors import CORS
from PyPDF2 import PdfReader
from docx import Document

# ------------------------------------------------------------
# APP SETUP
# ------------------------------------------------------------
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "https://rubric-engine.vercel.app"}})
openai.api_key = os.getenv("OPENAI_API_KEY")

# ------------------------------------------------------------
# UTILITIES
# ------------------------------------------------------------
def extract_text(file):
    """Extract text from .pdf, .docx, or .txt files."""
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
        stream = request.form.get("stream") or "SEL"
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded"}), 400
        lesson_text = extract_text(request.files["file"])
        if not lesson_text.strip():
            return jsonify({"error": "Empty lesson"}), 400

        # --------------------------------------------------------
        # ✅ FULL EMBEDDED PROMPT (as requested, no truncation)
        # --------------------------------------------------------
        system_prompt = f"""
You are an expert instructional designer working in a bilingual military academy.

There are two training streams:
1. SEL — focuses on English comprehension, vocabulary, and communication.
2. AW — focuses on technical/academic English (aviation, engineering, defense).

Analyze the given lesson and build a structured **assessment rubric** and **sample comprehension questions**.

🎯 **Your tasks**
1. Identify key learning outcomes in the lesson.
2. For each of the four fixed domains, create a measurable criterion and four performance levels (4–1).
3. Generate **four comprehension questions**, one for each domain, each with four multiple-choice options (A–D) and one correct answer.

🧱 **Fixed Domains**
- Understanding → measures comprehension of the lesson ideas.
- Application → measures use of knowledge or skills in context.
- Communication → measures accuracy, clarity, and fluency in English.
- Behavior → measures discipline, teamwork, and classroom engagement.

🧮 **Performance Levels (4–1)**
Use short, measurable descriptors for each domain.
- 4 = Excellent / Outstanding
- 3 = Good / Meets expectations
- 2 = Needs improvement
- 1 = Unsatisfactory / Limited ability

🧾 **Output Format**
Return ONLY valid JSON in exactly this structure:
{{
  "lesson": "Lesson title or topic",
  "stream": "{stream}",
  "rubric": [
    {{"domain": "Understanding", "criterion": "...", "4": "...", "3": "...", "2": "...", "1": "..." }},
    {{"domain": "Application",  "criterion": "...", "4": "...", "3": "...", "2": "...", "1": "..." }},
    {{"domain": "Communication","criterion": "...", "4": "...", "3": "...", "2": "...", "1": "..." }},
    {{"domain": "Behavior",     "criterion": "...", "4": "...", "3": "...", "2": "...", "1": "..." }}
  ],
  "questions": [
    {{"domain": "Understanding", "stem": "...", "options": ["A","B","C","D"], "answer": "A"}},
    {{"domain": "Application",  "stem": "...", "options": ["A","B","C","D"], "answer": "B"}},
    {{"domain": "Communication","stem": "...", "options": ["A","B","C","D"], "answer": "C"}},
    {{"domain": "Behavior",     "stem": "...", "options": ["A","B","C","D"], "answer": "D"}}
  ]
}}
Do not include any text, explanation, or markdown outside this JSON.
"""

        # --------------------------------------------------------
        #  OPENAI CALL
        # --------------------------------------------------------
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


# ------------------------------------------------------------
# TEST ROUTE
# ------------------------------------------------------------
@app.route("/")
def home():
    return jsonify({"status": "✅ AI Rubric Generator Backend Running"})


# ------------------------------------------------------------
# ENTRY POINT
# ------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
