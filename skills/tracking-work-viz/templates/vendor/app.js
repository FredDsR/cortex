// Entry point. Loads data, renders tree + content pane. Graph + watch wired later.

const STATUS_ORDER = ["in_progress", "open", "blocked", "resolved", "unknown"];

let cy = null;  // Cytoscape instance, lazily created

const state = {
  data: null,
  selection: null,        // { kind: "session"|"task", sessionSlug, taskSlug? }
  collapsedSessions: new Set(),
  hideClosed: false,
  showArchive: false,
  treeCollapsed: false,
  graphCollapsed: false,
  search: "",             // free-text filter against session/task slugs
  chips: {
    blocked: true,
    related: true,
    follows: true,
    mentions: false,
    global: false,
  },
};

async function loadData() {
  if (window.VIZ_MODE === "static") return window.VIZ_DATA;
  const r = await fetch("/data.json");
  return await r.json();
}

function _matchesSearch(slug) {
  if (!state.search) return true;
  return slug.toLowerCase().includes(state.search.toLowerCase());
}

function visibleTasks(session) {
  let tasks = session.tasks;
  if (state.hideClosed) {
    tasks = tasks.filter(t => t.status !== "resolved");
  }
  if (state.search) {
    // Show tasks that match OR keep all tasks if the parent session matches.
    const sessMatches = _matchesSearch(session.slug);
    if (!sessMatches) tasks = tasks.filter(t => _matchesSearch(t.slug));
  }
  return tasks;
}

function visibleSessions(ws) {
  let sess = ws.sessions.filter(s => state.showArchive || !s.archived);
  if (state.search) {
    sess = sess.filter(s => {
      if (_matchesSearch(s.slug)) return true;
      return s.tasks.some(t => _matchesSearch(t.slug));
    });
  }
  return sess;
}

function _toggleBtn(label, isActive, onClick) {
  const b = document.createElement("button");
  b.textContent = label;
  if (isActive) b.classList.add("active");
  b.onclick = onClick;
  return b;
}

function renderTopbar() {
  const ws = state.data;
  // Target #topbar-controls, not #topbar, so the chip markup stays intact.
  const bar = document.getElementById("topbar-controls");
  bar.innerHTML = "";

  const titleGroup = document.createElement("div");
  titleGroup.className = "group";
  const back = document.createElement("a");
  back.className = "back-link";
  back.href = "dashboard.html";
  back.textContent = "← dashboard";
  back.title = "Back to ~/.work/ overview";
  titleGroup.appendChild(back);

  const h = document.createElement("span");
  h.className = "ws-title";
  h.innerHTML = `<span class="ws-prefix">workspace:</span>`;
  titleGroup.appendChild(h);

  const slugs = (ws.available_workspaces && ws.available_workspaces.length > 1)
    ? ws.available_workspaces : null;
  if (slugs) {
    const sel = document.createElement("select");
    sel.className = "ws-switcher";
    sel.title = "Switch workspace";
    for (const s of slugs) {
      const opt = document.createElement("option");
      opt.value = s;
      opt.textContent = s;
      if (s === ws.slug) opt.selected = true;
      sel.appendChild(opt);
    }
    sel.onchange = () => { window.location.href = `${sel.value}.html`; };
    titleGroup.appendChild(sel);
  } else {
    const slugLbl = document.createElement("strong");
    slugLbl.className = "ws-slug-static";
    slugLbl.textContent = ws.slug;
    titleGroup.appendChild(slugLbl);
  }

  bar.appendChild(titleGroup);

  // Search box (middle)
  const searchGroup = document.createElement("div");
  searchGroup.className = "group search-group";
  const searchInput = document.createElement("input");
  searchInput.type = "search";
  searchInput.placeholder = "Filter sessions / tasks...";
  searchInput.value = state.search;
  searchInput.className = "search-input";
  searchInput.oninput = (e) => {
    state.search = e.target.value;
    // Only re-render the body; leave the topbar alone so the input keeps focus.
    renderBody();
  };
  searchGroup.appendChild(searchInput);
  bar.appendChild(searchGroup);

  const spacer = document.createElement("span");
  spacer.className = "spacer";
  bar.appendChild(spacer);

  const panes = document.createElement("div");
  panes.className = "group";
  const panesLbl = document.createElement("span");
  panesLbl.className = "group-label";
  panesLbl.textContent = "panes";
  panes.appendChild(panesLbl);
  panes.appendChild(_toggleBtn(
    state.treeCollapsed ? "Show tree" : "Hide tree",
    state.treeCollapsed,
    () => { state.treeCollapsed = !state.treeCollapsed; render(); }
  ));
  panes.appendChild(_toggleBtn(
    state.graphCollapsed ? "Show graph" : "Hide graph",
    state.graphCollapsed,
    () => { state.graphCollapsed = !state.graphCollapsed; render(); }
  ));
  bar.appendChild(panes);

  const filters = document.createElement("div");
  filters.className = "group";
  const filtersLbl = document.createElement("span");
  filtersLbl.className = "group-label";
  filtersLbl.textContent = "filters";
  filters.appendChild(filtersLbl);
  filters.appendChild(_toggleBtn(
    "Hide closed",
    state.hideClosed,
    () => { state.hideClosed = !state.hideClosed; render(); }
  ));
  filters.appendChild(_toggleBtn(
    "Show archive",
    state.showArchive,
    () => { state.showArchive = !state.showArchive; render(); }
  ));
  bar.appendChild(filters);
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
    const sessLbl = document.createElement("span");
    sessLbl.className = "tree-label";
    sessLbl.textContent = sess.slug;
    sessRow.title = sess.slug;
    sessRow.appendChild(sessLbl);
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
        const taskLbl = document.createElement("span");
        taskLbl.className = "tree-label";
        taskLbl.textContent = t.slug;
        taskRow.title = t.slug;
        taskRow.appendChild(taskLbl);
        taskRow.onclick = () => {
          state.selection = { kind: "task", sessionSlug: sess.slug, taskSlug: t.slug };
          render();
        };
        pane.appendChild(taskRow);
      }
    }
  }
}

