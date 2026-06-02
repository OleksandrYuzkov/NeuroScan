const scanCanvas = document.querySelector("#scanCanvas");
const heatmapCanvas = document.querySelector("#heatmapCanvas");
const scanCtx = scanCanvas.getContext("2d", { willReadFrequently: true });
const heatmapCtx = heatmapCanvas.getContext("2d");

const imageInput = document.querySelector("#imageInput");
const analyzeButton = document.querySelector("#analyzeButton");
const reportButton = document.querySelector("#reportButton");
const exportHistoryButton = document.querySelector("#exportHistoryButton");
const importHistoryButton = document.querySelector("#importHistoryButton");
const importHistoryInput = document.querySelector("#importHistoryInput");
const clearHistoryButton = document.querySelector("#clearHistoryButton");
const historyList = document.querySelector("#historyList");
const fileName = document.querySelector("#fileName");
const resultSource = document.querySelector("#resultSource");
const navLinks = document.querySelectorAll(".nav a");

const state = {
  lastResult: null,
  currentFile: null,
  history: JSON.parse(localStorage.getItem("neuroscan-history") || "[]"),
};

const classes = [
  ["glioma", "Glioma"],
  ["meningioma", "Meningioma"],
  ["pituitary", "Pituitary"],
  ["healthy", "No tumor"],
];

function drawEmptyState() {
  scanCtx.fillStyle = "#0c1117";
  scanCtx.fillRect(0, 0, scanCanvas.width, scanCanvas.height);
  scanCtx.fillStyle = "#2a3644";
  scanCtx.beginPath();
  scanCtx.arc(260, 260, 170, 0, Math.PI * 2);
  scanCtx.fill();
  scanCtx.fillStyle = "#101820";
  scanCtx.beginPath();
  scanCtx.arc(260, 260, 130, 0, Math.PI * 2);
  scanCtx.fill();
  scanCtx.fillStyle = "#cbd5e1";
  scanCtx.font = "700 22px Arial";
  scanCtx.textAlign = "center";
  scanCtx.fillText("МРТ-зображення", 260, 248);
  scanCtx.font = "16px Arial";
  scanCtx.fillText("завантажте файл для аналізу", 260, 278);
  heatmapCtx.clearRect(0, 0, heatmapCanvas.width, heatmapCanvas.height);
  heatmapCtx.fillStyle = "#0c1117";
  heatmapCtx.fillRect(0, 0, heatmapCanvas.width, heatmapCanvas.height);
}

function updateActiveNav() {
  const currentHash = window.location.hash || "#diagnostics";
  navLinks.forEach((link) => {
    link.classList.toggle("active", link.getAttribute("href") === currentHash);
  });
}

function updateResultSource(source) {
  if (!resultSource) return;
  resultSource.textContent = `Джерело: ${source}`;
}

function setupNavigation() {
  navLinks.forEach((link) => {
    link.addEventListener("click", () => {
      navLinks.forEach((item) => item.classList.remove("active"));
      link.classList.add("active");
    });
  });
  window.addEventListener("hashchange", updateActiveNav);
  updateActiveNav();
}

function clearHeatmap() {
  heatmapCtx.drawImage(scanCanvas, 0, 0, heatmapCanvas.width, heatmapCanvas.height);
  heatmapCtx.fillStyle = "rgba(12, 17, 23, 0.48)";
  heatmapCtx.fillRect(0, 0, heatmapCanvas.width, heatmapCanvas.height);
}

function loadImage(file) {
  const reader = new FileReader();
  reader.onload = () => {
    const img = new Image();
    img.onload = () => {
      scanCtx.fillStyle = "#090e13";
      scanCtx.fillRect(0, 0, scanCanvas.width, scanCanvas.height);
      const scale = Math.min(scanCanvas.width / img.width, scanCanvas.height / img.height);
      const drawWidth = img.width * scale;
      const drawHeight = img.height * scale;
      const x = (scanCanvas.width - drawWidth) / 2;
      const y = (scanCanvas.height - drawHeight) / 2;
      scanCtx.drawImage(img, x, y, drawWidth, drawHeight);
      state.imageRect = { x, y, w: drawWidth, h: drawHeight };
      state.lastResult = null;
      state.currentFile = file;
      fileName.textContent = file.name;
      clearHeatmap();
    };
    img.src = reader.result;
  };
  reader.readAsDataURL(file);
}

function extractFeatures() {
  const { width, height } = scanCanvas;
  const data = scanCtx.getImageData(0, 0, width, height).data;
  const pixels = [];
  let sum = 0;
  let bright = 0;
  let left = 0;
  let right = 0;
  let leftCount = 0;
  let rightCount = 0;

  for (let y = 0; y < height; y += 2) {
    for (let x = 0; x < width; x += 2) {
      const index = (y * width + x) * 4;
      const intensity = (data[index] + data[index + 1] + data[index + 2]) / 3;
      pixels.push(intensity);
      sum += intensity;
      if (intensity > 172) bright += 1;
      if (x < width / 2) {
        left += intensity;
        leftCount += 1;
      } else {
        right += intensity;
        rightCount += 1;
      }
    }
  }

  const mean = sum / pixels.length;
  const variance = pixels.reduce((acc, value) => acc + (value - mean) ** 2, 0) / pixels.length;
  const contrast = Math.min(1, Math.sqrt(variance) / 82);
  const asymmetry = Math.min(1, Math.abs(left / leftCount - right / rightCount) / 32);
  const hotspot = Math.min(1, bright / pixels.length / 0.18);

  return { contrast, asymmetry, hotspot };
}

