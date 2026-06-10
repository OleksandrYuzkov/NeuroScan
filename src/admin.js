

const API_BASE = "http://127.0.0.1:8000";

const DIAG_COLORS = {
  glioma: "#df6b57",
  meningioma: "#d8952f",
  pituitary: "#2563eb",
  no_tumor: "#0f766e",
  notumor: "#0f766e",
};

const DIAG_LABELS = {
  glioma: "Glioma",
  meningioma: "Meningioma",
  pituitary: "Pituitary",
  no_tumor: "No tumor",
  notumor: "No tumor",
};

const state = {
  token: localStorage.getItem("neuroscan-token") || null,
  user: null,
  currentSection: "dashboard",
};




function authHeaders() {
  const h = { "Content-Type": "application/json" };
  if (state.token) h["Authorization"] = `Bearer ${state.token}`;
  return h;
}

function authHeadersRaw() {
  const h = {};
  if (state.token) h["Authorization"] = `Bearer ${state.token}`;
  return h;
}

async function checkAuth() {
  const sections = document.querySelectorAll(".admin-section");

  if (!state.token) {
    sections.forEach((s) => (s.hidden = true));
    return false;
  }

  try {
    const res = await fetch(`${API_BASE}/auth/me`, { headers: authHeadersRaw() });
    if (!res.ok) throw new Error("Unauthorized");
    state.user = await res.json();

    if (state.user.role !== "admin") {
      alert("Доступ дозволено лише адміністраторам.");
      sections.forEach((s) => (s.hidden = true));
      return false;
    }

    updateUserUI();
    return true;
  } catch {
    sections.forEach((s) => (s.hidden = true));
    return false;
  }
}

function updateUserUI() {
  if (!state.user) return;
  const name = state.user.full_name || state.user.email.split("@")[0];
  document.getElementById("userDisplayName").textContent = name;
  document.getElementById("userEmail").textContent = state.user.email;
  document.getElementById("userAvatar").textContent = name.charAt(0).toUpperCase();
}

const logoutBtnEl = document.getElementById("logoutBtn");
if (logoutBtnEl) {
  logoutBtnEl.addEventListener("click", () => {
    state.token = null;
    state.user = null;
    localStorage.removeItem("neuroscan-token");
    window.location.href = "/";
  });
}




function navigateTo(section) {
  state.currentSection = section;
  document.querySelectorAll(".admin-section").forEach((s) => {
    s.hidden = s.id !== `sec-${section}`;
  });
  document.querySelectorAll("#adminNav a").forEach((a) => {
    a.classList.toggle("active", a.dataset.section === section);
  });

  switch (section) {
    case "dashboard": loadDashboard(); break;
    case "users": loadUsers(); break;
    case "scans": loadScans(); break;
    case "audit": loadAudit(); break;
    case "model": loadModelInfo(); break;
  }
}

document.querySelectorAll("#adminNav a").forEach((a) => {
  a.addEventListener("click", (e) => {
    e.preventDefault();
    navigateTo(a.dataset.section);
  });
});




async function loadDashboard() {
  try {
    const res = await fetch(`${API_BASE}/admin/stats?days=14`, { headers: authHeadersRaw() });
    if (!res.ok) return;
    const data = await res.json();

    document.getElementById("statUsers").textContent = data.total_users;
    document.getElementById("statActive").textContent = data.active_users;
    document.getElementById("statToday").textContent = data.scans_today;
    document.getElementById("statTotal").textContent = data.total_scans;

    drawScansChart(data.scans_by_day);
    drawDiagChart(data.diagnosis_distribution);
    renderRecentScans(data.recent_scans);
  } catch (err) {
    console.error("Dashboard load error:", err);
  }
}

