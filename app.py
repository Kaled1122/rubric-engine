import os, json, openai
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from PyPDF2 import PdfReader
from docx import Document

# ------------------------------------------------------------
# APP SETUP
# ------------------------------------------------------------
app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)
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
# ROUTES
# ------------------------------------------------------------
@app.route("/")
def serve_index():
    return send_from_directory(".", "index.html")


@app.route("/generate", methods=["POST"])
def generate():
    try:
        stream = request.form.get("stream") or "SEL"
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        lesson_text = extract_text(request.files["file"])
        if not lesson_text.strip():
            return jsonify({"error": "Empty lesson text"}), 400

        # --------------------------------------------------------
        # 🧠 FULL PROMPT
        # --------------------------------------------------------
        system_prompt = f"""
You are an expert instructional designer working in a bilingual military academy.

There are two training streams:
1. **SEL (School of English Language)** — focuses on English comprehension, vocabulary, and communication.
2. **AW (Academic Wing)** — focuses on technical and academic English (aviation, engineering, defense topics).

Analyze the following lesson and build a structured **assessment rubric** and **sample comprehension questions**.

🎯 **Your tasks**
1. Identify key learning outcomes in the lesson.
2. For each of four fixed domains, describe measurable criteria and four performance levels (4–1).
3. Generate two comprehension questions (multiple-choice, one correct answer) aligned with the lesson content.

🧱 **Fixed Domains**
- Understanding → How well the learner comprehends lesson ideas and key information.
- Application → How well the learner uses or applies knowledge from the lesson.
- Communication → Clarity, accuracy, and appropriateness in English communication.
- Behavior → Attitude, cooperation, discipline, and engagement in the learning process.

🧩 **Performance Levels (4–1)**
Use short, measurable descriptors that match each domain’s focus.
- **4 = Excellent / Outstanding performance**
- **3 = Good / Meets expectations**
- **2 = Needs improvement**
- **1 = Unsatisfactory / Limited ability**

🧮 **Comprehension Questions**
- Each question should test either understanding or application.
- Use simple, context-relevant stems and four options (A–D).
- Provide the correct answer letter and text.

🧾 **Output Format**
Return ONLY valid JSON in this exact structure:
{{
  "lesson": "Lesson title or topic (based on the text)",
  "stream": "{stream}",
  "rubric": [
    {{"domain": "Understanding", "criterion": "...", "4": "...", "3": "...", "2": "...", "1": "..." }},
    {{"domain": "Application",  "criterion": "...", "4": "...", "3": "...", "2": "...", "1": "..." }},
    {{"domain": "Communication","criterion": "...", "4": "...", "3": "...", "2": "...", "1": "..." }},
    {{"domain": "Behavior",     "criterion": "...", "4": "...", "3": "...", "2": "...", "1": "..." }}
  ],
  "questions": [
    {{"domain": "Understanding", "stem": "...", "options": ["A","B","C","D"], "answer": "A"}},
    {{"domain": "Application",  "stem": "...", "options": ["A","B","C","D"], "answer": "B"}}
  ]
}}
Do not include explanations, markdown, or text outside this JSON.
        """

        # --------------------------------------------------------
        #  CALL OPENAI
        # --------------------------------------------------------
        completion = openai.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.3,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": lesson_text}
            ],
            response_format={"type": "json_object"}
        )

        output = completion.choices[0].message.content
        return output, 200, {"Content-Type": "application/json"}

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ------------------------------------------------------------
# START
# ------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
