"use strict";
// AW 통합 화면(scene) 에디터 프런트엔드 (vanilla JS)
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const api = async (p, opt) => (await fetch(p, opt)).json();

const S = { scope: "all", scenes: [], scene: null, items: null, itab: "dialogue", item: null, dict: null, supported: null, dirty: 0 };

// ── 바이트 예산(Python encoded_len 미러: 한글2/전각공백2/줄바꿈1/ASCII1/기타2) ──
function encLen(t) {
  let n = 0;
  for (const ch of t) {
    const c = ch.codePointAt(0);
    if (c >= 0xAC00 && c <= 0xD7A3) n += 2;        // 완성형 한글
    else if (ch === "　") n += 2;                   // 전각 공백
    else if (ch === "\n") n += 1;                   // 줄바꿈 0x0A
    else if (c >= 0x20 && c <= 0x7E) n += 1;        // ASCII
    else n += 2;
  }
  return n;
}

// 폰트 미수록(2350 밖) 완성형 한글 = 인게임 '?'. 서버 syl 셋과 동일 판정.
function unsupportedChars(t) {
  if (!S.supported) return [];
  const bad = [];
  for (const ch of t) {
    const c = ch.codePointAt(0);
    if (c >= 0xAC00 && c <= 0xD7A3 && !S.supported.has(ch) && !bad.includes(ch)) bad.push(ch);
  }
  return bad;
}
async function loadSupported() {
  try { const d = await api("/api/syllables"); S.supported = new Set(d.syllables); }
  catch (e) { S.supported = null; }
}

function toast(msg, bad) {
  const t = $("#toast"); t.textContent = msg; t.hidden = false;
  t.className = bad ? "bad" : ""; clearTimeout(toast._t);
  toast._t = setTimeout(() => (t.hidden = true), 2600);
}

// ── GNB / 상태 ──────────────────────────────────────────────────────────
async function refreshState() {
  try {
    const st = await api("/api/state");
    const rom = st.rom.exists ? `ROM ${st.rom.sha256} · ${(st.rom.size / 1048576).toFixed(0)}MB` : "ROM 없음";
    const dirtyN = (st.dirty.dialogue_overrides || 0) + (st.dirty.sprite_overrides || 0);
    S.dirty = dirtyN;
    const dirty = dirtyN ? `<span class="warn">· 편집 ${dirtyN}건(미빌드)</span>` : `<span class="ok">· 동기</span>`;
    let build = "";
    if (st.build.status === "building") build = ` <span class="warn">· 빌드중…</span>`;
    else if (st.build.status === "fail") build = ` <span class="bad">· 빌드실패</span>`;
    $("#state").innerHTML = `${rom} ${dirty}${build}`;
    $("#apply").disabled = st.build.status === "building";
    $("#download").disabled = !st.rom.exists || st.build.status === "building";
    return st;
  } catch (e) { $("#state").textContent = "상태 조회 실패"; }
}

// ── 홈: scene 카드 ──────────────────────────────────────────────────────
async function loadScenes() {
  const q = $("#q").value.trim();
  const d = await api(`/api/scenes?scope=${S.scope}&q=${encodeURIComponent(q)}`);
  S.scenes = d.scenes;
  const c = d.coverage || {};
  $("#coverage").textContent =
    `scene ${d.scenes.length}개 · 대사그룹 ${c.dialogue_assigned}/${c.dialogue_groups_total} 배정 · ` +
    `텍스트 스프라이트 ${c.sprites_assigned}개 · 미배정 검토 ${c.dialogue_unassigned + (c.sprites_unassigned - (c.sprites_unassigned_scan_lz77 || 0))}건(+미분류 그래픽 ${c.sprites_unassigned_scan_lz77})`;
  const grid = $("#scenegrid"); grid.innerHTML = "";
  const SCOPE_KO = { all: "공통", shared_select: "선택", part1: "1편", part2: "2편" };
  for (const s of d.scenes) {
    const el = document.createElement("div");
    el.className = "card" + (s.id === "99_unassigned_review" ? " review" : "");
    el.innerHTML =
      `<div class="ord">#${(s.order / 10) | 0} · ${s.id}</div>
       <div class="title">${s.title}</div>
       <div class="chips"><span class="chip">${s.subtag}</span><span class="chip scope">${SCOPE_KO[s.scope] || s.scope}</span></div>
       <div class="counts">대사 <b>${s.counts.dialogue}</b> · 스프라이트 <b>${s.counts.sprite}</b></div>
       <div class="cv ${s.canvas_status}">실캡처 ${s.canvas_status === "ready" ? "지원" : "미지원"}</div>`;
    el.onclick = () => openScene(s.id);
    grid.appendChild(el);
  }
}

