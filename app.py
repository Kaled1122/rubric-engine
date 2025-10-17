import os, json, re, openai
from flask import Flask, request, jsonify
from flask_cors import CORS
from PyPDF2 import PdfReader
from docx import Document

# ------------------------------------------------------------
# APP SETUP
# ------------------------------------------------------------
app = Flask(__name__)

# Allow all origins while testing (you can restrict later)
CORS(app, resources={r"/*": {"origins": "*"}})

openai.api_key = os.getenv("OPENAI_API_KEY")

# ------------------------------------------------------------
# UTILITIES
# ------------------------------------------------------------
def extract_text(file):
    """Extract readable text from PDF, DOCX, or TXT files."""
    name = file.filename.lower()
    text = ""
    try:
        if name.endswith(".pdf"):
            reader = PdfReader(file)
            text = "\n".join([p.extract_text() or "" for p in reader.pages])
        elif name.endswith(".docx"):
            doc = Document(file)
            text = "\n".join([p.text for p in doc.paragraphs])
        else:
            text = file.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"[extract_text] Error: {e}")
    return text.strip()


def split_lessons(text):
    """
    Split book scope text into Lessons 1–4.
    Handles formats like 'Lesson 1', '1 Vending machines', etc.
    """
    pattern = r"(?:Lesson\s*)?(\b[1-4]\b)[\.:–-]?\s"
    chunks = re.split(pattern, text)
    results = []

    for i in range(1, len(chunks), 2):
        num = chunks[i].strip()
        content = chunks[i + 1] if i + 1 < len(chunks) else ""
        if num.isdigit():
            clean = " ".join(content.strip().split())
            results.append({"lesson_number": int(num), "content": clean})
    return results


# ------------------------------------------------------------
# MAIN ROUTE
# ------------------------------------------------------------
@app.route("/generate", methods=["POST"])
def generate():
    try:
        stream = request.form.get("stream") or "SEL"

        # ---------- Validation ----------
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        raw_text = extract_text(request.files["file"])
        if not raw_text:
            return jsonify({
                "error": "Empty or unreadable file. Try exporting as a text-based PDF or upload .docx."
            }), 400

        lessons = split_lessons(raw_text)
        if not lessons:
            return jsonify({
                "error": "No valid lessons (1–4) found. Ensure lesson numbers like '1', '2', '3', '4' appear clearly."
            }), 400

        results = []

        # ---------- Process each lesson ----------
        for lesson in lessons:
            lesson_num = lesson["lesson_number"]
            lesson_text = lesson["content"][:4000]  # Trim for token safety

            system_prompt = f"""
You are an expert instructional designer working with the American Language Course (ALC).

Create a *quantitative performance rubric and task matrix* for:
Book Scope Lesson {lesson_num}

Use the provided lesson text to infer title, vocabulary/functions, grammar, and skills.

-----------------------------------------------------------
🎯 OBJECTIVE
Generate a measurable rubric and scoring system that quantifies:
Understanding, Application, Communication, and Behavior domains.

-----------------------------------------------------------
🧱 OUTPUT FORMAT
Return ONLY valid JSON in this schema:
{{
  "lesson_number": {lesson_num},
  "lesson_title": "Infer from lesson content",
  "rubric_overview": [
    {{
      "domain": "Understanding",
      "areas": ["Listening comprehension", "Reading comprehension"],
      "tasks": 4,
      "points_per_task": 2,
      "domain_max": 8,
      "weight": 25,
      "description": "Measures comprehension of lesson ideas and vocabulary."
    }},
    {{
      "domain": "Application",
      "areas": ["Grammar patterns from lesson"],
      "tasks": 6,
      "points_per_task": 3,
      "domain_max": 18,
      "weight": 30,
      "description": "Measures grammatical accuracy and contextual use."
    }},
    {{
      "domain": "Communication",
      "areas": ["Speaking tasks", "Writing tasks"],
      "tasks": 4,
      "points_per_task": 5,
      "domain_max": 20,
      "weight": 30,
      "description": "Measures clarity, coherence, and fluency in productive skills."
    }},
    {{
      "domain": "Behavior",
      "areas": ["Teamwork", "Participation", "Responsibility"],
      "tasks": 3,
      "points_per_task": 3,
      "domain_max": 9,
      "weight": 15,
      "description": "Measures discipline, cooperation, and engagement."
    }}
  ],
  "task_matrix": {{
    "Understanding": [
      {{"area": "Listening comprehension", "question": "..." }},
      {{"area": "Reading comprehension", "question": "..." }}
    ],
    "Application": [
      {{"area": "Grammar – how + to-infinitive", "question": "..." }},
      {{"area": "Grammar – adverbial clause", "question": "..." }}
    ],
    "Communication": [
      {{"area": "Speaking", "task": "Give oral instructions..." }},
      {{"area": "Writing", "task": "Combine two sentences..." }}
    ],
    "Behavior": [
      {{"area": "Teamwork", "observation": "Collaborates effectively" }},
      {{"area": "Responsibility", "observation": "Completes tasks on time" }}
    ]
  }},
  "scoring_system": {{
    "total_points": 55,
    "weights": {{
      "Understanding": 0.25,
      "Application": 0.30,
      "Communication": 0.30,
      "Behavior": 0.15
    }},
    "bands": [
      {{"range": "90–100", "label": "Outstanding"}},
      {{"range": "75–89", "label": "Competent"}},
      {{"range": "60–74", "label": "Developing"}},
      {{"range": "<60", "label": "Needs Support"}}
    ]
  }}
}}

-----------------------------------------------------------
🧮 RULES
- Output JSON only (no commentary or markdown).
- Total = 55 points; weights = 100%.
- Derive lesson title & grammar from text.
"""

            # ---------- OpenAI Call ----------
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.3,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": lesson_text}
                ],
                response_format={"type": "json_object"}
            )

            try:
                data = json.loads(response.choices[0].message.content)
            except Exception as parse_err:
                print(f"[Lesson {lesson_num}] Parse error: {parse_err}")
                data = {
                    "lesson_number": lesson_num,
                    "error": "Invalid JSON returned by model."
                }

            results.append(data)

        # ---------- Success Response ----------
        return jsonify({
            "book_scope": "Processed successfully",
            "stream": stream,
            "lessons": results
        })

    except Exception as e:
        print(f"[Server Error] {e}")
        return jsonify({"error": str(e)}), 500


# ------------------------------------------------------------
# HEALTH CHECK
# ------------------------------------------------------------
@app.route("/")
def home():
    return jsonify({"status": "✅ Quantitative Rubric Engine Running"})


# ------------------------------------------------------------
# ENTRY POINT
# ------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
