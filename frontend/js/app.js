const API = {
  async request(path, options = {}) {
    const headers = options.headers || {};
    const token = localStorage.getItem("token");
    if (token) headers["Authorization"] = "Bearer " + token;
    if (options.body && !(options.body instanceof FormData)) headers["Content-Type"] = "application/json";
    const res = await fetch("/api" + path, { ...options, headers });
    let data = null;
    try { data = await res.json(); } catch (e) { data = {}; }
    if (!res.ok) throw new Error(data.detail || data.message || "Request failed (" + res.status + ")");
    return data;
  },
  get: (p) => API.request(p),
  post: (p, b) => API.request(p, { method: "POST", body: b ? JSON.stringify(b) : undefined }),
  put: (p, b) => API.request(p, { method: "PUT", body: JSON.stringify(b) }),
  del: (p) => API.request(p, { method: "DELETE" }),
};

const state = { user: null, currentDoc: null, pollTimer: null };

const $ = (id) => document.getElementById(id);

const VIEW_TITLES = {
  dashboard: "DASHBOARD", workspace: "WORKSPACE", upload: "UPLOAD DOCUMENT",
  processing: "PROCESSING", review: "REVIEW & RISK", audit: "AUDIT HISTORY",
  account: "ACCOUNT", profile: "PROFILE", settings: "SETTINGS",
};

