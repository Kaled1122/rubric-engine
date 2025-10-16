import os
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
from PyPDF2 import PdfReader
from docx import Document

# ------------------------------------------------------------
# ✅ APP CONFIG
# ------------------------------------------------------------
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.after_request
def after_request(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response

# ------------------------------------------------------------
# ✅ HEALTH CHECK
# ------------------------------------------------------------
@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Rubric engine running ✅"}), 200

# ------------------------------------------------------------
# ✅ TEXT EXTRACTION
# ------------------------------------------------------------
def extract_text(file):
    name = file.filename.lower()
    if name.endswith(".pdf"):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            file.save(tmp.name)
            reader = PdfReader(tmp.name)
            text = "\n".join([p.extract_text() or "" for p in reader.pages])
        os.unlink(tmp.name)
        return text.strip()
    elif name.endswith(".docx"):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            file.save(tmp.name)
            doc = Document(tmp.name)
            text = "\n".join([p.text for p in doc.paragraphs])
        os.unlink(tmp.name)
        return text.strip()
    elif name.endswith((".txt", ".md")):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            file.save(tmp.name)
            with open(tmp.name, "r", encoding="utf8", errors="ignore") as f:
                text = f.read()
        os.unlink(tmp.name)
        return text.strip()
    else:
        raise ValueError("Unsupported file type (.pdf, .docx, .txt only).")

# ------------------------------------------------------------
# ✅ SINGLE ENDPOINT FOR ALL
# ------------------------------------------------------------
@app.route("/generate", methods=["POST"])
def generate():
    try:
        stream = request.form.get("stream", "SEL").upper()
        title = request.form.get("lessonTitle", "Untitled Lesson")

        # Either file or text
        if "lessonFile" in request.files and request.files["lessonFile"].filename:
            text = extract_text(request.files["lessonFile"])
        else:
            text = request.form.get("lessonText", "")

        if not text.strip():
            return jsonify({"error": "No lesson content provided."}), 400

        system_prompt = """
You are an expert instructional designer in a bilingual military academy.
There are two streams:
1. SEL — School of English Language: focuses on English comprehension.
2. AW — Academic Wing: focuses on technical/academic English.

Generate a rubric with four fixed domains:
- Understanding
- Application
- Communication
- Behavior

Each domain must include:
- A measurable criterion
- Performance levels (4, 3, 2, 1)

Add 2 comprehension questions (multiple-choice, one correct answer).
Return only valid JSON:
{"lesson": "...", "stream": "...", "rubric": [...], "questions": [...]}
"""

        user_prompt = f"Stream: {stream}\nLesson: {title}\n\n{text}"

        res = client.chat.completions.create(
            model="gpt-5",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        return jsonify({"result": res.choices[0].message.content.strip()})

    except Exception as e:
        print("❌ Generation error:", e)
        return jsonify({"error": str(e)}), 500

# ------------------------------------------------------------
# ✅ RUN SERVER
# ------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
