import os, json
import psycopg2
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from PyPDF2 import PdfReader
from docx import Document
from openai import OpenAI

app = Flask(__name__)
CORS(app)

# -----------------------------
# CONFIG
# -----------------------------
DATABASE_URL = os.getenv("DATABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

def db():
    return psycopg2.connect(DATABASE_URL)

# -----------------------------
# DATABASE INIT
# -----------------------------
def init_db():
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS rubrics (
            id SERIAL PRIMARY KEY,
            lesson_title TEXT,
            domain TEXT,
            question TEXT,
            points INT
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            id SERIAL PRIMARY KEY,
            learner_id TEXT,
            lesson_title TEXT,
            domain TEXT,
            question TEXT,
            score FLOAT,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("✅ Database initialized")

# -----------------------------
# UTILITIES
# -----------------------------
def extract_text(file):
    name = file.filename.lower()
    if name.endswith(".pdf"):
        reader = PdfReader(file)
        return "\n".join([p.extract_text() or "" for p in reader.pages])
    elif name.endswith(".docx"):
        doc = Document(file)
        return "\n".join([p.text for p in doc.paragraphs])
    return file.read().decode("utf-8", errors="ignore")

# -----------------------------
# ROUTES
# -----------------------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/generate_rubric", methods=["POST"])
def generate_rubric():
    try:
        file = request.files["file"]
        text = extract_text(file)[:4000]
        system_prompt = """
        You are an expert instructional designer.
        Generate a quantitative rubric JSON for the uploaded lesson.
        Include four domains (Understanding, Application, Communication, Behavior)
        each with several questions and point allocations (total = 55).
        """

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.4,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            response_format={"type": "json_object"}
        )

        rubric = json.loads(response.choices[0].message.content)

        # Save to DB
        conn = db()
        cur = conn.cursor()
        for d in rubric["domains"]:
            for q in d["questions"]:
                cur.execute("""
                    INSERT INTO rubrics (lesson_title, domain, question, points)
                    VALUES (%s, %s, %s, %s);
                """, (rubric["lesson_title"], d["name"], q["text"], q["points"]))
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"message": "✅ Rubric generated & saved", "rubric": rubric})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/update_score", methods=["POST"])
def update_score():
    try:
        data = request.get_json()
        conn = db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO scores (learner_id, lesson_title, domain, question, score)
            VALUES (%s, %s, %s, %s, %s);
        """, (
            data["learner_id"],
            data["lesson_title"],
            data["domain"],
            data["question"],
            data["score"]
        ))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "✅ Score saved"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/get_scores")
def get_scores():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM scores;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(rows)

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
