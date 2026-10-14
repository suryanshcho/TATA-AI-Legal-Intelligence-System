/* ==============================================
   TATA GROUP AI LEGAL DOCUMENT INTELLIGENCE
   Landing Page + App Shell Controller
   ============================================== */

/* ============ API ============ */
const API = {
  async request(path, opts = {}) {
    const h = opts.headers || {};
    const t = localStorage.getItem("token");
    if (t) h["Authorization"] = "Bearer " + t;
    if (opts.body && !(opts.body instanceof FormData)) h["Content-Type"] = "application/json";
    const r = await fetch("/api" + path, { ...opts, headers: h });
    let d = null;
    try { d = await r.json(); } catch (e) { d = {}; }
    if (!r.ok) throw new Error(d.detail || d.message || "Request failed (" + r.status + ")");
    return d;
  },
  get: (p) => API.request(p),
  post: (p, b) => API.request(p, { method: "POST", body: b ? JSON.stringify(b) : undefined }),
  put: (p, b) => API.request(p, { method: "PUT", body: JSON.stringify(b) }),
  del: (p) => API.request(p, { method: "DELETE" }),
};

const state = { user: null, currentDoc: null, pollTimer: null, heroTimer: null, heroIdx: 0, view: "dashboard", flowDoc: null, flowName: "", flowStep: null };
const $ = (id) => document.getElementById(id);

function toast(msg, type = "ok") {
  const w = $("toast-wrap"), el = document.createElement("div");
  el.className = "toast " + type; el.textContent = msg;
  w.appendChild(el); setTimeout(() => el.remove(), 3200);
}
function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
function fmtDate(s) { return s ? String(s).replace("T", " ").slice(0, 16) : "\u2014"; }

/* ============ LANDING PAGE: HEADER SCROLL ============ */
(function initHeader() {
  const hdr = $("site-header");
  if (!hdr) return;
  let lastY = 0;
  window.addEventListener("scroll", () => {
    const y = window.scrollY;
    hdr.classList.toggle("scrolled", y > 50);
    lastY = y;
  }, { passive: true });
})();

/* ============ LANDING PAGE: HERO CAROUSEL ============ */
(function initHero() {
  const slides = document.querySelectorAll(".hero-slide");
  const dots = document.querySelectorAll(".hero-dot");
  const fill = $("hero-progress-fill");
  if (!slides.length) return;
  const TOTAL = slides.length, INTERVAL = 6000;
  let idx = 0, progress = 0, raf;

  function go(i) {
    slides.forEach(s => s.classList.remove("active"));
    dots.forEach(d => d.classList.remove("active"));
    slides[i].classList.add("active");
    dots[i].classList.add("active");
    idx = i; progress = 0;
    if (fill) fill.style.width = "0%";
  }

  function tick() {
    progress += 100 / (INTERVAL / 16);
    if (fill) fill.style.width = Math.min(progress, 100) + "%";
    if (progress >= 100) { go((idx + 1) % TOTAL); }
    raf = requestAnimationFrame(tick);
  }

  dots.forEach(d => d.addEventListener("click", () => {
    go(+d.dataset.slide);
  }));

  go(0);
  raf = requestAnimationFrame(tick);
})();

/* ============ LANDING PAGE: INNOVATION TABS ============ */
(function initInnoTabs() {
  const tabs = document.querySelectorAll(".inno-tab");
  const panels = document.querySelectorAll(".inno-display-card");
  if (!tabs.length) return;
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      const i = tab.dataset.tab;
      tabs.forEach(t => t.classList.remove("active"));
      panels.forEach(p => p.classList.remove("active"));
      tab.classList.add("active");
      const target = document.querySelector('.inno-display-card[data-panel="' + i + '"]');
      if (target) target.classList.add("active");
    });
  });
})();

