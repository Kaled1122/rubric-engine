import os
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
from PyPDF2 import PdfReader
from docx import Document

# ------------------------------------------------------------
# ✅ APP CONFIGURATION
# ------------------------------------------------------------
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ------------------------------------------------------------
# ✅ HEALTH CHECK
# ------------------------------------------------------------
@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Rubric engine running ✅"}), 200

# ------------------------------------------------------------
# ✅ EXTRACT TEXT FROM FILE
# ------------------------------------------------------------
def extract_text_from_file(uploaded_file):
    filename = uploaded_file.filename.lower()

    if filename.endswith(".pdf"):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            uploaded_file.save(tmp.name)
            reader = PdfReader(tmp.name)
            text = "\n".join([page.extract_text() or "" for page in reader.pages])
            os.unlink(tmp.name)
            return text.strip()

    elif filename.endswith(".docx"):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            uploaded_file.save(tmp.name)
            doc = Document(tmp.name)
            text = "\n".join([p.text for p in doc.paragraphs])
            os.unlink(tmp.name)
            return text.strip()

    elif filename.endswith((".txt", ".md")):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            uploaded_file.save(tmp.name)
            with open(tmp.name, "r", encoding="utf8", errors="ignore") as f:
                text = f.read()
            os.unlink(tmp.name)
            return text.strip()

    else:
        raise ValueError("Unsupported file type. Please upload PDF, DOCX, or TXT.")

# ------------------------------------------------------------
# ✅ UPLOAD ENDPOINT
# ------------------------------------------------------------
@app.route("/upload", methods=["POST"])
def upload_file():
    try:
        if "lessonFile" not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        uploaded_file = request.files["lessonFile"]
        text = extract_text_from_file(uploaded_file)

        return jsonify({
            "message": f"✅ File '{uploaded_file.filename}' processed successfully!",
            "text_length": len(text)
        })
    except Exception as e:
        print("❌ Upload error:", e)
        return jsonify({"error": str(e)}), 500

# ------------------------------------------------------------
# ✅ RUBRIC GENERATION ENDPOINT
# ------------------------------------------------------------
@app.route("/generate", methods=["POST"])
def generate_rubric():
    try:
        stream = request.form.get("stream", "SEL").upper()
        title = request.form.get("lessonTitle", "Untitled Lesson")

        # Lesson text
        if "lessonFile" in request.files and request.files["lessonFile"].filename:
            text = extract_text_from_file(request.files["lessonFile"])
        else:
            text = request.form.get("lessonText", "")

        if not text.strip():
            return jsonify({"error": "No lesson content provided."}), 400

        system_prompt = f"""
You are an expert instructional designer in a bilingual military academy.

Two streams:
1. SEL — School of English Language: focuses on English proficiency, vocabulary, and comprehension.
2. AW — Academic Wing: focuses on technical and academic English (e.g., avionics, maintenance, procedures).

Generate a 4-domain rubric:
1. Understanding
2. Application
3. Communication
4. Behavior

Each domain must include:
- A measurable criterion
- Performance descriptions for scores 4–1
Then add **2 sample comprehension questions** (multiple choice, with 1 correct answer).
Output **strict JSON only**:
{{"lesson": "...", "stream": "...", "rubric": [...], "questions": [...]}}.
        """

        user_prompt = f"""
Stream: {stream}
Lesson: {title}

Lesson Content:
{text}
        """

        completion = client.chat.completions.create(
            model="gpt-5",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        result = completion.choices[0].message.content.strip()
        return jsonify({"result": result})

    except Exception as e:
        print("❌ Generation error:", e)
        return jsonify({"error": str(e)}), 500

# ------------------------------------------------------------
# ✅ RUN SERVER
# ------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
