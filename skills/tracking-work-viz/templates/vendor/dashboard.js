(function () {
  const rows = document.getElementById("rows");
  const data = window.VIZ_DASHBOARD_DATA || { workspaces: [] };
  for (const ws of data.workspaces) {
    const row = document.createElement("div");
    row.className = "row";
    row.innerHTML = `
      <a href="${ws.slug}.html">${ws.slug}</a>
      <span class="num">${ws.session_count} sess</span>
      <span class="num">${ws.task_count} tasks</span>
      <span class="ts">${ws.last_updated || ""}</span>
      <span class="agents">${ws.agent_count > 0 ? ws.agent_count + " agents" : ""}</span>
    `;
    rows.appendChild(row);
  }
})();