/* ============ LANDING PAGE: COUNTER ANIMATION ============ */
(function initCounters() {
  const vals = document.querySelectorAll(".sustain-val[data-count]");
  if (!vals.length) return;
  let triggered = false;
  function animate() {
    if (triggered) return;
    const rect = vals[0].getBoundingClientRect();
    if (rect.top < window.innerHeight * 0.85) {
      triggered = true;
      vals.forEach(el => {
        const target = +el.dataset.count;
        const unit = el.querySelector(".sustain-unit");
        const unitText = unit ? unit.textContent : "";
        let current = 0;
        const step = Math.max(1, Math.ceil(target / 40));
        const timer = setInterval(() => {
          current += step;
          if (current >= target) { current = target; clearInterval(timer); }
          el.textContent = current;
          if (unitText) { const u = document.createElement("span"); u.className = "sustain-unit"; u.textContent = unitText; el.appendChild(u); }
        }, 30);
      });
    }
  }
  window.addEventListener("scroll", animate, { passive: true });
  animate();
})();

/* ============ LANDING PAGE: MOBILE DRAWER ============ */
(function initDrawer() {
  const btn = $("hamburger-btn"), drawer = $("mobile-drawer"), overlay = $("drawer-overlay"), close = $("drawer-close");
  if (!btn || !drawer) return;
  function open() { drawer.classList.add("open"); btn.classList.add("open"); document.body.style.overflow = "hidden"; }
  function shut() { drawer.classList.remove("open"); btn.classList.remove("open"); document.body.style.overflow = ""; }
  btn.addEventListener("click", () => drawer.classList.contains("open") ? shut() : open());
  if (overlay) overlay.addEventListener("click", shut);
  if (close) close.addEventListener("click", shut);
  drawer.querySelectorAll(".drawer-link").forEach(l => l.addEventListener("click", shut));
})();

/* ============ LANDING PAGE: SMOOTH SCROLL ============ */
document.querySelectorAll('a[href^="#"]').forEach(a => {
  a.addEventListener("click", e => {
    const id = a.getAttribute("href");
    if (id && id.length > 1) {
      const el = document.querySelector(id);
      if (el) { e.preventDefault(); el.scrollIntoView({ behavior: "smooth", block: "start" }); }
    }
  });
});

/* ============ LANDING <-> APP SHELL SWITCHING ============ */
function showLanding() {
  $("landing-page").classList.remove("hidden");
  $("app-shell").classList.add("hidden");
  document.body.style.overflow = "";
}

function showApp() {
  $("landing-page").classList.add("hidden");
  $("app-shell").classList.remove("hidden");
}

/* ============ AUTH ============ */
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
  showApp();
  $("app-user-name").textContent = state.user.name || state.user.email;
  var name = state.user.name || state.user.email || "";
  var initials = name.split(" ").map(w => w[0]).join("").toUpperCase().slice(0, 2);
  $("app-user-avatar").textContent = initials;
  showView("dashboard");
}

function logout() {
  localStorage.removeItem("token");
  state.user = null;
  exitWorkflow();
  state.currentDoc = null;
  showLanding();
}

/* Back to home */
document.addEventListener("click", e => {
  const b = e.target.closest("#back-home, #brand-home");
  if (b) { e.preventDefault(); if (state.user) showApp(); else showLanding(); }
});

/* ============ APP NAV ============ */
function showView(view) {
  clearInterval(state.pollTimer);
  state.view = view;
  document.querySelectorAll(".app-view").forEach(v => v.classList.remove("active"));
  const t = $("view-" + view);
  if (t) t.classList.add("active");
  document.querySelectorAll(".app-nav-tab").forEach(b => b.classList.toggle("active", b.dataset.view === view));
  showApp();
  renderWorkflow();

  if (view === "dashboard") loadDashboard();
  if (view === "workspace") loadWorkspace();
  if (view === "processing") loadProcessing();
  if (view === "review") loadReview();
  if (view === "audit") loadAudit();
  if (view === "settings") loadSettings();
}

/* ============ GUIDED WORKFLOW: Processing -> Review -> Audit ============ */
var WF_STEPS = ["processing", "review", "audit"];
var WF_LABELS = { processing: "Processing", review: "Review", audit: "Audit" };

