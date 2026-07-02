"use strict";
const $ = (s, r = document) => r.querySelector(s);
const el = (t, p = {}, ...k) => { const e = document.createElement(t); Object.assign(e, p); for (const c of k) e.append(c); return e; };
async function jget(u) { return (await fetch(u)).json(); }
async function jpost(u, b) { return (await fetch(u, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) })).json(); }
const setStatus = (s) => $("#status").textContent = s;

const URLP = new URLSearchParams(location.search);
const SECTION = URLP.get("section") || "all";
const EMBED = URLP.get("embed") === "1";
if (EMBED) document.documentElement.classList.add("embed");
const S = {
  id: null, w: 0, h: 0, indices: null, palette: null, sel: 1, zoom: 12,
  dirty: false, painting: false, section: SECTION, osmode: false, os: null, cols: 1,
  undoStack: [], strokeBefore: null, strokeChanged: false, paintKey: ""
};

async function loadList() {
  const p = new URLSearchParams({ type: $("#type").value, q: $("#q").value,
    curated: $("#curated").checked ? "1" : "", text: $("#textonly").checked ? "1" : "0" });
  if (S.section && S.section !== "all") p.set("section", S.section);
  const d = await jget("/api/sprites?" + p);
  const tsel = $("#type");
  if (tsel.options.length <= 1) for (const t of d.types) if (t) tsel.append(el("option", { value: t, textContent: t }));
  setStatus(`${d.count} 표시 · 텍스트 ${d.text_total} / 전체 ${d.total} · 편집됨 ${d.edited_count}`);
  const list = $("#list"); list.textContent = "";
  for (const s of d.sprites) list.append(card(s));
}
function card(s) {
  const img = el("img", { src: `/api/render?id=${encodeURIComponent(s.id)}&which=${s.edited ? "edit" : "orig"}`, loading: "lazy" });
  const meta = el("div", { className: "meta" },
    el("b", { className: "desc", textContent: s.desc || s.id }),
    el("span", { className: "src", textContent: `${s.type} ${s.width}×${s.height} · ${s.id}` }));
  if (s.edited) meta.append(el("span", { className: "ed", textContent: " ●편집됨" }));
  const c = el("div", { className: "card" }, img, meta);
  c.onclick = () => { document.querySelectorAll(".card").forEach(x => x.classList.remove("on")); c.classList.add("on"); selectSprite(s.id); };
  return c;
}

async function selectSprite(id) {
  const t = await jget(`/api/tile?id=${encodeURIComponent(id)}`);
  if (!t.ok) { setStatus("오류: " + t.error); return; }
  S.id = id; S.w = t.width; S.h = t.height; S.indices = t.indices; S.cols = t.tile_cols || (t.width / 8);
  S.palette = (t.palette || []).map(c => c.slice(0, 3));
  while (S.palette.length < 16) S.palette.push([0, 0, 0]);
  S.dirty = false; S.os = null; S.osmode = false;
  resetUndo();
  $("#info").textContent = `${t.desc || id} · ${t.type} ${t.width}×${t.height} · ${t.offset || ""} ${t.edited ? "(편집본)" : ""}`;
  $("#save").disabled = true; $("#revert").disabled = !t.edited;
  $("#compare").disabled = false;
  // 실제 화면 형태(WYSIWYG) — 레이아웃 있으면 기본 화면 편집
  $("#mode-screen").disabled = !t.has_onscreen;
  if (t.has_onscreen) {
    const o = await jget(`/api/onscreen_data?id=${encodeURIComponent(id)}`);
    if (o.ok) { S.os = o; S.osmode = true; S.palette = o.palette.map(c => c.slice(0, 3)); }
  }
  setMode(S.osmode ? "screen" : "tile");
  refreshOnscreen(t.has_onscreen && !S.osmode);
  drawPalette(); draw();
}
function setMode(m) {
  S.osmode = (m === "screen") && !!S.os;
  $("#mode-screen").classList.toggle("on", S.osmode);
  $("#mode-tile").classList.toggle("on", !S.osmode);
  if (S.indices) { drawPalette(); draw(); }
}
function refreshOnscreen(has) {
  const wrap = $("#onscreenwrap");
  if (has && S.id) {
    $("#onscreen").src = `/api/onscreen?id=${encodeURIComponent(S.id)}&t=${Date.now()}`;
    wrap.hidden = false;
  } else { wrap.hidden = true; }
}