function toast(msg, type = "ok") {
  const wrap = $("toast-wrap");
  const el = document.createElement("div");
  el.className = "toast " + type;
  el.textContent = msg;
  wrap.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function fmtDate(s) {
  if (!s) return "—";
  return String(s).replace("T", " ").slice(0, 16);
}

/* ---------------- AUTH ---------------- */
async function login(email, password) {
  try {
    const data = await API.post("/auth/login", { email, password });
    localStorage.setItem("token", data.token);
    state.user = data.user;
    enterApp();
  } catch (err) {
    $("login-error").textContent = err.message;
  }
}

async function checkSession() {
  if (!localStorage.getItem("token")) return;
  try {
    state.user = await API.get("/auth/me");
    enterApp();
  } catch (e) { localStorage.removeItem("token"); }
}

function enterApp() {
  $("view-login").classList.add("hidden");
  $("app-shell").classList.remove("hidden");
  $("user-chip").textContent = state.user.name || state.user.email;
  showView("dashboard");
  refreshHealth();
}

function logout() {
  localStorage.removeItem("token");
  location.reload();
}

/* ---------------- NAV ---------------- */
function showView(view) {
  clearInterval(state.pollTimer);
  document.querySelectorAll(".view-panel").forEach(v => v.classList.remove("active"));
  const target = $("view-" + view);
  if (target) target.classList.add("active");
  document.querySelectorAll(".nav-item").forEach(b => {
    b.classList.toggle("active", b.dataset.view === view);
  });
  $("topbar-title").textContent = VIEW_TITLES[view] || view.toUpperCase();
  $("app-shell").classList.remove("hidden");
  $("sidebar").classList.remove("open");

  if (view === "dashboard") loadDashboard();
  if (view === "workspace") loadWorkspace();
  if (view === "processing") loadProcessing();
  if (view === "review") loadReview();
  if (view === "audit") loadAudit();
  if (view === "account") loadAccount();
  if (view === "profile") loadProfile();
  if (view === "settings") loadSettings();
}

/* ---------------- CLOCK ---------------- */
setInterval(() => {
  const c = $("clock");
  if (c) c.textContent = new Date().toLocaleTimeString("en-GB");
}, 1000);

/* ---------------- DASHBOARD ---------------- */
async function loadDashboard() {
  try {
    const d = await API.get("/dashboard");
    const k = d.kpis;
    $("kpi-grid").innerHTML = `
      <div class="kpi cyan"><div class="k-value">${k.total}</div><div class="k-label">TOTAL DOCUMENTS</div><div class="k-sub">DATABASE ONLINE</div></div>
      <div class="kpi green"><div class="k-value">${k.completed}</div><div class="k-label">COMPLETED</div><div class="k-sub">${k.completion_percent}% COMPLETION</div></div>
      <div class="kpi amber"><div class="k-value">${k.processing}</div><div class="k-label">PROCESSING</div><div class="k-sub">IN PIPELINE: ${k.queue}</div></div>
      <div class="kpi red"><div class="k-value">${k.high_risk}</div><div class="k-label">HIGH RISK</div><div class="k-sub">NEEDS ATTENTION</div></div>
    `;

    const attention = k.attention;
    $("alert-title").textContent = `${attention} high-risk flags need review`;
    $("alert-sub").textContent = "Documents flagged by AI analysis require legal review.";
    if (attention === 0) { $("alert-banner").classList.add("hidden"); }

    $("pipe-stats").innerHTML = `
      <div class="pipe-stat"><div class="p-val">${k.avg_time} min</div><div class="p-lbl">AVG. ANALYSIS TIME</div></div>
      <div class="pipe-stat"><div class="p-val">${k.queue}</div><div class="p-lbl">DOCUMENTS IN QUEUE</div></div>
      <div class="pipe-stat"><div class="p-val">${k.ai_accuracy}%</div><div class="p-lbl">AI ACCURACY</div></div>
    `;
    $("pipe-bar").innerHTML = `<div class="pipe-fill" style="width:${k.completion_percent}%"></div>`;

    const cats = d.risk_by_category || [];
    const colors = ["crit", "high", "high", "med", "med", "med", "med", "med"];
    $("risk-matrix").innerHTML = cats.length
      ? cats.map((c, i) => `
        <div class="rm-row">
          <div class="rm-label">${esc(c.category)}</div>
          <div class="rm-track"><div class="rm-fill ${colors[i] || "med"}" style="width:${Math.min(100, c.c * 22)}%"></div></div>
          <div class="rm-count">${c.c}</div>
        </div>`).join("")
      : '<div class="empty">No risk data yet — upload a document to begin</div>';

    renderRecentTable(d.recent_documents || []);
  } catch (err) { toast(err.message, "err"); }
}

function renderRecentTable(docs) {
  const t = $("recent-table");
  if (!docs.length) {
    t.innerHTML = '<tr><td class="empty">No documents yet. Upload your first legal document.</td></tr>';
    return;
  }
  t.innerHTML = `<thead><tr>
    <th>DOCUMENT</th><th>TYPE</th><th>UPLOADED BY</th><th>DATE</th><th>STATUS</th><th>RISK</th>
  </tr></thead><tbody>` + docs.map(d => `
    <tr class="row-click" onclick="openDocument(${d.id})">
      <td class="t-doc">${esc(d.original_name)}</td>
      <td>${esc(d.doc_type)}</td>
      <td>${esc(d.owner_email || "—")}</td>
      <td>${fmtDate(d.created_at)}</td>
      <td>${statusBadge(d.status)}</td>
      <td>${riskBadge(d.high_risk_count)}</td>
    </tr>`).join("") + "</tbody>";
}

function statusBadge(status) {
  const map = {
    completed: ["green", "COMPLETED"], approved: ["green", "APPROVED"], attention: ["amber", "UNDER REVIEW"],
    processing: ["cyan", "PROCESSING"], uploaded: ["dim", "UPLOADED"], escalated: ["amber", "ESCALATED"],
    rejected: ["red", "REJECTED"], failed: ["red", "FAILED"],
  };
  const [cls, label] = map[status] || ["dim", (status || "?").toUpperCase()];
  return `<span class="badge ${cls}">${label}</span>`;
}

function riskBadge(n) {
  if (!n) return `<span class="badge green">LOW</span>`;
  if (n >= 3) return `<span class="badge red">HIGH (${n})</span>`;
  if (n >= 1) return `<span class="badge amber">MEDIUM (${n})</span>`;
  return `<span class="badge green">LOW</span>`;
}

/* ---------------- WORKSPACE ---------------- */
async function loadWorkspace() {
  try {
    const docs = await API.get("/documents");
    $("ws-count").textContent = docs.length + " RECORDS";
    renderWorkspace(docs);
  } catch (err) { toast(err.message, "err"); }
}

function renderWorkspace(docs) {
  const t = $("workspace-table");
  if (!docs.length) {
    t.innerHTML = '<tr><td class="empty">No documents found.</td></tr>';
    return;
  }
  t.innerHTML = `<thead><tr>
    <th>DOCUMENT</th><th>TYPE</th><th>UPLOADED BY</th><th>DATE</th><th>STATUS</th><th>RISK</th><th></th>
  </tr></thead><tbody>` + docs.map(d => `
    <tr>
      <td class="t-doc" onclick="openDocument(${d.id})">${esc(d.original_name)}</td>
      <td>${esc(d.doc_type)}</td>
      <td>${esc(d.owner_email || "—")}</td>
      <td>${fmtDate(d.created_at)}</td>
      <td>${statusBadge(d.status)}</td>
      <td>${riskBadge(d.high_risk_count)}</td>
      <td>
        <button class="btn btn-sm" onclick="openDocument(${d.id})">OPEN</button>
        <button class="btn btn-sm" onclick="deleteDocument(${d.id})">✕</button>
      </td>
    </tr>`).join("") + "</tbody>";
}

$("filter-search").addEventListener("input", applyWorkspaceFilters);
$("filter-status").addEventListener("change", applyWorkspaceFilters);
$("filter-risk").addEventListener("change", applyWorkspaceFilters);

async function applyWorkspaceFilters() {
  try {
    let docs = await API.get("/documents");
    const q = $("filter-search").value.toLowerCase();
    const st = $("filter-status").value;
    const rk = $("filter-risk").value;
    if (q) docs = docs.filter(d => (d.original_name + " " + d.doc_type + " " + (d.owner_email || "")).toLowerCase().includes(q));
    if (st !== "All") docs = docs.filter(d => statusFilter(d.status) === st);
    if (rk !== "All") docs = docs.filter(d => (rk === "High" ? d.high_risk_count > 0 : d.high_risk_count === 0));
    renderWorkspace(docs);
  } catch (err) { toast(err.message, "err"); }
}

function statusFilter(s) {
  if (s === "completed" || s === "approved") return "Completed";
  if (s === "processing" || s === "uploaded") return "Processing";
  return "Under Review";
}

function openDocument(id) {
  state.currentDoc = id;
  showView("review");
}

async function deleteDocument(id) {
  if (!confirm("Delete this document and its analysis?")) return;
  try { await API.del("/documents/" + id); toast("Document deleted"); loadWorkspace(); }
  catch (err) { toast(err.message, "err"); }
}

/* ---------------- UPLOAD ---------------- */
const dz = $("dropzone"), fileInput = $("file-input");
dz.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => setFile(fileInput.files[0]));
["dragover", "dragenter"].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.add("drag"); }));
["dragleave", "drop"].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.remove("drag"); }));
dz.addEventListener("drop", e => setFile(e.dataTransfer.files[0]));

