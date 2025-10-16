import os
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
from PyPDF2 import PdfReader

# ------------------------------------------------------------
# ✅ APP CONFIGURATION
# ------------------------------------------------------------
app = Flask(__name__)
CORS(app)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MEMORY_FILE = "previous_rubric.json"

# ------------------------------------------------------------
# ✅ HELPER: Extract text from uploaded file
# ------------------------------------------------------------
def extract_text_from_file(uploaded_file):
    filename = uploaded_file.filename.lower()
    lesson_text = ""

    # ---- PDF ----
    if filename.endswith(".pdf"):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            uploaded_file.save(tmp.name)
            reader = PdfReader(tmp.name)
            lesson_text = "\n".join([page.extract_text() or "" for page in reader.pages])
            os.unlink(tmp.name)

    # ---- Plain Text ----
    elif filename.endswith((".txt", ".md")):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            uploaded_file.save(tmp.name)
            with open(tmp.name, "r", encoding="utf8", errors="ignore") as f:
                lesson_text = f.read()
            os.unlink(tmp.name)

    # ---- Unsupported ----
    else:
        raise ValueError("Unsupported file type. Please upload .pdf or .txt only.")

    return lesson_text.strip()


# ------------------------------------------------------------
# ✅ MAIN ENDPOINT
# ------------------------------------------------------------
@app.route("/generate", methods=["POST"])
def generate_rubric():
    try:
        # ----------- 1. Read input -----------
        stream = request.form.get("stream", "SEL").upper()
        lesson_title = request.form.get("lessonTitle", "Untitled Lesson")

        if stream not in ["SEL", "AW"]:
            stream = "SEL"

        lesson_text = ""
        if "lessonFile" in request.files and request.files["lessonFile"].filename:
            try:
                lesson_text = extract_text_from_file(request.files["lessonFile"])
            except Exception as e:
                return jsonify({"error": str(e)}), 400
        elif request.form.get("lessonText"):
            lesson_text = request.form.get("lessonText")
        else:
            return jsonify({"error": "No lesson content provided."}), 400

        # ----------- 2. Prepare prompts -----------
        system_prompt = f"""
You are an expert instructional designer working in a bilingual military training academy.

There are only two training streams:
1. SEL (School of English Language) — focuses on English comprehension, vocabulary, and grammar.
2. AW (Academic Wing) — focuses on technical/academic English (avionics, maintenance, procedures).

Generate a measurable rubric and linked comprehension questions based on the provided lesson text.
Use the **universal 4-domain framework**:

1. Understanding
2. Application
3. Communication
4. Behavior

Numeric Scale (fixed):
4 = Consistently accurate / independent
3 = Usually accurate / minor help
2 = Partial / needs support
1 = Inaccurate / dependent

Rules:
- Adapt wording to the selected stream.
- Use observable, measurable verbs.
- Avoid generic adjectives like "good" or "bad".
- Output valid JSON using this schema:

{{
  "lesson": "Lesson title",
  "stream": "SEL | AW",
  "rubric": [
    {{ "domain": "Understanding", "criterion": "...", "4": "...", "3": "...", "2": "...", "1": "..." }},
    {{ "domain": "Application", "criterion": "...", "4": "...", "3": "...", "2": "...", "1": "..." }},
    {{ "domain": "Communication", "criterion": "...", "4": "...", "3": "...", "2": "...", "1": "..." }},
    {{ "domain": "Behavior", "criterion": "...", "4": "...", "3": "...", "2": "...", "1": "..." }}
  ],
  "questions": [
    {{ "domain": "Understanding", "stem": "...", "options": ["A","B","C","D"], "answer": "..." }},
    {{ "domain": "Application", "stem": "...", "options": ["A","B","C","D"], "answer": "..." }}
  ]
}}
        """

        user_prompt = f"""
Stream: {stream}
Lesson title: {lesson_title}

Lesson content:
{lesson_text}

Instructions:
1. Create criteria for the 4 domains (Understanding, Application, Communication, Behavior).
2. Adapt each to match the {stream} context.
3. Include one comprehension or performance question per criterion.
4. Follow the numeric scale and JSON schema exactly.
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # Optional memory continuity
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "r", encoding="utf8") as f:
                prev = f.read()
            messages.insert(1, {"role": "assistant", "content": prev})

        # ----------- 3. OpenAI call -----------
        completion = client.chat.completions.create(
            model="gpt-5",
            messages=messages
        )

        result = completion.choices[0].message.content.strip()

        # Save memory
        with open(MEMORY_FILE, "w", encoding="utf8") as f:
            f.write(result)

        return jsonify({"result": result})

    except Exception as e:
        print("❌ Error:", e)
        return jsonify({"error": str(e)}), 500


# ------------------------------------------------------------
# ✅ SERVER START
# ------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
