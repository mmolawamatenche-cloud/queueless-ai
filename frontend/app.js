/* QueueLess AI frontend */
const API = "";

const state = {
  lastPlan: null,
  location: "Johannesburg",
  lat: null,
  lon: null,
};

function $(sel, root = document) {
  return root.querySelector(sel);
}

function $$(sel, root = document) {
  return [...root.querySelectorAll(sel)];
}

async function api(path, options = {}) {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || res.statusText || "Request failed");
  }
  return res.json();
}

function savePlan(plan, intent, query) {
  const payload = { plan, intent, query, savedAt: new Date().toISOString() };
  localStorage.setItem("queueless_plan", JSON.stringify(payload));
  state.lastPlan = payload;
}

function loadPlan() {
  try {
    const raw = localStorage.getItem("queueless_plan");
    if (!raw) return null;
    state.lastPlan = JSON.parse(raw);
    return state.lastPlan;
  } catch {
    return null;
  }
}

function crowdClass(level) {
  const l = (level || "").toLowerCase();
  if (l === "low") return "crowd-low";
  if (l === "high") return "crowd-high";
  return "crowd-medium";
}

function renderDocuments(docs) {
  if (!docs?.length) return "<p class='empty'>No checklist for this service.</p>";
  return `<ul class="doc-list">${docs
    .map((d) => {
      const icon =
        d.status === "have"
          ? "<span class='ok'>✓</span>"
          : d.status === "missing"
            ? "<span class='warn'>⚠</span>"
            : "<span class='ok'>○</span>";
      return `<li>${icon}<div><strong>${d.name}</strong>${
        d.notes ? `<div style="color:var(--muted);font-size:.85rem">${d.notes}</div>` : ""
      }</div></li>`;
    })
    .join("")}</ul>`;
}

function renderEvidence(evidence) {
  if (!evidence?.sources) return "";
  const badgeClass = {
    historical_sample: "badge-hist",
    user_reported: "badge-report",
    ai_predicted: "badge-pred",
  };
  const rows = evidence.sources
    .map((s) => {
      const mins =
        s.value_minutes != null
          ? `${s.value_minutes} min`
          : s.range
            ? `${s.range[0]}–${s.range[1]} min`
            : "—";
      const extra =
        s.type === "historical_sample"
          ? `${s.rows_for_branch || 0} rows for branch`
          : s.type === "user_reported"
            ? `${s.reports_used || 0} recent report(s)`
            : `confidence ${Math.round((s.confidence || 0) * 100)}%`;
      return `<div class="evidence-row">
        <span class="badge ${badgeClass[s.type] || ""}">${s.label}</span>
        <strong>${mins}</strong>
        <span class="evidence-note">${extra} · ${s.note}</span>
      </div>`;
    })
    .join("");
  const model = evidence.model || {};
  return `
    <div class="evidence-block">
      <h3>Where this estimate comes from</h3>
      ${rows}
      <p class="evidence-model">
        Model: ${model.algorithm || "ML"} · trained on ${model.rows_trained ?? "—"} rows
        · hold-out MAE ~ ${model.mae_minutes ?? "—"} min
        · live government API: ${evidence.live_government_api ? "yes" : "no"}
      </p>
    </div>
  `;
}