function setFile(f) {
  if (!f) return;
  $("dz-file").textContent = "◉ " + f.name + "  (" + (f.size / 1024).toFixed(1) + " KB)";
  state.uploadFile = f;
}

$("upload-btn").addEventListener("click", async () => {
  const f = state.uploadFile;
  if (!f) { toast("Select a document first", "err"); return; }
  const fd = new FormData();
  fd.append("file", f);
  fd.append("doc_type", $("up-doc-type").value);
  fd.append("business_unit", $("up-bu").value);
  fd.append("counterparty", $("up-party").value);
  fd.append("jurisdiction", $("up-jur").value);
  fd.append("confidentiality", $("up-conf").value);
  fd.append("review_priority", $("up-prio").value);
  $("upload-status").textContent = "Transmitting...";
  try {
    const res = await API.request("/documents/upload", { method: "POST", body: fd });
    $("upload-status").textContent = "Uploaded. Starting AI processing pipeline...";
    toast("Document uploaded — starting AI analysis");
    await API.post(`/documents/${res.id}/process`);
    setTimeout(() => { state.currentDoc = res.id; showView("processing"); }, 800);
  } catch (err) { $("upload-status").textContent = "ERROR: " + err.message; toast(err.message, "err"); }
});

/* ---------------- PROCESSING ---------------- */
async function loadProcessing() {
  try {
    const docs = await API.get("/documents");
    const queue = docs.filter(d => d.status === "processing" || d.status === "uploaded");
    const done = docs.filter(d => d.status !== "processing" && d.status !== "uploaded");
    const renderCards = (arr, title) => arr.length
      ? `<div class="panel-head"><span>${title}</span></div><div class="proc-queue">` +
        arr.map(d => `
          <div class="proc-card ${state.currentDoc === d.id ? "selected" : ""}" onclick="openProcessing(${d.id})">
            <div class="pc-name">${esc(d.original_name)}</div>
            <div>${statusBadge(d.status)}</div>
            <div class="clause-meta" style="margin-top:8px">Progress: ${d.progress}% · Stage: ${esc(d.stage || "—")}</div>
            <div class="pipe-bar" style="margin-top:8px"><div class="pipe-fill" style="width:${d.progress}%"></div></div>
          </div>`).join("") + "</div>"
      : `<div class="panel-head"><span>${title}</span></div><div class="empty">None</div>`;

    $("proc-queue").innerHTML = renderCards(queue, "ACTIVE JOBS") + renderCards(done, "ARCHIVED JOBS");
    $("proc-tag").textContent = queue.length ? queue.length + " ACTIVE" : "IDLE";
    if (state.currentDoc && (state.currentDocDoc !== state.currentDoc)) {
      state.currentDocDoc = state.currentDoc;
      loadProcDetail(state.currentDoc);
    } else if (!state.currentDoc && queue.length) {
      openProcessing(queue[0].id);
    } else if (!queue.length) {
      $("proc-detail").innerHTML = '<div class="empty">No active processing jobs.</div>';
    }
  } catch (err) { toast(err.message, "err"); }
}

