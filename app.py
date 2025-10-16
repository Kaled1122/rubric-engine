import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
import tempfile

# ------------------------------------------------------------
# APP CONFIG
# ------------------------------------------------------------
app = Flask(__name__)
CORS(app)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MEMORY_FILE = "previous_rubric.json"

# ------------------------------------------------------------
# MAIN ROUTE
# ------------------------------------------------------------
@app.route("/generate", methods=["POST"])
def generate_rubric():
    try:
        # ----------- 1. Read input -----------
        stream = request.form.get("stream", "SEL")
        lesson_title = request.form.get("lessonTitle", "Untitled Lesson")

        if stream not in ["SEL", "AW"]:
            stream = "SEL"

        lesson_text = ""
        if "lessonFile" in request.files:
            f = request.files["lessonFile"]
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                f.save(tmp.name)
                with open(tmp.name, "r", encoding="utf8", errors="ignore") as file_data:
                    lesson_text = file_data.read()
                os.unlink(tmp.name)
        elif request.form.get("lessonText"):
            lesson_text = request.form.get("lessonText")
        else:
            return jsonify({"error": "No lesson content provided."}), 400

        # ----------- 2. Prepare messages -----------
        system_prompt = f"""
You are an expert instructional designer at a bilingual military training academy.
There are only two curriculum streams:

1. SEL (School of English Language) — English instruction (e.g., comprehension, vocabulary, grammar)
2. AW (Academic Wing) — technical or academic English (e.g., avionics, maintenance, procedures)

Generate a lesson-specific rubric and comprehension questions that fit the given stream.
Use the **universal 4-domain framework**:

1. Understanding
2. Application
3. Communication
4. Behavior

✅ Numeric scale (always fixed):
4 = Consistently accurate / independent
3 = Usually accurate / minor help
2 = Partial / needs support
1 = Inaccurate / dependent

Rules:
- Adapt descriptors to SEL or AW context.
- Use measurable, observable language (no "good"/"bad").
- Output only valid JSON in this format:

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
1. Create criteria for the four domains (Understanding, Application, Communication, Behavior).
2. Adapt wording to match the stream (SEL = English, AW = Technical).
3. Include one comprehension/performance question for each criterion.
4. Follow the numeric scale and JSON schema exactly.
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # Optional: previous context memory
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "r", encoding="utf8") as f:
                prev = f.read()
            messages.insert(1, {"role": "assistant", "content": prev})

        # ----------- 3. Call GPT-5 -----------
        completion = client.chat.completions.create(
            model="gpt-5",
            temperature=0.3,
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
# MAIN ENTRY POINT
# ------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))