// ── scene 상세 ──────────────────────────────────────────────────────────
async function openScene(id) {
  S.scene = id; S.item = null;
  S.items = await api(`/api/scene/items?id=${encodeURIComponent(id)}&type=all`);
  $("#home").hidden = true; $("#scene").hidden = false;
  $("#sceneTitle").textContent = S.items.title;
  $("#sceneMeta").textContent = `${S.items.subtag} · 실캡처 ${S.items.canvas_status === "ready" ? "지원(" + S.items.canvas + ")" : "미지원"}`;
  $("#cntD").textContent = `(${S.items.dialogue.length})`;
  $("#cntS").textContent = `(${S.items.sprites.length})`;
  S.itab = S.items.dialogue.length ? "dialogue" : "sprite";
  renderTabs(); renderItems();
  $("#editor").innerHTML = `<div class="empty">가운데에서 편집할 항목을 선택하세요.</div>`;
}

function renderTabs() {
  $$("#scene .itemtabs button").forEach(b => b.classList.toggle("on", b.dataset.it === S.itab));
}

function renderItems() {
  const box = $("#itemlist"); box.innerHTML = "";
  if (S.itab === "dialogue") {
    if (!S.items.dialogue.length) { box.innerHTML = `<div class="row"><span class="ja">대사 없음</span></div>`; return; }
    S.items.dialogue.forEach((g, i) => {
      const ko = g.members.map(m => m.ko).join(" ");
      const over = g.members.some(m => !m.budget.estimated && encLen(m.ko || "") > m.budget.slot);
      const el = document.createElement("div");
      el.className = "row";
      el.innerHTML = `<div class="ja">${esc(g.assembled_ja || "")}</div>
        <div class="ko ${over ? "over" : ""}">${esc(ko || "(미번역)")}${g.size > 1 ? `<span class="badge">${g.size}조각</span>` : ""}${over ? `<span class="badge over">초과</span>` : ""}</div>`;
      el.onclick = () => selectDialogue(i, el);
      box.appendChild(el);
    });
  } else {
    if (!S.items.sprites.length) { box.innerHTML = `<div class="row"><span class="ja">스프라이트 없음</span></div>`; return; }
    S.items.sprites.forEach((sp, i) => {
      const el = document.createElement("div");
      el.className = "row";
      el.innerHTML = `<img class="thumb" src="/api/sprite/render?id=${encodeURIComponent(sp.id)}&which=patched" onerror="this.style.display='none'">
        <span class="ko">${esc(sp.desc)}</span> <span class="ja">${esc(sp.type)} ${esc(sp.offset || "")}</span>`;
      el.onclick = () => selectSprite(i, el);
      box.appendChild(el);
    });
  }
}

const esc = s => (s || "").replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
function markSel(el) { $$("#itemlist .row").forEach(r => r.classList.remove("sel")); el.classList.add("sel"); }

