"use strict";
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
async function api(p, o) {
  const r = await fetch(p, o);
  if (!r.ok) { let m = r.statusText; try { const j = await r.json(); m = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch {} throw new Error(m); }
  return r.json();
}
function msg(t, err) { const m = $("#msg"); m.textContent = t || ""; m.className = err ? "err" : ""; if (t) setTimeout(() => { if (m.textContent === t) m.textContent = ""; }, 6000); }
const TIPS = {
  conf: "Detection confidence threshold", imgsz: "YOLO inference size", stride: "Process every Nth frame",
  tolerance_deg: "Default angular tolerance for zones (deg)", ww_min_opposed_s: "Opposed heading must last at least this long (s)",
  ww_borderline_s: "Opposed 0.8..min s => insufficient evidence", ww_min_disp: "Net displacement against direction (bbox-heights, or metres with homography)",
  ww_turn_deg: "Heading rotation above this = a turn, not wrong-way", ww_min_in_zone: "Min fraction of track inside the zone",
  stationary_speed: "Below this speed a bike counts as stopped (bbox-heights/s or m/s)", min_quality: "Min track quality (0-1) for a confident event",
  cw_min_frames: "Min frames with ground point inside crosswalk", cw_min_extent_frac: "Displacement through crosswalk / its extent",
  cw_walk_speed: "At/below this speed = walking pace", event_merge_s: "Merge events on same track closer than this (s)",
  merge_max_gap_s: "Max gap to merge fragmented tracks (s)", min_track_s: "Tracks shorter than this are low-confidence and skipped",
  max_interp_gap: "Interpolate gaps up to this many frames", vel_window_s: "Velocity window (s)", smooth_window: "Savitzky-Golay window (frames)",
};
const emptyCfg = () => ({ zones: [], crosswalks: [], homography_points: null, ground_size: [10, 10], default_direction: null, thresholds: {} });
let vid = null, cfg = emptyCfg(), defaults = {}, img = new Image();
let tool = "select", draft = [], arrowPts = [], pendingPoly = null, sel = null, drag = null, undo = [], pollTimer = null;

// ---------- videos ----------
async function loadVideos() {
  const vs = await api("/api/videos");
  $("#videos").innerHTML = "";
  vs.forEach(v => {
    const li = document.createElement("li"); if (vid && vid.id === v.id) li.className = "on";
    li.innerHTML = `<span>${v.filename}<small>${v.width}×${v.height} · ${v.fps.toFixed(1)} fps · ${v.duration_s.toFixed(1)} s</small></span>`;
    const d = document.createElement("button"); d.textContent = "✕"; d.title = "Delete video";
    d.onclick = async e => { e.stopPropagation(); if (!confirm("Delete this video and its results?")) return;
      try { await api("/api/videos/" + v.id, { method: "DELETE" }); if (vid && vid.id === v.id) { vid = null; $("#work").hidden = true; $("#empty").hidden = false; } loadVideos(); } catch (x) { msg(x.message, 1); } };
    li.append(d); li.onclick = () => selectVideo(v.id); $("#videos").append(li);
  });
}
$("#upBtn").onclick = () => {
  const f = $("#file").files[0]; if (!f) return msg("Choose a video file first", 1);
  const x = new XMLHttpRequest(), fd = new FormData(); fd.append("file", f);
  x.open("POST", "/api/videos"); $("#upProg").hidden = false;
  x.upload.onprogress = e => { if (e.lengthComputable) $("#upProg").value = e.loaded / e.total * 100; };
  x.onload = () => { $("#upProg").hidden = true;
    if (x.status === 200) { msg("Uploaded"); loadVideos().then(() => selectVideo(JSON.parse(x.responseText).id)); }
    else { let m = "Upload failed"; try { m = JSON.parse(x.responseText).detail; } catch {} msg(m, 1); } };
  x.onerror = () => { $("#upProg").hidden = true; msg("Upload failed (network)", 1); };
  x.send(fd);
};
async function selectVideo(id) {
  clearTimeout(pollTimer);
  vid = await api("/api/videos/" + id);
  const c = await api(`/api/videos/${id}/config`); cfg = Object.assign(emptyCfg(), c.config); defaults = c.defaults;
  undo = []; draft = []; arrowPts = []; pendingPoly = null; sel = null;
  $("#empty").hidden = true; $("#work").hidden = false; $("#job").hidden = true;
  img = new Image(); img.onload = () => { const cv = $("#cv"); cv.width = vid.width; cv.height = vid.height; redraw(); };
  img.src = `/api/videos/${id}/frame`;
  $("#defdir").value = cfg.default_direction ?? ""; $("#gw").value = cfg.ground_size[0]; $("#gh").value = cfg.ground_size[1];
  renderThr(); renderItems(); loadVideos(); await refreshJobs();
  const jobs = await api(`/api/videos/${id}/jobs`);
  const live = jobs.find(j => j.status === "queued" || j.status === "running");
  if (live) poll(live.id);
  showTab(jobs.some(j => j.status === "done") ? "res" : "cfg");
}
function showTab(t) {
  $("#cfg").hidden = t !== "cfg"; $("#res").hidden = t !== "res";
  $("#tabCfg").classList.toggle("on", t === "cfg"); $("#tabRes").classList.toggle("on", t === "res");
  if (t === "res") loadResults();
}
$("#tabCfg").onclick = () => showTab("cfg"); $("#tabRes").onclick = () => showTab("res");

// ---------- config canvas ----------
const cv = $("#cv"), cx = cv.getContext("2d");
const HINT = {
  select: "Click a shape to select; drag its vertices to edit. Delete removes it.",
  crosswalk: "Click to add polygon corners, then 'Finish polygon' (or double-click).",
  zone: "Click polygon corners, 'Finish polygon', then click twice: arrow start and end (permitted direction).",
  homography: "Click 4 ground-plane corners: top-left, top-right, bottom-right, bottom-left of a rectangle of known size.",
};
function setTool(t) { tool = t; draft = []; arrowPts = []; pendingPoly = null; $("#hint").textContent = HINT[t]; redraw(); }
$$("input[name=tool]").forEach(r => r.onchange = () => setTool(r.value)); $("#hint").textContent = HINT.select;
const pt = e => { const r = cv.getBoundingClientRect(); return [(e.clientX - r.left) * cv.width / r.width, (e.clientY - r.top) * cv.height / r.height]; };
const inPoly = (p, poly) => { let a = false; for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) { const [xi, yi] = poly[i], [xj, yj] = poly[j]; if ((yi > p[1]) !== (yj > p[1]) && p[0] < (xj - xi) * (p[1] - yi) / (yj - yi) + xi) a = !a; } return a; };
const snapshot = () => undo.push(JSON.stringify(cfg));
function arrowFrom(c, deg, len = 50) { const r = deg * Math.PI / 180, d = [Math.cos(r) * len, Math.sin(r) * len]; return [[c[0] - d[0] / 2, c[1] - d[1] / 2], [c[0] + d[0] / 2, c[1] + d[1] / 2]]; }
const centroid = poly => poly.reduce((a, p) => [a[0] + p[0] / poly.length, a[1] + p[1] / poly.length], [0, 0]);
function arrow(c, a, b, col) { c.strokeStyle = c.fillStyle = col; c.lineWidth = 3; c.beginPath(); c.moveTo(...a); c.lineTo(...b); c.stroke(); const t = Math.atan2(b[1] - a[1], b[0] - a[0]); c.beginPath(); c.moveTo(...b); c.lineTo(b[0] - 14 * Math.cos(t - .4), b[1] - 14 * Math.sin(t - .4)); c.lineTo(b[0] - 14 * Math.cos(t + .4), b[1] - 14 * Math.sin(t + .4)); c.fill(); }
function poly(c, p, col, fill, closed = true) { if (!p.length) return; c.beginPath(); p.forEach((q, i) => i ? c.lineTo(...q) : c.moveTo(...q)); if (closed) c.closePath(); if (fill) { c.fillStyle = fill; c.fill(); } c.strokeStyle = col; c.lineWidth = 2; c.stroke(); }
function drawZones(c, ids) {
  cfg.crosswalks.forEach(z => poly(c, z.polygon, "#ffd400", "#ffd40033"));
  cfg.zones.forEach(z => { if (!z.polygon.length) return; poly(c, z.polygon, "#3b9eff", "#3b9eff33"); const [a, b] = arrowFrom(centroid(z.polygon), z.direction_deg); arrow(c, a, b, "#3b9eff"); if (z.two_way) arrow(c, b, a, "#3b9eff"); });
}
function redraw() {
  if (!vid) return; cx.clearRect(0, 0, cv.width, cv.height); cx.drawImage(img, 0, 0);
  drawZones(cx);
  if (sel) { const s = cfg[sel.kind][sel.i]; if (s) { poly(cx, s.polygon, "#fff", null); s.polygon.forEach(p => { cx.fillStyle = "#fff"; cx.fillRect(p[0] - 5, p[1] - 5, 10, 10); }); } }
  const pp = pendingPoly || draft; poly(cx, pp, "#0f0", null, !!pendingPoly); pp.forEach(p => { cx.fillStyle = "#0f0"; cx.fillRect(p[0] - 3, p[1] - 3, 6, 6); });
  if (arrowPts.length === 2) arrow(cx, arrowPts[0], arrowPts[1], "#0f0");
  const H = cfg.homography_points; if (H) { poly(cx, H, "#f0f", null, H.length === 4); H.forEach((p, i) => { cx.fillStyle = "#f0f"; cx.font = "16px sans-serif"; cx.fillText(i + 1, p[0] + 6, p[1] - 6); }); }
}
function finishPoly() {
  if (draft.length < 3) return msg("Need at least 3 points", 1);
  if (tool === "crosswalk") { snapshot(); cfg.crosswalks.push({ id: "cw" + (cfg.crosswalks.length + 1) + "_" + Date.now() % 1000, polygon: draft }); sel = { kind: "crosswalks", i: cfg.crosswalks.length - 1 }; draft = []; }
  else if (tool === "zone") { pendingPoly = draft; draft = []; $("#hint").textContent = "Now click the arrow start, then the arrow end."; }
  renderItems(); redraw();
}
$("#finish").onclick = finishPoly; cv.ondblclick = () => { draft.pop(); finishPoly(); };   // the 2 mousedowns of a dblclick added a duplicate point
cv.onmousedown = e => {
  const p = pt(e);
  if (tool === "select") {
    if (sel) { const s = cfg[sel.kind][sel.i]; const vi = s && s.polygon.findIndex(q => Math.hypot(q[0] - p[0], q[1] - p[1]) < 10 * cv.width / cv.getBoundingClientRect().width); if (vi >= 0) { snapshot(); drag = vi; return; } }
    sel = null;
    for (const kind of ["zones", "crosswalks"]) cfg[kind].forEach((z, i) => { if (z.polygon.length && inPoly(p, z.polygon)) sel = { kind, i }; });
    renderItems(); redraw();
  } else if (tool === "homography") {
    if (!cfg.homography_points || cfg.homography_points.length >= 4) { snapshot(); cfg.homography_points = []; }
    cfg.homography_points.push(p); redraw();
  } else if (pendingPoly) {
    arrowPts.push(p);
    if (arrowPts.length === 2) {
      const [a, b] = arrowPts, deg = (Math.atan2(b[1] - a[1], b[0] - a[0]) * 180 / Math.PI + 360) % 360;
      snapshot(); cfg.zones.push({ id: "zone" + (cfg.zones.length + 1) + "_" + Date.now() % 1000, polygon: pendingPoly, direction_deg: Math.round(deg), tolerance_deg: +(defaults.tolerance_deg || 60), two_way: false });
      sel = { kind: "zones", i: cfg.zones.length - 1 }; pendingPoly = null; arrowPts = []; $("#hint").textContent = HINT.zone; renderItems();
    }
    redraw();
  } else { draft.push(p); redraw(); }
};
cv.onmousemove = e => { if (drag !== null && sel) { cfg[sel.kind][sel.i].polygon[drag] = pt(e); redraw(); } };
window.onmouseup = () => { drag = null; };
$("#undo").onclick = () => {
  if (draft.length) draft.pop(); else if (arrowPts.length) arrowPts.pop(); else if (pendingPoly) { draft = pendingPoly; pendingPoly = null; }
  else if (undo.length) { cfg = JSON.parse(undo.pop()); sel = null; renderItems(); } redraw();
};
$("#del").onclick = () => { if (!sel) return msg("Select a shape first", 1); snapshot(); cfg[sel.kind].splice(sel.i, 1); sel = null; renderItems(); redraw(); };
$("#clearH").onclick = () => { snapshot(); cfg.homography_points = null; redraw(); };
function renderItems() {
  const ul = $("#items"); ul.innerHTML = "";
  ["zones", "crosswalks"].forEach(kind => cfg[kind].forEach((z, i) => { const li = document.createElement("li");
    li.textContent = (kind === "zones" ? "↗ " : "▭ ") + z.id + (kind === "zones" ? ` (${z.direction_deg}°)` : ""); li.className = sel && sel.kind === kind && sel.i === i ? "on" : "";
    li.onclick = () => { sel = { kind, i }; renderItems(); redraw(); }; ul.append(li); }));
  const pr = $("#props"); pr.innerHTML = ""; if (!sel || !cfg[sel.kind][sel.i]) return;
  const z = cfg[sel.kind][sel.i]; if (sel.kind !== "zones") return;
  pr.innerHTML = `<h3>Selected zone</h3>
   <label>Direction (deg) <input type="number" id="pDir" value="${z.direction_deg}" step="1"></label>
   <label title="Allowed deviation from the permitted direction">Tolerance <input type="range" id="pTol" min="10" max="90" value="${z.tolerance_deg}"> <span id="pTolV">${z.tolerance_deg}°</span></label>
   <label><input type="checkbox" id="pTwo" ${z.two_way ? "checked" : ""}> two-way (never wrong-way)</label>`;
  $("#pDir").onchange = e => { snapshot(); z.direction_deg = ((+e.target.value % 360) + 360) % 360; renderItems(); redraw(); };
  $("#pTol").oninput = e => { z.tolerance_deg = +e.target.value; $("#pTolV").textContent = z.tolerance_deg + "°"; };
  $("#pTol").onchange = () => snapshot();
  $("#pTwo").onchange = e => { snapshot(); z.two_way = e.target.checked; redraw(); };
}
function renderThr() {
  const box = $("#thr"); box.innerHTML = "";
  Object.entries(defaults).filter(([, v]) => typeof v === "number").forEach(([k, v]) => {
    const l = document.createElement("label"); l.title = TIPS[k] || k; l.innerHTML = `<span>${k}</span>`;
    const i = document.createElement("input"); i.type = "number"; i.step = "any"; i.placeholder = v; i.value = cfg.thresholds[k] ?? "";
    i.onchange = () => { if (i.value === "") delete cfg.thresholds[k]; else cfg.thresholds[k] = +i.value; }; l.append(i); box.append(l);
  });
}
async function save() {
  const dd = $("#defdir").value; cfg.default_direction = dd === "" ? null : +dd; cfg.ground_size = [+$("#gw").value || 10, +$("#gh").value || 10];
  if (cfg.homography_points && cfg.homography_points.length !== 4) { msg("Homography needs exactly 4 points (or clear it)", 1); return false; }
  try { await api(`/api/videos/${vid.id}/config`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cfg) }); msg("Config saved"); return true; }
  catch (e) { msg("Save failed: " + e.message, 1); return false; }
}
$("#save").onclick = save;
$("#process").onclick = async () => {
  if (!(await save())) return;
  try { const r = await api(`/api/videos/${vid.id}/process`, { method: "POST" }); poll(r.job_id); } catch (e) { msg(e.message, 1); }
};
function poll(jobId) {
  $("#job").hidden = false;
  const tick = async () => {
    let j; try { j = await api("/api/jobs/" + jobId); } catch (e) { $("#jtxt").textContent = "Error: " + e.message; return; }
    $("#jprog").value = j.progress * 100;
    if (j.status === "error") { $("#jtxt").textContent = "FAILED: " + j.error; $("#jtxt").style.color = "var(--bad)"; return; }
    $("#jtxt").style.color = "";
    if (j.status === "done") { $("#jtxt").textContent = `Done in ${j.processing.duration_s}s (${j.processing.fps} FPS)`; await refreshJobs(jobId); showTab("res"); return; }
    $("#jtxt").textContent = `${j.status} · ${j.stage || ""} · ${(j.progress * 100).toFixed(0)}%` + (j.eta_s != null ? ` · ETA ${j.eta_s.toFixed(0)}s` : "") + (j.fps ? ` · ${j.fps.toFixed(1)} FPS` : "");
    pollTimer = setTimeout(tick, 1000);
  };
  clearTimeout(pollTimer); tick();
}