function openProcessing(id) {
  state.currentDoc = id;
  loadProcDetail(id);
}

async function loadProcDetail(id) {
  try {
    const s = await API.get(`/documents/${id}/status`);
    const stages = s.stages || [];
    const order = ["ocr", "parsing", "clause_extraction", "rag_retrieval", "legal_reasoning", "risk_flagging", "summarization", "review"];
    const byName = {};
    stages.forEach(st => byName[st.stage] = st);
    const labels = {
      ocr: "OCR & TEXT EXTRACTION", parsing: "DOCUMENT PARSING", clause_extraction: "CLAUSE EXTRACTION",
      rag_retrieval: "RAG RETRIEVAL", legal_reasoning: "LEGAL REASONING", risk_flagging: "RISK FLAGGING",
      summarization: "SUMMARIZATION", review: "HUMAN REVIEW",
    };
    $("proc-detail").innerHTML = `
      <div class="panel-head"><span>${esc(s.id ? "JOB #" + s.id : "JOB")} · ${s.status.toUpperCase()}</span>
        <span class="panel-tag">${s.progress || 0}%</span></div>
      <div class="stage-list">` + order.map(st => {
        const row = byName[st];
        const cls = row ? (row.status === "done" ? "done" : row.status === "failed" ? "failed" : "running") : "pending";
        const detail = row && row.detail ? `<div class="stage-detail">${esc(row.detail)}</div>` : "";
        return `<div class="stage-row ${cls}"><span class="stage-dot ${cls}"></span>
          <span class="stage-name">${labels[st] || st.toUpperCase()}</span></div>${detail}`;
      }).join("") + `</div>
      ${s.status === "processing" || s.status === "uploaded"
        ? `<div style="margin-top:16px"><button class="btn btn-primary" onclick="loadProcDetail(${s.id})">REFRESH</button></div>`
        : `<div style="margin-top:16px;display:flex;gap:10px;flex-wrap:wrap">
            <button class="btn btn-green" onclick="openDocument(${s.id})">REVIEW RESULT</button>
          </div>`}
    `;
    if (s.status === "processing" || s.status === "uploaded") {
      clearInterval(state.pollTimer);
      state.pollTimer = setInterval(() => loadProcDetail(id), 3000);
    }
  } catch (err) { toast(err.message, "err"); }
}