// ── 대사 편집(요구7: 줄당 바이트 예산 + 멀티라인) ─────────────────────────
function selectDialogue(i, el) {
  markSel(el);
  const g = S.items.dialogue[i]; S.item = { kind: "dialogue", g, i };
  const ed = $("#editor");
  let html = `<h3>대사 편집 — ${esc(S.items.title)}</h3>
    <div class="sub">${g.size}조각 · region ${g.region}${g.flagged ? " · ⚠flagged" : ""}</div>`;
  g.members.forEach((m, mi) => {
    const ed = m.budget.editable;
    if (!ed) {
      html += `<div class="frag readonly" data-addr="${m.address}" data-mi="${mi}">
        <div class="fja">원문: ${esc(m.ja || "")} <span class="ja">@${m.address}</span></div>
        <div class="ko">${esc(m.ko || "(미번역)")}</div>
        <div class="fragfoot"><span class="est">🔒 편집 불가 — ${esc(m.budget.reason || "빌드 미적용")}</span></div></div>`;
      return;
    }
    html += `<div class="frag" data-addr="${m.address}" data-mi="${mi}">
      <div class="fja">원문: ${esc(m.ja || "")} <span class="ja">@${m.address}</span></div>
      <div class="lines"></div>
      <div class="fragfoot">
        <button class="addline" type="button">+ 줄</button>
        <button class="delline" type="button">− 줄</button>
        <span class="budget" data-total>·</span>
      </div></div>`;
  });
  html += `<div class="dictwarn" id="dictwarn"></div>
    <div class="btnrow">
      <button id="dSave">저장</button>
      <button id="dPreview" ${S.items.canvas_status === "ready" ? "" : "disabled title='이 화면은 실캡처 미지원'"}>미리보기(원본↔편집)</button>
      <button id="dCheck">사전 검사</button>
    </div>`;
  ed.innerHTML = html;
  // 각 편집가능 fragment의 라인 입력 생성(readonly 제외)
  $$("#editor .frag:not(.readonly)").forEach((fr) => {
    const mi = +fr.dataset.mi;
    const m = g.members[mi];
    const lines = (m.ko || "").split("\n");
    buildLines(fr, m, lines.length ? lines : [""]);
    fr.querySelector(".addline").onclick = () => { addLine(fr, m); };
    fr.querySelector(".delline").onclick = () => { delLine(fr, m); };
  });
  $("#dSave").onclick = saveDialogue;
  $("#dPreview").onclick = previewDialogue;
  $("#dCheck").onclick = checkDict;
}

function buildLines(fr, m, lines) {
  const box = fr.querySelector(".lines"); box.innerHTML = "";
  lines.forEach(ln => addLineInput(box, ln));
  bindFrag(fr, m);
  updateFragBudget(fr, m);
}
function addLineInput(box, val) {
  const row = document.createElement("div"); row.className = "lineinput";
  const inp = document.createElement("input");
  inp.type = "text";
  inp.value = val || "";
  const span = document.createElement("span");
  span.className = "budget";
  span.textContent = "·";
  row.appendChild(inp);
  row.appendChild(span);
  box.appendChild(row);
}
function addLine(fr, m) {
  if (fr.querySelectorAll(".lineinput").length >= 4) return toast("최대 4줄");
  addLineInput(fr.querySelector(".lines"), ""); bindFrag(fr, m); updateFragBudget(fr, m);
}
function delLine(fr, m) {
  const rows = fr.querySelectorAll(".lineinput");
  if (rows.length <= 1) return;
  rows[rows.length - 1].remove(); updateFragBudget(fr, m);
}
function bindFrag(fr, m) {
  $$(".lineinput input", fr).forEach(inp => { inp.oninput = () => updateFragBudget(fr, m); });
}
function fragText(fr) { return $$(".lineinput input", fr).map(i => i.value).join("\n"); }
function updateFragBudget(fr, m) {
  const slot = m.budget.slot;
  let total = 0, badAll = [];
  $$(".lineinput", fr).forEach(row => {
    const inp = row.querySelector("input"); const b = row.querySelector(".budget");
    const ln = encLen(inp.value); total += ln;
    const bad = unsupportedChars(inp.value); badAll = badAll.concat(bad);
    b.textContent = `${ln}B`;
    b.className = "budget" + (bad.length ? " over" : "");
    inp.style.borderColor = bad.length ? "var(--bad)" : "";
  });
  const nlines = fr.querySelectorAll(".lineinput").length;
  total += (nlines - 1); // 줄바꿈 바이트
  const tb = fr.querySelector("[data-total]");
  const over = !m.budget.estimated && total > slot;
  let txt = `합계 ${total}/${slot}B (≤${m.budget.max_syllables}자)`;
  if (badAll.length) txt += ` · 미수록 ${[...new Set(badAll)].join("")}`;
  tb.textContent = txt;
  tb.className = "budget" + (over || badAll.length ? " over" : (total > slot * 0.85 ? " warn" : ""));
  fr._over = over; fr._bad = [...new Set(badAll)];
}