// ---------- results ----------
let jobId = null, tracks = [], events = [], fps = 25, selTrack = null, selEvent = null;
const show = { boxes: true, ids: true, traj: true, zones: true };
async function refreshJobs(pick) {
  const jobs = (await api(`/api/videos/${vid.id}/jobs`)).filter(j => j.status === "done");
  const s = $("#jobSel"); s.innerHTML = jobs.map(j => `<option value="${j.id}">${new Date(j.created * 1000).toLocaleString()} (${j.id})</option>`).join("");
  if (pick) s.value = pick;
}
$("#jobSel").onchange = loadResults;
async function loadResults() {
  jobId = $("#jobSel").value; if (!jobId) { events = []; tracks = []; renderEvents(); return; }
  const [ev, tr] = await Promise.all([api(`/api/jobs/${jobId}/events`), api(`/api/jobs/${jobId}/tracks`)]);
  events = ev; tracks = tr.tracks; fps = tr.fps; selTrack = selEvent = null;
  $("#exJson").href = `/api/jobs/${jobId}/export?format=json`; $("#exCsv").href = `/api/jobs/${jobId}/export?format=csv`;
  setSource(); renderEvents(); $("#detail").innerHTML = "<small>Click an event to review its evidence.</small>";
}
function setSource() { const v = $("#vid"); const b = $("#burned").checked; v.src = `/api/jobs/${jobId}/video?variant=${b ? "annotated" : "clean"}`; $("#ov").style.display = b ? "none" : ""; }
$("#burned").onchange = () => { const t = $("#vid").currentTime; setSource(); $("#vid").onloadedmetadata = () => { $("#vid").currentTime = t; }; };
$$("[data-show]").forEach(c => c.onchange = () => { show[c.dataset.show] = c.checked; });
const step = d => { const v = $("#vid"); v.pause(); v.currentTime = Math.max(0, v.currentTime + d / fps); };
$("#back").onclick = () => step(-1); $("#fwd").onclick = () => step(1);
function seek(t) { const v = $("#vid"); v.pause(); v.currentTime = t; }
const bis = (a, x) => { let lo = 0, hi = a.length; while (lo < hi) { const m = (lo + hi) >> 1; if (a[m] <= x) lo = m + 1; else hi = m; } return lo - 1; };
function overlay() {
  requestAnimationFrame(overlay);
  const v = $("#vid"), o = $("#ov"); if ($("#res").hidden || !vid || !jobId) return;
  if (o.width !== vid.width) { o.width = vid.width; o.height = vid.height; }
  const c = o.getContext("2d"); c.clearRect(0, 0, o.width, o.height);
  const f = Math.round(v.currentTime * fps); $("#fr").textContent = `frame ${f} · ${v.currentTime.toFixed(2)}s`;
  if (show.zones) drawZones(c);
  const active = new Map(events.filter(e => e.start_frame <= f && f <= e.end_frame).map(e => [e.track_id, e]));
  c.font = "bold 16px sans-serif"; c.lineWidth = 2;
  tracks.forEach(t => {
    if (f < t.start_frame || f > t.end_frame) return;
    const i = bis(t.frames, f), b = t.boxes[i], ev = active.get(t.id), hot = ev || t.id === selTrack;
    const col = hot ? (ev && ev.status === "insufficient_evidence" ? "#f5a524" : "#ff3b3b") : t.low_confidence ? "#999" : "#00c8ff";
    if (show.traj) { c.strokeStyle = col; c.beginPath(); const from = t.id === selTrack ? 0 : Math.max(0, i - 60); for (let k = from; k <= i; k++) { const bb = t.boxes[k], x = (bb[0] + bb[2]) / 2; k === from ? c.moveTo(x, bb[3]) : c.lineTo(x, bb[3]); } c.stroke(); }
    if (show.boxes) { c.strokeStyle = col; c.lineWidth = hot ? 4 : 2; c.strokeRect(b[0], b[1], b[2] - b[0], b[3] - b[1]); c.lineWidth = 2; }
    if (show.ids) { c.fillStyle = col; c.fillText("#" + t.id + (t.low_confidence ? " (low conf)" : "") + (ev ? (ev.type === "wrong_way" ? " WRONG WAY" : " CROSSWALK") + (ev.status === "insufficient_evidence" ? "?" : "") : ""), b[0], Math.max(b[1] - 6, 14)); }
  });
}
requestAnimationFrame(overlay);