/* ---------------- REVIEW & RISK ---------------- */
async function loadReview() {
  try {
    const docs = await API.get("/documents");
    const analyzed = docs.filter(d => d.status !== "uploaded" && d.status !== "failed");
    if (!analyzed.length) {
      $("review-doc-select").innerHTML = '<div class="empty">No analyzed documents yet. Upload and process a document first.</div>';
      return;
    }
    const sel = state.currentDoc && docs.find(d => d.id === state.currentDoc) ? state.currentDoc : analyzed[0].id;
    state.currentDoc = sel;
    const current = docs.find(d => d.id === sel);
    $("review-doc-select").innerHTML = `
      <div class="panel-head"><span>SELECT DOCUMENT</span></div>
      <div class="filters">
        <select id="review-select" class="input">` + analyzed.map(d =>
          `<option value="${d.id}" ${d.id === sel ? "selected" : ""}>${esc(d.original_name)}</option>`).join("") + `</select>
        <div style="display:flex;gap:8px;align-items:center">
          ${statusBadge(current.status)}
          <button class="btn btn-sm" onclick="reprocess(${sel})">⟳ REPROCESS</button>
        </div>
      </div>
    `;
    $("review-select").addEventListener("change", e => { state.currentDoc = +e.target.value; loadReviewDetail(); });
    loadReviewDetail();
  } catch (err) { toast(err.message, "err"); }
}

async function reprocess(id) {
  try { await API.post(`/documents/${id}/process`); toast("Reprocessing started"); showView("processing"); }
  catch (err) { toast(err.message, "err"); }
}

