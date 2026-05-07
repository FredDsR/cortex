(function () {
  const data = window.VIZ_DASHBOARD_DATA || { workspaces: [] };
  const workspaces = data.workspaces || [];

  function relativeTime(mtimeSecs) {
    if (!mtimeSecs) return "";
    const now = Date.now() / 1000;
    const diff = Math.max(0, now - mtimeSecs);
    if (diff < 60) return "just now";
    if (diff < 3600) return Math.floor(diff / 60) + " min ago";
    if (diff < 86400) return Math.floor(diff / 3600) + " hr ago";
    if (diff < 86400 * 14) return Math.floor(diff / 86400) + " d ago";
    return Math.floor(diff / 86400) + " d ago";
  }

  function statusBar(counts, total) {
    if (!total) return '<div class="statusbar"><div class="seg unknown" style="width:100%"></div></div>';
    const order = ["in_progress", "open", "blocked", "resolved", "unknown"];
    const segs = order
      .filter(k => counts[k] > 0)
      .map(k => `<div class="seg ${k}" style="width:${(counts[k] / total) * 100}%" title="${k.replace('_', ' ')}: ${counts[k]}"></div>`)
      .join("");
    return `<div class="statusbar">${segs}</div>`;
  }

  function legend(counts) {
    const order = ["in_progress", "open", "blocked", "resolved"];
    return order
      .filter(k => counts[k] > 0)
      .map(k => `<span><span class="dot ${k}" style="background: var(--status-${k})"></span>${counts[k]}</span>`)
      .join("");
  }

  // Aggregate header summary
  const totals = workspaces.reduce(
    (acc, ws) => {
      acc.tasks += ws.task_count || 0;
      acc.sessions += ws.session_count || 0;
      acc.agents += ws.agent_count || 0;
      const sc = ws.status_counts || {};
      acc.in_progress += sc.in_progress || 0;
      acc.blocked += sc.blocked || 0;
      acc.open += sc.open || 0;
      acc.resolved += sc.resolved || 0;
      return acc;
    },
    { tasks: 0, sessions: 0, agents: 0, in_progress: 0, blocked: 0, open: 0, resolved: 0 }
  );

  const summaryEl = document.getElementById("summary");
  if (summaryEl) {
    summaryEl.innerHTML = `
      <div class="stat"><span class="num">${workspaces.length}</span><span class="lbl">workspaces</span></div>
      <div class="stat"><span class="num">${totals.sessions}</span><span class="lbl">sessions</span></div>
      <div class="stat"><span class="num">${totals.tasks}</span><span class="lbl">tasks</span></div>
      <div class="stat"><span class="num" style="color:var(--status-in-progress)">${totals.in_progress}</span><span class="lbl">in progress</span></div>
      <div class="stat attention ${totals.blocked === 0 ? "zero" : ""}"><span class="num">${totals.blocked}</span><span class="lbl">blocked</span></div>
      <div class="stat"><span class="num" style="color:var(--status-resolved)">${totals.resolved}</span><span class="lbl">resolved</span></div>
      ${totals.agents > 0 ? `<div class="stat"><span class="num" style="color:var(--status-in-progress)">${totals.agents}</span><span class="lbl">active agents</span></div>` : ""}
    `;
  }

  // Sort: most recently touched first
  workspaces.sort((a, b) => (b.last_mtime || 0) - (a.last_mtime || 0));

  // A workspace is "idle" if it has no in-progress / blocked / open work AND is older than 7 days,
  // OR it has zero tasks AND zero agents AND is older than 7 days.
  const SEVEN_DAYS = 7 * 86400;
  const now = Date.now() / 1000;
  function isIdle(ws) {
    const sc = ws.status_counts || {};
    const live = (sc.in_progress || 0) + (sc.blocked || 0) + (sc.open || 0);
    const stale = !ws.last_mtime || (now - ws.last_mtime) > SEVEN_DAYS;
    if (ws.agent_count > 0) return false;
    if (live > 0) return false;
    return stale;
  }

  function buildRow(ws) {
    const counts = ws.status_counts || {};
    const total = ws.task_count || 0;
    const row = document.createElement("div");
    row.className = "row" + (total === 0 ? " empty-row" : "");
    row.innerHTML = `
      <div class="slug">
        <a href="${ws.slug}.html">${ws.slug}</a>
        <span class="meta">${ws.session_count} session${ws.session_count === 1 ? "" : "s"}</span>
      </div>
      <div>
        ${total === 0 ? '<span style="color:var(--text-muted);font-size:12px;">no tasks yet</span>' : statusBar(counts, total)}
        ${total === 0 ? "" : `<div class="statusbar-legend">${legend(counts)}</div>`}
      </div>
      <div class="tasks">
        ${total}
        <span class="label">tasks</span>
      </div>
      <div class="updated">
        <span class="when">${relativeTime(ws.last_mtime)}</span>
        <div style="font-size:11px;">${ws.last_updated || ""}</div>
      </div>
      <div class="agents">
        ${ws.agent_count > 0
          ? `<span class="badge">${ws.agent_count} agent${ws.agent_count === 1 ? "" : "s"}</span>`
          : '<span class="empty">idle</span>'}
      </div>
    `;
    return row;
  }

  const active = workspaces.filter(ws => !isIdle(ws));
  const idle = workspaces.filter(ws => isIdle(ws));

  const rowsEl = document.getElementById("rows");
  rowsEl.innerHTML = "";
  for (const ws of active) rowsEl.appendChild(buildRow(ws));

  const idleSection = document.getElementById("idle-section");
  const idleRowsEl = document.getElementById("idle-rows");
  const idleToggle = document.getElementById("idle-toggle");
  const idleLabel = document.getElementById("idle-toggle-label");
  if (idle.length > 0 && idleSection) {
    idleSection.style.display = "block";
    idleLabel.textContent = `${idle.length} idle workspace${idle.length === 1 ? "" : "s"}`;
    for (const ws of idle) idleRowsEl.appendChild(buildRow(ws));
    idleToggle.addEventListener("click", () => {
      const open = idleRowsEl.classList.toggle("open");
      idleToggle.classList.toggle("open", open);
    });
  }

  // Cross-workspace graph (uses window.__CY_DATA__.modes.global).
  const cyData = window.__CY_DATA__;
  const graphSection = document.getElementById("dash-graph-section");
  if (!graphSection) return;
  const globalMode = cyData && cyData.modes && cyData.modes.global;
  if (!globalMode || !globalMode.nodes || globalMode.nodes.length === 0) {
    graphSection.style.display = "none";
    return;
  }

  function _shortTaskLabel(slug) {
    return slug.startsWith("task-") ? slug.slice(5) : slug;
  }

  function buildElements(mode) {
    const elements = [];
    for (const node of mode.nodes) {
      elements.push({ data: {
        id: node.id,
        label: _shortTaskLabel(node.label || node.id.split("/").pop()),
        ws: node.ws || "",
        session: node.session || "",
        status: node.status || "unknown",
        ghost: node.ghost ? "true" : "false",
      }});
    }
    for (const edge of mode.edges) {
      elements.push({ data: {
        id: edge.id || `e:${edge.source}:${edge.target}:${edge.kind}`,
        source: edge.source, target: edge.target,
        kind: edge.kind, resolved: edge.resolved ? "true" : "false",
      }});
    }
    return elements;
  }

  if (window.cytoscape && window.cytoscapeDagre && !window._dashCyDagre) {
    window.cytoscape.use(window.cytoscapeDagre);
    window._dashCyDagre = true;
  }

  const dashCy = window.cytoscape({
    container: document.getElementById("dash-cy-host"),
    wheelSensitivity: 0.25,
    elements: buildElements(globalMode),
    layout: { name: "dagre", rankDir: "LR", nodeSep: 14, rankSep: 110, edgeSep: 8, padding: 28, fit: true },
    style: [
      { selector: "node", style: {
          "label": "data(label)", "font-size": 10, "text-valign": "center",
          "text-halign": "right", "text-margin-x": 6, "color": "#1f2933",
          "shape": "ellipse", "width": 14, "height": 14,
          "background-color": "#9aa3ad", "border-width": 2, "border-color": "#ffffff",
      }},
      { selector: 'node[status = "in_progress"]', style: { "background-color": "#1f7ae0" } },
      { selector: 'node[status = "blocked"]', style: { "background-color": "#e53935" } },
      { selector: 'node[status = "resolved"]', style: { "background-color": "#2e9358", "opacity": 0.7 } },
      { selector: 'node[status = "open"]', style: { "background-color": "#9aa3ad" } },
      { selector: 'node[ghost = "true"]', style: {
          "border-style": "dashed", "border-color": "#9aa3ad",
          "background-color": "#cdd2da", "opacity": 0.6, "color": "#7a828c",
      }},
      { selector: "edge", style: {
          "width": 1.4, "line-color": "#cdd2da",
          "target-arrow-shape": "triangle", "target-arrow-color": "#cdd2da",
          "arrow-scale": 0.8, "curve-style": "bezier",
      }},
      { selector: 'edge[kind = "blocked"]', style: {
          "line-color": "#e53935", "target-arrow-color": "#e53935", "width": 1.8,
      }},
      { selector: 'edge[kind = "related"]', style: {
          "line-color": "#9aa3ad", "target-arrow-color": "#9aa3ad",
      }},
      { selector: 'edge[kind = "follows"]', style: {
          "line-color": "#9aa3ad", "target-arrow-color": "#9aa3ad", "line-style": "dashed",
      }},
      { selector: 'edge[kind = "mentions"]', style: {
          "line-color": "#cdd2da", "target-arrow-color": "#cdd2da", "line-style": "dotted",
      }},
    ],
  });

  // Initial chip state matches workspace page defaults: mentions OFF.
  const chipState = { blocked: true, related: true, follows: true, mentions: false };

  function syncEdgeVisibility() {
    for (const kind of ["blocked", "related", "follows", "mentions"]) {
      dashCy.edges(`[kind = "${kind}"]`).style("display", chipState[kind] ? "element" : "none");
    }
  }
  syncEdgeVisibility();

  for (const kind of ["blocked", "related", "follows", "mentions"]) {
    const btn = document.getElementById("chip-" + kind);
    if (!btn) continue;
    btn.addEventListener("click", () => {
      chipState[kind] = !chipState[kind];
      btn.classList.toggle("on", chipState[kind]);
      btn.setAttribute("aria-pressed", chipState[kind] ? "true" : "false");
      syncEdgeVisibility();
    });
  }

  // Tap-to-open: clicking a real (non-ghost) node opens that workspace's page.
  dashCy.on("tap", "node", (ev) => {
    const d = ev.target.data();
    if (d.ghost === "true" || !d.ws) return;
    window.location.href = d.ws + ".html";
  });
})();