function renderPlan(plan, intent, demoNotice) {
  const el = $("#plan-panel");
  if (!el || !plan) return;

  const conf = Math.round((plan.prediction_confidence || 0) * 100);
  el.classList.remove("hidden");
  el.innerHTML = `
    <div class="notice">${demoNotice || plan.data_labels?.prediction || "Demo prediction based on historical/sample data."}</div>
    <div class="plan-hero">
      <div class="plan-main">
        <p class="tagline" style="font-size:1rem">YOUR AI PLAN</p>
        <h2>${plan.branch_name}</h2>
        <p style="color:var(--ink-soft);margin:0">${plan.address} · ${plan.city}</p>
        <div class="meta-grid">
          <div class="meta">
            <span class="k">Service</span>
            <span class="v">${plan.service_name}</span>
          </div>
          <div class="meta">
            <span class="k">Queue signal</span>
            <span class="v ${crowdClass(plan.crowd_level)}">${plan.crowd_label}</span>
          </div>
          <div class="meta">
            <span class="k">AI estimate</span>
            <span class="v">${plan.estimated_wait_low}–${plan.estimated_wait_high} min</span>
          </div>
          <div class="meta">
            <span class="k">Recommended</span>
            <span class="v">${plan.recommended_day}<br>${plan.recommended_time}</span>
          </div>
          <div class="meta">
            <span class="k">Confidence</span>
            <span class="v">${conf}%</span>
          </div>
          <div class="meta">
            <span class="k">Category</span>
            <span class="v">${plan.category}</span>
          </div>
        </div>
        ${renderEvidence(plan.evidence)}
        <div class="reason">
          <strong>Why this plan</strong>
          ${plan.ai_recommendation}
          <div style="margin-top:.65rem;color:var(--ink-soft)">${plan.reason}</div>
        </div>
        <p class="disclaimer">${plan.disclaimer || "AI estimate only — verify official requirements before travelling."}</p>
      </div>
      <div>
        <h3>Documents checklist</h3>
        <p style="color:var(--muted);font-size:.88rem;margin:0 0 .5rem">Sample MVP checklist — we do not store your IDs. Confirm with Home Affairs.</p>
        ${renderDocuments(plan.documents)}
        ${
          plan.missing_documents?.length
            ? `<p style="margin-top:.75rem;color:#7a5610"><strong>Missing:</strong> ${plan.missing_documents.join(", ")}</p>`
            : ""
        }
      </div>
    </div>
    ${
      plan.alternatives?.length
        ? `<h3 style="margin-top:1.25rem">Other options</h3>
           <div class="alts">${plan.alternatives
             .map(
               (a) =>
                 `<div class="alt"><strong>${a.branch_name}</strong> · ${a.day} ${a.time} · ~${a.estimated_wait} min <span class="badge badge-pred">AI predicted</span></div>`
             )
             .join("")}</div>`
        : ""
    }
    <div class="feedback-row">
      <span>Was this plan useful?</span>
      <button type="button" class="btn btn-ghost" data-useful="1">Yes</button>
      <button type="button" class="btn btn-ghost" data-useful="0">Not really</button>
      <span id="feedback-thanks" class="hidden" style="color:var(--green);font-weight:600"></span>
    </div>
    <div style="margin-top:1rem;display:flex;gap:.6rem;flex-wrap:wrap">
      <a class="btn btn-primary" href="/report.html">Report a queue</a>
      <a class="btn btn-ghost" href="/plan.html">Open My Plan</a>
    </div>
  `;

  el.querySelectorAll("[data-useful]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        const res = await api("/api/feedback", {
          method: "POST",
          body: JSON.stringify({ useful: btn.dataset.useful === "1" }),
        });
        const thanks = $("#feedback-thanks", el);
        if (thanks) {
          thanks.classList.remove("hidden");
          thanks.textContent = res.message;
        }
      } catch (err) {
        const thanks = $("#feedback-thanks", el);
        if (thanks) {
          thanks.classList.remove("hidden");
          thanks.textContent = err.message;
        }
      }
    });
  });
}

function renderAnalysing(steps) {
  const el = $("#analyse-panel");
  if (!el) return;
  el.classList.remove("hidden");
  el.classList.add("analysing");
  el.innerHTML = `
    <h3>Analysing…</h3>
    <ul class="steps">
      ${(steps || [])
        .map(
          (s) =>
            `<li class="${s.status === "done" ? "done" : "pending"}">${s.label}</li>`
        )
        .join("")}
    </ul>
  `;
}

async function runAssist(query) {
  const btn = $("#ask-btn");
  const intentPanel = $("#intent-panel");
  const analysePanel = $("#analyse-panel");
  const planPanel = $("#plan-panel");
  const errorPanel = $("#error-panel");

  if (errorPanel) {
    errorPanel.classList.add("hidden");
    errorPanel.textContent = "";
  }
  if (planPanel) planPanel.classList.add("hidden");

  const progressive = [
    { id: "service", label: "Service identified", status: "pending" },
    { id: "branches", label: "Branches found", status: "pending" },
    { id: "queue", label: "Queue data analysed", status: "pending" },
    { id: "docs", label: "Documents checked", status: "pending" },
    { id: "time", label: "Best time calculated", status: "pending" },
  ];
  renderAnalysing(progressive);

  if (btn) btn.disabled = true;

  // Progressive reveal for demo polish
  for (let i = 0; i < progressive.length; i++) {
    await new Promise((r) => setTimeout(r, 280));
    progressive[i].status = "done";
    renderAnalysing(progressive);
  }

  try {
    const data = await api("/api/assist", {
      method: "POST",
      body: JSON.stringify({
        query,
        location: $("#location-input")?.value || state.location,
        latitude: state.lat,
        longitude: state.lon,
      }),
    });

    if (intentPanel) {
      intentPanel.classList.remove("hidden");
      if (!data.ok) {
        intentPanel.innerHTML = `
          <h3>I need a bit more detail</h3>
          <p>${data.message}</p>
        `;
        analysePanel?.classList.add("hidden");
        return;
      }
      intentPanel.innerHTML = `
        <h3>You need</h3>
        <p style="font-size:1.35rem;font-family:var(--font-display);font-weight:700;margin:.25rem 0">${data.intent.service_name}</p>
        <p style="color:var(--ink-soft);margin:0">Service category: <strong>${data.intent.category}</strong>
        · Confidence: ${Math.round(data.intent.confidence * 100)}%</p>
        <p style="color:var(--muted);font-size:.9rem;margin:.5rem 0 0">${data.intent.explanation}</p>
      `;
    }

    if (data.plan) {
      savePlan(data.plan, data.intent, query);
      analysePanel?.classList.remove("analysing");
      renderPlan(data.plan, data.intent, data.demo_notice);
      planPanel?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  } catch (err) {
    analysePanel?.classList.add("hidden");
    if (errorPanel) {
      errorPanel.classList.remove("hidden");
      errorPanel.textContent = err.message || "Something went wrong.";
    }
  } finally {
    if (btn) btn.disabled = false;
  }
}

function initHome() {
  const form = $("#assist-form");
  if (!form) return;

  $$(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const q = $("#query-input");
      if (q) {
        q.value = chip.dataset.query || chip.textContent.trim();
        q.focus();
      }
    });
  });

  $("#use-location")?.addEventListener("click", () => {
    if (!navigator.geolocation) {
      alert("Geolocation is not available in this browser.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        state.lat = pos.coords.latitude;
        state.lon = pos.coords.longitude;
        const input = $("#location-input");
        if (input) input.value = "Near me (GPS)";
      },
      () => alert("Could not read your location. Enter a city instead.")
    );
  });

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const query = $("#query-input")?.value?.trim();
    if (!query) return;
    runAssist(query);
  });
}