async function loadReviewDetail() {
  const id = state.currentDoc;
  $("review-summary").classList.remove("hidden");
  $("review-clauses").classList.remove("hidden");
  $("review-risks").classList.remove("hidden");
  try {
    const [summary, clauses, risks] = await Promise.all([
      API.get(`/documents/${id}/summary`),
      API.get(`/documents/${id}/clauses`),
      API.get(`/documents/${id}/risks`),
    ]);
    $("sum-approval").textContent = (summary.approval_status || "PENDING").toUpperCase();
    $("sum-content").textContent = summary.content || "Summary not generated yet.";

    $("review-actions").innerHTML = `
      <button class="btn btn-green" onclick="reviewAction('approve')">✓ APPROVE</button>
      <button class="btn btn-primary" onclick="editSummary()">✎ EDIT SUMMARY</button>
      <button class="btn btn-alert" onclick="reviewAction('escalate')">▲ ESCALATE</button>
      <button class="btn" onclick="reviewAction('reject')">✕ REJECT</button>
      <button class="btn" onclick="reviewAction('comment', prompt('Add review comment:'))">◉ COMMENT</button>
    `;

    $("clause-list").innerHTML = clauses.length ? clauses.map(c => `
      <div class="clause-card">
        <div class="clause-head">
          <span class="clause-title">▸ ${esc(c.label || c.clause_type)}</span>
          <span class="clause-meta">PAGE ${c.page || "—"} · CONF ${(c.confidence * 100).toFixed(0)}%</span>
          ${c.section ? `<span class="badge dim">${esc(c.section)}</span>` : ""}
        </div>
        <div class="clause-body">${esc(c.clause_text || "")}</div>
      </div>`).join("")
      : '<div class="empty">No clauses extracted.</div>';

    $("risk-list").innerHTML = risks.length ? risks.map(r => `
      <div class="risk-card ${(r.severity || "low").toLowerCase()}">
        <div class="risk-head">
          <span class="badge ${sevClass(r.severity)}">${esc(r.severity)}</span>
          <span class="risk-cat">${esc(r.category)}</span>
          <span class="clause-meta">CONF ${(r.confidence * 100).toFixed(0)}% · ${esc(r.status || "open")}</span>
        </div>
        <div class="risk-rationale">${esc(r.rationale)}</div>
        <div class="risk-evidence">EVIDENCE: ${esc(r.evidence)}</div>
        <div class="risk-rec">→ ${esc(r.recommendation)}</div>
        ${r.reviewer_note ? `<div class="risk-rationale" style="color:var(--amber)">REVIEWER: ${esc(r.reviewer_note)}</div>` : ""}
        <div class="risk-actions">
          <button class="btn btn-sm btn-green" onclick="riskAction(${r.id},'accepted')">ACCEPT</button>
          <button class="btn btn-sm" onclick="riskAction(${r.id},'escalated')">ESCALATE</button>
          <button class="btn btn-sm" onclick="riskAction(${r.id},'rejected')">REJECT</button>
        </div>
      </div>`).join("")
      : '<div class="empty">No risk flags detected for this document.</div>';
  } catch (err) { toast(err.message, "err"); }
}

function sevClass(s) {
  const map = { Critical: "red", High: "amber", Medium: "cyan", Low: "green" };
  return map[s] || "dim";
}

async function reviewAction(action, note) {
  try {
    await API.post(`/documents/${state.currentDoc}/review`, { action, note, risk_id: null });
    toast("Review action recorded: " + action.toUpperCase());
    loadReviewDetail();
  } catch (err) { toast(err.message, "err"); }
}

async function riskAction(id, action) {
  try {
    await API.post(`/documents/${state.currentDoc}/review`, { action: "comment", risk_id: id, note: action });
    toast("Risk flag marked: " + action.toUpperCase());
    loadReviewDetail();
  } catch (err) { toast(err.message, "err"); }
}

async function editSummary() {
  const content = prompt("Edit AI summary (pre-approval edit):", $("sum-content").textContent);
  if (!content) return;
  try {
    await API.post(`/documents/${state.currentDoc}/review`, { action: "edit", edited_summary: content });
    toast("Summary edited — version saved");
    loadReviewDetail();
  } catch (err) { toast(err.message, "err"); }
}

/* ---------------- AUDIT ---------------- */
async function loadAudit() {
  try {
    const logs = await API.get("/audit");
    const t = $("audit-table");
    t.innerHTML = `<thead><tr>
      <th>TIME</th><th>ACTOR</th><th>ACTION</th><th>DOC ID</th><th>DETAIL</th>
    </tr></thead><tbody>` + logs.map(l => `
      <tr>
        <td>${fmtDate(l.created_at)}</td>
        <td>${esc(l.actor)}</td>
        <td>${esc(l.action)}</td>
        <td>${l.document_id || "—"}</td>
        <td style="color:var(--dim)">${esc(l.detail || "—")}</td>
      </tr>`).join("") + "</tbody>";
  } catch (err) { toast(err.message, "err"); }
}

