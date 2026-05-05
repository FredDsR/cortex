// Entry point. Loads data, renders tree + content pane. Graph + watch wired later.

const STATUS_ORDER = ["in_progress", "open", "blocked", "resolved", "unknown"];

const state = {
  data: null,
  selection: null,        // { kind: "session"|"task", sessionSlug, taskSlug? }
  collapsedSessions: new Set(),
  hideClosed: false,
  showArchive: false,
  treeCollapsed: false,
  graphCollapsed: false,
};

async function loadData() {
  if (window.VIZ_MODE === "static") return window.VIZ_DATA;
  const r = await fetch("/data.json");
  return await r.json();
}

function visibleTasks(session) {
  let tasks = session.tasks;
  if (state.hideClosed) {
    tasks = tasks.filter(t => t.status !== "resolved");
  }
  return tasks;
}

function visibleSessions(ws) {
  return ws.sessions.filter(s => state.showArchive || !s.archived);
}

function renderTopbar() {
  const ws = state.data;
  const bar = document.getElementById("topbar");
  bar.innerHTML = "";
  const h = document.createElement("h1");
  h.textContent = `Workspace: ${ws.slug}`;
  bar.appendChild(h);

  const spacer = document.createElement("span"); spacer.className = "spacer"; bar.appendChild(spacer);

  const treeBtn = document.createElement("button");
  treeBtn.textContent = state.treeCollapsed ? "Show tree" : "Hide tree";
  treeBtn.onclick = () => { state.treeCollapsed = !state.treeCollapsed; render(); };
  bar.appendChild(treeBtn);

  const graphBtn = document.createElement("button");
  graphBtn.textContent = state.graphCollapsed ? "Show graph" : "Hide graph";
  graphBtn.onclick = () => { state.graphCollapsed = !state.graphCollapsed; render(); };
  bar.appendChild(graphBtn);

  const closedBtn = document.createElement("button");
  closedBtn.textContent = state.hideClosed ? "Show closed" : "Hide closed";
  closedBtn.onclick = () => { state.hideClosed = !state.hideClosed; render(); };
  bar.appendChild(closedBtn);

  const archBtn = document.createElement("button");
  archBtn.textContent = state.showArchive ? "Hide archive" : "Show archive";
  archBtn.onclick = () => { state.showArchive = !state.showArchive; render(); };
  bar.appendChild(archBtn);
}

function statusPill(status) {
  const span = document.createElement("span");
  span.className = `status-pill ${status}`;
  return span;
}

function aggregateSessionStatus(sess) {
  const statuses = sess.tasks.map(t => t.status);
  if (statuses.includes("in_progress")) return "in_progress";
  if (statuses.includes("blocked")) return "blocked";
  if (statuses.length && statuses.every(s => s === "resolved")) return "resolved";
  if (statuses.includes("open")) return "open";
  return "unknown";
}

