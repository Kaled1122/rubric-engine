import os
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
from PyPDF2 import PdfReader
from docx import Document

app = Flask(__name__)
# Allow any origin and all HTTP methods
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ----- Preflight (Safari / Chrome) -----
@app.after_request
def after_request(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response

# ----- Health check -----
@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Rubric engine running ✅"}), 200


# ----- Text extraction -----
def extract_text(uploaded):
    name = uploaded.filename.lower()
    if name.endswith(".pdf"):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            uploaded.save(tmp.name)
            text = "\n".join([p.extract_text() or "" for p in PdfReader(tmp.name).pages])
        os.unlink(tmp.name)
        return text.strip()
    if name.endswith(".docx"):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            uploaded.save(tmp.name)
            doc = Document(tmp.name)
            text = "\n".join([p.text for p in doc.paragraphs])
        os.unlink(tmp.name)
        return text.strip()
    if name.endswith((".txt", ".md")):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            uploaded.save(tmp.name)
            with open(tmp.name, "r", encoding="utf8", errors="ignore") as f:
                text = f.read()
        os.unlink(tmp.name)
        return text.strip()
    raise ValueError("Unsupported file type (.pdf, .docx, .txt only).")


# ----- Upload -----
@app.route("/upload", methods=["POST"])
def upload():
    try:
        if "lessonFile" not in request.files:
            return jsonify({"error": "No file uploaded"}), 400
        f = request.files["lessonFile"]
        text = extract_text(f)
        return jsonify({"message": f"✅ {f.filename} uploaded", "chars": len(text)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ----- Generate rubric -----
@app.route("/generate", methods=["POST"])
def generate():
    try:
        stream = request.form.get("stream", "SEL").upper()
        title = request.form.get("lessonTitle", "Untitled Lesson")

        if "lessonFile" in request.files and request.files["lessonFile"].filename:
            text = extract_text(request.files["lessonFile"])
        else:
            text = request.form.get("lessonText", "")
        if not text.strip():
            return jsonify({"error": "No lesson content provided"}), 400

        system_prompt = """You are an instructional designer in a bilingual military academy.
Two streams:
1. SEL — School of English Language (English comprehension)
2. AW — Academic Wing (technical/academic English)

Create a 4-domain rubric (Understanding, Application, Communication, Behavior)
with levels 4–1 and 2 sample comprehension questions.
Return only valid JSON:
{"lesson": "...", "stream": "...", "rubric": [...], "questions": [...]}"""

        user_prompt = f"Stream: {stream}\nLesson: {title}\n\n{text}"

        res = client.chat.completions.create(
            model="gpt-5",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return jsonify({"result": res.choices[0].message.content.strip()})
    except Exception as e:
        print("❌ Error:", e)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