/* ---------------- ACCOUNT ---------------- */
async function loadAccount() {
  try {
    const user = state.user || (await API.get("/auth/me"));
    const health = await API.get("/health");
    $("account-info").innerHTML = `
      <div class="kv-row"><span class="kv-key">OPERATOR</span><span class="kv-val">${esc(user.name || "—")}</span></div>
      <div class="kv-row"><span class="kv-key">EMAIL</span><span class="kv-val">${esc(user.email)}</span></div>
      <div class="kv-row"><span class="kv-key">ROLE</span><span class="kv-val">${esc(user.role)}</span></div>
      <div class="kv-row"><span class="kv-key">BUSINESS UNIT</span><span class="kv-val">${esc(user.business_unit || "—")}</span></div>
      <div class="kv-row"><span class="kv-key">CLEARANCE</span><span class="kv-val">${esc(user.role === "admin" ? "LEVEL 5 / FULL" : "LEVEL 3 / REVIEW")}</span></div>
    `;
    $("health-info").innerHTML = `
      <div class="kv-row"><span class="kv-key">CORE</span><span class="kv-val">${esc(health.status)}</span></div>
      <div class="kv-row"><span class="kv-key">SYSTEM</span><span class="kv-val">${esc(health.app)}</span></div>
      <div class="kv-row"><span class="kv-key">VERSION</span><span class="kv-val">${esc(health.version)}</span></div>
      <div class="kv-row"><span class="kv-key">AI MODE</span><span class="kv-val" style="color:var(--green)">${esc(health.ai_mode)}</span></div>
    `;
  } catch (err) { toast(err.message, "err"); }
}

/* ---------------- PROFILE ---------------- */
async function loadProfile() {
  try {
    const user = state.user || (await API.get("/auth/me"));
    $("pf-name").value = user.name || "";
    $("pf-email").value = user.email || "";
    $("pf-role").value = user.role || "";
    $("pf-bu").value = user.business_unit || "";
  } catch (err) { toast(err.message, "err"); }
}

$("pf-save").addEventListener("click", async (e) => {
  e.preventDefault();
  try {
    await API.put("/account/profile", {
      name: $("pf-name").value, business_unit: $("pf-bu").value,
      password: $("pf-pass").value || null,
    });
    $("pf-status").textContent = "Profile saved.";
    toast("Profile updated");
  } catch (err) { $("pf-status").textContent = "ERROR: " + err.message; }
});

/* ---------------- SETTINGS ---------------- */
async function loadSettings() {
  try {
    const s = await API.get("/account/settings");
    $("st-mode").value = s.ai_mode || "auto";
    $("st-model").value = s.llm_model || "gemini-1.5-flash";
    $("st-routing").value = s.auto_review_routing || "high_risk";
  } catch (err) { toast(err.message, "err"); }
}

$("st-save").addEventListener("click", async (e) => {
  e.preventDefault();
  try {
    await API.put("/account/settings", {
      ai_mode: $("st-mode").value, llm_model: $("st-model").value,
      auto_review_routing: $("st-routing").value,
    });
    $("st-status").textContent = "Settings applied.";
    toast("Settings saved");
    refreshHealth();
  } catch (err) { $("st-status").textContent = "ERROR: " + err.message; }
});

/* ---------------- MISC ---------------- */
async function refreshHealth() {
  try {
    const h = await API.get("/health");
    $("ai-mode-text").textContent = h.ai_mode.toUpperCase();
    $("ai-mode-led").className = "led " + (h.ai_mode === "gemini" ? "green" : "amber");
  } catch (e) { $("ai-mode-text").textContent = "OFFLINE"; }
}

$("logout-btn").addEventListener("click", logout);
$("hamburger").addEventListener("click", () => $("sidebar").classList.toggle("open"));

document.addEventListener("click", (e) => {
  const nav = e.target.closest("[data-nav]");
  if (nav) showView(nav.dataset.nav);
  const navItem = e.target.closest(".nav-item[data-view]");
  if (navItem) showView(navItem.dataset.view);
});

document.getElementById("login-form").addEventListener("submit", (e) => {
  e.preventDefault();
  login($("login-email").value, $("login-password").value);
});

checkSession();