function initPlanPage() {
  const mount = $("#saved-plan");
  if (!mount) return;
  const saved = loadPlan();
  if (!saved?.plan) {
    mount.innerHTML = `<p class="empty">No plan yet. Go to <a href="/" style="color:var(--green);font-weight:700">Home</a> and tell QueueLess AI what you need.</p>`;
    return;
  }
  // Reuse render into mount
  const tempId = "plan-panel";
  mount.id = tempId;
  renderPlan(saved.plan, saved.intent, "Saved plan · Demo Mode estimates");
}

async function initReport() {
  const form = $("#report-form");
  if (!form) return;

  const select = $("#branch-select");
  try {
    const branches = await api("/api/branches");
    select.innerHTML = branches
      .map((b) => `<option value="${b.branch_id}">${b.branch_name} (${b.city})</option>`)
      .join("");

    const saved = loadPlan();
    if (saved?.plan?.branch_id) select.value = saved.plan.branch_id;
  } catch (err) {
    select.innerHTML = `<option>Could not load branches</option>`;
  }

  let crowd = "medium";
  $$(".crowd-picker button").forEach((btn) => {
    btn.addEventListener("click", () => {
      $$(".crowd-picker button").forEach((b) => b.classList.remove("selected"));
      btn.classList.add("selected");
      crowd = btn.dataset.level;
    });
  });
  $(".crowd-picker button[data-level='medium']")?.classList.add("selected");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const result = $("#report-result");
    const wait = $("#wait-input")?.value;
    const saved = loadPlan();
    try {
      const data = await api("/api/reports", {
        method: "POST",
        body: JSON.stringify({
          branch_id: select.value,
          crowd_level: crowd,
          wait_minutes: wait ? Number(wait) : null,
          service_id: saved?.plan?.service_id || null,
        }),
      });
      result.classList.remove("hidden");
      const p = data.updated_prediction;
      result.innerHTML = `
        <div class="notice">${data.message}</div>
        <p><strong>Your report is labelled user-reported.</strong> It is blended into the next AI prediction — not treated as official DHA data.</p>
        <div class="meta-grid">
          <div class="meta"><span class="k"><span class="badge badge-report">Reported</span></span><span class="v">${crowd}${wait ? ` · ${wait} min` : ""}</span></div>
          <div class="meta"><span class="k"><span class="badge badge-pred">AI predicted</span></span><span class="v">${p.wait_range_low}–${p.wait_range_high} min</span></div>
          <div class="meta"><span class="k">Point estimate</span><span class="v">${p.predicted_wait_minutes} min</span></div>
          <div class="meta"><span class="k">Confidence</span><span class="v">${Math.round(p.confidence * 100)}%</span></div>
        </div>
        <p style="color:var(--muted);font-size:.9rem;margin-top:.75rem">${p.explanation}</p>
        <p class="disclaimer">AI estimate only — information may change. Not a guaranteed wait time.</p>
      `;
    } catch (err) {
      result.classList.remove("hidden");
      result.innerHTML = `<p>${err.message}</p>`;
    }
  });
}