async function canvasToFile() {
  return new Promise((resolve) => {
    scanCanvas.toBlob((blob) => {
      resolve(new File([blob], "demo_mri_brain_tumor.png", { type: "image/png" }));
    }, "image/png");
  });
}

function normalizeBackendResult(payload) {
  const labelMap = {
    glioma: "Glioma",
    meningioma: "Meningioma",
    pituitary: "Pituitary",
    notumor: "No tumor",
    no_tumor: "No tumor",
    "No tumor": "No tumor",
  };
  const probabilities = {
    glioma: payload.probabilities.glioma || 0,
    meningioma: payload.probabilities.meningioma || 0,
    pituitary: payload.probabilities.pituitary || 0,
    healthy:
      payload.probabilities.no_tumor ||
      payload.probabilities.notumor ||
      payload.probabilities["No tumor"] ||
      0,
  };

  return {
    label: labelMap[payload.label] || payload.label,
    risk: payload.risk,
    probabilities,
    source: payload.model || "backend",
    gradcam: payload.gradcam || null,
  };
}

async function predictWithBackend() {
  const formData = new FormData();
  const file = state.currentFile || (await canvasToFile());
  formData.append("file", file);

  const url = "http://127.0.0.1:8000/predict?gradcam=true";
  const response = await fetch(url, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Backend prediction failed: ${response.status}`);
  }

  return normalizeBackendResult(await response.json());
}

function drawGradcamBase64(b64png) {
  if (!b64png) return;
  const img = new Image();
  img.crossOrigin = "anonymous";
  img.onload = () => {
    heatmapCtx.clearRect(0, 0, heatmapCanvas.width, heatmapCanvas.height);
    heatmapCtx.drawImage(scanCanvas, 0, 0, heatmapCanvas.width, heatmapCanvas.height);

    const w = heatmapCanvas.width;
    const h = heatmapCanvas.height;
    const oc = document.createElement("canvas");
    oc.width = w; oc.height = h;
    const ocCtx = oc.getContext("2d");
    const rect = state.imageRect || { x: 0, y: 0, w: w, h: h };
    ocCtx.drawImage(img, rect.x, rect.y, rect.w, rect.h);
    const imgData = ocCtx.getImageData(0, 0, w, h);
    const data = imgData.data;

    for (let i = 0; i < data.length; i += 4) {
      const v = data[i];
      const t = v / 255;
      const r = Math.max(0, Math.min(1, 1.5 - Math.abs(4 * t - 3)));
      const g = Math.max(0, Math.min(1, 1.5 - Math.abs(4 * t - 2)));
      const b = Math.max(0, Math.min(1, 1.5 - Math.abs(4 * t - 1)));
      data[i] = Math.round(r * 255);
      data[i + 1] = Math.round(g * 255);
      data[i + 2] = Math.round(b * 255);
      data[i + 3] = Math.round(Math.min(1, t) * 255 * 0.7);
    }

    ocCtx.putImageData(imgData, 0, 0);
    heatmapCtx.drawImage(oc, 0, 0, w, h);
  };
  img.src = `data:image/png;base64,${b64png}`;
}

function clamp(value) {
  return Math.max(0, Math.min(1, value));
}

function percentage(value) {
  return `${Math.round(value * 100)}%`;
}

function updateResults(result, features) {
  document.querySelector("#diagnosisLabel").textContent = result.label;
  document.querySelector("#riskValue").textContent = percentage(result.risk);
  document.querySelector("#riskBar").style.width = percentage(result.risk);

  updateResultSource(result.source || "невідоме джерело");

  classes.forEach(([key]) => {
    document.querySelector(`#${key}Value`).textContent = percentage(result.probabilities[key]);
    document.querySelector(`#${key}Bar`).style.width = percentage(result.probabilities[key]);
  });

  document.querySelector("#contrastMetric").textContent = percentage(features.contrast);
  document.querySelector("#asymmetryMetric").textContent = percentage(features.asymmetry);
  document.querySelector("#hotspotMetric").textContent = percentage(features.hotspot);
}