async function saveDialogue() {
  const g = S.item.g;
  let anyOver = false, anyBad = [];
  const writes = [];
  $$("#editor .frag:not(.readonly)").forEach((fr) => {
    if (fr._over) anyOver = true;
    if (fr._bad && fr._bad.length) anyBad = anyBad.concat(fr._bad);
    writes.push({ address: g.members[+fr.dataset.mi].address, ko: fragText(fr) });
  });
  if (!writes.length) return toast("편집 가능한 조각이 없습니다", true);
  if (anyOver) return toast("슬롯 초과 — 저장 불가(줄여 주세요)", true);
  if (anyBad.length) return toast("폰트 미수록 음절 — 저장 불가: " + [...new Set(anyBad)].join(""), true);
  for (const w of writes) {
    const r = await api("/api/dialogue/line", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(w) });
    if (!r.ok) return toast("저장 실패: " + (r.error || ""), true);  // 서버 하드게이트
    const m = g.members.find(x => x.address === w.address); if (m) m.ko = w.ko;
  }
  toast("저장됨(빌드 전까지 미반영)"); refreshState(); renderItems();
  return true;
}

async function previewDialogue() {
  const g = S.item.g;
  // 멀티 조각이면 첫 조각 기준(canvas 슬롯 길이 한계). assembled로 합쳐 표시.
  const ja = g.assembled_ja || (g.members[0] && g.members[0].ja) || "";
  const ko = g.members.map((m, mi) => {
    if (m.budget.editable) {
      const fr = $(`#editor .frag[data-mi="${mi}"]`);
      return fr ? fragText(fr) : (m.ko || "");
    }
    return m.ko || "";
  }).join(" ").replace(/\n/g, " ");
  S.applyAction = saveDialogue;  // 모달 '적용' = 현재 편집 저장 후 빌드
  openModal("미리보기 — 원본 ↔ 편집(실캡처)", `<div class="note">캡처 중… (헤드리스 mGBA, 수십 초 소요)</div>`);
  $("#modalApply").disabled = true;
  const r = await api("/api/dialogue/preview", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ja, ko, canvas: S.items.canvas }) });
  if (!r.ok) { $("#modalGrid").innerHTML = `<div class="note bad">${esc(r.error || "캡처 실패")}</div>`; return; }
  $("#modalGrid").innerHTML =
    `<figure><figcaption>원본 (일본판)</figcaption><img src="${r.orig.url}?t=${Date.now()}"><div class="note">${esc(r.orig.text)}</div></figure>
     <figure><figcaption>편집 (한글)</figcaption><img src="${r.applied.url}?t=${Date.now()}"><div class="note">${esc(r.applied.text)}${r.applied.truncated ? " ⚠잘림" : ""}</div></figure>`;
  $("#modalNote").textContent = "‘적용(빌드)’을 누르면 저장된 편집이 ROM에 반영됩니다.";
  $("#modalApply").disabled = false;
}

async function checkDict() {
  const w = $("#dictwarn"); w.textContent = "검사 중…";
  if (!S.dict) S.dict = await api("/api/dict");
  const g = S.item.g; const issues = [];
  const cats = Object.entries(S.dict).filter(([k, v]) => Array.isArray(v));
  for (const m of g.members) {
    const ko = fragTextFor(m.address);
    for (const [cat, list] of cats) for (const e of list) {
      const eja = (e.ja || "").trim(), eko = ((e.edit || "").trim() || (e.ko || "").trim());
      if (eja && eko && (m.ja || "").includes(eja) && !ko.includes(eko))
        issues.push(`${eja}→${eko}(${cat})`);
    }
  }
  w.textContent = issues.length ? "사전 불일치: " + [...new Set(issues)].join(", ") : "사전 일치 ✓";
  w.style.color = issues.length ? "" : "var(--ok)";
}
function fragTextFor(addr) {
  const fr = $(`#editor .frag[data-addr="${addr}"]`);
  if (!fr) return "";
  if (fr.classList.contains("readonly")) {
    const mi = +fr.dataset.mi;
    return (S.item.g.members[mi] && S.item.g.members[mi].ko) || "";
  }
  return fragText(fr);
}

