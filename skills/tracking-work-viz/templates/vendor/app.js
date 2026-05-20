(function () {
  'use strict';

  var STORE = { cy: null, payload: null, layout: 'concentric-hier',
                rootPrefix: '', contentBase: '', wikilinkIndex: new Map(),
                selectedId: null };
  var KIND_RADIUS = { root: 0, workspace: 320, session: 600, task: 1050,
                      memory: 600, workbench: 600 };
  var SIBLING_GAP_FRAC = 0.28;
  var MAX_LABEL_CHARS = 22;

  function parsePayload() {
    var node = document.getElementById('__SCOPE__');
    if (!node) throw new Error('missing __SCOPE__ payload');
    return JSON.parse(node.textContent);
  }

  function readFragment() {
    var hash = window.location.hash || '';
    var params = {};
    hash.replace(/^#/, '').split('&').forEach(function (kv) {
      var eq = kv.indexOf('=');
      if (eq < 0) return;
      params[kv.slice(0, eq)] = kv.slice(eq + 1);
    });
    return params;
  }

  function writeFragment(params) {
    var parts = [];
    Object.keys(params).sort().forEach(function (k) {
      if (params[k] !== undefined && params[k] !== null) {
        parts.push(k + '=' + params[k]);
      }
    });
    window.location.hash = parts.join('&');
  }

  function updateFragment(updates) {
    var p = readFragment();
    Object.keys(updates).forEach(function (k) { p[k] = updates[k]; });
    writeFragment(p);
  }

  // ---- Tree ----------------------------------------------------------------

  function renderTree(rootNodes, scopeId) {
    var aside = document.getElementById('tree');
    aside.innerHTML = '';
    var toolbar = document.createElement('div');
    toolbar.id = 'tree-toolbar';
    toolbar.innerHTML =
      '<button class="tree-toolbtn" data-cmd="collapse" title="Collapse one level">−</button>' +
      '<button class="tree-toolbtn" data-cmd="expand" title="Expand one level">+</button>' +
      '<span class="tree-depth-label" id="tree-depth-label"></span>';
    aside.appendChild(toolbar);
    var ul = document.createElement('ul');
    var maxDepth = 0;
    function rec(n, parent, depth) {
      if (depth > maxDepth) maxDepth = depth;
      var li = document.createElement('li');
      li.dataset.depth = depth;
      var hasChildren = n.children && n.children.length > 0;
      if (hasChildren) li.classList.add('has-children');
      var row = document.createElement('div');
      row.className = 'tree-row';
      var arrow = document.createElement('span');
      arrow.className = hasChildren ? 'tree-arrow' : 'tree-arrow tree-arrow-empty';
      arrow.textContent = hasChildren ? '▾' : '';
      if (hasChildren) {
        arrow.addEventListener('click', function (ev) {
          ev.stopPropagation();
          li.classList.toggle('collapsed');
        });
      }
      row.appendChild(arrow);
      var el = document.createElement('span');
      el.className = 'tree-node kind-' + n.kind;
      if (n.id === scopeId) el.classList.add('current');
      el.textContent = n.label;
      el.dataset.id = n.id;
      el.dataset.kind = n.kind;
      if (n.contentPath) el.dataset.contentPath = n.contentPath;
      if (n.href) el.dataset.href = n.href;
      el.addEventListener('click', function (ev) { onTreeClick(n, ev); });
      row.appendChild(el);
      li.appendChild(row);
      if (hasChildren) {
        var sub = document.createElement('ul');
        n.children.forEach(function (c) { rec(c, sub, depth + 1); });
        li.appendChild(sub);
      }
      parent.appendChild(li);
    }
    rootNodes.forEach(function (n) { rec(n, ul, 0); });
    aside.appendChild(ul);

    // Stepwise depth controller. The buttons are asymmetric to match how a
    // user mentally navigates a tree:
    //   + raises everyone to (min visible depth + 1) — open closed branches,
    //     even at the cost of collapsing deeper branches that were further
    //     open, because the user is asking for a uniform view at the next
    //     level.
    //   - lowers only the deepest visible level by 1 — close just the
    //     deepest branches, leave shallower branches alone.
    STORE.treeMaxDepth = maxDepth;

    function isVisibleLi(li) {
      var p = li.parentElement;
      while (p && p !== aside) {
        if (p.tagName === 'LI' && p.classList.contains('collapsed')) return false;
        p = p.parentElement;
      }
      return true;
    }
    function visibleHasChildren() {
      return Array.from(aside.querySelectorAll('li.has-children')).filter(isVisibleLi);
    }
    function setUniformDepth(target) {
      aside.querySelectorAll('li.has-children').forEach(function (li) {
        var d = parseInt(li.dataset.depth, 10);
        if (d >= target) li.classList.add('collapsed');
        else li.classList.remove('collapsed');
      });
      updateDepthLabel();
    }
    function stepExpand() {
      var coll = visibleHasChildren().filter(function (li) { return li.classList.contains('collapsed'); });
      if (coll.length === 0) return;
      var minD = Math.min.apply(null, coll.map(function (li) { return parseInt(li.dataset.depth, 10); }));
      setUniformDepth(minD + 1);
    }
    function stepCollapse() {
      var open = visibleHasChildren().filter(function (li) { return !li.classList.contains('collapsed'); });
      if (open.length === 0) return;
      var maxD = Math.max.apply(null, open.map(function (li) { return parseInt(li.dataset.depth, 10); }));
      open.forEach(function (li) {
        if (parseInt(li.dataset.depth, 10) === maxD) li.classList.add('collapsed');
      });
      updateDepthLabel();
    }
    function updateDepthLabel() {
      var label = document.getElementById('tree-depth-label');
      if (!label) return;
      // Effective visible depth per branch = depth of first .collapsed ancestor,
      // or treeMaxDepth if fully open. Show min-max range when they differ.
      var hc = visibleHasChildren();
      var openDepths = hc.filter(function (li) { return !li.classList.contains('collapsed'); })
                          .map(function (li) { return parseInt(li.dataset.depth, 10) + 1; });
      var collDepths = hc.filter(function (li) { return li.classList.contains('collapsed'); })
                          .map(function (li) { return parseInt(li.dataset.depth, 10); });
      var maxV = openDepths.length ? Math.max.apply(null, openDepths) : 0;
      var minV = collDepths.length ? Math.min.apply(null, collDepths) : maxV;
      // If every branch is fully expanded, both equal treeMaxDepth.
      if (collDepths.length === 0) minV = maxV;
      label.textContent = (minV === maxV)
        ? minV + ' / ' + STORE.treeMaxDepth
        : minV + '–' + maxV + ' / ' + STORE.treeMaxDepth;
    }
    updateDepthLabel();
    toolbar.querySelectorAll('.tree-toolbtn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (btn.dataset.cmd === 'expand') stepExpand();
        else stepCollapse();
      });
    });
  }

  function relHref(href) {
    var depth = window.location.pathname.split('/').filter(Boolean).length - 1;
    if (depth <= 0) return href;
    return Array(depth).fill('..').join('/') + '/' + href;
  }

  function onTreeClick(n, ev) {
    ev.preventDefault();
    var cy = STORE.cy;
    var scope = STORE.payload && STORE.payload.scope;
    // Navigate when:
    //  - target node is not in the current graph (need to load a wider scope), OR
    //  - user clicked a higher-scope node than we're on (e.g. workspace from
    //    a session page, or root from any deeper page) so the dashboard at
    //    that scope shows the full subtree.
    var widerScope = (
      (n.kind === 'root' && scope !== 'root') ||
      (n.kind === 'workspace' && scope === 'session' &&
        STORE.payload.scopeId.indexOf(n.id) === 0)
    );
    var inGraph = cy && cy.getElementById(n.id).length > 0;
    if ((!inGraph || widerScope) && n.href) {
      window.location.href = relHref(n.href);
      return;
    }
    if (inGraph) {
      var coll = clusterFor(cy, n);
      if (coll && coll.length > 0) {
        cy.animate({ fit: { eles: coll, padding: 40 } },
                   { duration: 300, easing: 'ease-in-out' });
      }
    }
    if (n.contentPath) {
      loadContent(n.contentPath);  // also calls setSelected via the derived id
    } else {
      setSelected(n.id);
    }
  }

  function clusterFor(cy, n) {
    if (n.kind === 'root') return cy.elements();
    var id = n.id;
    var parts = id.split('/');
    var ws = parts[0];
    if (n.kind === 'workspace') {
      return cy.nodes().filter(function (el) {
        var d = el.data('id') || '';
        return d === ws + '/' || d.indexOf(ws + '/') === 0;
      });
    }
    if (n.kind === 'session' || n.kind === 'task') {
      var sessId = parts[0] + '/' + parts[1] + '/';
      return cy.nodes().filter(function (el) {
        var d = el.data('id') || '';
        return d === sessId || d.indexOf(sessId) === 0;
      });
    }
    return cy.collection();
  }

  // ---- Hierarchical concentric positions ----------------------------------

  function computeHierPositions(nodes, edges) {
    var byId = new Map(nodes.map(function (n) { return [n.id, n]; }));
    var children = new Map(nodes.map(function (n) { return [n.id, []]; }));
    edges.forEach(function (e) {
      if (e.kind !== 'contains') return;
      if (byId.has(e.source) && byId.has(e.target)) {
        children.get(e.source).push(e.target);
      }
    });
    children.forEach(function (v) { v.sort(); });

    var root = nodes.find(function (n) { return n.kind === 'root'; });
    var pos = new Map();
    if (!root) return pos;
    pos.set(root.id, { x: 0, y: 0 });

    var leafCount = new Map();
    function countLeaves(id) {
      if (leafCount.has(id)) return leafCount.get(id);
      var kids = children.get(id) || [];
      var n = kids.length === 0 ? 1 : kids.reduce(function (a, k) { return a + countLeaves(k); }, 0);
      leafCount.set(id, n);
      return n;
    }
    countLeaves(root.id);

    function place(id, a0, a1) {
      var node = byId.get(id);
      var mid = (a0 + a1) / 2;
      var r = KIND_RADIUS[node.kind];
      if (r === undefined) r = 600;
      pos.set(id, { x: r * Math.cos(mid), y: r * Math.sin(mid) });
      var kids = children.get(id) || [];
      var total = kids.reduce(function (s, k) { return s + leafCount.get(k); }, 0);
      var span = a1 - a0;
      var gapAngle = kids.length > 1 ? span * SIBLING_GAP_FRAC : 0;
      var perGap = kids.length > 1 ? gapAngle / (kids.length - 1) : 0;
      var contentSpan = span - gapAngle;
      var cursor = a0;
      kids.forEach(function (k, i) {
        var share = contentSpan * (leafCount.get(k) / (total || 1));
        place(k, cursor, cursor + share);
        cursor += share + (i < kids.length - 1 ? perGap : 0);
      });
    }
    place(root.id, -Math.PI, Math.PI);
    return pos;
  }

  // ---- Graph ---------------------------------------------------------------

  function edgeStyle(kind) {
    switch (kind) {
      case 'contains': return { 'line-color': '#dde2e8', 'width': 1, 'opacity': 0.4,
                                 'target-arrow-shape': 'none' };
      case 'blocked':  return { 'line-color': '#e53935', 'width': 1.5,
                                 'target-arrow-shape': 'triangle', 'target-arrow-color': '#e53935' };
      case 'related':  return { 'line-color': '#5a6573', 'width': 1.2,
                                 'target-arrow-shape': 'triangle', 'target-arrow-color': '#5a6573' };
      case 'follows':  return { 'line-color': '#1f2933', 'width': 1.2, 'line-style': 'dashed',
                                 'target-arrow-shape': 'triangle', 'target-arrow-color': '#1f2933' };
      case 'mentions': return { 'line-color': '#1f7ae0', 'width': 1, 'line-style': 'dotted',
                                 'target-arrow-shape': 'triangle', 'target-arrow-color': '#1f7ae0' };
    }
    return {};
  }

  function nodeStyleByKind(kind) {
    // Labels are always visible. Task labels truncate with ellipsis at the
    // node's text-max-width and the underlying label string is shortened to
    // MAX_LABEL_CHARS before reaching the renderer, so dense clusters still
    // get readable per-node text without smearing across neighbors.
    var s = {
      'label': 'data(label)',
      'font-size': 10,
      'text-valign': 'bottom',
      'text-halign': 'center',
      'text-margin-y': 4,
      'text-wrap': 'ellipsis',
      'text-max-width': '110px',
      'text-background-color': '#ffffff',
      'text-background-opacity': 0.92,
      'text-background-padding': 3,
      'text-background-shape': 'roundrectangle',
      'text-border-opacity': 0,
      'background-color': 'data(tint)',
      'border-width': 1,
      'border-color': '#5a6573',
      'shape': 'ellipse',
      'width': 26, 'height': 26,
      'color': '#1f2933',
    };
    if (kind === 'workspace') {
      s['width'] = 48; s['height'] = 48;
      s['font-size'] = 12; s['text-valign'] = 'center'; s['text-margin-y'] = 0;
      s['text-background-opacity'] = 0;
      s['font-weight'] = 600;
      s['border-width'] = 2;
    }
    if (kind === 'session') {
      s['width'] = 38; s['height'] = 38;
      s['font-size'] = 11; s['text-valign'] = 'center'; s['text-margin-y'] = 0;
      s['text-background-opacity'] = 0;
      s['border-width'] = 1.5;
    }
    if (kind === 'task') {
      s['width'] = 24; s['height'] = 24;
    }
    if (kind === 'root') {
      s['background-color'] = '#1f2933'; s['color'] = '#fff';
      s['width'] = 86; s['height'] = 86; s['font-size'] = 14;
      s['text-valign'] = 'center'; s['text-margin-y'] = 0;
      s['text-background-opacity'] = 0;
      s['font-weight'] = 700;
      s['border-width'] = 0;
    }
    return s;
  }

  function shortenLabel(label) {
    if (!label || label.length <= MAX_LABEL_CHARS) return label;
    // Drop the conventional task- prefix first so the meaningful tail survives.
    var stripped = label.replace(/^task-/, '');
    if (stripped.length <= MAX_LABEL_CHARS) return stripped;
    return stripped.slice(0, MAX_LABEL_CHARS - 1) + '…';
  }

  function hashString(s) {
    var h = 0;
    for (var i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
    return Math.abs(h);
  }

  function tintForNode(node) {
    // Hue derived from the (workspace, session) pair so all tasks in a session
    // share a soft pastel, all sessions in a workspace are distinct hues, and
    // tasks of different sessions in the same workspace are visually grouped.
    if (node.kind === 'root') return '#1f2933';
    var key;
    if (node.kind === 'workspace') key = node.id.replace(/\/$/, '');
    else key = (node.id.split('/').slice(0, 2).join('/'));  // workspace/session
    var hue = hashString(key) % 360;
    var sat = node.kind === 'task' ? 35 : 50;
    var light = node.kind === 'task' ? 92 : 86;
    return 'hsl(' + hue + ', ' + sat + '%, ' + light + '%)';
  }

  function buildCy(payload) {
    var elements = [];
    payload.nodes.forEach(function (n) {
      elements.push({ group: 'nodes',
                      data: { id: n.id, label: shortenLabel(n.label),
                              fullLabel: n.label, kind: n.kind,
                              contentPath: n.contentPath,
                              tint: tintForNode(n) } });
    });
    payload.edges.forEach(function (e) {
      elements.push({ group: 'edges',
                      data: { id: e.source + '|' + e.kind + '|' + e.target,
                              source: e.source, target: e.target, kind: e.kind } });
    });
    var styles = [
      { selector: 'node', style: nodeStyleByKind('task') },
    ];
    ['root','workspace','session','task','memory','workbench'].forEach(function (k) {
      styles.push({ selector: 'node[kind="' + k + '"]', style: nodeStyleByKind(k) });
    });
    // Hover highlight: lifted to top, accented border. Labels stay visible
    // at all times so we don't toggle text-opacity here.
    styles.push({ selector: 'node.hovered', style: { 'z-index': 99,
                                                      'border-color': '#1f7ae0',
                                                      'border-width': 2.5 } });
    // Selected (currently shown in the content pane): blue halo + thick ring.
    styles.push({ selector: 'node.selected', style: {
      'z-index': 100,
      'border-color': '#1f7ae0',
      'border-width': 4,
      'border-opacity': 1,
      'overlay-color': '#1f7ae0',
      'overlay-padding': 10,
      'overlay-opacity': 0.18,
    } });
    styles.push({ selector: 'node.selected:active', style: { 'overlay-opacity': 0.18 } });
    ['contains','blocked','related','follows','mentions'].forEach(function (k) {
      styles.push({ selector: 'edge[kind="' + k + '"]', style: edgeStyle(k) });
    });
    styles.push({ selector: 'edge', style: { 'curve-style': 'bezier' } });
    styles.push({ selector: 'edge.hidden', style: { 'display': 'none' } });

    var cy = cytoscape({
      container: document.getElementById('graph'),
      elements: elements,
      style: styles,
      layout: { name: 'preset' },
    });
    cy.on('tap', 'node', function (evt) {
      var cp = evt.target.data('contentPath');
      if (cp) loadContent(cp);
    });
    cy.on('tap', function (evt) {
      // Tap on the graph background (not a node/edge) -> reset to fit-all.
      if (evt.target === cy) {
        cy.animate({ fit: { eles: cy.elements(), padding: 30 } },
                   { duration: 300, easing: 'ease-in-out' });
      }
    });
    cy.on('mouseover', 'node', function (evt) { evt.target.addClass('hovered'); });
    cy.on('mouseout', 'node', function (evt) { evt.target.removeClass('hovered'); });
    return cy;
  }

  function bindFitAllButton() {
    var btn = document.getElementById('fit-all');
    if (!btn) return;
    btn.addEventListener('click', function () {
      if (!STORE.cy) return;
      STORE.cy.animate({ fit: { eles: STORE.cy.elements(), padding: 30 } },
                       { duration: 300, easing: 'ease-in-out' });
    });
  }

  function setGraphHidden(hidden) {
    var layout = document.getElementById('layout');
    var btn = document.getElementById('toggle-graph');
    if (!layout) return;
    if (hidden) {
      layout.classList.add('graph-hidden');
      if (btn) { btn.textContent = 'Show graph'; btn.classList.add('on'); }
    } else {
      layout.classList.remove('graph-hidden');
      if (btn) { btn.textContent = 'Hide graph'; btn.classList.remove('on'); }
      if (STORE.cy) STORE.cy.resize();  // recompute viewport after layout change
    }
    updateFragment({ graph: hidden ? 'hidden' : null });
  }

  function bindToggleGraphButton() {
    var btn = document.getElementById('toggle-graph');
    if (!btn) return;
    btn.addEventListener('click', function () {
      var layout = document.getElementById('layout');
      setGraphHidden(!layout.classList.contains('graph-hidden'));
    });
  }

  function applyLayout(cy, payload, name) {
    if (name === 'cose') {
      cy.layout({
        name: 'cose', animate: false,
        nodeRepulsion: 14000, idealEdgeLength: 80, edgeElasticity: 100,
        gravity: 0.2, numIter: 2000, padding: 30,
      }).run();
    } else {
      var pos = computeHierPositions(payload.nodes, payload.edges);
      cy.nodes().forEach(function (n) {
        var p = pos.get(n.data('id'));
        if (p) n.position(p);
      });
      cy.fit(undefined, 30);
    }
    document.querySelectorAll('#layout-toggle .chip').forEach(function (b) {
      if (b.dataset.layout === name) b.classList.add('on');
      else b.classList.remove('on');
    });
  }

  // ---- Edge-kind chips -----------------------------------------------------

  function applyChipState(cy, active) {
    cy.edges().forEach(function (e) {
      var k = e.data('kind');
      if (k === 'contains') { e.removeClass('hidden'); return; }
      if (active.has(k)) e.removeClass('hidden'); else e.addClass('hidden');
    });
  }

  function bindEdgeChips(cy) {
    var params = readFragment();
    var active;
    if (params.chips !== undefined) {
      // Honor an explicit "all off" choice (chips=) as well as any subset.
      active = new Set(params.chips.split(',').filter(Boolean));
      document.querySelectorAll('#edge-chips .chip').forEach(function (el) {
        if (active.has(el.dataset.kind)) el.classList.add('on');
        else el.classList.remove('on');
      });
    } else {
      active = new Set();
      document.querySelectorAll('#edge-chips .chip.on').forEach(function (el) {
        active.add(el.dataset.kind);
      });
    }
    applyChipState(cy, active);
    document.querySelectorAll('#edge-chips .chip').forEach(function (el) {
      el.addEventListener('click', function () {
        var k = el.dataset.kind;
        if (active.has(k)) { active.delete(k); el.classList.remove('on'); }
        else { active.add(k); el.classList.add('on'); }
        applyChipState(cy, active);
        updateFragment({ chips: Array.from(active).sort().join(',') });
      });
    });
  }

  function bindLayoutToggle() {
    document.querySelectorAll('#layout-toggle .chip').forEach(function (el) {
      el.addEventListener('click', function () {
        var name = el.dataset.layout;
        STORE.layout = name;
        applyLayout(STORE.cy, STORE.payload, name);
        updateFragment({ layout: name });
      });
    });
  }

  // ---- Content pane --------------------------------------------------------

  function resolveContent(path) {
    if (!path) return path;
    if (/^https?:\/\//.test(path) || path.charAt(0) === '/') return path;
    return STORE.rootPrefix + path;
  }

  function idFromContentPath(path) {
    if (!path) return null;
    var p = path.replace(/^\//, '');
    if (p === 'index.md') return '/';
    var m;
    m = /^workspaces\/([^/]+)\/index\.md$/.exec(p);
    if (m) return m[1] + '/';
    m = /^workspaces\/([^/]+)\/sessions\/([^/]+)\/SUMMARY\.md$/.exec(p);
    if (m) return m[1] + '/' + m[2] + '/';
    m = /^workspaces\/([^/]+)\/sessions\/([^/]+)\/tasks\/([^/]+)\.md$/.exec(p);
    if (m) return m[1] + '/' + m[2] + '/task/' + m[3];
    m = /^workspaces\/([^/]+)\/sessions\/([^/]+)\/workbench\/([^/]+)\.md$/.exec(p);
    if (m) return m[1] + '/' + m[2] + '/workbench/' + m[3];
    m = /^workspaces\/([^/]+)\/memory\/([^/]+)\.md$/.exec(p);
    if (m) return m[1] + '/memory/' + m[2];
    return null;
  }

  function setSelected(id) {
    STORE.selectedId = id;
    document.querySelectorAll('#tree .tree-node.current').forEach(function (el) {
      el.classList.remove('current');
    });
    if (id) {
      var rows = document.querySelectorAll('#tree .tree-node');
      for (var i = 0; i < rows.length; i++) {
        if (rows[i].dataset.id === id) { rows[i].classList.add('current'); break; }
      }
    }
    if (STORE.cy) {
      STORE.cy.nodes('.selected').removeClass('selected');
      if (id) {
        var n = STORE.cy.getElementById(id);
        if (n && n.length) n.addClass('selected');
      }
    }
  }

  function stripFrontmatter(text) {
    if (!text.startsWith('---\n')) return text;
    var end = text.indexOf('\n---\n', 4);
    if (end < 0) return text;
    return text.slice(end + 5).replace(/^\n+/, '');
  }

  function buildWikilinkIndex(nodes) {
    // Map slug -> contentPath. First-seen wins on ties. Slug is the trailing
    // segment of the canonical id ("/task-foo" or "/session-name/" etc.).
    var idx = new Map();
    nodes.forEach(function (n) {
      if (!n.contentPath || n.ghost) return;
      var clean = n.id.replace(/\/$/, '');
      var slug = clean.indexOf('/') < 0 ? clean : clean.split('/').pop();
      if (slug && !idx.has(slug)) idx.set(slug, n.contentPath);
    });
    return idx;
  }

  function renderWikilinks(html) {
    // Post-process the rendered HTML to convert [[target]] tokens to anchors.
    // Done after marked because the bracket form is ambiguous with markdown's
    // reference-style links; doing it on rendered output avoids fighting marked.
    // Wikilink hrefs are absolute (leading slash) so the content-pane click
    // handler resolves them correctly regardless of which doc is loaded.
    return html.replace(/\[\[([^\]\n]+)\]\]/g, function (_, target) {
      var t = target.trim();
      var path = STORE.wikilinkIndex.get(t);
      if (path) {
        return '<a href="/' + path + '" class="wikilink">' + t + '</a>';
      }
      return '<span class="wikilink wikilink-broken" title="no doc for [[' + t + ']]">' + t + '</span>';
    });
  }

  function loadContent(path) {
    var pane = document.getElementById('content');
    var url = resolveContent(path);
    STORE.contentBase = url.replace(/[^/]+$/, ''); // dirname + trailing slash
    setSelected(idFromContentPath(path));
    fetch(url).then(function (r) {
      if (!r.ok) throw new Error('Could not load ' + url + ': ' + r.status);
      return r.text();
    }).then(function (txt) {
      var body = stripFrontmatter(txt);
      pane.innerHTML = renderWikilinks(marked.parse(body));
    }).catch(function (err) {
      pane.innerHTML = '<p style="color:#a00">' + err.message + '</p>';
    });
  }

  function isExternalUrl(href) {
    return /^https?:\/\//.test(href) || href.charAt(0) === '#';
  }

  function bindContentPaneLinks() {
    var pane = document.getElementById('content');
    pane.addEventListener('click', function (ev) {
      var a = ev.target.closest('a[href]');
      if (!a || !pane.contains(a)) return;
      var href = a.getAttribute('href');
      if (!href || isExternalUrl(href)) return;
      // Resolve href against the document the pane currently shows.
      var resolved;
      try {
        resolved = new URL(href, new URL(STORE.contentBase, window.location.href)).pathname;
      } catch (e) { return; }
      if (/\.md$/.test(resolved)) {
        ev.preventDefault();
        // Convert back to a path relative to the site root for loadContent.
        var rootAbs = new URL(STORE.rootPrefix || './', window.location.href).pathname;
        var relToRoot = resolved.indexOf(rootAbs) === 0 ? resolved.slice(rootAbs.length) : resolved;
        loadContent(relToRoot);
      }
      // .html links navigate natively (full reload to that shell).
    });
  }

  // ---- Boot ----------------------------------------------------------------

  function init() {
    var payload = parsePayload();
    STORE.payload = payload;
    // rootHref is page-relative and ends in "index.html". The prefix (sans
    // filename) is the path back to the site root, which all contentPaths are
    // expressed relative to.
    STORE.rootPrefix = (payload.rootHref || '').replace(/index\.html$/, '');
    STORE.wikilinkIndex = payload.wikilinks
      ? new Map(Object.entries(payload.wikilinks))
      : buildWikilinkIndex(payload.nodes);
    renderTree(payload.tree, payload.scopeId);
    var cy = buildCy(payload);
    STORE.cy = cy;
    bindEdgeChips(cy);
    bindLayoutToggle();
    bindFitAllButton();
    bindToggleGraphButton();
    bindContentPaneLinks();
    var params = readFragment();
    STORE.layout = params.layout === 'cose' ? 'cose' : 'concentric-hier';
    applyLayout(cy, payload, STORE.layout);
    if (params.graph === 'hidden') setGraphHidden(true);
    if (payload.defaultContentPath) loadContent(payload.defaultContentPath);
  }

  document.addEventListener('DOMContentLoaded', init);
})();
