(function () {
  'use strict';

  function parsePayload() {
    var node = document.getElementById('__SCOPE__');
    if (!node) throw new Error('missing __SCOPE__ payload');
    return JSON.parse(node.textContent);
  }

  function readFragmentChips() {
    var hash = window.location.hash || '';
    var m = /chips=([a-z,]+)/.exec(hash);
    if (!m) return null;
    return new Set(m[1].split(',').filter(Boolean));
  }

  function writeFragmentChips(active) {
    var arr = Array.from(active).sort();
    window.location.hash = 'chips=' + arr.join(',');
  }

  function renderTree(rootNodes, scopeId) {
    var aside = document.getElementById('tree');
    aside.innerHTML = '';
    var ul = document.createElement('ul');
    function rec(n, parent) {
      var li = document.createElement('li');
      var span = document.createElement(n.href ? 'a' : 'span');
      span.className = 'tree-node kind-' + n.kind;
      if (n.id === scopeId) span.classList.add('current');
      span.textContent = n.label;
      if (n.href) span.href = relHref(n.href);
      span.dataset.id = n.id;
      li.appendChild(span);
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
    // Tree hrefs are relative to root; rewrite relative to current page.
    var depth = window.location.pathname.split('/').filter(Boolean).length - 1;
    if (depth <= 0) return href;
    return Array(depth).fill('..').join('/') + '/' + href;
  }

  function edgeStyle(kind) {
    switch (kind) {
      case 'contains': return { 'line-color': '#cccccc', 'width': 1, 'line-style': 'solid', 'target-arrow-shape': 'none' };
      case 'blocked':  return { 'line-color': '#d33', 'width': 2, 'line-style': 'solid', 'target-arrow-shape': 'triangle', 'target-arrow-color': '#d33' };
      case 'related':  return { 'line-color': '#666', 'width': 2, 'line-style': 'solid', 'target-arrow-shape': 'triangle', 'target-arrow-color': '#666' };
      case 'follows':  return { 'line-color': '#333', 'width': 2, 'line-style': 'dashed', 'target-arrow-shape': 'triangle', 'target-arrow-color': '#333' };
      case 'mentions': return { 'line-color': '#6ad', 'width': 1.5, 'line-style': 'dotted', 'target-arrow-shape': 'triangle', 'target-arrow-color': '#6ad' };
    }
    return {};
  }

  function nodeStyle(kind, ghost) {
    var base = { 'label': 'data(label)', 'font-size': 11, 'text-valign': 'center',
                 'text-halign': 'center', 'background-color': '#fff',
                 'border-width': 1, 'border-color': '#333',
                 'shape': 'roundrectangle', 'padding': 6 };
    if (kind === 'workspace') { base['background-color'] = '#e3f0ff'; base['shape'] = 'rectangle'; }
    if (kind === 'session') { base['background-color'] = '#eef'; }
    if (kind === 'task') { base['background-color'] = '#fff'; }
    if (kind === 'memory') { base['background-color'] = '#fff5d6'; }
    if (kind === 'workbench') { base['background-color'] = '#e8f7e0'; }
    if (kind === 'root') { base['background-color'] = '#333'; base['color'] = '#fff'; }
    if (ghost) { base['border-style'] = 'dashed'; base['opacity'] = 0.6; base['font-style'] = 'italic'; }
    return base;
  }

  function initGraph(payload) {
    var elements = [];
    payload.nodes.forEach(function (n) {
      elements.push({ group: 'nodes', data: { id: n.id, label: n.label, kind: n.kind, ghost: !!n.ghost, contentPath: n.contentPath } });
    });
    payload.edges.forEach(function (e) {
      elements.push({ group: 'edges', data: { id: e.source + '|' + e.kind + '|' + e.target, source: e.source, target: e.target, kind: e.kind } });
    });
    var cy = cytoscape({
      container: document.getElementById('graph'),
      elements: elements,
      style: [
        { selector: 'node', style: { 'label': 'data(label)', 'font-size': 11 } },
        ...['root','workspace','session','task','memory','workbench'].map(function (k) {
          return { selector: 'node[kind="' + k + '"]', style: nodeStyle(k, false) };
        }),
        { selector: 'node[?ghost]', style: { 'border-style': 'dashed', 'opacity': 0.6 } },
        ...['contains','blocked','related','follows','mentions'].map(function (k) {
          return { selector: 'edge[kind="' + k + '"]', style: edgeStyle(k) };
        }),
        { selector: 'edge.hidden', style: { 'display': 'none' } },
      ],
      layout: { name: 'dagre', rankDir: 'LR', nodeSep: 30, rankSep: 70 },
    });
    cy.on('tap', 'node', function (evt) {
      var n = evt.target;
      var cp = n.data('contentPath');
      if (cp) loadContent(cp);
    });
    return cy;
  }

  function applyChipState(cy, active) {
    cy.edges().forEach(function (e) {
      var k = e.data('kind');
      if (k === 'contains') { e.removeClass('hidden'); return; }
      if (active.has(k)) e.removeClass('hidden'); else e.addClass('hidden');
    });
  }

  function bindChips(cy) {
    var active = readFragmentChips();
    if (!active) {
      active = new Set();
      document.querySelectorAll('#chips .chip.on').forEach(function (el) { active.add(el.dataset.kind); });
    } else {
      document.querySelectorAll('#chips .chip').forEach(function (el) {
        if (active.has(el.dataset.kind)) el.classList.add('on'); else el.classList.remove('on');
      });
    }
    applyChipState(cy, active);
    document.querySelectorAll('#chips .chip').forEach(function (el) {
      el.addEventListener('click', function () {
        var k = el.dataset.kind;
        if (active.has(k)) { active.delete(k); el.classList.remove('on'); }
        else { active.add(k); el.classList.add('on'); }
        applyChipState(cy, active);
        writeFragmentChips(active);
      });
    });
  }

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

  function init() {
    var payload = parsePayload();
    renderTree(payload.tree, payload.scopeId);
    var cy = initGraph(payload);
    bindChips(cy);
    if (payload.defaultContentPath) loadContent(payload.defaultContentPath);
  }

  document.addEventListener('DOMContentLoaded', init);
})();