function startWorkflow(docId, docName) {
  state.flowDoc = docId;
  state.flowName = docName || "";
  state.flowStep = "processing";
  state.currentDoc = docId;
  state.currentDocDoc = null;
  showView("processing");
  toast("Workflow started \u2014 Processing \u2192 Review \u2192 Audit");
}

function goStep(step) {
  if (WF_STEPS.indexOf(step) === -1) return;
  state.flowStep = step;
  if (step === "review" || step === "audit") state.currentDoc = state.flowDoc;
  showView(step);
}

function nextStep() {
  var i = WF_STEPS.indexOf(state.view);
  if (i === -1) return;
  if (i < WF_STEPS.length - 1) { goStep(WF_STEPS[i + 1]); }
  else { toast("Workflow complete \u2014 document filed"); exitWorkflow(); showView("dashboard"); }
}

function exitWorkflow() {
  state.flowDoc = null; state.flowStep = null; state.flowName = "";
  renderWorkflow();
}

function continueToReview(id, name) {
  if (state.flowDoc !== id) { state.flowDoc = id; state.flowName = name || ""; }
  goStep("review");
}

function renderWorkflow() {
  var bar = $("workflow-bar"), steps = $("wf-steps");
  if (!bar || !steps) return;
  var onStepView = WF_STEPS.indexOf(state.view) !== -1;
  if (!state.flowDoc || !onStepView) { bar.classList.add("hidden"); return; }
  bar.classList.remove("hidden");
  $("wf-doc").innerHTML = "Document: <strong>" + esc(state.flowName || ("Job #" + state.flowDoc)) + "</strong>";
  var order = WF_STEPS.indexOf(state.view);
  steps.querySelectorAll(".wf-step").forEach(function(el) {
    var idx = WF_STEPS.indexOf(el.dataset.step);
    el.classList.toggle("active", idx === order);
    el.classList.toggle("done", idx < order);
  });
  var btn = $("wf-next");
  btn.textContent = order < WF_STEPS.length - 1 ? ("Next: " + WF_LABELS[WF_STEPS[order + 1]] + " \u203a") : "Finish \u2713";
}

/* ============ DASHBOARD ============ */
async function loadDashboard() {
  try {
    const d = await API.get("/dashboard"), k = d.kpis;
    $("stat-grid").innerHTML =
      '<div class="stat-card blue"><div class="stat-value">' + k.total + '</div><div class="stat-label">Total Documents</div><div class="stat-sub">Database Online</div></div>' +
      '<div class="stat-card green"><div class="stat-value">' + k.completed + '</div><div class="stat-label">Completed</div><div class="stat-sub">' + k.completion_percent + '% done</div></div>' +
      '<div class="stat-card amber"><div class="stat-value">' + k.processing + '</div><div class="stat-label">Processing</div><div class="stat-sub">Queue: ' + k.queue + '</div></div>' +
      '<div class="stat-card red"><div class="stat-value">' + k.high_risk + '</div><div class="stat-label">High Risk</div><div class="stat-sub">Needs attention</div></div>';

    var att = k.attention;
    $("alert-title").textContent = att + " high-risk flags need review";
    $("alert-desc").textContent = "Documents flagged by AI analysis require legal review.";
    if (att === 0) $("alert-card").classList.add("hidden"); else $("alert-card").classList.remove("hidden");

    $("pipe-stats").innerHTML =
      '<div class="pipe-stat"><div class="pipe-val">' + k.avg_time + ' min</div><div class="pipe-lbl">Avg Analysis Time</div></div>' +
      '<div class="pipe-stat"><div class="pipe-val">' + k.queue + '</div><div class="pipe-lbl">In Queue</div></div>' +
      '<div class="pipe-stat"><div class="pipe-val">' + k.ai_accuracy + '%</div><div class="pipe-lbl">AI Accuracy</div></div>';
    $("pipe-bar").innerHTML = '<div class="progress-fill" style="width:' + k.completion_percent + '%"></div>';

    var cats = d.risk_by_category || [];
    var colors = ["crit", "high", "high", "med", "med", "med", "med", "med"];
    $("risk-matrix").innerHTML = cats.length
      ? cats.map(function(c, i) {
          return '<div class="rm-row"><div class="rm-label">' + esc(c.category) + '</div><div class="rm-track"><div class="rm-fill ' + (colors[i] || "med") + '" style="width:' + Math.min(100, c.c * 22) + '%"></div></div><div class="rm-count">' + c.c + '</div></div>';
        }).join("")
      : '<div class="empty">No risk data yet \u2014 upload a document to begin</div>';

    renderRecentTable(d.recent_documents || []);
  } catch (err) { toast(err.message, "err"); }
}