function renderTree() {
  const pane = document.getElementById("tree-pane");
  pane.classList.toggle("hidden", state.treeCollapsed);
  pane.innerHTML = "";

  for (const sess of visibleSessions(state.data)) {
    const sessRow = document.createElement("div");
    sessRow.className = "tree-session";
    if (state.selection && state.selection.kind === "session" && state.selection.sessionSlug === sess.slug) {
      sessRow.classList.add("selected");
    }
    const collapsed = state.collapsedSessions.has(sess.slug);
    const caret = document.createElement("span");
    caret.className = "caret";
    caret.textContent = collapsed ? "+" : "-";
    sessRow.appendChild(caret);
    sessRow.appendChild(statusPill(aggregateSessionStatus(sess)));
    sessRow.appendChild(document.createTextNode(sess.slug));
    if (sess.active_agent_count > 1) {
      const badge = document.createElement("span");
      badge.className = "agent-badge";
      badge.textContent = `${sess.active_agent_count} agents`;
      sessRow.appendChild(badge);
    }
    if (sess.archived) {
      const tag = document.createElement("span");
      tag.className = "archived-tag";
      tag.textContent = "(archived)";
      sessRow.appendChild(tag);
    }
    sessRow.onclick = (e) => {
      // Caret toggles expansion; clicking row selects.
      if (e.target === caret) {
        if (collapsed) state.collapsedSessions.delete(sess.slug);
        else state.collapsedSessions.add(sess.slug);
      } else {
        state.selection = { kind: "session", sessionSlug: sess.slug };
      }
      render();
    };
    pane.appendChild(sessRow);

    if (!collapsed) {
      for (const t of visibleTasks(sess)) {
        const taskRow = document.createElement("div");
        taskRow.className = "tree-task";
        if (state.selection && state.selection.kind === "task" &&
            state.selection.sessionSlug === sess.slug && state.selection.taskSlug === t.slug) {
          taskRow.classList.add("selected");
        }
        taskRow.appendChild(statusPill(t.status));
        taskRow.appendChild(document.createTextNode(t.slug));
        taskRow.onclick = () => {
          state.selection = { kind: "task", sessionSlug: sess.slug, taskSlug: t.slug };
          render();
        };
        pane.appendChild(taskRow);
      }
    }
  }
}

function renderContent() {
  const pane = document.getElementById("content-pane");
  pane.innerHTML = "";
  if (!state.selection) {
    pane.textContent = "Select a session or task on the left.";
    return;
  }
  const sess = state.data.sessions.find(s => s.slug === state.selection.sessionSlug);
  if (!sess) { pane.textContent = "(no longer present)"; return; }

  if (state.selection.kind === "session") {
    const fields = document.createElement("div");
    fields.className = "content-fields";
    if (sess.summary_meta && Object.keys(sess.summary_meta).length) {
      for (const [k, v] of Object.entries(sess.summary_meta)) {
        const f = document.createElement("span");
        f.className = "field";
        f.innerHTML = `<strong>${k}:</strong> ${v}`;
        fields.appendChild(f);
      }
    }
    pane.appendChild(fields);
    const md = document.createElement("div");
    md.className = "markdown-body";
    md.innerHTML = window.marked.parse(sess.summary_text || "(empty SUMMARY.md)");
    pane.appendChild(md);
    rewriteIntraTaskLinks(md, sess.slug);
    return;
  }

  // task
  const task = sess.tasks.find(t => t.slug === state.selection.taskSlug);
  if (!task) { pane.textContent = "(task no longer present)"; return; }

  const fields = document.createElement("div");
  fields.className = "content-fields";
  for (const [k, v] of Object.entries(task.inline_fields)) {
    const f = document.createElement("span");
    f.className = "field";
    f.innerHTML = `<strong>${k}:</strong> ${v}`;
    fields.appendChild(f);
  }
  pane.appendChild(fields);
  const md = document.createElement("div");
  md.className = "markdown-body";
  md.innerHTML = window.marked.parse(task.body || "");
  pane.appendChild(md);
  rewriteIntraTaskLinks(md, sess.slug);
}

function rewriteIntraTaskLinks(rootEl, sessionSlug) {
  for (const a of rootEl.querySelectorAll("a")) {
    const href = a.getAttribute("href") || "";
    const m = href.match(/^tasks\/([a-z0-9-]+)\.md$/);
    if (m) {
      a.addEventListener("click", (ev) => {
        ev.preventDefault();
        state.selection = { kind: "task", sessionSlug, taskSlug: m[1] };
        render();
      });
    }
  }
}

function render() {
  renderTopbar();
  renderTree();
  // Graph wired in Task 10.
  renderContent();
}

(async function init() {
  state.data = await loadData();
  // default selection: first non-archived session
  const ws = state.data;
  const firstSess = ws.sessions.find(s => !s.archived);
  if (firstSess) state.selection = { kind: "session", sessionSlug: firstSess.slug };
  render();
})();