function drawScansChart(data) {
  const canvas = document.getElementById("scansChart");
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  const pad = { top: 20, right: 20, bottom: 40, left: 50 };
  const chartW = w - pad.left - pad.right;
  const chartH = h - pad.top - pad.bottom;

  ctx.clearRect(0, 0, w, h);

  if (!data.length) {
    ctx.fillStyle = "#65717f";
    ctx.font = "14px Arial";
    ctx.textAlign = "center";
    ctx.fillText("Немає даних", w / 2, h / 2);
    return;
  }

  const maxCount = Math.max(...data.map((d) => d.count), 1);
  const barW = Math.min(36, (chartW / data.length) * 0.7);
  const gap = (chartW - barW * data.length) / (data.length + 1);


  ctx.strokeStyle = "#e8eef5";
  ctx.lineWidth = 1;
  const ySteps = 4;
  for (let i = 0; i <= ySteps; i++) {
    const y = pad.top + (chartH / ySteps) * i;
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(w - pad.right, y);
    ctx.stroke();

    ctx.fillStyle = "#65717f";
    ctx.font = "12px Arial";
    ctx.textAlign = "right";
    ctx.fillText(Math.round(maxCount * (1 - i / ySteps)), pad.left - 8, y + 4);
  }


  data.forEach((d, i) => {
    const x = pad.left + gap + i * (barW + gap);
    const barH = (d.count / maxCount) * chartH;
    const y = pad.top + chartH - barH;


    const radius = Math.min(4, barW / 2);
    ctx.fillStyle = "#0f766e";
    ctx.beginPath();
    ctx.moveTo(x, y + radius);
    ctx.arcTo(x, y, x + radius, y, radius);
    ctx.arcTo(x + barW, y, x + barW, y + radius, radius);
    ctx.lineTo(x + barW, pad.top + chartH);
    ctx.lineTo(x, pad.top + chartH);
    ctx.closePath();
    ctx.fill();


    const dateStr = d.date.slice(5);
    ctx.fillStyle = "#65717f";
    ctx.font = "11px Arial";
    ctx.textAlign = "center";
    ctx.fillText(dateStr, x + barW / 2, h - pad.bottom + 18);
  });
}

function drawDiagChart(distribution) {
  const canvas = document.getElementById("diagChart");
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  const cx = w / 2;
  const cy = h / 2;
  const r = Math.min(cx, cy) - 20;

  ctx.clearRect(0, 0, w, h);

  const entries = Object.entries(distribution);
  const total = entries.reduce((sum, [, v]) => sum + v, 0);

  if (total === 0) {
    ctx.fillStyle = "#65717f";
    ctx.font = "14px Arial";
    ctx.textAlign = "center";
    ctx.fillText("Немає даних", cx, cy);
    return;
  }

  let startAngle = -Math.PI / 2;
  entries.forEach(([label, count]) => {
    const sliceAngle = (count / total) * Math.PI * 2;
    ctx.fillStyle = DIAG_COLORS[label] || "#94a3b8";
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, r, startAngle, startAngle + sliceAngle);
    ctx.closePath();
    ctx.fill();
    startAngle += sliceAngle;
  });


  ctx.fillStyle = "#ffffff";
  ctx.beginPath();
  ctx.arc(cx, cy, r * 0.55, 0, Math.PI * 2);
  ctx.fill();


  ctx.fillStyle = "#17202a";
  ctx.font = "800 28px Arial";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(total, cx, cy - 6);
  ctx.font = "12px Arial";
  ctx.fillStyle = "#65717f";
  ctx.fillText("аналізів", cx, cy + 16);


  const legend = document.getElementById("diagLegend");
  legend.innerHTML = "";
  entries.forEach(([label, count]) => {
    const pct = Math.round((count / total) * 100);
    legend.innerHTML += `
      <div class="diag-legend-item">
        <span class="diag-legend-dot" style="background:${DIAG_COLORS[label] || '#94a3b8'}"></span>
        ${DIAG_LABELS[label] || label} (${pct}%)
      </div>
    `;
  });
}

function renderRecentScans(scans) {
  const tbody = document.querySelector("#recentScansTable tbody");
  tbody.innerHTML = "";
  if (!scans.length) {
    tbody.innerHTML = '<tr><td colspan="4" style="color:var(--muted)">Немає даних</td></tr>';
    return;
  }
  scans.forEach((s) => {
    tbody.innerHTML += `
      <tr>
        <td>${escHtml(s.file_name)}</td>
        <td><span class="badge badge-${s.predicted_label}">${DIAG_LABELS[s.predicted_label] || s.predicted_label}</span></td>
        <td>${Math.round(s.risk_score * 100)}%</td>
        <td>${formatDate(s.created_at)}</td>
      </tr>
    `;
  });
}




let usersPage = 1;

