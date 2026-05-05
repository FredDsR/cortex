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

  const rowsEl = document.getElementById("rows");
  rowsEl.innerHTML = "";
  for (const ws of workspaces) {
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
    rowsEl.appendChild(row);
  }
})();
