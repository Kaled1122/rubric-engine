import os, json, re, openai
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
    """Extract text from PDF, DOCX, or TXT files."""
    name = file.filename.lower()
    if name.endswith(".pdf"):
        reader = PdfReader(file)
        return "\n".join([p.extract_text() or "" for p in reader.pages])
    elif name.endswith(".docx"):
        doc = Document(file)
        return "\n".join([p.text for p in doc.paragraphs])
    else:
        return file.read().decode("utf-8", errors="ignore")


def split_lessons(text):
    """
    Split scope text into individual lessons (1–4 only).
    """
    lessons = re.split(r"\bLesson\s+(\d+)\b", text)
    blocks = []
    for i in range(1, len(lessons), 2):
        num = lessons[i]
        content = lessons[i + 1]
        if num.isdigit() and int(num) <= 4:
            cleaned = " ".join(content.strip().split())
            blocks.append({"lesson_number": int(num), "content": cleaned})
    return blocks


# ------------------------------------------------------------
# MAIN ROUTE
# ------------------------------------------------------------
@app.route("/generate", methods=["POST"])
def generate():
    try:
        stream = request.form.get("stream") or "SEL"

        # Validate upload
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        raw_text = extract_text(request.files["file"])
        if not raw_text.strip():
            return jsonify({"error": "Empty or unreadable file"}), 400

        lessons = split_lessons(raw_text)
        if not lessons:
            return jsonify({"error": "No valid lessons (1–4) found"}), 400

        results = []

        # --------------------------------------------------------
        # PROCESS EACH LESSON
        # --------------------------------------------------------
        for lesson in lessons:
            lesson_num = lesson["lesson_number"]
            lesson_text = lesson["content"][:4000]  # limit tokens

            system_prompt = f"""
You are an expert instructional designer working with the American Language Course (ALC).

Create a *quantitative performance rubric and task matrix* for:
Book Scope Lesson {lesson_num}

Base your output on the provided lesson text.

-----------------------------------------------------------
🎯 OBJECTIVE
Produce a measurable rubric and scoring system that converts qualitative domains
(Understanding, Application, Communication, Behavior)
into quantifiable points and tasks.

-----------------------------------------------------------
🧱 OUTPUT FORMAT
Return ONLY valid JSON, exactly in this structure:
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
- JSON only; no markdown, commentary, or prose.
- Use lesson content to infer grammar and skills.
- Total points = 55; weights = 100%.
- One complete object per lesson.
"""

            # --------------------------------------------------------
            # OPENAI CALL
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

            result = json.loads(response.choices[0].message.content)
            results.append(result)

        # --------------------------------------------------------
        # COMBINED OUTPUT
        # --------------------------------------------------------
        return jsonify({
            "book_scope": "Processed successfully",
            "stream": stream,
            "lessons": results
        })

    except Exception as e:
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