async function showCompare() {
  if (!S.id) return;
  setStatus("비교 렌더 중…");
  const r = await jget(`/api/compare?id=${encodeURIComponent(S.id)}`);
  if (!r.ok) { setStatus("비교 오류: " + r.error); return; }
  const bust = "&t=" + Date.now();
  $("#cmpOrig").src = (r.orig_url || "") + bust;
  $("#cmpPatched").src = r.patched_url ? r.patched_url + bust : "";
  if (r.edit_url) { $("#cmpEdit").src = r.edit_url + bust; $("#cmpEditFig").hidden = false; }
  else $("#cmpEditFig").hidden = true;
  $("#cmpInfo").textContent = `${r.id} · ${r.type} · ${r.offset || ""} · ${r.build_changed ? "빌드에서 변경됨" : "빌드 동일"}`;
  $("#cmpNote").textContent = r.note + (r.build_changed ? "" : "  (원본과 적용 빌드가 동일 — 이 스프라이트는 빌드에서 수정되지 않음.)");
  $("#cmpModal").hidden = false;
  setStatus("비교 표시");
}

let PALS = [];
async function loadPalettes() {
  const r = await jget("/api/palettes");
  PALS = r.palettes || [];
  const sel = $("#palpick"); sel.length = 1;
  // OBJ 먼저(스프라이트용), 그다음 BG
  for (const region of ["OBJ", "BG"]) {
    const grp = PALS.filter(p => p.region === region);
    if (!grp.length) continue;
    const og = el("optgroup", { label: region });
    grp.forEach((p, i) => og.append(el("option", { value: p.name, textContent: p.name })));
    sel.append(og);
  }
}
function applyPalette(name) {
  const p = PALS.find(x => x.name === name);
  if (!p || !S.indices) return;
  S.palette = p.colors.map(c => c.slice(0, 3));
  while (S.palette.length < 16) S.palette.push([0, 0, 0]);
  drawPalette(); draw();
  $("#palfix").disabled = false;
  setStatus("팔레트 적용: " + name + " (고정하려면 ‘고정’)");
}
function rgb(c) { return `rgb(${c[0]},${c[1]},${c[2]})`; }
function drawPalette() {
  const sw = $("#swatches"); sw.textContent = "";
  S.palette.forEach((c, i) => {
    const d = el("div", { className: "sw" + (i === S.sel ? " on" : ""), title: `index ${i}` }, el("span", { textContent: i }));
    d.style.background = rgb(c);
    d.onclick = () => { S.sel = i; $("#selidx").textContent = i; drawPalette(); };
    d.ondblclick = () => {
      const cur = "#" + c.map(v => v.toString(16).padStart(2, "0")).join("");
      const v = prompt(`index ${i} 색 (hex, 원본색)`, cur);
      if (v && /^#?[0-9a-fA-F]{6}$/.test(v)) {
        const h = v.replace("#", ""); S.palette[i] = [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
        S.dirty = true; $("#save").disabled = false; drawPalette(); draw();
      }
    };
    sw.append(d);
  });
  $("#selidx").textContent = S.sel;
}
// 현재 indices에서 (linear tile T, 읽기 좌표 rx,ry) → indices 그리드 픽셀
function tilePixel(T, rx, ry) {
  const gx = (T % S.cols) * 8 + rx, gy = Math.floor(T / S.cols) * 8 + ry;
  return (S.indices[gy] && S.indices[gy][gx] !== undefined) ? (S.indices[gy][gx] & 15) : 0;
}
function setTilePixel(T, rx, ry, v) {
  const gx = (T % S.cols) * 8 + rx, gy = Math.floor(T / S.cols) * 8 + ry;
  if (S.indices[gy] && S.indices[gy][gx] !== undefined) S.indices[gy][gx] = v;
}
function cloneIndices() {
  return S.indices ? S.indices.map(row => Array.isArray(row) ? row.slice() : []) : null;
}
function resetUndo() {
  S.undoStack = [];
  S.strokeBefore = null;
  S.strokeChanged = false;
  S.paintKey = "";
  updateUndoButton();
}
function updateUndoButton() {
  const btn = $("#undo");
  if (btn) btn.disabled = !S.undoStack.length;
}
function beginStroke() {
  if (!S.indices) return;
  S.strokeBefore = cloneIndices();
  S.strokeChanged = false;
  S.paintKey = "";
}
function markStrokeChanged() {
  S.strokeChanged = true;
}
function finishStroke() {
  if (S.strokeBefore && S.strokeChanged) {
    S.undoStack.push(S.strokeBefore);
    if (S.undoStack.length > 80) S.undoStack.shift();
  }
  S.strokeBefore = null;
  S.strokeChanged = false;
  S.paintKey = "";
  updateUndoButton();
}
function undoDraw() {
  const prev = S.undoStack.pop();
  if (!prev) return;
  S.indices = cloneGrid(prev);
  S.painting = false;
  S.paintKey = "";
  S.dirty = true;
  $("#save").disabled = false;
  draw();
  updateUndoButton();
}
function cloneGrid(grid) {
  return grid ? grid.map(row => Array.isArray(row) ? row.slice() : []) : null;
}
function drawOnscreen() {
  const o = S.os, z = S.zoom, cv = $("#cv");
  cv.width = o.w * z; cv.height = o.h * z;
  const g = cv.getContext("2d");
  // 투명(idx0) 체커보드 배경
  for (let y = 0; y < o.h; y++) for (let x = 0; x < o.w; x++) {
    g.fillStyle = ((x >> 2) + (y >> 2)) & 1 ? "#2a2a2a" : "#222"; g.fillRect(x * z, y * z, z, z);
  }
  for (const c of o.cells) {
    for (let ty = 0; ty < c.th; ty++) for (let tx = 0; tx < c.tw; tx++) {
      const T = c.tile_off + (o.obj1d ? ty * c.tw + tx : ty * 32 + tx);
      for (let yy = 0; yy < 8; yy++) for (let xx = 0; xx < 8; xx++) {
        const idx = tilePixel(T, c.fh ? 7 - xx : xx, c.fv ? 7 - yy : yy);
        if (idx === 0) continue;
        const sx = (c.x - o.x0) + (c.fh ? c.tw - 1 - tx : tx) * 8 + xx;
        const sy = (c.y - o.y0) + (c.fv ? c.th - 1 - ty : ty) * 8 + yy;
        g.fillStyle = rgb(S.palette[idx]); g.fillRect(sx * z, sy * z, z, z);
      }
    }
  }
}
function paintOnscreenAt(ev) {
  const o = S.os, cv = $("#cv"), r = cv.getBoundingClientRect();
  const ax = Math.floor((ev.clientX - r.left) / S.zoom), ay = Math.floor((ev.clientY - r.top) / S.zoom);
  for (const c of o.cells) {
    const cx = c.x - o.x0, cy = c.y - o.y0;
    if (ax < cx || ay < cy || ax >= cx + c.tw * 8 || ay >= cy + c.th * 8) continue;
    const sl = ax - cx, st = ay - cy;
    const txs = Math.floor(sl / 8), xx = sl % 8, tys = Math.floor(st / 8), yy = st % 8;
    const tx = c.fh ? c.tw - 1 - txs : txs, ty = c.fv ? c.th - 1 - tys : tys;
    const rx = c.fh ? 7 - xx : xx, ry = c.fv ? 7 - yy : yy;
    const T = c.tile_off + (o.obj1d ? ty * c.tw + tx : ty * 32 + tx);
    const key = `${T}:${rx}:${ry}`;
    if (key === S.paintKey) return;
    S.paintKey = key;
    if (tilePixel(T, rx, ry) === S.sel) return;
    setTilePixel(T, rx, ry, S.sel); S.dirty = true; $("#save").disabled = false;
    markStrokeChanged();
    drawOnscreen();
    return;
  }
}
function draw() {
  if (S.osmode && S.os) return drawOnscreen();
  const z = S.zoom, cv = $("#cv"); cv.width = S.w * z; cv.height = S.h * z;
  const g = cv.getContext("2d");
  for (let y = 0; y < S.h; y++) for (let x = 0; x < S.w; x++) { g.fillStyle = rgb(S.palette[S.indices[y][x] & 15]); g.fillRect(x * z, y * z, z, z); }
  if ($("#grid").checked && z >= 6) {
    g.strokeStyle = "rgba(0,0,0,.18)"; g.lineWidth = 1;
    for (let x = 0; x <= S.w; x++) { g.beginPath(); g.moveTo(x * z, 0); g.lineTo(x * z, S.h * z); g.stroke(); }
    for (let y = 0; y <= S.h; y++) { g.beginPath(); g.moveTo(0, y * z); g.lineTo(S.w * z, y * z); g.stroke(); }
    g.strokeStyle = "rgba(0,80,255,.5)"; g.lineWidth = 1;  // 8px 타일 경계
    for (let x = 0; x <= S.w; x += 8) { g.beginPath(); g.moveTo(x * z, 0); g.lineTo(x * z, S.h * z); g.stroke(); }
    for (let y = 0; y <= S.h; y += 8) { g.beginPath(); g.moveTo(0, y * z); g.lineTo(S.w * z, y * z); g.stroke(); }
  }
}
function paintAt(ev) {
  if (!S.indices) return;
  if (S.osmode && S.os) return paintOnscreenAt(ev);
  const cv = $("#cv"), r = cv.getBoundingClientRect();
  const x = Math.floor((ev.clientX - r.left) / S.zoom), y = Math.floor((ev.clientY - r.top) / S.zoom);
  if (x < 0 || y < 0 || x >= S.w || y >= S.h) return;
  const key = `${x}:${y}`;
  if (key === S.paintKey) return;
  S.paintKey = key;
  if (S.indices[y][x] === S.sel) return;
  S.indices[y][x] = S.sel; S.dirty = true; $("#save").disabled = false;
  markStrokeChanged();
  const g = cv.getContext("2d"); g.fillStyle = rgb(S.palette[S.sel]); g.fillRect(x * S.zoom, y * S.zoom, S.zoom, S.zoom);
}

function wire() {
  let t; $("#q").oninput = () => { clearTimeout(t); t = setTimeout(loadList, 250); };
  $("#type").onchange = loadList; $("#curated").onchange = loadList; $("#textonly").onchange = loadList;
  $("#zoomin").onclick = () => { S.zoom = Math.min(40, S.zoom + 2); $("#zoomlbl").textContent = S.zoom + "×"; if (S.indices) draw(); };
  $("#zoomout").onclick = () => { S.zoom = Math.max(2, S.zoom - 2); $("#zoomlbl").textContent = S.zoom + "×"; if (S.indices) draw(); };
  $("#grid").onchange = () => { if (S.indices) draw(); };
  $("#mode-screen").onclick = () => { setMode("screen"); refreshOnscreen(false); };
  $("#mode-tile").onclick = () => { setMode("tile"); refreshOnscreen(!!S.os); };
  const cv = $("#cv");
  cv.onmousedown = (e) => {
    if (e.button !== 0) return;
    e.preventDefault();
    beginStroke();
    S.painting = true;
    paintAt(e);
    window.addEventListener("mouseup", () => { S.painting = false; finishStroke(); }, { once: true });
  };
  cv.onmousemove = (e) => { if (S.painting) paintAt(e); };
  $("#undo").onclick = undoDraw;
  document.addEventListener("keydown", (e) => {
    const tag = (e.target && e.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || e.target?.isContentEditable) return;
    if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key.toLowerCase() === "z") {
      if (!S.undoStack.length) return;
      e.preventDefault();
      undoDraw();
    }
  });
  $("#save").onclick = async () => {
    if (!S.id) return;
    const r = await jpost("/api/save", { id: S.id, indices: S.indices, palette: S.palette });
    if (r.ok) { setStatus(`저장됨 ${S.id} (raw ${r.raw_len}B / 원본 ${r.orig_size}B, fits=${r.fits_raw})`); S.dirty = false; $("#save").disabled = true; $("#revert").disabled = false; loadList(); refreshOnscreen(!$("#onscreenwrap").hidden); }
    else setStatus("오류: " + r.error);
  };
  $("#revert").onclick = async () => {
    if (!S.id || !confirm("편집을 되돌릴까요?")) return;
    await jpost("/api/revert", { id: S.id }); resetUndo(); selectSprite(S.id); loadList();
  };
  $("#applybuild").onclick = async () => {
    if (!confirm("저장된 모든 편집을 재빌드로 ROM에 반영합니다(수십 초 소요). 진행할까요?")) return;
    const btn = $("#applybuild"); btn.disabled = true; setStatus("재빌드 중… (편집을 ROM에 반영)");
    try {
      const r = await jpost("/api/build", {});
      if (r.ok) { setStatus("반영 완료 ✓ " + (r.applied || "(오버라이드 없음)")); if (S.id) selectSprite(S.id); }
      else setStatus("빌드 실패: " + (r.error || "").slice(0, 200));
    } catch (e) { setStatus("빌드 호출 오류: " + e); }
    btn.disabled = false;
  };
  $("#compare").onclick = showCompare;
  $("#cmpClose").onclick = () => { $("#cmpModal").hidden = true; };
  $("#cmpModal").onclick = (e) => { if (e.target.id === "cmpModal") $("#cmpModal").hidden = true; };
  $("#palpick").onchange = (e) => applyPalette(e.target.value);
  $("#palfix").onclick = async () => {
    if (!S.id || !S.palette) return;
    const r = await jpost("/api/setpalette", { id: S.id, palette: S.palette });
    setStatus(r.ok ? `팔레트 고정 저장: ${S.id}` : "오류: " + r.error);
    if (r.ok) loadList();
  };
}
wire(); loadPalettes(); loadList();