async function initHistory() {
  const mount = $("#history-list");
  if (!mount) return;
  try {
    const items = await api("/api/history");
    if (!items.length) {
      mount.innerHTML = `<p class="empty">No plans yet. Ask QueueLess AI on the home screen.</p>`;
      return;
    }
    mount.innerHTML = items
      .map((item) => {
        const p = item.plan || {};
        return `<div class="history-item">
          <div class="q">“${item.user_query}”</div>
          <div class="meta-line">${p.service_name || item.service_id || "—"} → ${p.branch_name || "—"} · ${p.recommended_time || ""} · ${new Date(item.created_at).toLocaleString()}</div>
        </div>`;
      })
      .join("");
  } catch (err) {
    mount.innerHTML = `<p class="empty">${err.message}</p>`;
  }
}

async function initDashboard() {
  const mount = $("#dashboard");
  if (!mount) return;
  try {
    const [d, cred] = await Promise.all([
      api("/api/dashboard"),
      api("/api/credibility"),
    ]);
    const t = d.traction || {};
    const dist = d.data_quality?.distinction || {};
    mount.innerHTML = `
      <div class="notice">${d.data_quality.label} · ${d.data_quality.mode} · Live DHA API: no</div>

      <div class="panel" style="margin-top:0">
        <h3>Judge-facing data answer</h3>
        <p style="line-height:1.55;margin:0">${cred.judge_answer}</p>
        <ol class="pipeline-list">
          ${(cred.pipeline || []).map((step) => `<li>${step}</li>`).join("")}
        </ol>
      </div>

      <h3 style="margin:1.25rem 0 .5rem;font-family:var(--font-display)">Traction</h3>
      <div class="stat-grid">
        <div class="stat"><div class="num">${t.service_searches ?? d.plans_created}</div><div class="lbl">Service searches / plans</div></div>
        <div class="stat"><div class="num">${t.queue_reports ?? d.queue_reports}</div><div class="lbl">Queue reports</div></div>
        <div class="stat"><div class="num">${t.sessions ?? d.active_sessions_approx}</div><div class="lbl">Sessions</div></div>
        <div class="stat"><div class="num">${t.useful_percent != null ? t.useful_percent + "%" : "—"}</div><div class="lbl">Found plan useful</div></div>
        <div class="stat"><div class="num">${d.pipeline?.historical_rows ?? "—"}</div><div class="lbl">Historical training rows</div></div>
        <div class="stat"><div class="num">${d.prediction_accuracy?.value_minutes ?? "—"}</div><div class="lbl">Model MAE (min)</div></div>
      </div>

      <div class="source-legend" style="margin:1rem 0">
        <span class="badge badge-hist">Historical / sample — ${dist.demo_sample || ""}</span>
        <span class="badge badge-report">Reported — ${dist.reported || ""}</span>
        <span class="badge badge-pred">Predicted — ${dist.predicted || ""}</span>
      </div>

      <div class="panel">
        <h3>Most-reported branches</h3>
        <table class="table">
          <thead><tr><th>Branch</th><th>Reports</th></tr></thead>
          <tbody>
            ${(d.top_branches || [])
              .map(
                (b) =>
                  `<tr><td>${b.branch_name || b.branch_id}</td><td>${b.reports}</td></tr>`
              )
              .join("") || "<tr><td colspan='2'>No reports yet</td></tr>"}
          </tbody>
        </table>
      </div>
      <div class="panel">
        <h3>Most-requested services</h3>
        <table class="table">
          <thead><tr><th>Service ID</th><th>Requests</th></tr></thead>
          <tbody>
            ${(d.top_services || [])
              .map((s) => `<tr><td>${s.service_id}</td><td>${s.requests}</td></tr>`)
              .join("") || "<tr><td colspan='2'>No plans yet</td></tr>"}
          </tbody>
        </table>
      </div>
      <div class="panel">
        <h3>Latest crowd levels <span class="badge badge-report">User-reported</span></h3>
        <table class="table">
          <thead><tr><th>Branch</th><th>Crowd</th><th>Wait</th></tr></thead>
          <tbody>
            ${(d.current_crowd_reports || [])
              .map(
                (r) =>
                  `<tr><td>${r.branch_name || r.branch_id}</td><td class="${crowdClass(r.crowd_level)}">${r.crowd_level}</td><td>${r.wait_minutes ?? "—"} min</td></tr>`
              )
              .join("") || "<tr><td colspan='3'>No reports</td></tr>"}
          </tbody>
        </table>
        <p style="color:var(--muted);font-size:.88rem;margin-top:.75rem">${d.prediction_accuracy?.note || ""}</p>
        <p style="color:var(--muted);font-size:.88rem">Privacy: ${cred.privacy?.document_feature || "checklist only"}</p>
      </div>
    `;
  } catch (err) {
    mount.innerHTML = `<p class="empty">${err.message}</p>`;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const page = document.body.dataset.page;
  if (page === "home") initHome();
  if (page === "plan") initPlanPage();
  if (page === "report") initReport();
  if (page === "history") initHistory();
  if (page === "dashboard") initDashboard();
});