// ---------- events ----------
const label = { wrong_way: "Wrong way", crosswalk_riding: "Crosswalk riding" };
function filtered() { const t = $("#fType").value, s = $("#fStatus").value, r = $("#fReview").value, c = +$("#fConf").value || 0;
  return events.filter(e => (!t || e.type === t) && (!s || e.status === s) && (!r || e.review === r) && e.confidence >= c); }
function renderEvents() {
  const tb = $("#evt tbody"); tb.innerHTML = "";
  filtered().forEach(e => { const tr = document.createElement("tr"); if (selEvent && selEvent.event_id === e.event_id) tr.className = "on";
    tr.innerHTML = `<td>${label[e.type]}</td><td><span class="badge ${e.status}">${e.status === "suspected" ? "Suspected" : "Insufficient evidence"}</span></td><td>#${e.track_id}</td><td>${e.start_time_s.toFixed(1)}–${e.end_time_s.toFixed(1)}</td><td>${e.confidence.toFixed(2)}</td><td class="${e.review}">${e.review}</td>`;
    tr.onclick = () => { selEvent = e; selTrack = e.track_id; seek(e.start_time_s); renderEvents(); renderDetail(e); }; tb.append(tr); });
  if (!tb.children.length) tb.innerHTML = `<tr><td colspan="6"><small>No events${events.length ? " match the filters" : ""}.</small></td></tr>`;
}
["fType", "fStatus", "fReview", "fConf"].forEach(id => $("#" + id).onchange = renderEvents);
function renderDetail(e) {
  const merged = e.raw_track_ids.length > 1 ? ` (merged from raw IDs ${e.raw_track_ids.join(", ")})` : ` (raw ID ${e.raw_track_ids[0]})`;
  const ins = e.status === "insufficient_evidence" ? `<p><span class="badge insufficient_evidence">Insufficient evidence</span> — not forced into a classification; please review.</p>` : "";
  $("#detail").innerHTML = `<h3>${label[e.type]} · track #${e.track_id}${merged}</h3>${ins}
   <p>Time ${e.start_time_s.toFixed(2)}–${e.end_time_s.toFixed(2)} s (frames ${e.start_frame}–${e.end_frame}) · confidence ${e.confidence.toFixed(2)}
   ${e.rider_state ? `· rider: <b>${e.rider_state}</b>` : ""} ${e.zone_id ? "· zone " + e.zone_id : ""} ${e.crosswalk_id ? "· crosswalk " + e.crosswalk_id : ""}</p>
   <ul>${e.reasons.map(r => `<li>• ${r}</li>`).join("")}</ul>
   <pre>${JSON.stringify(e.metrics, null, 1)}</pre>
   <div class="thumbs">${e.evidence.map(n => `<img src="/api/jobs/${jobId}/evidence/${n}" alt="${n}" loading="lazy">`).join("")}</div>
   <div class="bar"><button id="ok">✔ Confirm</button><button id="no">✘ Reject</button><button id="rs">Reset</button><span>Review: <b class="${e.review}">${e.review}</b></span></div>`;
  $$("#detail .thumbs img").forEach(im => im.onclick = () => { $("#lightbox img").src = im.src; $("#lightbox").hidden = false; });
  const rv = async r => { try { const u = await api(`/api/events/${e.event_id}/review`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ review: r }) }); Object.assign(e, u); renderEvents(); renderDetail(e); } catch (x) { msg(x.message, 1); } };
  $("#ok").onclick = () => rv("confirmed"); $("#no").onclick = () => rv("rejected"); $("#rs").onclick = () => rv("pending");
}
$("#lightbox").onclick = () => { $("#lightbox").hidden = true; };

loadVideos().catch(e => msg(e.message, 1));