async function loadUsers(page = 1) {
  usersPage = page;
  const search = document.getElementById("userSearch").value;
  const role = document.getElementById("userRoleFilter").value;
  const isActive = document.getElementById("userStatusFilter").value;

  const params = new URLSearchParams({ page, per_page: 15 });
  if (search) params.set("search", search);
  if (role) params.set("role", role);
  if (isActive) params.set("is_active", isActive);

  try {
    const res = await fetch(`${API_BASE}/admin/users?${params}`, { headers: authHeadersRaw() });
    if (!res.ok) return;
    const data = await res.json();

    const tbody = document.querySelector("#usersTable tbody");
    tbody.innerHTML = "";
    data.items.forEach((u) => {
      const isSelf = state.user && u.id === state.user.id;
      const actionsHtml = isSelf ? `
        <span style="color:var(--muted);font-size:12px;font-style:italic">Це ви (поточний сеанс)</span>
      ` : `
        <div class="table-actions">
          <button class="btn-small" onclick="toggleUserRole('${u.id}','${u.role}')" title="Змінити роль">${u.role === "admin" ? "→user" : "→admin"}</button>
          <button class="btn-small" onclick="toggleUserActive('${u.id}',${u.is_active})" title="${u.is_active ? "Деактивувати" : "Активувати"}">${u.is_active ? "Деакт." : "Актив."}</button>
          <button class="btn-small btn-danger" onclick="deleteUser('${u.id}')" title="Видалити">✕</button>
        </div>
      `;
      tbody.innerHTML += `
        <tr>
          <td>${escHtml(u.email)}</td>
          <td>${escHtml(u.full_name || "—")}</td>
          <td><span class="badge badge-${u.role}">${u.role}</span></td>
          <td><span class="badge badge-${u.is_active ? "active" : "inactive"}">${u.is_active ? "Активний" : "Деактивований"}</span></td>
          <td>${formatDate(u.created_at)}</td>
          <td>${u.scan_count}</td>
          <td>${actionsHtml}</td>
        </tr>
      `;
    });

    renderPagination("usersPagination", data.total, data.page, data.per_page, loadUsers);
  } catch (err) {
    console.error("Users load error:", err);
  }
}

async function toggleUserRole(userId, currentRole) {
  const newRole = currentRole === "admin" ? "user" : "admin";
  await fetch(`${API_BASE}/admin/users/${userId}`, {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify({ role: newRole }),
  });
  loadUsers(usersPage);
}

async function toggleUserActive(userId, isActive) {
  await fetch(`${API_BASE}/admin/users/${userId}`, {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify({ is_active: !isActive }),
  });
  loadUsers(usersPage);
}

async function deleteUser(userId) {
  if (!confirm("Ви впевнені, що хочете видалити цього користувача?")) return;
  await fetch(`${API_BASE}/admin/users/${userId}`, {
    method: "DELETE",
    headers: authHeadersRaw(),
  });
  loadUsers(usersPage);
}


document.getElementById("userSearch").addEventListener("input", debounce(() => loadUsers(1), 400));
document.getElementById("userRoleFilter").addEventListener("change", () => loadUsers(1));
document.getElementById("userStatusFilter").addEventListener("change", () => loadUsers(1));




let scansPage = 1;

async function loadScans(page = 1) {
  scansPage = page;
  const label = document.getElementById("scanLabelFilter").value;
  const params = new URLSearchParams({ page, per_page: 15 });
  if (label) params.set("label", label);

  try {
    const res = await fetch(`${API_BASE}/admin/scans?${params}`, { headers: authHeadersRaw() });
    if (!res.ok) return;
    const data = await res.json();

    const tbody = document.querySelector("#scansTable tbody");
    tbody.innerHTML = "";
    data.items.forEach((s) => {
      tbody.innerHTML += `
        <tr>
          <td>${escHtml(s.file_name)}</td>
          <td>${escHtml(s.user_email || s.session_id?.slice(0, 8) || "анонім")}</td>
          <td><span class="badge badge-${s.predicted_label}">${DIAG_LABELS[s.predicted_label] || s.predicted_label}</span></td>
          <td>${Math.round(s.risk_score * 100)}%</td>
          <td>${escHtml(s.model_name)}</td>
          <td>${formatDate(s.created_at)}</td>
          <td>
            <div class="table-actions">
              <button class="btn-small" onclick="viewScan('${s.id}')">Деталі</button>
              <button class="btn-small btn-danger" onclick="deleteScan('${s.id}')">✕</button>
            </div>
          </td>
        </tr>
      `;
    });

    renderPagination("scansPagination", data.total, data.page, data.per_page, loadScans);
  } catch (err) {
    console.error("Scans load error:", err);
  }
}