function renderRecentTable(docs) {
  var t = $("recent-table");
  if (!docs.length) { t.innerHTML = '<tr><td class="empty">No documents yet.</td></tr>'; return; }
  t.innerHTML = '<thead><tr><th>DOCUMENT</th><th>TYPE</th><th>UPLOADED BY</th><th>DATE</th><th>STATUS</th><th>RISK</th></tr></thead><tbody>' +
    docs.map(function(d) {
      return '<tr class="row-click" onclick="openDocument(' + d.id + ')"><td class="t-doc">' + esc(d.original_name) + '</td><td>' + esc(d.doc_type) + '</td><td>' + esc(d.owner_email || "\u2014") + '</td><td>' + fmtDate(d.created_at) + '</td><td>' + statusBadge(d.status) + '</td><td>' + riskBadge(d.high_risk_count) + '</td></tr>';
    }).join("") + "</tbody>";
}

function statusBadge(s) {
  var m = { completed: ["green", "COMPLETED"], approved: ["green", "APPROVED"], attention: ["amber", "UNDER REVIEW"], processing: ["blue", "PROCESSING"], uploaded: ["gray", "UPLOADED"], escalated: ["amber", "ESCALATED"], rejected: ["red", "REJECTED"], failed: ["red", "FAILED"] };
  var p = m[s] || ["gray", (s || "?").toUpperCase()];
  return '<span class="badge badge-' + p[0] + '">' + p[1] + '</span>';
}

function riskBadge(n) {
  if (!n) return '<span class="badge badge-green">LOW</span>';
  if (n >= 3) return '<span class="badge badge-red">HIGH (' + n + ')</span>';
  return '<span class="badge badge-amber">MED (' + n + ')</span>';
}

/* ============ WORKSPACE ============ */
async function loadWorkspace() {
  try {
    var docs = await API.get("/documents");
    $("ws-count").textContent = docs.length + " RECORDS";
    renderWorkspace(docs);
  } catch (err) { toast(err.message, "err"); }
}

function renderWorkspace(docs) {
  var t = $("workspace-table");
  if (!docs.length) { t.innerHTML = '<tr><td class="empty">No documents found.</td></tr>'; return; }
  t.innerHTML = '<thead><tr><th>DOCUMENT</th><th>TYPE</th><th>UPLOADED BY</th><th>DATE</th><th>STATUS</th><th>RISK</th><th></th></tr></thead><tbody>' +
    docs.map(function(d) {
      return '<tr><td class="t-doc" onclick="openDocument(' + d.id + ')">' + esc(d.original_name) + '</td><td>' + esc(d.doc_type) + '</td><td>' + esc(d.owner_email || "\u2014") + '</td><td>' + fmtDate(d.created_at) + '</td><td>' + statusBadge(d.status) + '</td><td>' + riskBadge(d.high_risk_count) + '</td><td><button class="btn btn-sm" onclick="openDocument(' + d.id + ')">OPEN</button> <button class="btn btn-sm" onclick="deleteDocument(' + d.id + ')">&times;</button></td></tr>';
    }).join("") + "</tbody>";
}