// ── 스프라이트 편집 ──────────────────────────────────────────────────────
const SP = { id: null, w: 0, h: 0, cols: 0, grid: null, pal: null, sel: 1, zoom: 10, type: null };
async function selectSprite(i, el) {
  markSel(el);
  const sp = S.items.sprites[i]; S.item = { kind: "sprite", sp, i };
  const d = await api(`/api/sprite/tile?id=${encodeURIComponent(sp.id)}`);
  if (!d.ok) { $("#editor").innerHTML = `<div class="empty">디코드 실패: ${esc(d.error || "")}</div>`; return; }
  SP.id = sp.id; SP.w = d.width; SP.h = d.height; SP.cols = d.tile_cols; SP.grid = d.indices;
  SP.pal = d.palette; SP.type = d.type; SP.sel = 1;
  const ed = $("#editor");
  ed.innerHTML = `<h3>스프라이트 편집 — ${esc(sp.desc)}</h3>
    <div class="sub">${esc(sp.type)} ${esc(sp.offset || "")} · ${d.width}×${d.height}px${d.edited ? " · 편집됨" : ""}</div>
    <div id="spwrap"><canvas id="spcv"></canvas></div>
    <div class="swatches" id="swatches"></div>
    <div class="sphint">스와치 클릭=색 선택, 캔버스 클릭/드래그=칠하기. 색은 표시용(실기 팔레트는 화면별 적용).</div>
    <div class="btnrow">
      <button id="spZoomOut">−</button><button id="spZoomIn">+</button>
      <button id="spSave">저장</button>
      <button id="spRevert">되돌리기</button>
      <button id="spCompare">원본↔적용 비교</button>
    </div>`;
  renderSwatches(); drawSprite();
  $("#spZoomOut").onclick = () => { SP.zoom = Math.max(4, SP.zoom - 2); drawSprite(); };
  $("#spZoomIn").onclick = () => { SP.zoom = Math.min(24, SP.zoom + 2); drawSprite(); };
  $("#spSave").onclick = saveSprite;
  $("#spRevert").onclick = revertSprite;
  $("#spCompare").onclick = compareSprite;
}
function renderSwatches() {
  const box = $("#swatches"); box.innerHTML = "";
  SP.pal.forEach((c, i) => {
    const sw = document.createElement("div");
    sw.className = "sw" + (i === SP.sel ? " sel" : "");
    sw.style.background = `rgb(${c[0]},${c[1]},${c[2]})`;
    sw.title = "색 " + i;
    sw.onclick = () => { SP.sel = i; renderSwatches(); };
    box.appendChild(sw);
  });
}
function drawSprite() {
  const cv = $("#spcv"); const z = SP.zoom;
  cv.width = SP.w * z; cv.height = SP.h * z;
  const ctx = cv.getContext("2d");
  for (let y = 0; y < SP.h; y++) for (let x = 0; x < SP.w; x++) {
    const c = SP.pal[SP.grid[y][x] & 15] || [0, 0, 0];
    ctx.fillStyle = `rgb(${c[0]},${c[1]},${c[2]})`;
    ctx.fillRect(x * z, y * z, z, z);
  }
  let painting = false;
  const paint = (e) => {
    const r = cv.getBoundingClientRect();
    const x = Math.floor((e.clientX - r.left) / z), y = Math.floor((e.clientY - r.top) / z);
    if (x < 0 || y < 0 || x >= SP.w || y >= SP.h) return;
    SP.grid[y][x] = SP.sel;
    const c = SP.pal[SP.sel]; ctx.fillStyle = `rgb(${c[0]},${c[1]},${c[2]})`; ctx.fillRect(x * z, y * z, z, z);
  };
  cv.onmousedown = e => {
    painting = true;
    paint(e);
    window.addEventListener("mouseup", () => (painting = false), { once: true });
  };
  cv.onmousemove = e => { if (painting) paint(e); };
}
async function saveSprite() {
  const r = await api("/api/sprite/save", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: SP.id, indices: SP.grid, palette: SP.pal }) });
  if (!r.ok) return toast("저장 실패: " + (r.error || ""), true);
  toast(`저장됨 (raw ${r.raw_len}B, fit=${r.fits_raw})`); refreshState();
}
async function revertSprite() {
  await api("/api/sprite/revert", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: SP.id }) });
  toast("되돌림");
  S.items = await api(`/api/scene/items?id=${encodeURIComponent(S.scene)}&type=all`);
  selectSprite(S.item.i, $$("#itemlist .row")[S.item.i]);
  renderItems();
  refreshState();
}
async function compareSprite() {
  const c = await api(`/api/sprite/compare?id=${encodeURIComponent(SP.id)}`);
  if (!c.ok) return toast(c.error || "비교 실패", true);
  let g = `<figure><figcaption>원본(일본판)</figcaption><img src="${c.orig_url}&t=${Date.now()}"></figure>`;
  if (c.patched_url) g += `<figure><figcaption>적용(한글 빌드)</figcaption><img src="${c.patched_url}&t=${Date.now()}"></figure>`;
  if (c.edit_url) g += `<figure><figcaption>편집중</figcaption><img src="${c.edit_url}&t=${Date.now()}"></figure>`;
  S.applyAction = saveSprite;  // 모달 '적용' = 현재 canvas 편집 저장 후 빌드
  openModal("스프라이트 — 원본 ↔ 적용 비교", g);
  $("#modalNote").textContent = c.build_changed ? "빌드 ROM이 원본과 다름(한글화 반영됨)." : "빌드 ROM이 원본과 동일.";
  $("#modalApply").disabled = false;
}