async function viewScan(scanId) {
  try {
    const res = await fetch(`${API_BASE}/admin/scans/${scanId}`, { headers: authHeadersRaw() });
    if (!res.ok) return;
    const s = await res.json();

    document.getElementById("scanModalTitle").textContent = `Скан: ${s.file_name}`;

    let probBars = "";
    if (s.probabilities) {
      Object.entries(s.probabilities).forEach(([label, prob]) => {
        const pct = Math.round(prob * 100);
        probBars += `
          <div class="prob-row">
            <span>${DIAG_LABELS[label] || label}</span>
            <div class="prob-bar-track">
              <div class="prob-bar-fill" style="width:${pct}%;background:${DIAG_COLORS[label] || "#94a3b8"}"></div>
            </div>
            <strong>${pct}%</strong>
          </div>
        `;
      });
    }

    let imagesHtml = "";
    if (s.images && s.images.length) {
      imagesHtml = '<div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:8px">';
      s.images.forEach((img) => {
        imagesHtml += `<img src="${API_BASE}/images/${img.storage_path}" alt="${img.image_type}" style="max-width:200px;border-radius:8px;border:1px solid var(--line)" />`;
      });
      imagesHtml += "</div>";
    }

    document.getElementById("scanModalContent").innerHTML = `
      <dl>
        <dt>Діагноз</dt><dd><span class="badge badge-${s.predicted_label}">${DIAG_LABELS[s.predicted_label] || s.predicted_label}</span></dd>
        <dt>Ризик</dt><dd>${Math.round(s.risk_score * 100)}%</dd>
        <dt>SHA256</dt><dd style="font-family:monospace;font-size:12px;word-break:break-all">${s.file_sha256}</dd>
        <dt>Модель</dt><dd>${escHtml(s.model_name)} (${escHtml(s.model_architecture || "?")})</dd>
        <dt>Glioma margin</dt><dd>${s.glioma_margin ?? "—"}</dd>
        <dt>Grad-CAM</dt><dd>${s.gradcam_generated ? "✓" : "✗"}</dd>
        <dt>Користувач</dt><dd>${escHtml(s.user_email || s.session_id || "анонім")}</dd>
        <dt>Дата</dt><dd>${formatDate(s.created_at)}</dd>
        <dt>Нотатки</dt><dd>${escHtml(s.notes || "—")}</dd>
      </dl>
      <h3 style="margin:8px 0 4px;font-size:15px">Ймовірності</h3>
      <div class="prob-bars">${probBars}</div>
      ${imagesHtml ? `<h3 style="margin:8px 0 4px;font-size:15px">Зображення</h3>${imagesHtml}` : ""}
    `;

    document.getElementById("scanModal").hidden = false;
  } catch (err) {
    console.error("Scan detail error:", err);
  }
}

async function deleteScan(scanId) {
  if (!confirm("Видалити цей скан?")) return;
  await fetch(`${API_BASE}/admin/scans/${scanId}`, {
    method: "DELETE",
    headers: authHeadersRaw(),
  });
  loadScans(scansPage);
}

document.getElementById("scanModalClose").addEventListener("click", () => {
  document.getElementById("scanModal").hidden = true;
});
document.getElementById("scanModal").addEventListener("click", (e) => {
  if (e.target.id === "scanModal") document.getElementById("scanModal").hidden = true;
});

document.getElementById("scanLabelFilter").addEventListener("change", () => loadScans(1));

let auditPage = 1;

async function loadAudit(page = 1) {
  auditPage = page;
  const action = document.getElementById("auditActionFilter").value;
  const params = new URLSearchParams({ page, per_page: 20 });
  if (action) params.set("action", action);

  try {
    const res = await fetch(`${API_BASE}/admin/audit?${params}`, { headers: authHeadersRaw() });
    if (!res.ok) return;
    const data = await res.json();

    const tbody = document.querySelector("#auditTable tbody");
    tbody.innerHTML = "";
    data.items.forEach((e) => {
      const detailsStr = e.details ? JSON.stringify(e.details).slice(0, 60) : "—";
      tbody.innerHTML += `
        <tr>
          <td>${formatDate(e.created_at)}</td>
          <td>${escHtml(e.user_email || "анонім")}</td>
          <td><span class="badge badge-user">${e.action}</span></td>
          <td>${escHtml(e.ip_address || "—")}</td>
          <td style="font-size:12px;color:var(--muted);max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escHtml(JSON.stringify(e.details || ''))}">${escHtml(detailsStr)}</td>
        </tr>
      `;
    });

    renderPagination("auditPagination", data.total, data.page, data.per_page, loadAudit);
  } catch (err) {
    console.error("Audit load error:", err);
  }
}