function applyWorkspaceFilters() {
  API.get("/documents").then(function(docs) {
    var q = $("filter-search").value.toLowerCase(), st = $("filter-status").value, rk = $("filter-risk").value;
    if (q) docs = docs.filter(function(d) { return (d.original_name + " " + d.doc_type + " " + (d.owner_email || "")).toLowerCase().includes(q); });
    if (st !== "All") docs = docs.filter(function(d) { return (d.status === "completed" || d.status === "approved" ? "Completed" : d.status === "processing" || d.status === "uploaded" ? "Processing" : "Under Review") === st; });
    if (rk !== "All") docs = docs.filter(function(d) { return rk === "High" ? d.high_risk_count > 0 : d.high_risk_count === 0; });
    renderWorkspace(docs);
  }).catch(function(err) { toast(err.message, "err"); });
}

function openDocument(id) { state.currentDoc = id; showView("review"); }
async function deleteDocument(id) {
  if (!confirm("Delete this document and its analysis?")) return;
  try { await API.del("/documents/" + id); toast("Document deleted"); loadWorkspace(); } catch (err) { toast(err.message, "err"); }
}

/* ============ UPLOAD ============ */
(function initUpload() {
  var dz = $("dropzone"), fi = $("file-input");
  if (!dz || !fi) return;
  dz.addEventListener("click", () => fi.click());
  fi.addEventListener("change", () => setFile(fi.files[0]));
  ["dragover", "dragenter"].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.add("drag"); }));
  ["dragleave", "drop"].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.remove("drag"); }));
  dz.addEventListener("drop", e => setFile(e.dataTransfer.files[0]));

  function setFile(f) {
    if (!f) return;
    $("dz-file").textContent = f.name + " (" + (f.size / 1024).toFixed(1) + " KB)";
    state.uploadFile = f;
  }

  $("upload-btn").addEventListener("click", function() {
    var f = state.uploadFile;
    if (!f) { toast("Select a document first", "err"); return; }
    var fileName = f.name;
    var fd = new FormData();
    fd.append("file", f);
    fd.append("doc_type", $("up-doc-type").value);
    fd.append("business_unit", $("up-bu").value);
    fd.append("counterparty", $("up-party").value);
    fd.append("jurisdiction", $("up-jur").value);
    fd.append("confidentiality", $("up-conf").value);
    fd.append("review_priority", $("up-prio").value);
    $("upload-status").textContent = "Transmitting...";
    API.request("/documents/upload", { method: "POST", body: fd }).then(function(res) {
      $("upload-status").textContent = "Uploaded. Starting AI processing pipeline...";
      toast("Document uploaded \u2014 starting AI analysis");
      return API.post("/documents/" + res.id + "/process").then(function() { return res; });
    }).then(function(res) {
      $("upload-status").textContent = "Analysis in progress \u2014 follow the steps below.";
      setTimeout(function() { startWorkflow(res.id, fileName); }, 800);
    }).catch(function(err) { $("upload-status").textContent = "ERROR: " + err.message; toast(err.message, "err"); });
  });
})();