function _stripLeadingFields(body) {
  // Strip the leading **Key:** value / **Key**: value lines that we already render in the fields panel.
  // Stops at the first non-blank, non-field line so the rest of the body is preserved verbatim.
  const lines = body.split("\n");
  let i = 0;
  // Skip the first leading H1 (task title) since we render it as content-title.
  let titleSkipped = false;
  if (i < lines.length && /^#\s+/.test(lines[i])) {
    titleSkipped = true;
    i++;
    while (i < lines.length && lines[i].trim() === "") i++;
  }
  const fieldRe = /^\s*\*\*[^*:]+(?::\*\*|\*\*:)\s*.*$/;
  while (i < lines.length) {
    const line = lines[i];
    if (line.trim() === "") { i++; continue; }
    if (fieldRe.test(line)) { i++; continue; }
    break;
  }
  return { rest: lines.slice(i).join("\n"), strippedTitle: titleSkipped };
}

function _renderFields(parent, entries) {
  if (!entries.length) return;
  const grid = document.createElement("div");
  grid.className = "content-fields";
  for (const [k, v] of entries) {
    const key = document.createElement("div");
    key.className = "field-key";
    key.textContent = k;
    const val = document.createElement("div");
    val.className = "field-val";
    val.textContent = v;
    grid.appendChild(key);
    grid.appendChild(val);
  }
  parent.appendChild(grid);
}

