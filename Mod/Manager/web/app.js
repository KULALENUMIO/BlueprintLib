"use strict";
/* Blueprint Lib Manager - browser side.
 * Edits Mod/Data/library.json (same format the in-game tool uses) through the local server.
 * Library format: { folders:[path], items:{id:{folder?,tags[],fav?,hidden?,used?}}, collapsed:{path:true},
 *                   settings:{...game only}, useCounter, rev, version }
 */

const S_ALL = "*all", S_FAV = "*fav", S_RECENT = "*recent", S_UNFILED = "*unfiled",
  S_WORKSHOP = "*workshop", S_NOTINST = "*notinstalled", S_HIDDEN = "*hidden";
const RECENT_LIMIT = 60;
const MAX_PATH = 240;

const st = {
  index: [], byId: new Map(), lib: null, rev: 0, installed: { names: new Set(), files: new Set() },
  scope: S_ALL, tab: "folders", search: "", view: "G", sort: "new",
  sel: new Set(), anchor: null, focus: null, filtered: [],
  pending: [], saveLoop: null, online: true,
};
const $ = (q) => document.querySelector(q);

// ---------------------------------------------------------------------------------------------
// prefs (browser only; the game's own view/sort settings in library.json are left alone)
try {
  const p = JSON.parse(localStorage.getItem("br-prefs") || "{}");
  if (["L", "G", "R"].includes(p.view)) st.view = p.view;
  if (["new", "old", "name", "used"].includes(p.sort)) st.sort = p.sort;
} catch (e) { /* storage unavailable */ }
function savePrefs() {
  try { localStorage.setItem("br-prefs", JSON.stringify({ view: st.view, sort: st.sort })); } catch (e) { /* ignore */ }
}