/* ============ PROCESSING ============ */
async function loadProcessing() {
  try {
    var docs = await API.get("/documents");
    var queue = docs.filter(function(d) { return d.status === "processing" || d.status === "uploaded"; });
    var done = docs.filter(function(d) { return d.status !== "processing" && d.status !== "uploaded"; });
    function renderCards(arr, title) {
      if (!arr.length) return '<div class="card"><div class="card-head"><h3>' + title + '</h3><span class="badge badge-gray">0</span></div><div class="card-pad"><div class="empty">No ' + title.toLowerCase() + '.</div></div></div>';
      var tagCls = title === "Active Jobs" ? "badge-amber" : "badge-gray";
      return '<div class="card"><div class="card-head"><h3>' + title + '</h3><span class="badge ' + tagCls + '">' + arr.length + '</span></div><div class="card-pad proc-grid">' +
        arr.map(function(d) {
          return '<div class="proc-card' + (state.currentDoc === d.id ? " selected" : "") + '" onclick="openProcessing(' + d.id + ')"><div class="pc-top"><div class="pc-name" title="' + esc(d.original_name) + '">' + esc(d.original_name) + '</div>' + statusBadge(d.status) + '</div><div class="pc-meta"><span>Progress <strong>' + (d.progress || 0) + '%</strong></span><span class="pc-dot">&middot;</span><span>Stage <strong>' + esc(d.stage || "\u2014") + '</strong></span></div><div class="progress-bar"><div class="progress-fill" style="width:' + (d.progress || 0) + '%"></div></div></div>';
        }).join("") + "</div></div>";
    }
    $("proc-queue").innerHTML = renderCards(queue, "Active Jobs") + renderCards(done, "Archived Jobs");
    $("proc-tag").textContent = queue.length ? queue.length + " ACTIVE" : "IDLE";
    $("proc-tag").className = "badge " + (queue.length ? "badge-amber" : "badge-gray");
    if (state.currentDoc && state.currentDocDoc !== state.currentDoc) { state.currentDocDoc = state.currentDoc; loadProcDetail(state.currentDoc); }
    else if (!state.currentDoc && queue.length) openProcessing(queue[0].id);
    else if (!queue.length) $("proc-detail").innerHTML = '<div class="empty">No active processing jobs.</div>';
  } catch (err) { toast(err.message, "err"); }
}

function openProcessing(id) {
  state.currentDoc = id;
  if (state.flowDoc) { state.flowDoc = id; state.flowStep = "processing"; }
  loadProcDetail(id);
}

async function loadProcDetail(id) {
  try {
    var s = await API.get("/documents/" + id + "/status"), stages = s.stages || [];
    var order = ["ocr", "parsing", "clause_extraction", "rag_retrieval", "legal_reasoning", "risk_flagging", "summarization", "review"];
    var byName = {}; stages.forEach(function(st) { byName[st.stage] = st; });
    var labels = { ocr: "OCR & Text Extraction", parsing: "Document Parsing", clause_extraction: "Clause Extraction", rag_retrieval: "RAG Retrieval", legal_reasoning: "Legal Reasoning", risk_flagging: "Risk Flagging", summarization: "Summarization", review: "Human Review" };
    $("proc-detail").innerHTML = '<div class="card-head"><h3>' + esc(s.id ? "Job #" + s.id : "Job") + " \u00b7 " + s.status.toUpperCase() + '</h3><span class="badge badge-blue">' + (s.progress || 0) + '%</span></div><div class="card-pad stage-list">' +
      order.map(function(st) {
        var row = byName[st], cls = row ? (row.status === "done" ? "done" : row.status === "failed" ? "failed" : "running") : "pending";
        var det = row && row.detail ? '<div class="stage-detail">' + esc(row.detail) + '</div>' : "";
        return '<div class="stage-row ' + cls + '"><span class="stage-dot ' + cls + '"></span><span class="stage-name">' + (labels[st] || st.toUpperCase()) + '</span></div>' + det;
      }).join("") + "</div>" +
      (s.status === "processing" || s.status === "uploaded"
        ? '<div class="card-foot"><button class="btn btn-accent btn-sm" onclick="loadProcDetail(' + s.id + ')">Refresh</button></div>'
        : '<div class="card-foot"><button class="btn btn-accent btn-sm" onclick="continueToReview(' + s.id + ')">Continue to Review &rsaquo;</button></div>');
    if (s.status === "processing" || s.status === "uploaded") { clearInterval(state.pollTimer); state.pollTimer = setInterval(function() { loadProcDetail(id); }, 3000); }
  } catch (err) { toast(err.message, "err"); }
}