function _bodyTitle(body, fallback) {
  const m = body.match(/^#\s+(.+?)\s*$/m);
  return m ? m[1] : fallback;
}

function renderContent() {
  const pane = document.getElementById("content-pane");
  pane.innerHTML = "";
  if (!state.selection) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    const hasSessions = state.data && (state.data.sessions || []).some(s => !s.archived);
    empty.textContent = hasSessions
      ? "Select a session or task on the left."
      : "This workspace has no sessions yet. Start one with the tracking-work skill.";
    pane.appendChild(empty);
    return;
  }
  const sess = state.data.sessions.find(s => s.slug === state.selection.sessionSlug);
  if (!sess) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "(no longer present)";
    pane.appendChild(empty);
    return;
  }

  if (state.selection.kind === "session") {
    const header = document.createElement("div");
    header.className = "content-header";
    const kicker = document.createElement("div");
    kicker.className = "content-kicker";
    kicker.textContent = `session ${sess.archived ? "(archived)" : ""}`;
    header.appendChild(kicker);
    const title = document.createElement("h2");
    title.className = "content-title";
    title.appendChild(statusPill(aggregateSessionStatus(sess)));
    title.appendChild(document.createTextNode(_bodyTitle(sess.summary_text || "", sess.slug)));
    header.appendChild(title);
    _renderFields(header, Object.entries(sess.summary_meta || {}));
    pane.appendChild(header);

    const { rest } = _stripLeadingFields(sess.summary_text || "");
    const md = document.createElement("div");
    md.className = "markdown-body";
    md.innerHTML = window.marked.parse(rest || "(empty SUMMARY.md)");
    pane.appendChild(md);
    rewriteIntraTaskLinks(md, sess.slug);
    return;
  }

  // task
  const task = sess.tasks.find(t => t.slug === state.selection.taskSlug);
  if (!task) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "(task no longer present)";
    pane.appendChild(empty);
    return;
  }

  const header = document.createElement("div");
  header.className = "content-header";
  const kicker = document.createElement("div");
  kicker.className = "content-kicker";
  kicker.textContent = `task in ${sess.slug}`;
  header.appendChild(kicker);
  const title = document.createElement("h2");
  title.className = "content-title";
  title.appendChild(statusPill(task.status));
  title.appendChild(document.createTextNode(_bodyTitle(task.body || "", task.slug)));
  header.appendChild(title);
  _renderFields(header, Object.entries(task.inline_fields || {}));
  pane.appendChild(header);

  const { rest } = _stripLeadingFields(task.body || "");
  const md = document.createElement("div");
  md.className = "markdown-body";
  md.innerHTML = window.marked.parse(rest || "");
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

function renderBody() {
  // Sync layout grid to current pane state so collapsed panes don't reserve empty space.
  const layoutEl = document.getElementById("layout");
  if (layoutEl) {
    layoutEl.classList.toggle("tree-collapsed", state.treeCollapsed);
    layoutEl.classList.toggle("graph-collapsed", state.graphCollapsed);
  }
  renderTree();
  // Re-fit the graph after a pane toggle since the available width changes.
  if (window._cyRefit) window._cyRefit();
  renderGraph();
  renderContent();
}

function render() {
  renderTopbar();
  renderBody();
}

function _shortTaskLabel(slug) {
  return slug.startsWith("task-") ? slug.slice(5) : slug;
}

// Build Cytoscape elements from a cy_data mode object.
function buildCyElements(modeData) {
  const elements = [];
  for (const node of (modeData.nodes || [])) {
    elements.push({
      data: {
        id: node.id,
        label: _shortTaskLabel(node.label || node.id.split("/").pop()),
        kind: "task",
        status: node.status || "unknown",
        ws: node.ws || "",
        session: node.session || "",
        ghost: node.ghost ? "true" : "false",
      },
    });
  }
  for (const edge of (modeData.edges || [])) {
    elements.push({
      data: {
        id: edge.id || `e:${edge.source}:${edge.target}:${edge.kind}`,
        source: edge.source,
        target: edge.target,
        kind: edge.kind,
        resolved: edge.resolved ? "true" : "false",
      },
    });
  }
  return elements;
}

const _DAGRE_LAYOUT = {
  name: "dagre",
  rankDir: "LR",
  nodeSep: 14,
  rankSep: 110,
  edgeSep: 8,
  padding: 28,
  fit: true,
};

// Replace current graph elements with the provided mode data and re-run layout.
function renderMode(cyInst, modeData) {
  if (!cyInst) return;
  const _z = cyInst.zoom();
  const _p = cyInst.pan();
  cyInst.elements().remove();
  cyInst.add(buildCyElements(modeData));
  cyInst.layout(_DAGRE_LAYOUT).run();
  cyInst.zoom(_z);
  cyInst.pan(_p);
}

// Toggle edge display based on state.chips.
function syncEdgeVisibility(cyInst) {
  if (!cyInst) return;
  const kindMap = {
    blocked: "blocked",
    related: "related",
    follows: "follows",
    mentions: "mentions",
  };
  for (const [chipKey, edgeKind] of Object.entries(kindMap)) {
    const show = state.chips[chipKey];
    cyInst.edges(`[kind = "${edgeKind}"]`).style("display", show ? "element" : "none");
  }
}

