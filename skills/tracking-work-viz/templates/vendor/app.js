(function () {
  'use strict';

  var STORE = { cy: null, payload: null, layout: 'concentric-hier' };
  var KIND_RADIUS = { root: 0, workspace: 240, session: 420, task: 700,
                      memory: 420, workbench: 420 };
  var SIBLING_GAP_FRAC = 0.18;

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
      if (params[k] !== undefined && params[k] !== null && params[k] !== '') {
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
    var ul = document.createElement('ul');
    function rec(n, parent) {
      var li = document.createElement('li');
      var el = document.createElement('span');
      el.className = 'tree-node kind-' + n.kind;
      if (n.id === scopeId) el.classList.add('current');
      el.textContent = n.label;
      el.dataset.id = n.id;
      el.dataset.kind = n.kind;
      if (n.contentPath) el.dataset.contentPath = n.contentPath;
      if (n.href) el.dataset.href = n.href;
      el.addEventListener('click', function (ev) { onTreeClick(n, ev); });
      li.appendChild(el);
      if (n.children && n.children.length) {
        var sub = document.createElement('ul');
        n.children.forEach(function (c) { rec(c, sub); });
        li.appendChild(sub);
      }
      parent.appendChild(li);
    }
    rootNodes.forEach(function (n) { rec(n, ul); });
    aside.appendChild(ul);
  }

  function relHref(href) {
    var depth = window.location.pathname.split('/').filter(Boolean).length - 1;
    if (depth <= 0) return href;
    return Array(depth).fill('..').join('/') + '/' + href;
  }

  function onTreeClick(n, ev) {
    ev.preventDefault();
    var cy = STORE.cy;
    var inGraph = cy && cy.getElementById(n.id).length > 0;
    if (!inGraph && n.href) {
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
    document.querySelectorAll('#tree .tree-node.current').forEach(function (el) {
      el.classList.remove('current');
    });
    var elNow = ev.currentTarget;
    if (elNow && elNow.classList) elNow.classList.add('current');
    if (n.contentPath) loadContent(n.contentPath);
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
    var s = {
      'label': 'data(label)',
      'font-size': 10,
      'text-valign': 'center',
      'text-halign': 'center',
      'background-color': '#ffffff',
      'border-width': 1,
      'border-color': '#5a6573',
      'shape': 'ellipse',
      'width': 24, 'height': 24,
      'color': '#1f2933',
    };
    if (kind === 'workspace') { s['background-color'] = '#eef4fb'; s['width'] = 40; s['height'] = 40; s['font-size'] = 11; }
    if (kind === 'session')   { s['background-color'] = '#f3f5fa'; s['width'] = 32; s['height'] = 32; }
    if (kind === 'task')      { s['background-color'] = '#ffffff'; }
    if (kind === 'memory')    { s['background-color'] = '#fff5d6'; }
    if (kind === 'workbench') { s['background-color'] = '#e8f7e0'; }
    if (kind === 'root')      { s['background-color'] = '#1f2933'; s['color'] = '#fff';
                                s['width'] = 56; s['height'] = 56; s['font-size'] = 12; }
    return s;
  }

  function buildCy(payload) {
    var elements = [];
    payload.nodes.forEach(function (n) {
      elements.push({ group: 'nodes',
                      data: { id: n.id, label: n.label, kind: n.kind,
                              contentPath: n.contentPath } });
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
    return cy;
  }

  function applyLayout(cy, payload, name) {
    if (name === 'cose') {
      cy.layout({
        name: 'cose', animate: false,
        nodeRepulsion: 8000, idealEdgeLength: 60, edgeElasticity: 100,
        gravity: 0.25, numIter: 1500, padding: 30,
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
    if (params.chips) {
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

  function loadContent(path) {
    var pane = document.getElementById('content');
    fetch(path).then(function (r) {
      if (!r.ok) throw new Error('Could not load ' + path + ': ' + r.status);
      return r.text();
    }).then(function (txt) {
      pane.innerHTML = marked.parse(txt);
    }).catch(function (err) {
      pane.innerHTML = '<p style="color:#a00">' + err.message + '</p>';
    });
  }

  // ---- Boot ----------------------------------------------------------------

  function init() {
    var payload = parsePayload();
    STORE.payload = payload;
    renderTree(payload.tree, payload.scopeId);
    var cy = buildCy(payload);
    STORE.cy = cy;
    bindEdgeChips(cy);
    bindLayoutToggle();
    var params = readFragment();
    STORE.layout = params.layout === 'cose' ? 'cose' : 'concentric-hier';
    applyLayout(cy, payload, STORE.layout);
    if (payload.defaultContentPath) loadContent(payload.defaultContentPath);
  }

  document.addEventListener('DOMContentLoaded', init);
})();