function drawHeatmap(features) {
  heatmapCtx.drawImage(scanCanvas, 0, 0, heatmapCanvas.width, heatmapCanvas.height);
  heatmapCtx.fillStyle = "rgba(12, 17, 23, 0.34)";
  heatmapCtx.fillRect(0, 0, heatmapCanvas.width, heatmapCanvas.height);

  const x = 260 + (features.asymmetry > 0.18 ? 76 : 12);
  const y = 250 - features.hotspot * 54;
  const radius = 64 + features.hotspot * 80;
  const gradient = heatmapCtx.createRadialGradient(x, y, 10, x, y, radius);
  gradient.addColorStop(0, "rgba(255, 76, 66, 0.86)");
  gradient.addColorStop(0.42, "rgba(255, 181, 69, 0.48)");
  gradient.addColorStop(1, "rgba(15, 118, 110, 0)");
  heatmapCtx.fillStyle = gradient;
  heatmapCtx.beginPath();
  heatmapCtx.arc(x, y, radius, 0, Math.PI * 2);
  heatmapCtx.fill();
}

async function analyze() {
  if (!state.currentFile) {
    alert("Завантажте МРТ-зображення перед аналізом.");
    return;
  }

  const features = extractFeatures();
  let result;

  try {
    result = await predictWithBackend();
  } catch (error) {
    console.error(error);
    alert("Не вдалося виконати аналіз. Перевірте, чи бекенд запущено та доступний.");
    return;
  }

  state.lastResult = {
    ...result,
    features,
    file: fileName.textContent,
    date: new Date().toLocaleString("uk-UA"),
  };

  updateResults(result, features);
  if (result.gradcam && result.source && result.source !== "browser-demo") {
    drawGradcamBase64(result.gradcam);
  } else {
    drawHeatmap(features);
  }
  addToHistory(state.lastResult);
}

function addToHistory(entry) {
  state.history = [entry, ...state.history].slice(0, 6);
  localStorage.setItem("neuroscan-history", JSON.stringify(state.history));
  renderHistory();
}

function renderHistory() {
  historyList.innerHTML = "";
  if (state.history.length === 0) {
    historyList.innerHTML = '<p class="empty-history">Поки що немає виконаних аналізів.</p>';
    return;
  }

  state.history.forEach((entry) => {
    const item = document.createElement("article");
    item.className = "history-item";
    item.innerHTML = `
      <div>
        <strong>${entry.label}</strong>
        <span>${entry.file} · ${entry.date}</span>
      </div>
      <div class="history-risk">${percentage(entry.risk)}</div>
    `;
    historyList.appendChild(item);
  });
}

async function exportHistory() {
  const json = JSON.stringify(state.history, null, 2);
  const blob = new Blob([json], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "neuroscan-history.json";
  link.click();
  URL.revokeObjectURL(url);
}

function importHistoryFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const content = JSON.parse(reader.result);
        if (!Array.isArray(content)) {
          throw new Error("Файл має містити масив об'єктів історії.");
        }
        const valid = content.filter((item) => item && item.date && item.file && item.label);
        state.history = valid.slice(0, 6);
        localStorage.setItem("neuroscan-history", JSON.stringify(state.history));
        renderHistory();
        resolve();
      } catch (error) {
        reject(error);
      }
    };
    reader.onerror = () => reject(new Error("Не вдалося прочитати файл."));
    reader.readAsText(file, "UTF-8");
  });
}

async function exportReport() {
  if (!state.lastResult) {
    await analyze();
  }

  const result = state.lastResult;
  const report = [
    "NeuroScan AI - висновок аналізу МРТ",
    `Дата: ${result.date}`,
    `Файл: ${result.file}`,
    `Попередній клас: ${result.label}`,
    `Джерело прогнозу: ${result.source}`,
    `Ризик патології: ${percentage(result.risk)}`,
    "",
    "Ймовірності класів:",
    `Glioma: ${percentage(result.probabilities.glioma)}`,
    `Meningioma: ${percentage(result.probabilities.meningioma)}`,
    `Pituitary: ${percentage(result.probabilities.pituitary)}`,
    `No tumor: ${percentage(result.probabilities.healthy)}`,
    "",
    "Ознаки зображення:",
    `Контрастність: ${percentage(result.features.contrast)}`,
    `Асиметрія: ${percentage(result.features.asymmetry)}`,
    `Яскрава зона: ${percentage(result.features.hotspot)}`,
    "",
    "Примітка: результат є навчальним прототипом і не замінює медичний висновок лікаря.",
  ].join("\n");

  const blob = new Blob([report], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "neuroscan-ai-report.txt";
  link.click();
  URL.revokeObjectURL(url);
}

imageInput.addEventListener("change", (event) => {
  const [file] = event.target.files;
  if (file) loadImage(file);
});

analyzeButton.addEventListener("click", analyze);
reportButton.addEventListener("click", exportReport);
exportHistoryButton.addEventListener("click", exportHistory);
importHistoryButton.addEventListener("click", () => importHistoryInput.click());
importHistoryInput.addEventListener("change", async (event) => {
  const [file] = event.target.files;
  if (!file) return;
  try {
    await importHistoryFile(file);
    alert("Історію імпортовано успішно.");
  } catch (error) {
    alert(`Не вдалося імпортувати історію: ${error.message}`);
  } finally {
    importHistoryInput.value = "";
  }
});
clearHistoryButton.addEventListener("click", () => {
  state.history = [];
  localStorage.removeItem("neuroscan-history");
  renderHistory();
});

setupNavigation();
drawEmptyState();
renderHistory();
