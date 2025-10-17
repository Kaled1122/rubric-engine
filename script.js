const backendURL = "https://ai-rubric-generator.onrender.com/generate"; // change to your Render URL

document.getElementById("generateBtn").addEventListener("click", async () => {
  const fileInput = document.getElementById("fileInput");
  const stream = document.getElementById("stream").value;
  const status = document.getElementById("status");
  const results = document.getElementById("results");
  const rubricDiv = document.getElementById("rubricTable");
  const questionsDiv = document.getElementById("questionsList");

  if (!fileInput.files.length) {
    status.textContent = "⚠️ Please upload a lesson file.";
    return;
  }

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  formData.append("stream", stream);

  status.textContent = "⏳ Generating rubric... please wait.";
  results.classList.add("hidden");

  try {
    const res = await fetch(backendURL, { method: "POST", body: formData });
    if (!res.ok) throw new Error(`Server error: ${res.status}`);
    const data = await res.json();

    status.textContent = "✅ Rubric generated successfully!";
    results.classList.remove("hidden");

    // --- Build Rubric Table ---
    const table = document.createElement("table");
    table.className = "min-w-full border text-sm";
    const header = `
      <thead class="bg-gray-100">
        <tr>
          <th class="border px-3 py-2 text-left">Domain</th>
          <th class="border px-3 py-2 text-left">Criterion</th>
          <th class="border px-3 py-2 text-left">4</th>
          <th class="border px-3 py-2 text-left">3</th>
          <th class="border px-3 py-2 text-left">2</th>
          <th class="border px-3 py-2 text-left">1</th>
        </tr>
      </thead>`;
    const body = data.rubric.map(r => `
      <tr>
        <td class="border px-3 py-2 font-semibold">${r.domain}</td>
        <td class="border px-3 py-2">${r.criterion}</td>
        <td class="border px-3 py-2">${r["4"]}</td>
        <td class="border px-3 py-2">${r["3"]}</td>
        <td class="border px-3 py-2">${r["2"]}</td>
        <td class="border px-3 py-2">${r["1"]}</td>
      </tr>`).join("");
    table.innerHTML = header + "<tbody>" + body + "</tbody>";
    rubricDiv.innerHTML = "";
    rubricDiv.appendChild(table);

    // --- Build Questions ---
    questionsDiv.innerHTML = data.questions.map(q => `
      <div class="mb-4">
        <p class="font-semibold">${q.domain}:</p>
        <p>${q.stem}</p>
        <ul class="list-disc ml-5">
          ${q.options.map(o => `<li>${o}</li>`).join("")}
        </ul>
        <p class="text-green-700 font-semibold mt-1">Answer: ${q.answer}</p>
      </div>
    `).join("");

  } catch (err) {
    status.textContent = "❌ Error: " + err.message;
    console.error(err);
  }
});