/* ============ REVIEW ============ */
async function loadReview() {
  try {
    var docs = await API.get("/documents");
    var analyzed = docs.filter(function(d) { return d.status !== "uploaded" && d.status !== "failed"; });
    if (state.currentDoc && !analyzed.some(function(d) { return d.id === state.currentDoc; })) {
      var cur = docs.find(function(d) { return d.id === state.currentDoc; });
      if (cur) analyzed = [cur].concat(analyzed);
    }
    if (!analyzed.length) { $("review-doc-select").querySelector(".card-pad").innerHTML = '<div class="empty">No analyzed documents yet.</div>'; return; }
    var sel = state.currentDoc && docs.find(function(d) { return d.id === state.currentDoc; }) ? state.currentDoc : analyzed[0].id;
    state.currentDoc = sel;
    var current = docs.find(function(d) { return d.id === sel; });
    $("review-doc-select").querySelector(".card-pad").innerHTML =
      '<label>Select Document</label><div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap"><select id="review-select" class="input" style="max-width:360px">' +
      analyzed.map(function(d) { return '<option value="' + d.id + '"' + (d.id === sel ? " selected" : "") + '>' + esc(d.original_name) + '</option>'; }).join("") +
      '</select>' + statusBadge(current.status) + '<button class="btn btn-sm btn-ghost" onclick="reprocess(' + sel + ')">&#8635; Reprocess</button></div>';
    $("review-select").addEventListener("change", function(e) { state.currentDoc = +e.target.value; loadReviewDetail(); });
    loadReviewDetail();
  } catch (err) { toast(err.message, "err"); }
}

async function reprocess(id) { try { await API.post("/documents/" + id + "/process"); toast("Reprocessing started"); showView("processing"); } catch (err) { toast(err.message, "err"); } }

async function loadReviewDetail() {
  var id = state.currentDoc;
  $("review-summary").classList.remove("hidden");
  $("review-clauses").classList.remove("hidden");
  $("review-risks").classList.remove("hidden");
  try {
    var summary = await API.get("/documents/" + id + "/summary");
    var clauses = await API.get("/documents/" + id + "/clauses");
    var risks = await API.get("/documents/" + id + "/risks");
    var appStatus = (summary.approval_status || "PENDING").toUpperCase();
    $("sum-approval").textContent = appStatus;
    $("sum-approval").className = "badge " + (appStatus === "APPROVED" ? "badge-green" : appStatus === "REJECTED" ? "badge-red" : "badge-amber");
    $("sum-content").textContent = summary.content || "Summary not generated yet.";
    $("review-actions").innerHTML =
      '<button class="btn btn-accent btn-sm" onclick="reviewAction(\'approve\')">&#10003; Approve</button>' +
      '<button class="btn btn-ghost btn-sm" onclick="editSummary()">&#9998; Edit</button>' +
      '<button class="btn btn-danger btn-sm" onclick="reviewAction(\'escalate\')">&#9650; Escalate</button>' +
      '<button class="btn btn-sm" onclick="reviewAction(\'reject\')">&times; Reject</button>';
    $("clause-list").innerHTML = clauses.length ? clauses.map(function(c) {
      return '<div class="clause-card"><div class="clause-head"><span class="clause-title">' + esc(c.label || c.clause_type) + '</span><span class="clause-meta">PAGE ' + (c.page || "\u2014") + ' \u00b7 CONF ' + (c.confidence * 100).toFixed(0) + '%</span>' + (c.section ? '<span class="badge badge-gray">' + esc(c.section) + '</span>' : "") + '</div><div class="clause-body">' + esc(c.clause_text || "") + '</div></div>';
    }).join("") : '<div class="empty">No clauses extracted.</div>';
    $("risk-list").innerHTML = risks.length ? risks.map(function(r) {
      return '<div class="risk-card ' + (r.severity || "low").toLowerCase() + '"><div class="risk-head"><span class="badge badge-' + sevClass(r.severity) + '">' + esc(r.severity) + '</span><span class="risk-cat">' + esc(r.category) + '</span><span class="clause-meta">CONF ' + (r.confidence * 100).toFixed(0) + '%</span></div><div class="risk-rationale">' + esc(r.rationale) + '</div><div class="risk-evidence">EVIDENCE: ' + esc(r.evidence) + '</div><div class="risk-rec">&#8594; ' + esc(r.recommendation) + '</div><div class="risk-actions"><button class="btn btn-sm btn-accent" onclick="riskAction(' + r.id + ',\'accepted\')">Accept</button><button class="btn btn-sm btn-ghost" onclick="riskAction(' + r.id + ',\'escalated\')">Escalate</button><button class="btn btn-sm" onclick="riskAction(' + r.id + ',\'rejected\')">Reject</button></div></div>';
    }).join("") : '<div class="empty">No risk flags detected.</div>';
  } catch (err) { toast(err.message, "err"); }
}