// ---------------------------------------------------------------------------------------------
// API
async function api(method, url, body) {
  const res = await fetch(url, {
    method, headers: { "X-BR-Token": window.BR_TOKEN, "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let data = null;
  try { data = await res.json(); } catch (e) { /* empty */ }
  return { status: res.status, data };
}

/* status takes a translation key and remembers it, so switching the language re-renders it */
let statusKey = "status.loading", statusErr = false;
function setStatus(key, err) {
  statusKey = key;
  statusErr = !!err;
  const el = $("#status");
  el.textContent = t(key);
  el.classList.toggle("err", statusErr);
}

function toast(msg, err) {
  const el = document.createElement("div");
  el.className = "toast" + (err ? " err" : "");
  el.textContent = msg;
  $("#toasts").appendChild(el);
  setTimeout(() => el.remove(), err ? 5000 : 2600);
}

// ---------------------------------------------------------------------------------------------
// folder paths (same rules as the Lua side)
const parentOf = (p) => (p.includes("/") ? p.slice(0, p.lastIndexOf("/")) : null);
const leafOf = (p) => p.slice(p.lastIndexOf("/") + 1);
const depthOf = (p) => p.split("/").length - 1;
const isUnder = (p, a) => p === a || p.startsWith(a + "/");
const sortKey = (p) => p.toLowerCase().replaceAll("/", "\u0001");

function cleanPath(s) {
  s = String(s || "").replaceAll("／", "/");
  const segs = s.split("/").map((x) => x.replace(/^[\s　]+|[\s　]+$/g, ""));
  if (!segs.length || segs.some((x) => !x || x[0] === "*" || x[0] === "#")) return null;
  const path = segs.join("/");
  return new TextEncoder().encode(path).length <= MAX_PATH ? path : null;
}

function ensureFolder(lib, path) {
  for (let p = path; p; p = parentOf(p)) if (!lib.folders.includes(p)) lib.folders.push(p);
}

function normalize(lib) {
  lib = lib && typeof lib === "object" ? lib : {};
  const folders = Array.isArray(lib.folders) ? lib.folders : [];
  lib.items = lib.items && typeof lib.items === "object" && !Array.isArray(lib.items) ? lib.items : {};
  lib.collapsed = lib.collapsed && typeof lib.collapsed === "object" && !Array.isArray(lib.collapsed) ? lib.collapsed : {};
  lib.folders = [];
  // folder names go through the same validation as typed ones ("#x" would look like a tag scope)
  for (const f of folders) { const p = typeof f === "string" ? cleanPath(f) : null; if (p) ensureFolder(lib, p); }
  for (const [id, m] of Object.entries(lib.items)) {
    if (!m || typeof m !== "object") { delete lib.items[id]; continue; }
    m.tags = Array.isArray(m.tags) ? m.tags.filter((t) => typeof t === "string" && t) : [];
    const p = typeof m.folder === "string" ? cleanPath(m.folder) : null;
    if (p) { m.folder = p; ensureFolder(lib, p); } else delete m.folder;
  }
  lib.folders.sort((a, b) => (sortKey(a) < sortKey(b) ? -1 : 1));
  lib.useCounter = Number(lib.useCounter) || 0;
  return lib;
}

function prune(lib, id) {
  const m = lib.items[id];
  if (m && !m.folder && !m.fav && !m.hidden && !m.used && m.tags.length === 0) delete lib.items[id];
}

function metaOf(lib, id, create) {
  let m = lib.items[id];
  if (!m && create) { m = { tags: [] }; lib.items[id] = m; }
  return m;
}

const hasTag = (m, lt) => !!m && m.tags.some((t) => t.toLowerCase() === lt);

// ---------------------------------------------------------------------------------------------
// loading / saving
async function loadState() {
  const r = await api("GET", "/api/state");
  if (r.status !== 200) throw new Error(r.data && r.data.error === "nomod" ? t("load.nomod") : "state " + r.status);
  applyIndex(r.data.index);
  st.lib = normalize(r.data.library);
  st.rev = Number(r.data.library && r.data.library.rev) || 0;
  st.installed = { names: new Set(), files: new Set() };
  for (const m of r.data.installedMods || []) {
    st.installed.names.add(m.name);
    if (m.fileId) st.installed.files.add(String(m.fileId));
  }
}

function applyIndex(index) {
  st.index = (index && Array.isArray(index.blueprints) ? index.blueprints : []).map((b) => ({
    ...b, plain: stripColors(b.name || b.id).toLowerCase(),
  }));
  st.byId = new Map(st.index.map((b) => [b.id, b]));
  for (const id of [...st.sel]) if (!st.byId.has(id)) st.sel.delete(id);
  if (st.focus && !st.byId.has(st.focus)) st.focus = null;
}

/* Every edit goes through here: fn mutates the library (and must be safe to run again: it
 * describes the intended end state, e.g. "set fav", never "toggle").
 * Edits are queued until the server confirms them. If the game saved in between (409), the latest
 * file is loaded and ALL unconfirmed edits are replayed on it, so neither side loses anything. */
function mutate(fn, message) {
  fn(st.lib);
  normalize(st.lib);
  render();
  if (message) toast(message);
  st.pending.push(fn);
  if (!st.saveLoop) st.saveLoop = runSaves().finally(() => { st.saveLoop = null; });
  return st.saveLoop;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function runSaves() {
  let conflicts = 0, failures = 0;
  while (st.pending.length) {
    const sent = st.pending.length; // edits made while this request is in flight stay queued
    setStatus("status.saving");
    let r;
    try {
      r = await api("PUT", "/api/library", { library: st.lib, baseRev: st.rev });
    } catch (e) {
      r = { status: 0 };
    }
    if (r.status === 200) {
      st.rev = r.data.rev;
      st.pending.splice(0, sent);
      conflicts = failures = 0;
      st.online = true;
      continue;
    }
    if (r.status === 409 && r.data && conflicts < 5) {
      conflicts++;
      const fresh = normalize(r.data.library);
      for (const fn of st.pending) fn(fresh);
      st.lib = normalize(fresh);
      st.rev = Number(r.data.rev) || 0;
      render();
      toast(t("toast.mergedGame"));
      continue;
    }
    // 503 = the file is busy (the game is reading/writing it), 0 = no connection: retry for a while
    if ((r.status === 503 || r.status === 0) && failures < 8) {
      failures++;
      setStatus((r.status === 503 ? "status.busyRetry" : "status.reconnect"), true);
      await sleep(1000);
      continue;
    }
    st.online = r.status !== 0;
    setStatus((r.status === 0 ? "status.offline" : "status.cantSave"), true);
    toast(r.status === 0 ? t("toast.offline") : t("toast.saveFailed", { code: r.status }), true);
    return; // edits stay in st.pending and are retried with the next edit
  }
  setStatus("status.saved");
}

// notice edits made in game (library.json rev changed on disk)
async function pollRev() {
  if (st.pending.length || st.saveLoop) return;
  try {
    const r = await api("GET", "/api/rev");
    if (r.status === 503) { setStatus("status.busy", true); return; }
    if (!st.online) { st.online = true; setStatus("status.connected"); }
    if (r.status !== 200 || !(r.data.rev > st.rev)) return;
    const s = await api("GET", "/api/state");
    const rev = s.status === 200 ? Number(s.data.library && s.data.library.rev) || 0 : -1;
    // ignore answers that are older than what we have, or that raced with a new local edit
    if (rev > st.rev && !st.pending.length && !st.saveLoop) {
      st.lib = normalize(s.data.library);
      st.rev = rev;
      render();
      toast(t("toast.gameLoaded"));
    }
  } catch (e) {
    st.online = false;
    setStatus("status.offline", true);
  }
}

// ---------------------------------------------------------------------------------------------
// filtering
function missingMods(bp) {
  const out = [];
  for (const m of bp.mods || []) {
    const inst = (m.fileId && st.installed.files.has(String(m.fileId))) || st.installed.names.has(m.name);
    if (!inst) out.push(m);
  }
  return out;
}

function inScope(bp, m) {
  const s = st.scope, hidden = !!(m && m.hidden);
  if (s === S_HIDDEN) return hidden;
  if (hidden) return false;
  if (s === S_ALL) return true;
  if (s === S_FAV) return !!(m && m.fav);
  if (s === S_RECENT) return !!(m && m.used);
  if (s === S_UNFILED) return !(m && m.folder);
  if (s === S_WORKSHOP) return bp.source === "workshop";
  if (s === S_NOTINST) return missingMods(bp).length > 0;
  if (s.startsWith("#")) return hasTag(m, s.slice(1));
  return !!(m && m.folder && isUnder(m.folder, s));
}

function matches(bp, m, terms) {
  for (const t of terms) {
    let ok = false;
    if (t.text && bp.plain.includes(t.text)) ok = true;
    if (!ok && t.text && m && m.folder && m.folder.toLowerCase().includes(t.text)) ok = true;
    if (!ok && m) ok = m.tags.some((x) => x.toLowerCase().includes(t.tag || t.text));
    if (!ok) return false;
  }
  return true;
}

function computeFiltered() {
  const terms = st.search.toLowerCase().replaceAll("＃", "#").split(/[\s　]+/).filter(Boolean)
    .map((w) => (w[0] === "#" ? (w.length > 1 ? { tag: w.slice(1) } : null) : { text: w })).filter(Boolean);
  const items = st.lib.items;
  let out = st.index.filter((bp) => inScope(bp, items[bp.id]) && matches(bp, items[bp.id], terms));
  const used = (bp) => (items[bp.id] && items[bp.id].used) || 0;
  const byNew = (a, b) => b.mtime - a.mtime || (a.id < b.id ? -1 : 1);
  if (st.scope === S_RECENT || st.sort === "used") {
    out.sort((a, b) => used(b) - used(a) || byNew(a, b));
    if (st.scope === S_RECENT) out = out.slice(0, RECENT_LIMIT);
  } else if (st.sort === "old") out.sort((a, b) => -byNew(a, b));
  else if (st.sort === "name") out.sort((a, b) => a.plain.localeCompare(b.plain, LANG) || (a.id < b.id ? -1 : 1));
  else out.sort(byNew);
  st.filtered = out;
}

// ---------------------------------------------------------------------------------------------
// rendering helpers
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const stripColors = (s) => String(s ?? "").replace(/#[0-9a-fA-F]{6}/g, "");

/* blueprint names may contain the game's colour codes ("#ff0000Red #ffffffWhite") */
function nameHtml(name) {
  const s = String(name ?? "");
  let html = "", color = null, last = 0;
  const re = /#([0-9a-fA-F]{6})/g;
  let m;
  const flush = (end) => {
    const part = s.slice(last, end);
    if (part) html += color ? `<span style="color:#${color}">${esc(part)}</span>` : esc(part);
  };
  while ((m = re.exec(s))) {
    flush(m.index);
    color = m[1].toLowerCase() === "ffffff" ? null : m[1];
    last = m.index + 7;
  }
  flush(s.length);
  return html || esc(s);
}

const iconUrl = (bp) => (bp.hasIcon === false ? "" : `/icon/${encodeURIComponent(bp.id)}`);
const fmtDate = (ts) => (ts ? new Date(ts * 1000).toLocaleDateString(LOCALE[LANG]) : "");
const steamUrl = (fileId) => `https://steamcommunity.com/sharedfiles/filedetails/?id=${encodeURIComponent(fileId)}`;

// ---------------------------------------------------------------------------------------------
// left panel
function leftEntries() {
  const items = st.lib.items, out = [];
  if (st.tab === "tags") {
    const counts = new Map(), disp = new Map();
    for (const bp of st.index) {
      const m = items[bp.id];
      if (!m || m.hidden) continue;
      for (const t of m.tags) {
        const k = t.toLowerCase();
        counts.set(k, (counts.get(k) || 0) + 1);
        if (!disp.has(k)) disp.set(k, t);
      }
    }
    [...counts.keys()].sort((a, b) => a.localeCompare(b, LANG)).forEach((k) =>
      out.push({ id: "#" + k, label: "#" + disp.get(k), n: counts.get(k), tag: disp.get(k) }));
    return out;
  }
  const n = { all: 0, fav: 0, recent: 0, unfiled: 0, ws: 0, notinst: 0, hidden: 0 };
  const direct = new Map();
  for (const bp of st.index) {
    const m = items[bp.id];
    if (m && m.hidden) { n.hidden++; continue; }
    n.all++;
    if (m && m.fav) n.fav++;
    if (m && m.used) n.recent++;
    if (bp.source === "workshop") n.ws++;
    if (missingMods(bp).length) n.notinst++;
    if (m && m.folder) direct.set(m.folder, (direct.get(m.folder) || 0) + 1);
    else n.unfiled++;
  }
  const v = (id, label, count, cls) => out.push({ id, label, n: count, virt: true, cls });
  v(S_ALL, t("scope.all"), n.all);
  v(S_FAV, t("scope.fav"), n.fav);
  v(S_RECENT, t("scope.recent"), Math.min(n.recent, RECENT_LIMIT));
  v(S_UNFILED, t("scope.unfiled"), n.unfiled);
  if (n.ws) v(S_WORKSHOP, t("scope.workshop"), n.ws);
  if (n.notinst) v(S_NOTINST, t("scope.notinst"), n.notinst, "warnrow");
  v(S_HIDDEN, t("scope.hidden"), n.hidden);
  out.push({ sep: true });

  const total = new Map();
  for (const [f, c] of direct) for (let p = f; p; p = parentOf(p)) total.set(p, (total.get(p) || 0) + c);
  for (const f of st.lib.folders) {
    let visible = true;
    for (let p = parentOf(f); p; p = parentOf(p)) if (st.lib.collapsed[p]) { visible = false; break; }
    if (!visible) continue;
    const hasKids = st.lib.folders.some((x) => x !== f && isUnder(x, f));
    out.push({ id: f, label: leafOf(f), n: total.get(f) || 0, folder: true, depth: depthOf(f), hasKids });
  }
  return out;
}

function renderLeft() {
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === st.tab));
  const tree = $("#tree");
  tree.innerHTML = "";
  for (const e of leftEntries()) {
    const li = document.createElement("li");
    if (e.sep) { li.className = "sep"; tree.appendChild(li); continue; }
    li.dataset.id = e.id;
    li.className = (e.virt ? "virt " : "") + (e.cls || "") + (e.id === st.scope ? " on" : "");
    if (e.folder) li.style.paddingLeft = 6 + e.depth * 16 + "px";
    const tw = e.folder && e.hasKids ? (st.lib.collapsed[e.id] ? "▶" : "▼") : "";
    li.innerHTML = `<span class="tw ${tw ? "has" : ""}">${tw}</span><span class="label">${esc(e.label)}</span><span class="n">${e.n}</span>`;
    li.title = e.folder ? e.id : e.label;
    if (e.folder) li.draggable = true;
    li._entry = e;
    tree.appendChild(li);
  }
  const userFolder = st.lib.folders.includes(st.scope);
  $("#where").textContent = userFolder ? st.scope + "/" : st.scope.startsWith("#") ? st.scope : "";
  $("#folderActions").style.display = st.tab === "folders" ? "" : "none";
  $("#renameFolder").disabled = $("#deleteFolder").disabled = !userFolder;
}

// ---------------------------------------------------------------------------------------------
// center
function renderItems() {
  computeFiltered();
  const box = $("#items");
  box.className = "items " + st.view;
  document.querySelectorAll("#viewSeg button").forEach((b) => b.classList.toggle("on", b.dataset.view === st.view));
  $("#sort").value = st.sort;
  const items = st.lib.items;
  const parts = [];
  for (const bp of st.filtered) {
    const m = items[bp.id];
    const miss = missingMods(bp);
    const badges = (m && m.fav ? `<span class="badge fav">★</span>` : "")
      + (bp.source === "workshop" ? `<span class="badge ws">WS</span>` : "")
      + (miss.length ? `<span class="badge warn" title="${esc(t("badge.missing", { mods: miss.map((x) => x.name).join(", ") }))}">⚠ MOD</span>` : "");
    const tags = m ? m.tags.map((t) => "#" + t).join(" ") : "";
    const img = iconUrl(bp) ? `<img loading="lazy" src="${esc(iconUrl(bp))}" alt="" onerror="this.remove()">` : "";
    const sel = st.sel.has(bp.id) ? " sel" : "";
    if (st.view === "R") {
      parts.push(`<div class="card${sel}" data-id="${esc(bp.id)}" draggable="true">
        <div class="thumb">${img}</div>
        <div class="name">${nameHtml(bp.name)}</div>
        <div class="col">${esc(m && m.folder ? m.folder : "")}</div>
        <div class="col">${esc(tags)} <span class="badges">${badges}</span></div>
        <div class="col">${fmtDate(bp.mtime)}</div></div>`);
    } else {
      parts.push(`<div class="card${sel}" data-id="${esc(bp.id)}" draggable="true" title="${esc(stripColors(bp.name))}">
        <div class="badges">${badges}</div>
        <div class="thumb">${img}</div>
        <div class="name">${nameHtml(bp.name)}</div>
        ${st.view === "L" ? `<div class="tagline">${esc(tags)}</div>` : ""}</div>`);
    }
  }
  const top = box.scrollTop; // rebuilding the cards must not move the list
  box.innerHTML = parts.join("") || `<div class="empty">${esc(t("items.empty"))}</div>`;
  box.scrollTop = top;
  updateCount();
}

// the list content changed (search, sort, view, folder): start from the top
function toTop() {
  $("#items").scrollTop = 0;
  // the visible list changed: drop selected blueprints that are no longer shown, so bulk actions
  // never touch things the user can't see
  const visible = new Set(st.filtered.map((b) => b.id));
  let changed = false;
  for (const id of [...st.sel]) if (!visible.has(id)) { st.sel.delete(id); changed = true; }
  if (changed) updateSelection();
}

function updateCount() {
  $("#count").textContent = t("count.total", { n: st.filtered.length }) + (st.sel.size ? t("count.sel", { n: st.sel.size }) : "");
}

/* Selection changes only toggle classes - rebuilding every card on each click made the
 * browser's scroll anchoring shift the list. */
function updateSelection() {
  document.querySelectorAll("#items .card").forEach((c) => c.classList.toggle("sel", st.sel.has(c.dataset.id)));
  updateCount();
  renderDetail();
}

// ---------------------------------------------------------------------------------------------
// right
function renderDetail() {
  const box = $("#detail");
  const ids = st.index.filter((b) => st.sel.has(b.id)).map((b) => b.id);
  if (!ids.length) {
    box.innerHTML = `<div class="sub">${esc(t("detail.none"))}</div>
      <div class="hint">${t("detail.help")}</div>`; // detail.help is trusted HTML (line breaks)
    return;
  }
  const items = st.lib.items;
  const focus = st.byId.get(st.focus && st.sel.has(st.focus) ? st.focus : ids[0]);
  const fm = items[focus.id];
  const n = ids.length;
  const tagCount = new Map(), tagDisp = new Map();
  let folder, mixed = false, allFav = true, allHidden = true;
  ids.forEach((id, i) => {
    const m = items[id];
    const f = (m && m.folder) || null;
    if (i === 0) folder = f; else if (f !== folder) mixed = true;
    if (!(m && m.fav)) allFav = false;
    if (!(m && m.hidden)) allHidden = false;
    for (const t of (m ? m.tags : [])) {
      const k = t.toLowerCase();
      tagCount.set(k, (tagCount.get(k) || 0) + 1);
      if (!tagDisp.has(k)) tagDisp.set(k, t);
    }
  });
  const chips = [...tagCount.keys()].map((k) =>
    `<span class="chip">#${esc(tagDisp.get(k))}${n > 1 ? ` <span class="part">${tagCount.get(k)}/${n}</span>` : ""}<button class="x" data-untag="${esc(tagDisp.get(k))}" title="${esc(t("detail.untag"))}">×</button></span>`).join("")
    || `<span class="sub">${esc(t("detail.none2"))}</span>`;
  const allTags = new Set();
  for (const m of Object.values(items)) for (const t of m.tags) allTags.add(t);

  let modsHtml = "";
  if (n === 1) {
    const mods = focus.mods || [];
    const miss = new Set(missingMods(focus).map((m) => m.name));
    modsHtml = mods.length ? `<ul class="mods">${mods.map((m) => {
      const ok = !miss.has(m.name);
      const link = m.fileId ? ` <a href="${steamUrl(m.fileId)}" target="_blank" rel="noopener">Steam</a>` : "";
      return `<li><span class="st ${ok ? "ok" : "ng"}">${ok ? "✓" : "✗"}</span><span>${esc(m.name === "?" ? t("mods.unknown") : m.name)}${link}</span></li>`;
    }).join("")}</ul><div class="hint">${esc(t("mods.hint"))}</div>`
      : `<div class="sub">${esc(t("mods.vanilla"))}</div>`;
  } else {
    const blocked = ids.filter((id) => missingMods(st.byId.get(id)).length).length;
    modsHtml = blocked ? `<div class="warnbox">${esc(t("mods.blocked", { n: blocked }))}</div>` : `<div class="sub">${esc(t("mods.allInstalled"))}</div>`;
  }

  box.innerHTML = `
    <div class="bigicon">${iconUrl(focus) ? `<img src="${esc(iconUrl(focus))}" alt="" onerror="this.remove()">` : ""}</div>
    <h2>${n === 1 ? nameHtml(focus.name) : esc(t("detail.multi", { n }))}</h2>
    <div class="sub">${n === 1 ? `${esc(t(focus.source === "workshop" ? "detail.workshop" : "detail.local"))} · ${fmtDate(focus.mtime)} · ${esc(focus.id)}` : t("detail.andMore", { name: nameHtml(focus.name) })}</div>
    <section><h3>${esc(t("detail.folder"))}</h3><div class="sub">${mixed ? esc(t("detail.mixed")) : esc(folder || t("detail.none2"))}</div></section>
    <section><h3>${esc(t("detail.tags"))}</h3><div class="chips">${chips}</div>
      <div class="row"><input id="tagInput" list="tagList" placeholder="${esc(t("detail.tagPh"))}"><button id="addTag" style="flex:none">${esc(t("detail.add"))}</button></div>
      <datalist id="tagList">${[...allTags].sort().map((t) => `<option value="${esc(t)}">`).join("")}</datalist></section>
    <section><h3>${esc(t("detail.actions"))}</h3>
      <div class="row"><button id="favBtn">${esc(t(allFav ? "detail.favOn" : "detail.favOff"))}</button><button id="hideBtn">${esc(t(allHidden ? "detail.unhide" : "detail.hide"))}</button></div>
      <div class="row"><button id="unfileBtn" ${folder || mixed ? "" : "disabled"}>${esc(t("detail.unfile"))}</button></div></section>
    <section><h3>${esc(t("detail.mods"))}</h3>${modsHtml}</section>
    ${n === 1 ? `<button id="placeBtn" class="primary placebtn" title="${esc(t("detail.place.title"))}">${esc(t("detail.place"))}</button>` : ""}`;

  const addTag = () => {
    const tag = $("#tagInput").value.trim().replace(/^[#＃]+/, "").replace(/\s+/g, "_");
    if (!tag) return;
    mutate((lib) => ids.forEach((id) => { const m = metaOf(lib, id, true); if (!hasTag(m, tag.toLowerCase())) m.tags.push(tag); }),
      t("toast.tagged", { n, tag }));
  };
  $("#addTag").onclick = addTag;
  $("#tagInput").onkeydown = (e) => { if (e.key === "Enter") addTag(); };
  box.querySelectorAll("[data-untag]").forEach((b) => (b.onclick = () => {
    const lt = b.dataset.untag.toLowerCase();
    mutate((lib) => ids.forEach((id) => { const m = metaOf(lib, id); if (m) { m.tags = m.tags.filter((t) => t.toLowerCase() !== lt); prune(lib, id); } }),
      t("toast.untagged", { tag: b.dataset.untag }));
  }));
  $("#favBtn").onclick = () => mutate((lib) => ids.forEach((id) => { const m = metaOf(lib, id, true); if (allFav) delete m.fav; else m.fav = true; prune(lib, id); }));
  $("#hideBtn").onclick = () => mutate((lib) => ids.forEach((id) => { const m = metaOf(lib, id, true); if (allHidden) delete m.hidden; else m.hidden = true; prune(lib, id); }),
    t(allHidden ? "toast.unhidden" : "toast.hidden", { n }));
  $("#unfileBtn").onclick = () => mutate((lib) => ids.forEach((id) => { const m = metaOf(lib, id); if (m) { delete m.folder; prune(lib, id); } }));
  const pb = $("#placeBtn");
  if (pb) pb.onclick = () => placeInGame(focus.id);
}

function scopeExists() {
  const s = st.scope;
  if (s.startsWith("*")) return true;
  if (s.startsWith("#")) return Object.values(st.lib.items).some((m) => hasTag(m, s.slice(1)));
  return st.lib.folders.includes(s);
}

function render() {
  if (!scopeExists()) st.scope = S_ALL;
  renderLeft();
  renderItems();
  renderDetail();
}

// ---------------------------------------------------------------------------------------------
// actions
async function placeInGame(id) {
  const bp = st.byId.get(id);
  let r;
  try { r = await api("POST", "/api/place", { id }); } catch (e) { r = { status: 0 }; }
  if (r.status === 200) toast(t("toast.sent", { name: stripColors(bp ? bp.name : id) }));
  else toast(t(r.status === 503 ? "toast.sendBusy" : "toast.sendFailed"), true);
}

/* "drop" the given blueprints onto a left-panel entry (same meaning as in game) */
function dropItems(ids, e) {
  const n = ids.length;
  const all = (fn) => (lib) => ids.forEach((id) => { fn(metaOf(lib, id, true)); prune(lib, id); });
  if (e.folder) return mutate(all((m) => { m.folder = e.id; }), t("toast.dropped", { n, folder: e.id }));
  if (e.tag) return mutate(all((m) => { if (!hasTag(m, e.tag.toLowerCase())) m.tags.push(e.tag); }), t("toast.tagged", { n, tag: e.tag }));
  switch (e.id) {
    case S_UNFILED: return mutate(all((m) => { delete m.folder; }), t("toast.dropUnfiled", { n }));
    case S_FAV: return mutate(all((m) => { m.fav = true; }), t("toast.dropFav", { n }));
    case S_HIDDEN: return mutate(all((m) => { m.hidden = true; }), t("toast.hidden", { n }));
    case S_ALL: return mutate(all((m) => { delete m.hidden; }), t("toast.unhidden", { n }));
    default: toast(t("toast.dropInvalid"), true);
  }
}

function moveFolder(oldPath, newPath) {
  if (!newPath || newPath === oldPath) return;
  if (new TextEncoder().encode(newPath).length > MAX_PATH) return toast(t("toast.pathLong"), true);
  if (isUnder(newPath, oldPath)) return toast(t("toast.intoSelf"), true);
  if (st.lib.folders.includes(newPath)) return toast(t("toast.exists"), true);
  const remap = (p) => (p && isUnder(p, oldPath) ? newPath + p.slice(oldPath.length) : p);
  mutate((lib) => {
    if (!lib.folders.includes(oldPath)) return;
    const folders = lib.folders;
    lib.folders = [];
    folders.forEach((f) => ensureFolder(lib, remap(f)));
    for (const m of Object.values(lib.items)) if (m.folder) m.folder = remap(m.folder);
    const c = {};
    for (const [k, v] of Object.entries(lib.collapsed)) c[remap(k)] = v;
    lib.collapsed = c;
  }, t("toast.renamed", { path: newPath }));
  if (isUnder(st.scope, oldPath)) st.scope = remap(st.scope);
  render();
}

function newFolder() {
  const parent = st.lib.folders.includes(st.scope) ? st.scope : null;
  const raw = prompt(parent ? t("prompt.newIn", { parent }) : t("prompt.new"), "");
  if (raw == null) return;
  const absolute = raw.trim().startsWith("/") || raw.trim().startsWith("／");
  const rel = cleanPath(absolute ? raw.trim().slice(1) : raw);
  if (!rel) return toast(t("toast.badName"), true);
  const path = parent && !absolute ? parent + "/" + rel : rel;
  if (st.lib.folders.includes(path)) return toast(t("toast.exists"), true);
  mutate((lib) => { ensureFolder(lib, path); if (parent) delete lib.collapsed[parent]; }, t("toast.created", { path }));
  st.scope = path;
  render();
}

function renameFolder() {
  const old = st.scope;
  if (!st.lib.folders.includes(old)) return;
  const raw = prompt(t("prompt.rename"), leafOf(old));
  if (raw == null) return;
  // same rules as in game: "Name" / "A/B" are relative to where the folder is now, "/A/B" is absolute
  let path;
  const typed = raw.trim().replaceAll("／", "/"); // (not "t": that would hide the t() translator)
  if (typed.startsWith("/")) path = cleanPath(typed.slice(1));
  else {
    const rel = cleanPath(typed);
    path = rel && (parentOf(old) ? parentOf(old) + "/" + rel : rel);
  }
  if (!path) return toast(t("toast.badName"), true);
  moveFolder(old, path);
}

function deleteFolder() {
  const name = st.scope;
  if (!st.lib.folders.includes(name)) return;
  if (!confirm(t("confirm.delete", { name }))) return;
  const parent = parentOf(name);
  mutate((lib) => {
    lib.folders = lib.folders.filter((f) => !isUnder(f, name));
    for (const [id, m] of Object.entries(lib.items)) if (m.folder && isUnder(m.folder, name)) { if (parent) m.folder = parent; else delete m.folder; prune(lib, id); }
    for (const k of Object.keys(lib.collapsed)) if (isUnder(k, name)) delete lib.collapsed[k];
  }, parent ? t("toast.deletedUp", { parent }) : t("toast.deletedTop"));
  st.scope = parent || S_ALL;
  render();
}

async function rescan() {
  const b = $("#rescan");
  b.disabled = true;
  setStatus("status.scanning");
  try {
    const r = await api("POST", "/api/sync");
    if (r.status !== 200) throw new Error(r.status);
    applyIndex(r.data.index);
    render();
    toast(t("toast.scanned", { n: st.index.length }));
    setStatus("status.saved");
  } catch (e) {
    toast(t("toast.scanFailed"), true);
    setStatus("status.error", true);
  } finally {
    b.disabled = false;
  }
}

// ---------------------------------------------------------------------------------------------
// selection & events
function clickCard(id, ev) {
  const list = st.filtered.map((b) => b.id);
  if (ev.shiftKey && st.anchor && list.includes(st.anchor)) {
    const [a, b] = [list.indexOf(st.anchor), list.indexOf(id)].sort((x, y) => x - y);
    if (!ev.ctrlKey) st.sel.clear();
    list.slice(a, b + 1).forEach((x) => st.sel.add(x));
  } else if (ev.ctrlKey || ev.metaKey) {
    if (st.sel.has(id)) st.sel.delete(id); else st.sel.add(id);
    st.anchor = id;
  } else {
    st.sel = new Set([id]);
    st.anchor = id;
  }
  st.focus = id;
  updateSelection();
}

function bindEvents() {
  $("#search").addEventListener("input", (e) => { st.search = e.target.value; renderItems(); toTop(); });
  $("#sort").addEventListener("change", (e) => { st.sort = e.target.value; savePrefs(); renderItems(); toTop(); });
  $("#viewSeg").addEventListener("click", (e) => { const v = e.target.dataset.view; if (v) { st.view = v; savePrefs(); renderItems(); toTop(); } });
  $("#rescan").onclick = rescan;
  $("#lang").value = LANG;
  $("#lang").addEventListener("change", (e) => {
    setLang(e.target.value);
    $("#sort").value = st.sort; // option texts were replaced
    setStatus(statusKey, statusErr);
    if (st.lib) render();
  });
  $("#selectAll").onclick = () => { st.filtered.forEach((b) => st.sel.add(b.id)); updateSelection(); };
  $("#selectNone").onclick = () => { st.sel.clear(); updateSelection(); };
  $("#newFolder").onclick = newFolder;
  $("#renameFolder").onclick = renameFolder;
  $("#deleteFolder").onclick = deleteFolder;
  document.querySelectorAll(".tabs button").forEach((b) => (b.onclick = () => { st.tab = b.dataset.tab; renderLeft(); }));

  const items = $("#items");
  items.addEventListener("click", (e) => {
    const card = e.target.closest(".card");
    if (card) clickCard(card.dataset.id, e);
    else if (e.target === items && !e.ctrlKey && !e.shiftKey) { st.sel.clear(); updateSelection(); }
  });
  items.addEventListener("dblclick", (e) => { const card = e.target.closest(".card"); if (card) placeInGame(card.dataset.id); });
  items.addEventListener("dragstart", (e) => {
    const card = e.target.closest(".card");
    if (!card) return;
    if (!st.sel.has(card.dataset.id)) { st.sel = new Set([card.dataset.id]); st.focus = card.dataset.id; updateSelection(); }
    const ids = [...st.sel];
    e.dataTransfer.setData("application/x-br-items", JSON.stringify(ids));
    e.dataTransfer.effectAllowed = "move";
    const ghost = document.createElement("div");
    ghost.className = "dragghost";
    ghost.textContent = t("drag.count", { n: ids.length });
    document.body.appendChild(ghost);
    e.dataTransfer.setDragImage(ghost, 10, 10);
    setTimeout(() => ghost.remove(), 0);
  });

  const tree = $("#tree");
  tree.addEventListener("click", (e) => {
    const li = e.target.closest("li");
    if (!li || !li._entry) return;
    const en = li._entry;
    if (en.folder && en.hasKids && e.target.classList.contains("tw")) {
      // fold / unfold with the arrow
      const collapse = !st.lib.collapsed[en.id];
      mutate((lib) => { if (collapse) lib.collapsed[en.id] = true; else delete lib.collapsed[en.id]; });
      return;
    }
    st.scope = en.id;
    render();
    toTop();
  });
  tree.addEventListener("dblclick", (e) => { const li = e.target.closest("li"); if (li && li._entry && li._entry.folder) { st.scope = li._entry.id; renameFolder(); } });
  tree.addEventListener("dragstart", (e) => {
    const li = e.target.closest("li");
    if (!li || !li._entry || !li._entry.folder) return;
    e.dataTransfer.setData("application/x-br-folder", li._entry.id);
    e.dataTransfer.effectAllowed = "move";
  });
  const acceptable = (en, types) => {
    if (types.includes("application/x-br-folder")) return en.folder || en.id === S_ALL;
    if (types.includes("application/x-br-items")) return en.folder || en.tag || [S_UNFILED, S_FAV, S_HIDDEN, S_ALL].includes(en.id);
    return false;
  };
  tree.addEventListener("dragover", (e) => {
    const li = e.target.closest("li");
    if (li && li._entry && acceptable(li._entry, [...e.dataTransfer.types])) {
      e.preventDefault();
      tree.querySelectorAll(".drop").forEach((x) => x !== li && x.classList.remove("drop"));
      li.classList.add("drop");
    }
  });
  tree.addEventListener("dragleave", (e) => { const li = e.target.closest("li"); if (li) li.classList.remove("drop"); });
  tree.addEventListener("drop", (e) => {
    const li = e.target.closest("li");
    tree.querySelectorAll(".drop").forEach((x) => x.classList.remove("drop"));
    if (!li || !li._entry) return;
    e.preventDefault();
    const folder = e.dataTransfer.getData("application/x-br-folder");
    if (folder) {
      const target = li._entry.id === S_ALL ? leafOf(folder) : li._entry.id + "/" + leafOf(folder);
      return moveFolder(folder, target);
    }
    try { dropItems(JSON.parse(e.dataTransfer.getData("application/x-br-items") || "[]"), li._entry); } catch (err) { /* ignore */ }
  });

  document.addEventListener("keydown", (e) => {
    const typing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName);
    if (e.key === "/" && !typing) { e.preventDefault(); $("#search").focus(); }
    else if (e.key === "Escape") { if (typing) document.activeElement.blur(); else { st.sel.clear(); updateSelection(); } }
    else if (!typing && (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "a") { e.preventDefault(); st.filtered.forEach((b) => st.sel.add(b.id)); updateSelection(); }
    else if (!typing && e.key === "F2") { e.preventDefault(); renameFolder(); }
    else if (e.key === "Enter" && st.sel.size === 1 && (document.activeElement === document.body || document.activeElement === null))
      placeInGame([...st.sel][0]);
  });
}

// ---------------------------------------------------------------------------------------------
/* Deep link: #view=L&scope=Tanks/Heavy&q=text&select=id1,id2 (bookmarks, screenshots) */
function applyHash() {
  const h = new URLSearchParams(location.hash.slice(1));
  if (["L", "G", "R"].includes(h.get("view"))) st.view = h.get("view");
  if (h.get("scope")) st.scope = h.get("scope");
  if (h.get("q")) { st.search = h.get("q"); $("#search").value = st.search; }
  for (const id of (h.get("select") || "").split(",")) if (st.byId.has(id)) { st.sel.add(id); st.focus = st.focus || id; }
}

async function main() {
  applyStaticTexts();
  setStatus("status.loading");
  bindEvents();
  try {
    await loadState();
    setStatus("status.saved");
  } catch (e) {
    setStatus("status.loadFailed", true);
    const msg = String(e && e.message || "");
    $("#items").innerHTML = `<div class="empty">${esc(msg.startsWith("state") ? t("load.unreadable") : msg)}</div>`;
    toast(t("toast.loadFailed"), true);
    return;
  }
  applyHash();
  render();
  setInterval(pollRev, 2000);
  setInterval(() => api("POST", "/api/heartbeat").catch(() => {}), 5000);
  api("POST", "/api/heartbeat").catch(() => {});
  window.addEventListener("pagehide", () => {
    try { navigator.sendBeacon("/api/bye?t=" + encodeURIComponent(window.BR_TOKEN)); } catch (e) { /* ignore */ }
  });
}
main();
