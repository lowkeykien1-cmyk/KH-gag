const $ = (id) => document.getElementById(id);
let nextCursor = "";
let allServers = [];
let busy = false;

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[ch]);
}
function setMessage(message, error = false) {
  const el = $("serverMessage");
  el.textContent = message;
  el.classList.toggle("error", error);
  el.classList.remove("hidden");
}
function fmtTime(epoch) {
  return new Date(epoch * 1000).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit", second: "2-digit"});
}

async function loadServers(loadMore = false) {
  if (busy) return;
  busy = true;
  $("refreshBtn").disabled = true;
  $("scanTop").disabled = true;
  setMessage(loadMore ? "Loading more public servers…" : "Scanning public Roblox servers…");
  try {
    const params = new URLSearchParams({limit: "100"});
    if (loadMore && nextCursor) params.set("cursor", nextCursor);
    const response = await fetch(`/api/servers?${params.toString()}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Server scan failed.");
    allServers = loadMore ? allServers.concat(data.servers || []) : (data.servers || []);
    nextCursor = data.nextPageCursor || "";
    $("moreBtn").classList.toggle("hidden", !nextCursor);
    $("serverCount").textContent = allServers.length;
    $("slotCount").textContent = allServers.reduce((sum, server) => sum + (server.slotsLeft || 0), 0);
    setMessage(`Updated ${fmtTime(data.checkedAt)} · Luck weather is unverified.`);
    renderServers();
  } catch (error) {
    setMessage(`${error.message} Check your connection and try again.`, true);
  } finally {
    busy = false;
    $("refreshBtn").disabled = false;
    $("scanTop").disabled = false;
  }
}

function renderServers() {
  const query = $("serverFilter").value.trim().toLowerCase();
  const lowOnly = $("showOnlyLow").checked;
  const visible = allServers.filter(server => {
    const idMatch = String(server.id || "").toLowerCase().includes(query);
    const lowMatch = !lowOnly || server.playing <= 5;
    return idMatch && lowMatch;
  });
  const list = $("serverList");
  if (!visible.length) {
    list.innerHTML = `<div class="empty-state">No servers match these filters. Try refreshing or changing the filter.</div>`;
    return;
  }
  list.innerHTML = visible.map((server, index) => `
    <article class="server-card">
      <div>
        <strong>Public server ${index + 1}</strong>
        <div class="server-id" title="${escapeHtml(server.id)}">${escapeHtml(server.id)}</div>
        <div class="server-meta">
          <span>☻ ${server.playing}/9 players</span>
          <span>Luck: <b style="color:#e9b86d">Unverified</b></span>
          ${server.ping ? `<span>${server.ping} ms ping</span>` : ""}
        </div>
      </div>
      <div class="server-right">
        <span class="slot-badge">${server.slotsLeft} SLOT${server.slotsLeft === 1 ? "" : "S"} OPEN</span>
        <a class="join-btn" href="${escapeHtml(server.joinUrl)}" target="_blank" rel="noopener">JOIN ↗</a>
      </div>
    </article>`).join("");
}

async function lookupUsername(username) {
  const box = $("userResult");
  box.classList.remove("hidden");
  box.textContent = "Looking up Roblox username…";
  try {
    const response = await fetch("/api/lookup-user", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({username})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Lookup failed.");
    if (!data.found) {
      box.innerHTML = `No Roblox account matched <b>${escapeHtml(username)}</b>. Check the spelling and try again.`;
      return;
    }
    box.innerHTML = `<b>${escapeHtml(data.name)}</b> (${escapeHtml(data.displayName)})<br>
      <span style="color:#a99db8">Profile found. Current server: not available through this lookup.</span><br>
      <a href="${escapeHtml(data.profileUrl)}" target="_blank" rel="noopener">Open profile ↗</a>
      &nbsp;·&nbsp;<a href="${escapeHtml(data.searchUrl)}" target="_blank" rel="noopener">Roblox player search ↗</a>`;
  } catch (error) {
    box.textContent = error.message;
  }
}

function getNotes() {
  try { return JSON.parse(localStorage.getItem("kyoshRollNotes") || "[]"); }
  catch { return []; }
}
function saveNote() {
  const username = $("username").value.trim();
  const unit = $("unit").value.trim();
  if (!username) {
    $("username").focus();
    $("userResult").classList.remove("hidden");
    $("userResult").textContent = "Enter a username first.";
    return;
  }
  const notes = getNotes();
  notes.unshift({username, unit, created: new Date().toISOString()});
  localStorage.setItem("kyoshRollNotes", JSON.stringify(notes.slice(0, 30)));
  renderNotes();
  lookupUsername(username);
}
function renderNotes() {
  const notes = getNotes();
  const list = $("notesList");
  if (!notes.length) {
    list.innerHTML = `<div class="empty-state">Your saved notes will appear here.</div>`;
    return;
  }
  list.innerHTML = notes.map(note => `<div class="note">
    <div><strong>${escapeHtml(note.username)}</strong><small>${escapeHtml(note.unit || "Unit not specified")} · ${new Date(note.created).toLocaleString()}</small></div>
    <a href="https://www.roblox.com/search/users?keyword=${encodeURIComponent(note.username)}" target="_blank" rel="noopener">SEARCH ↗</a>
  </div>`).join("");
}

$("scanTop").addEventListener("click", () => loadServers(false));
$("refreshBtn").addEventListener("click", () => loadServers(false));
$("moreBtn").addEventListener("click", () => loadServers(true));
$("serverFilter").addEventListener("input", renderServers);
$("showOnlyLow").addEventListener("change", renderServers);
$("lookupForm").addEventListener("submit", event => {
  event.preventDefault();
  const username = $("username").value.trim();
  if (username) lookupUsername(username);
});
$("saveRoll").addEventListener("click", saveNote);
$("clearNotes").addEventListener("click", () => {
  localStorage.removeItem("kyoshRollNotes");
  renderNotes();
});
renderNotes();