// Wire click handlers for the five chip buttons.
function bindChips(cyInst, cyData) {
  const kindChips = [
    { id: "chip-blocked", key: "blocked" },
    { id: "chip-related", key: "related" },
    { id: "chip-follows", key: "follows" },
    { id: "chip-mentions", key: "mentions" },
  ];
  for (const { id, key } of kindChips) {
    const el = document.getElementById(id);
    if (!el) continue;
    el.addEventListener("click", () => {
      state.chips[key] = !state.chips[key];
      el.classList.toggle("on", state.chips[key]);
      el.setAttribute("aria-pressed", state.chips[key] ? "true" : "false");
      syncEdgeVisibility(cyInst);
    });
  }
  const globalEl = document.getElementById("chip-global");
  if (globalEl) {
    globalEl.addEventListener("click", () => {
      state.chips.global = !state.chips.global;
      globalEl.classList.toggle("on", state.chips.global);
      globalEl.setAttribute("aria-pressed", state.chips.global ? "true" : "false");
      const modeName = state.chips.global ? "global" : "local";
      const modeData = (cyData.modes && cyData.modes[modeName]) || { nodes: [], edges: [] };
      renderMode(cyInst, modeData);
      syncEdgeVisibility(cyInst);
    });
  }
}

function renderGraph() {
  const pane = document.getElementById("graph-pane");
  pane.classList.toggle("hidden", state.graphCollapsed);
  if (state.graphCollapsed) return;

  if (!cy) {
    // Register dagre extension once. The UMD bundle from unpkg exposes it as window.cytoscapeDagre.
    if (window.cytoscape && window.cytoscapeDagre && !window._cyDagreRegistered) {
      window.cytoscape.use(window.cytoscapeDagre);
      window._cyDagreRegistered = true;
    }
    pane.innerHTML = '<div id="cy-host"></div>';

    // Read the cy_data that was set during init.
    const cyData = window.__CY_DATA__ || { modes: { local: { nodes: [], edges: [] }, global: { nodes: [], edges: [] } }, default_mode: "local" };
    const defaultModeName = state.chips.global ? "global" : (cyData.default_mode || "local");
    const defaultModeData = (cyData.modes && cyData.modes[defaultModeName]) || { nodes: [], edges: [] };

    cy = window.cytoscape({
      container: document.getElementById("cy-host"),
      wheelSensitivity: 0.25,
      style: [
        // All nodes: label, font, color.
        { selector: "node", style: {
            "label": "data(label)",
            "font-size": 11,
            "font-family": "-apple-system, BlinkMacSystemFont, Segoe UI, system-ui, sans-serif",
            "text-valign": "center",
            "text-halign": "center",
            "color": "#ffffff",
            "text-outline-width": 0,
        }},
        // Task nodes: small dot with label to the right.
        { selector: 'node[kind = "task"]', style: {
            "shape": "ellipse",
            "background-color": "#8a929c",
            "width": 16,
            "height": 16,
            "border-width": 2,
            "border-color": "#ffffff",
            "label": "data(label)",
            "color": "#1f2933",
            "text-valign": "center",
            "text-halign": "right",
            "text-margin-x": 6,
            "font-size": 10.5,
            "text-wrap": "none",
        }},
        { selector: 'node[kind = "task"][status = "in_progress"]', style: { "background-color": "#1f7ae0" } },
        { selector: 'node[kind = "task"][status = "blocked"]', style: { "background-color": "#e53935" } },
        { selector: 'node[kind = "task"][status = "resolved"]', style: { "background-color": "#2e9358", "opacity": 0.7 } },
        { selector: 'node[kind = "task"][status = "open"]', style: { "background-color": "#9aa3ad" } },
        // Ghost (cross-WS) nodes: dashed border, faded.
        { selector: 'node[ghost = "true"]', style: {
            "border-style": "dashed",
            "border-color": "#9aa3ad",
            "border-width": 2,
            "opacity": 0.6,
            "color": "#8a929c",
        }},
        { selector: ":selected", style: { "border-width": 3, "border-color": "#f1c40f" } },
        // Base edge style.
        { selector: "edge", style: {
            "width": 1.4,
            "line-color": "#cdd2da",
            "target-arrow-shape": "triangle",
            "target-arrow-color": "#cdd2da",
            "arrow-scale": 0.8,
            "curve-style": "bezier",
        }},
        // Per-kind edge styles.
        { selector: 'edge[kind = "blocked"]', style: {
            "line-color": "#e53935",
            "target-arrow-color": "#e53935",
            "line-style": "solid",
            "width": 1.8,
        }},
        { selector: 'edge[kind = "related"]', style: {
            "line-color": "#9aa3ad",
            "target-arrow-color": "#9aa3ad",
            "line-style": "solid",
            "width": 1.4,
        }},
        { selector: 'edge[kind = "follows"]', style: {
            "line-color": "#9aa3ad",
            "target-arrow-color": "#9aa3ad",
            "line-style": "dashed",
            "width": 1.4,
        }},
        { selector: 'edge[kind = "mentions"]', style: {
            "line-color": "#cdd2da",
            "target-arrow-color": "#cdd2da",
            "line-style": "dotted",
            "width": 1.4,
        }},
      ],
      layout: _DAGRE_LAYOUT,
      elements: buildCyElements(defaultModeData),
    });

    // Fit on initial render so the workspace uses the full pane (clamped so a single-node
    // workspace doesn't blow up to fill the whole viewport).
    const _fitClamped = () => {
      cy.fit(undefined, 24);
      if (cy.zoom() > 1.4) { cy.zoom(1.4); cy.center(); }
    };
    cy.ready(_fitClamped);
    // Re-fit on window resize / pane toggle so the graph keeps using the full area.
    if (!window._cyResizeAttached) {
      window._cyResizeAttached = true;
      let _resizeT = null;
      const refit = () => {
        if (_resizeT) clearTimeout(_resizeT);
        _resizeT = setTimeout(() => {
          if (cy && !state.graphCollapsed) { cy.resize(); _fitClamped(); }
        }, 100);
      };
      window.addEventListener("resize", refit);
      window._cyRefit = refit;
    }

    cy.on("tap", "node", (ev) => {
      const d = ev.target.data();
      // Ghost (cross-WS) nodes: ignore taps to avoid crashes on missing session data.
      if (d.ghost === "true") return;
      if (d.kind === "task") {
        // id is "ws/session/task-slug" — extract session and task slugs.
        const sessionSlug = d.session || (d.id.split("/").slice(0, -1).pop());
        const taskSlug = d.id.split("/").pop();
        state.selection = { kind: "task", sessionSlug, taskSlug };
        render();
      }
    });

    // Wire chips and apply initial visibility.
    bindChips(cy, cyData);
    syncEdgeVisibility(cy);
  } else {
    // Graph already initialised: just sync chip visibility (mode changes go through renderMode).
    syncEdgeVisibility(cy);
  }

  // Sync selection ring to graph.
  cy.nodes().unselect();
  if (state.selection && state.selection.kind === "task") {
    // The new task-centric id format is "ws/session/taskSlug".
    // Try to find the node by searching for one whose id ends with the task slug in the right session.
    const candidates = cy.nodes().filter(n => {
      const d = n.data();
      if (d.ghost === "true") return false;
      const parts = d.id.split("/");
      return parts[parts.length - 1] === state.selection.taskSlug &&
             (d.session === state.selection.sessionSlug || parts[parts.length - 2] === state.selection.sessionSlug);
    });
    if (candidates.length) candidates.first().select();
  }
}

function attachLiveReload() {
  if (window.VIZ_MODE !== "dynamic" || typeof EventSource === "undefined") return;
  const es = new EventSource("/events");
  es.addEventListener("change", async () => {
    state.data = await loadData();
    render();
  });
  es.onerror = () => {
    // Browser will auto-retry. Optional: show a small indicator.
  };
}

(async function init() {
  state.data = await loadData();
  const ws = state.data;
  const firstSess = ws.sessions.find(s => !s.archived);
  if (firstSess) state.selection = { kind: "session", sessionSlug: firstSess.slug };
  render();
  attachLiveReload();
})();
