const backendURL = "https://rubric-engine.onrender.com/generate";

const status = document.getElementById("status");
const output = document.getElementById("output");
const lessonTitle = document.getElementById("lessonTitle");
const rubricContainer = document.getElementById("rubricContainer");
const questionsContainer = document.getElementById("questionsContainer");

document.getElementById("generateBtn").addEventListener("click", async () => {
  const file = document.getElementById("fileInput").files[0];
  const stream = document.getElementById("stream").value;
  if (!file) return (status.textContent = "⚠️ Please upload a file first.");

  const form = new FormData();
  form.append("file", file);
  form.append("stream", stream);

  status.textContent = "⏳ Generating rubric...";
  output.classList.add("hidden");

  try {
    const res = await fetch(backendURL, { method: "POST", body: form });
    if (!res.ok) throw new Error(`Server error: ${res.status}`);
    const data = await res.json();

    lessonTitle.textContent = `${data.lesson} (${data.stream})`;
    renderRubric(data.rubric);
    renderQuestions(data.questions);

    status.textContent = "✅ Generation successful!";
    output.classList.remove("hidden");
    output.scrollIntoView({ behavior: "smooth" });
  } catch (err) {
    console.error(err);
    status.textContent = "❌ " + err.message;
  }
});

function renderRubric(rubric) {
  if (!rubric || rubric.length === 0) {
    rubricContainer.innerHTML = "<p>No rubric data available.</p>";
    return;
  }

  let html = `<h3 class="rubric-title">Performance Rubric</h3>`;
  html += `<table><thead><tr>
    <th>Domain</th><th>Criterion</th><th>4</th><th>3</th><th>2</th><th>1</th>
  </tr></thead><tbody>`;

  rubric.forEach(r => {
    html += `<tr>
      <td>${r.domain}</td>
      <td>${r.criterion}</td>
      <td>${r["4"]}</td>
      <td>${r["3"]}</td>
      <td>${r["2"]}</td>
      <td>${r["1"]}</td>
    </tr>`;
  });

  html += `</tbody></table>`;
  rubricContainer.innerHTML = html;
}

function renderQuestions(questions) {
  if (!questions || questions.length === 0) {
    questionsContainer.innerHTML = "<p>No questions generated.</p>";
    return;
  }

  questionsContainer.innerHTML = questions
    .map((q, i) => `
      <div class="question-block">
        <div class="question-stem">${i + 1}. [${q.domain}] ${q.stem}</div>
        <ul class="mt-1">
          ${q.options.map(opt => `<li>${opt}</li>`).join("")}
        </ul>
        <div class="mt-2 text-green-600 text-sm">✔️ Correct answer: ${q.answer}</div>
      </div>
    `)
    .join("");
}
