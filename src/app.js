const API_BASE = "http://127.0.0.1:8000";

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


const loginModal = document.querySelector("#loginModal");
const registerModal = document.querySelector("#registerModal");
const closeModalButtons = document.querySelectorAll("[data-modal-close]");
const loginForm = document.querySelector("#loginForm");
const registerForm = document.querySelector("#registerForm");
const loginBtn = document.querySelector("#loginBtn");
const registerBtn = document.querySelector("#registerBtn");
const logoutBtn = document.querySelector("#logoutBtn");
const authGuest = document.querySelector("#authGuest");
const authUser = document.querySelector("#authUser");
const userAvatar = document.querySelector("#userAvatar");
const userDisplayName = document.querySelector("#userDisplayName");
const userEmail = document.querySelector("#userEmail");
const loginError = document.querySelector("#loginError");
const registerError = document.querySelector("#registerError");

const state = {
  lastResult: null,
  currentFile: null,
  history: [],
  token: localStorage.getItem("neuroscan-token") || null,
  user: null,
  sessionId: localStorage.getItem("neuroscan-session") || crypto.randomUUID(),
};


if (!localStorage.getItem("neuroscan-session")) {
  localStorage.setItem("neuroscan-session", state.sessionId);
}

const classes = [
  ["glioma", "glioma"],
  ["meningioma", "meningioma"],
  ["pituitary", "pituitary"],
  ["healthy", "no_tumor"],
];




function authHeaders() {
  const headers = {};
  if (state.token) {
    headers["Authorization"] = `Bearer ${state.token}`;
  }
  return headers;
}

function updateAuthUI() {
  if (state.user) {
    authGuest.hidden = true;
    authUser.hidden = false;
    const name = state.user.full_name || state.user.email.split("@")[0];
    userDisplayName.textContent = name;
    userEmail.textContent = state.user.email;
    userAvatar.textContent = name.charAt(0).toUpperCase();
  } else {
    authGuest.hidden = false;
    authUser.hidden = true;
  }
}

async function fetchCurrentUser() {
  if (!state.token) {
    state.user = null;
    updateAuthUI();
    return;
  }
  try {
    const res = await fetch(`${API_BASE}/auth/me`, { headers: authHeaders() });
    if (res.ok) {
      state.user = await res.json();
    } else {
      state.token = null;
      state.user = null;
      localStorage.removeItem("neuroscan-token");
    }
  } catch {
  }
  updateAuthUI();
}

function openLoginModal() {
  loginModal.hidden = false;
  registerModal.hidden = true;
  loginError.hidden = true;
  registerError.hidden = true;
}

function openRegisterModal() {
  registerModal.hidden = false;
  loginModal.hidden = true;
  loginError.hidden = true;
  registerError.hidden = true;
}

function closeModal() {
  loginModal.hidden = true;
  registerModal.hidden = true;
  loginForm.reset();
  registerForm.reset();
  loginError.hidden = true;
  registerError.hidden = true;
}

loginBtn.addEventListener("click", openLoginModal);
registerBtn.addEventListener("click", openRegisterModal);
closeModalButtons.forEach((btn) => {
  btn.addEventListener("click", closeModal);
});

loginModal.addEventListener("click", (e) => {
  if (e.target === loginModal) closeModal();
});
registerModal.addEventListener("click", (e) => {
  if (e.target === registerModal) closeModal();
});

loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  loginError.hidden = true;
  const email = document.querySelector("#loginEmail").value;
  const password = document.querySelector("#loginPassword").value;

  try {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const data = await res.json();
      loginError.textContent = data.detail || t("login_error");
      loginError.hidden = false;
      return;
    }
    const data = await res.json();
    state.token = data.access_token;
    localStorage.setItem("neuroscan-token", state.token);
    await fetchCurrentUser();
    if (state.user && state.user.role === "admin") {
      window.location.href = "/admin.html";
      return;
    }
    closeModal();
    loadHistoryFromServer();
  } catch (err) {
    loginError.textContent = t("connection_error");
    loginError.hidden = false;
  }
});

registerForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  registerError.hidden = true;
  const full_name = document.querySelector("#registerName").value || null;
  const email = document.querySelector("#registerEmail").value;
  const password = document.querySelector("#registerPassword").value;

  try {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, full_name }),
    });
    if (!res.ok) {
      const data = await res.json();
      registerError.textContent = data.detail || t("register_error");
      registerError.hidden = false;
      return;
    }
    const data = await res.json();
    state.token = data.access_token;
    localStorage.setItem("neuroscan-token", state.token);
    await fetchCurrentUser();
    if (state.user && state.user.role === "admin") {
      window.location.href = "/admin.html";
      return;
    }
    closeModal();
    loadHistoryFromServer();
  } catch (err) {
    registerError.textContent = t("connection_error");
    registerError.hidden = false;
  }
});

