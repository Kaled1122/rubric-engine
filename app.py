import os
import tempfile
import numpy as np
import faiss
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
FAISS_INDEX = "rubric_index.faiss"
EMBEDDING_MODEL = "text-embedding-3-small"

# ------------------------------------------------------------
# ✅ Initialize FAISS
# ------------------------------------------------------------
if os.path.exists(FAISS_INDEX):
    index = faiss.read_index(FAISS_INDEX)
else:
    index = faiss.IndexFlatL2(1536)  # dimension for text-embedding-3-small

# ------------------------------------------------------------
# ✅ Helper: Extract text from file
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

    else:
        raise ValueError("Unsupported file type. Please upload .pdf or .txt only.")

    return lesson_text.strip()

# ------------------------------------------------------------
# ✅ Helper: Store embeddings in FAISS
# ------------------------------------------------------------
def store_text_in_faiss(text, lesson_title):
    if not text.strip():
        return

    # Create embedding vector
    emb = client.embeddings.create(input=text, model=EMBEDDING_MODEL).data[0].embedding
    vector = np.array([emb], dtype="float32")

    # Add vector to FAISS index
    index.add(vector)
    faiss.write_index(index, FAISS_INDEX)

    print(f"✅ Added to FAISS index: {lesson_title} (length={len(text)} chars)")

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Rubric engine running ✅"}), 200

# ------------------------------------------------------------
# ✅ File Upload Endpoint (Frontend confirmation)
# ------------------------------------------------------------
@app.route("/upload", methods=["POST"])
def upload_file():
    try:
        if "lessonFile" not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        uploaded_file = request.files["lessonFile"]
        lesson_text = extract_text_from_file(uploaded_file)
        lesson_title = uploaded_file.filename

        # Store text in FAISS
        store_text_in_faiss(lesson_text, lesson_title)

        return jsonify({"message": f"File '{lesson_title}' uploaded successfully ✅"})

    except Exception as e:
        print("❌ Upload error:", e)
        return jsonify({"error": str(e)}), 500

# ------------------------------------------------------------
# ✅ Rubric Generation Endpoint
# ------------------------------------------------------------
@app.route("/generate", methods=["POST"])
def generate_rubric():
    try:
        stream = request.form.get("stream", "SEL").upper()
        lesson_title = request.form.get("lessonTitle", "Untitled Lesson")

        if stream not in ["SEL", "AW"]:
            stream = "SEL"

        # If file uploaded, process it
        lesson_text = ""
        if "lessonFile" in request.files and request.files["lessonFile"].filename:
            lesson_text = extract_text_from_file(request.files["lessonFile"])
            store_text_in_faiss(lesson_text, lesson_title)
        elif request.form.get("lessonText"):
            lesson_text = request.form.get("lessonText")
        else:
            return jsonify({"error": "No lesson content provided."}), 400

        # ---- PROMPT ----
        system_prompt = f"""
You are an expert instructional designer at a bilingual military training academy.

There are two streams:
1. SEL (School of English Language) — English language comprehension and vocabulary.
2. AW (Academic Wing) — technical/academic English (avionics, maintenance, procedures).

Generate a measurable rubric and comprehension questions for the provided lesson.
Use the universal 4-domain framework:
1. Understanding
2. Application
3. Communication
4. Behavior

Numeric Scale:
4 = Consistently accurate / independent
3 = Usually accurate / minor help
2 = Partial / needs support
1 = Inaccurate / dependent

Output valid JSON using this structure:
{{"lesson": "...", "stream": "...", "rubric": [...], "questions": [...]}}.
        """

        user_prompt = f"""
Stream: {stream}
Lesson title: {lesson_title}

Lesson content:
{lesson_text}

Instructions:
- Create measurable descriptors per domain.
- Match language complexity to {stream}.
- Output valid JSON only.
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "r", encoding="utf8") as f:
                prev = f.read()
            messages.insert(1, {"role": "assistant", "content": prev})

        completion = client.chat.completions.create(
            model="gpt-5",
            messages=messages
        )

        result = completion.choices[0].message.content.strip()
        with open(MEMORY_FILE, "w", encoding="utf8") as f:
            f.write(result)

        return jsonify({"result": result})

    except Exception as e:
        print("❌ Generation error:", e)
        return jsonify({"error": str(e)}), 500

# ------------------------------------------------------------
# ✅ START SERVER
# ------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
