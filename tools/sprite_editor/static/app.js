"use strict";
const $ = (s, r = document) => r.querySelector(s);
const el = (t, p = {}, ...k) => { const e = document.createElement(t); Object.assign(e, p); for (const c of k) e.append(c); return e; };
async function jget(u) { return (await fetch(u)).json(); }
async function jpost(u, b) { return (await fetch(u, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) })).json(); }
const setStatus = (s) => $("#status").textContent = s;

const S = { id: null, w: 0, h: 0, indices: null, palette: null, sel: 1, zoom: 12, dirty: false, painting: false };

async function loadList() {
  const p = new URLSearchParams({ type: $("#type").value, q: $("#q").value, curated: $("#curated").checked ? "1" : "" });
  const d = await jget("/api/sprites?" + p);
  const tsel = $("#type");
  if (tsel.options.length <= 1) for (const t of d.types) if (t) tsel.append(el("option", { value: t, textContent: t }));
  setStatus(`${d.count}/${d.total} 스프라이트 · 편집됨 ${d.edited_count}`);
  const list = $("#list"); list.textContent = "";
  for (const s of d.sprites) list.append(card(s));
}
function card(s) {
  const img = el("img", { src: `/api/png?id=${encodeURIComponent(s.id)}`, loading: "lazy" });
  const meta = el("div", { className: "meta" },
    el("b", { textContent: s.id }),
    el("span", { className: "src", textContent: `${s.type} ${s.width}×${s.height} ${s.source || ""}` }));
  if (s.edited) meta.append(el("span", { className: "ed", textContent: " ●편집됨" }));
  const c = el("div", { className: "card" }, img, meta);
  c.onclick = () => { document.querySelectorAll(".card").forEach(x => x.classList.remove("on")); c.classList.add("on"); selectSprite(s.id); };
  return c;
}

async function selectSprite(id) {
  const t = await jget(`/api/tile?id=${encodeURIComponent(id)}`);
  if (!t.ok) { setStatus("오류: " + t.error); return; }
  S.id = id; S.w = t.width; S.h = t.height; S.indices = t.indices;
  S.palette = (t.palette || []).map(c => c.slice(0, 3));
  while (S.palette.length < 16) S.palette.push([0, 0, 0]);
  S.dirty = false;
  $("#info").textContent = `${id}  ${t.type}  ${t.width}×${t.height}  ${t.offset || ""}  ${t.edited ? "(편집본)" : ""}`;
  $("#save").disabled = true; $("#revert").disabled = !t.edited;
  drawPalette(); draw();
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
function draw() {
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
  const cv = $("#cv"), r = cv.getBoundingClientRect();
  const x = Math.floor((ev.clientX - r.left) / S.zoom), y = Math.floor((ev.clientY - r.top) / S.zoom);
  if (x < 0 || y < 0 || x >= S.w || y >= S.h) return;
  if (S.indices[y][x] === S.sel) return;
  S.indices[y][x] = S.sel; S.dirty = true; $("#save").disabled = false;
  const g = cv.getContext("2d"); g.fillStyle = rgb(S.palette[S.sel]); g.fillRect(x * S.zoom, y * S.zoom, S.zoom, S.zoom);
}

function wire() {
  let t; $("#q").oninput = () => { clearTimeout(t); t = setTimeout(loadList, 250); };
  $("#type").onchange = loadList; $("#curated").onchange = loadList;
  $("#zoomin").onclick = () => { S.zoom = Math.min(40, S.zoom + 2); $("#zoomlbl").textContent = S.zoom + "×"; if (S.indices) draw(); };
  $("#zoomout").onclick = () => { S.zoom = Math.max(2, S.zoom - 2); $("#zoomlbl").textContent = S.zoom + "×"; if (S.indices) draw(); };
  $("#grid").onchange = () => { if (S.indices) draw(); };
  const cv = $("#cv");
  cv.onmousedown = (e) => { S.painting = true; paintAt(e); };
  cv.onmousemove = (e) => { if (S.painting) paintAt(e); };
  window.addEventListener("mouseup", () => S.painting = false);
  $("#save").onclick = async () => {
    if (!S.id) return;
    const r = await jpost("/api/save", { id: S.id, indices: S.indices, palette: S.palette });
    if (r.ok) { setStatus(`저장됨 ${S.id} (raw ${r.raw_len}B / 원본 ${r.orig_size}B, fits=${r.fits_raw})`); S.dirty = false; $("#save").disabled = true; $("#revert").disabled = false; loadList(); }
    else setStatus("오류: " + r.error);
  };
  $("#revert").onclick = async () => {
    if (!S.id || !confirm("편집을 되돌릴까요?")) return;
    await jpost("/api/revert", { id: S.id }); selectSprite(S.id); loadList();
  };
}
wire(); loadList();