// ── 모달 / 빌드(적용) / 다운로드 ─────────────────────────────────────────
function openModal(title, gridHtml) {
  $("#modalTitle").textContent = title; $("#modalGrid").innerHTML = gridHtml;
  $("#modalNote").textContent = ""; $("#modal").hidden = false;
}
$("#modalClose").onclick = () => ($("#modal").hidden = true);
$("#modalApply").onclick = async () => {
  // 적용 = (현재 편집 저장) → 전체 빌드. 미저장 편집이 빌드에 빠지지 않게.
  if (S.applyAction) { const ok = await S.applyAction(); if (ok === false) return; }
  $("#modal").hidden = true; applyBuild();
};

async function applyBuild() {
  const r = await api("/api/build", { method: "POST" });
  if (!r.ok) return toast(r.error || "빌드 시작 실패", true);
  toast("전체 재빌드 시작… 완료까지 대기");
  pollBuild();
}
async function pollBuild() {
  const j = await api("/api/jobs");
  refreshState();
  if (j.status === "building") return setTimeout(pollBuild, 2500);
  if (j.status === "success") {
    // lz77 재압축 초과 등으로 일부 편집이 skip될 수 있음 → 로그에 skip 흔적 있으면 경고
    const skipped = /skip|초과|comp_size|overflow/i.test(j.log_tail || "");
    toast(skipped ? "빌드 완료(일부 편집 skip 가능 — 로그 확인)" : "빌드 완료 — ROM 반영됨. 다운로드 가능.", skipped);
  } else if (j.status === "fail") toast("빌드 실패: " + (j.error || "").slice(0, 120), true);
}
$("#download").onclick = () => {
  if (S.dirty > 0 && !confirm(`미빌드 편집 ${S.dirty}건이 있습니다. 지금 받는 ROM에는 반영되지 않습니다.\n먼저 ‘적용(빌드)’을 권장합니다. 그래도 현재 ROM을 받으시겠습니까?`)) return;
  window.location = "/api/download/gba?variant=full";
};
$("#apply").onclick = applyBuild;

// ── 이벤트 바인딩 ───────────────────────────────────────────────────────
$$("#scope button").forEach(b => b.onclick = () => {
  $$("#scope button").forEach(x => x.classList.toggle("on", x === b));
  S.scope = b.dataset.scope; loadScenes();
});
$("#q").oninput = () => { clearTimeout($("#q")._t); $("#q")._t = setTimeout(loadScenes, 250); };
$("#back").onclick = () => { $("#scene").hidden = true; $("#home").hidden = false; S.scene = null; };
$$("#scene .itemtabs button").forEach(b => b.onclick = () => {
  S.itab = b.dataset.it;
  renderTabs();
  renderItems();
  $("#editor").innerHTML = `<div class="empty">가운데에서 편집할 항목을 선택하세요.</div>`;
});

// 시작
loadSupported(); loadScenes(); refreshState(); setInterval(refreshState, 8000);