document.getElementById("auditActionFilter").addEventListener("change", () => loadAudit(1));

async function loadModelInfo() {
  try {
    const res = await fetch(`${API_BASE}/admin/model-info`, { headers: authHeadersRaw() });
    if (!res.ok) return;
    const data = await res.json();

    const infoEl = document.getElementById("modelGeneralInfo");
    const sizeMB = data.file_size_bytes ? (data.file_size_bytes / 1024 / 1024).toFixed(1) : "—";
    infoEl.innerHTML = `
      <dt>Модель</dt><dd>${escHtml(data.model_name)}</dd>
      <dt>Архітектура</dt><dd>${escHtml(data.architecture || "—")}</dd>
      <dt>Розмір зображення</dt><dd>${data.image_size || "—"}px</dd>
      <dt>Glioma margin</dt><dd>${data.glioma_margin}</dd>
      <dt>Розмір файлу</dt><dd>${sizeMB} MB</dd>
    `;

    const classesEl = document.getElementById("modelClasses");
    classesEl.innerHTML = "";
    (data.classes || []).forEach((cls) => {
      const color = DIAG_COLORS[cls] || "#94a3b8";
      classesEl.innerHTML += `<span class="class-chip" style="background:${color}22;color:${color}">${cls}</span>`;
    });


    const metricsEl = document.getElementById("modelMetrics");
    metricsEl.innerHTML = "";
    if (data.metrics) {
      const show = [
        ["best_accuracy", "Accuracy"],
        ["best_glioma_margin", "Glioma Margin"],
        ["best_epoch", "Best Epoch"],
        ["total_epochs", "Total Epochs"],
      ];
      show.forEach(([key, label]) => {
        if (data.metrics[key] !== undefined) {
          let val = data.metrics[key];
          if (key === "best_accuracy") val = (val * 100).toFixed(1) + "%";
          metricsEl.innerHTML += `
            <div class="metric-card">
              <dt>${label}</dt>
              <dd>${val}</dd>
            </div>
          `;
        }
      });


      if (data.metrics.classification_report) {
        const report = data.metrics.classification_report;
        Object.keys(report).forEach((cls) => {
          if (typeof report[cls] === "object" && report[cls]["f1-score"] !== undefined) {
            const f1 = (report[cls]["f1-score"] * 100).toFixed(1);
            const color = DIAG_COLORS[cls] || "var(--ink)";
            metricsEl.innerHTML += `
              <div class="metric-card">
                <dt>F1 — ${cls}</dt>
                <dd style="color:${color}">${f1}%</dd>
              </div>
            `;
          }
        });
      }
    }
  } catch (err) {
    console.error("Model info error:", err);
  }
}




function renderPagination(containerId, total, page, perPage, loadFn) {
  const container = document.getElementById(containerId);
  const totalPages = Math.ceil(total / perPage);
  container.innerHTML = "";

  if (totalPages <= 1) return;

  const prevBtn = document.createElement("button");
  prevBtn.className = "page-btn";
  prevBtn.textContent = "←";
  prevBtn.disabled = page <= 1;
  prevBtn.addEventListener("click", () => loadFn(page - 1));
  container.appendChild(prevBtn);

  const info = document.createElement("span");
  info.className = "page-info";
  info.textContent = `${page} / ${totalPages}`;
  container.appendChild(info);

  const nextBtn = document.createElement("button");
  nextBtn.className = "page-btn";
  nextBtn.textContent = "→";
  nextBtn.disabled = page >= totalPages;
  nextBtn.addEventListener("click", () => loadFn(page + 1));
  container.appendChild(nextBtn);
}

function formatDate(isoStr) {
  try {
    return new Date(isoStr).toLocaleString("uk-UA", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return isoStr;
  }
}

function escHtml(str) {
  const div = document.createElement("div");
  div.textContent = str || "";
  return div.innerHTML;
}

function debounce(fn, delay) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}




(async function init() {
  const ok = await checkAuth();
  if (ok) {
    const hash = window.location.hash.replace("#", "") || "dashboard";
    navigateTo(hash);
  }
})();