logoutBtn.addEventListener("click", () => {
  state.token = null;
  state.user = null;
  localStorage.removeItem("neuroscan-token");
  updateAuthUI();
  loadHistoryFromServer();
});

window.appLogout = function () {
  state.token = null;
  state.user = null;
  localStorage.removeItem("neuroscan-token");
  try { updateAuthUI(); } catch (e) {}
  try { loadHistoryFromServer(); } catch (e) {}
  window.location.href = "/";
};




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
  scanCtx.fillText(t("mri_image"), 260, 248);
  scanCtx.font = "16px Arial";
  scanCtx.fillText(t("upload_file_for_analysis"), 260, 278);
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
  resultSource.textContent = `${t("source")}: ${source}`;
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
      fileName.removeAttribute("data-i18n");
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
    glioma: "glioma",
    meningioma: "meningioma",
    pituitary: "pituitary",
    notumor: "no_tumor",
    no_tumor: "no_tumor",
    "No tumor": "no_tumor",
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
    id: payload.id || null,
    label: labelMap[payload.label] || payload.label,
    risk: payload.risk,
    probabilities,
    source: payload.model || "backend",
    gradcam: payload.gradcam || null,
  };
}

async function predictWithBackend(features) {
  const formData = new FormData();
  const file = state.currentFile || (await canvasToFile());
  formData.append("file", file);

  const params = new URLSearchParams({ gradcam: "true" });
  if (features) {
    params.set("features", JSON.stringify(features));
  }
  if (!state.token) {
    params.set("session_id", state.sessionId);
  }

  const url = `${API_BASE}/predict?${params}`;
  const response = await fetch(url, {
    method: "POST",
    headers: authHeaders(),
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

function diagnosisKey(label) {
  const map = {
    glioma: "glioma",
    meningioma: "meningioma",
    pituitary: "pituitary",
    healthy: "no_tumor",
    notumor: "no_tumor",
    no_tumor: "no_tumor",
    "No tumor": "no_tumor",
  };
  return map[label] || label;
}

function translateDiagnosis(label) {
  const key = diagnosisKey(label);
  return ["glioma", "meningioma", "pituitary", "no_tumor"].includes(key) ? t(key) : label;
}

function updateDiagnosisLabels() {
  document.querySelectorAll("[data-diagnosis-label]").forEach((element) => {
    element.textContent = translateDiagnosis(element.dataset.diagnosisLabel);
  });
  if (state.lastResult) {
    updateResults(state.lastResult, state.lastResult.features);
  }
  renderHistory();
}

function updateResults(result, features) {
  document.querySelector("#diagnosisLabel").textContent = translateDiagnosis(result.label);
  document.querySelector("#riskValue").textContent = percentage(result.risk);
  document.querySelector("#riskBar").style.width = percentage(result.risk);

  updateResultSource(result.source || t("unknown_source"));

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
    alert(t("upload_mri_image"));
    return;
  }

  const features = extractFeatures();
  let result;

  try {
    result = await predictWithBackend(features);
  } catch (error) {
    console.error(error);
    alert(t("analysis_failed"));
    return;
  }

  state.lastResult = {
    ...result,
    features,
    file: fileName.textContent,
    date: new Date().toLocaleString(getLocale()),
  };

  updateResults(result, features);
  if (result.gradcam && result.source && result.source !== "browser-demo") {
    drawGradcamBase64(result.gradcam);
  } else {
    drawHeatmap(features);
  }


  loadHistoryFromServer();
}




async function loadHistoryFromServer() {
  try {
    const params = new URLSearchParams({ per_page: "10" });
    const res = await fetch(`${API_BASE}/history?${params}`, {
      headers: authHeaders(),
    });
    if (res.ok) {
      const data = await res.json();
      state.history = data.items.map((item) => ({
        id: item.id,
        label: item.predicted_label,
        risk: item.risk_score,
        file: item.file_name,
        date: new Date(item.created_at).toLocaleString(getLocale()),
        createdAt: item.created_at,
        probabilities: item.probabilities,
        features: item.image_features || {},
        notes: item.notes,
      }));
      renderHistory();
      return;
    }
  } catch {

  }

  state.history = JSON.parse(localStorage.getItem("neuroscan-history") || "[]");
  renderHistory();
}

function renderHistory() {
  historyList.innerHTML = "";
  if (state.history.length === 0) {
    historyList.innerHTML = `<p class="empty-history">${t("no_history")}</p>`;
    return;
  }
  state.history.forEach((entry) => {
    const item = document.createElement("article");
    item.className = "history-item";

    const infoDiv = document.createElement("div");
    const titleEl = document.createElement("strong");
    titleEl.textContent = translateDiagnosis(entry.label);
    const metaEl = document.createElement("span");
    const localizedDate = entry.createdAt ? new Date(entry.createdAt).toLocaleString(getLocale()) : entry.date;
    metaEl.textContent = `${entry.file} · ${localizedDate}`;
    infoDiv.appendChild(titleEl);
    infoDiv.appendChild(metaEl);

    const riskDiv = document.createElement("div");
    riskDiv.className = "history-risk";
    riskDiv.textContent = percentage(entry.risk);

    item.appendChild(infoDiv);
    item.appendChild(riskDiv);

    if (state.token) {
      const editBtn = document.createElement("button");
      editBtn.className = "text-button edit-scan";
      editBtn.type = "button";
      editBtn.title = t("edit_scan_name");
      editBtn.textContent = "✎";
      editBtn.style.marginLeft = "8px";
      infoDiv.appendChild(editBtn);

      editBtn.addEventListener("click", () => {
        const form = document.createElement("div");
        form.className = "rename-form";
        const input = document.createElement("input");
        input.className = "rename-input";
        const orig = entry.file || "";
        const lastDot = orig.lastIndexOf('.');
        let base = orig;
        let ext = '';
        if (lastDot > 0) {
          base = orig.slice(0, lastDot);
          ext = orig.slice(lastDot);
        }
        input.value = base;
        const extSpan = document.createElement('span');
        extSpan.className = 'rename-ext';
        extSpan.textContent = ext;

        const actions = document.createElement('div');
        actions.className = 'rename-actions';
        const saveBtn = document.createElement("button");
        saveBtn.className = "btn-small btn-save";
        saveBtn.textContent = t("save");
        const cancelBtn = document.createElement("button");
        cancelBtn.className = "btn-small btn-cancel";
        cancelBtn.textContent = t("cancel");

        editBtn.hidden = true;
        infoDiv.replaceChild(form, metaEl);
        form.appendChild(input);
        form.appendChild(extSpan);
        actions.appendChild(saveBtn);
        actions.appendChild(cancelBtn);
        form.appendChild(actions);

        cancelBtn.addEventListener("click", () => {
          form.remove();
          infoDiv.appendChild(metaEl);
          editBtn.hidden = false;
        });

        saveBtn.addEventListener("click", async () => {
          const newBase = input.value.trim();
          if (!newBase) {
            alert(t("empty_name"));
            return;
          }
          const newName = newBase + ext;
          saveBtn.disabled = true;
          try {
            const res = await fetch(`${API_BASE}/history/${entry.id}/rename`, {
              method: "PATCH",
              headers: { ...(authHeaders()), "Content-Type": "application/json" },
              body: JSON.stringify({ file_name: newName }),
            });
            if (!res.ok) {
              const err = await res.json().catch(() => ({}));
              alert(err.detail || t("rename_failed"));
              saveBtn.disabled = false;
              return;
            }
            entry.file = newName;
            renderHistory();
          } catch (e) {
            alert(t("connection_error"));
            saveBtn.disabled = false;
          }
        });
      });
    }

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
          throw new Error(t("history_file_error"));
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
    reader.onerror = () => reject(new Error(t("file_read_error")));
    reader.readAsText(file, "UTF-8");
  });
}

async function exportReport() {
  if (!state.lastResult) {
    await analyze();
  }

  const result = state.lastResult;
  const report = [
    t("report_title"),
    `${t("report_date")}: ${result.date}`,
    `${t("report_file")}: ${result.file}`,
    `${t("report_predicted_class")}: ${translateDiagnosis(result.label)}`,
    `${t("report_prediction_source")}: ${result.source}`,
    `${t("report_pathology_risk")}: ${percentage(result.risk)}`,
    "",
    `${t("report_class_probabilities")}:`,
    `${t("glioma")}: ${percentage(result.probabilities.glioma)}`,
    `${t("meningioma")}: ${percentage(result.probabilities.meningioma)}`,
    `${t("pituitary")}: ${percentage(result.probabilities.pituitary)}`,
    `${t("no_tumor")}: ${percentage(result.probabilities.healthy)}`,
    "",
    `${t("report_image_features")}:`,
    `${t("contrast")}: ${percentage(result.features.contrast)}`,
    `${t("asymmetry")}: ${percentage(result.features.asymmetry)}`,
    `${t("bright_area")}: ${percentage(result.features.hotspot)}`,
    "",
    t("report_note"),
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
    alert(t("history_imported"));
  } catch (error) {
    alert(formatI18n("history_import_failed", { message: error.message }));
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
fetchCurrentUser();
loadHistoryFromServer();

window.addEventListener("languagechange", () => {
  if (!state.currentFile) {
    drawEmptyState();
  }
  if (state.lastResult) {
    updateResultSource(state.lastResult.source || t("unknown_source"));
  }
  updateDiagnosisLabels();
});