function sevClass(s) { var m = { Critical: "red", High: "amber", Medium: "blue", Low: "green" }; return m[s] || "gray"; }
async function reviewAction(action, note) { try { await API.post("/documents/" + state.currentDoc + "/review", { action: action, note: note, risk_id: null }); toast("Review action: " + action.toUpperCase()); loadReviewDetail(); } catch (err) { toast(err.message, "err"); } }
async function riskAction(id, action) { try { await API.post("/documents/" + state.currentDoc + "/review", { action: "comment", risk_id: id, note: action }); toast("Risk marked: " + action.toUpperCase()); loadReviewDetail(); } catch (err) { toast(err.message, "err"); } }
async function editSummary() { var c = prompt("Edit AI summary:", $("sum-content").textContent); if (!c) return; try { await API.post("/documents/" + state.currentDoc + "/review", { action: "edit", edited_summary: c }); toast("Summary edited"); loadReviewDetail(); } catch (err) { toast(err.message, "err"); } }

/* ============ AUDIT ============ */
async function loadAudit() {
  try {
    var logs = await API.get("/audit");
    $("audit-table").innerHTML = '<thead><tr><th>TIME</th><th>ACTOR</th><th>ACTION</th><th>DOC ID</th><th>DETAIL</th></tr></thead><tbody>' +
      logs.map(function(l) { return '<tr><td>' + fmtDate(l.created_at) + '</td><td>' + esc(l.actor) + '</td><td>' + esc(l.action) + '</td><td>' + (l.document_id || "\u2014") + '</td><td>' + esc(l.detail || "\u2014") + '</td></tr>'; }).join("") + "</tbody>";
  } catch (err) { toast(err.message, "err"); }
}

/* ============ SETTINGS ============ */
async function loadSettings() {
  try {
    var s = await API.get("/account/settings");
    $("st-mode").value = s.ai_mode || "auto";
    $("st-model").value = s.llm_model || "gemini-1.5-flash";
    $("st-routing").value = s.auto_review_routing || "high_risk";
  } catch (err) { toast(err.message, "err"); }
}

/* ============ EVENT LISTENERS ============ */
$("logout-btn").addEventListener("click", logout);

document.addEventListener("click", e => {
  var nav = e.target.closest("[data-nav]");
  if (nav) showView(nav.dataset.nav);
  var tab = e.target.closest(".app-nav-tab[data-view]");
  if (tab) showView(tab.dataset.view);
});

$("login-form").addEventListener("submit", function(e) {
  e.preventDefault();
  login($("login-email").value, $("login-password").value);
});

$("filter-search").addEventListener("input", applyWorkspaceFilters);
$("filter-status").addEventListener("change", applyWorkspaceFilters);
$("filter-risk").addEventListener("change", applyWorkspaceFilters);

$("st-save").addEventListener("click", function(e) {
  e.preventDefault();
  API.put("/account/settings", { ai_mode: $("st-mode").value, llm_model: $("st-model").value, auto_review_routing: $("st-routing").value })
    .then(function() { $("st-status").textContent = "Settings applied."; toast("Settings saved"); })
    .catch(function(err) { $("st-status").textContent = "ERROR: " + err.message; });
});

$("wf-next").addEventListener("click", nextStep);
$("wf-exit").addEventListener("click", function() { exitWorkflow(); showView("dashboard"); });
$("wf-steps").addEventListener("click", function(e) {
  var s = e.target.closest(".wf-step");
  if (s && state.flowDoc) goStep(s.dataset.step);
});

checkSession();
