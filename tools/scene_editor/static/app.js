"use strict";
// AW 통합 화면(scene) 에디터 프런트엔드 (vanilla JS)
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
// 네트워크/HTTP 오류를 일관된 {ok:false,error} 또는 throw로(미처리 rejection 방지 — m2)
const api = async (p, opt) => {
  const res = await fetch(p, opt);
  if (!res.ok) {
    let body = {};
    try { body = await res.json(); } catch (e) { }
    return { ok: false, error: body.error || `HTTP ${res.status}`, _status: res.status };
  }
  return res.json();
};

const S = { scope: "all", scenes: [], scene: null, items: null, itab: "dialogue", item: null, dict: null, supported: null, dirty: 0, _reqSeq: 0, _limit: 0, applyAction: null };

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
    // dirty=빌드 후 override 파일이 더 새것(미빌드 변경 있음). 숫자는 누적 override 총량(델타 아님).
    const isDirty = st.dirty.dirty;
    const totalOv = (st.dirty.dialogue_total || 0) + (st.dirty.sprite_total || 0);
    S.dirty = isDirty ? totalOv : 0;
    const dirty = isDirty ? `<span class="warn">· 미빌드 변경 있음(override ${totalOv}건)</span>` : `<span class="ok">· 동기</span>`;
    let build = "";
    if (st.build.status === "building") build = ` <span class="warn">· 빌드중…</span>`;
    else if (st.build.status === "fail") build = ` <span class="bad">· 빌드실패</span>`;
    $("#state").innerHTML = `${rom} ${dirty}${build}`;
    $("#apply").disabled = st.build.status === "building";
    $("#download").disabled = !st.rom.exists || st.build.status === "building";
    return st;
  } catch (e) { $("#state").textContent = "상태 조회 실패"; }
}

const esc = s => (s || "").replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
const RENDER_LIMIT = 300;  // 한 scene 펼침 시 그리는 항목 상한(대형 scene jank 방지 — M2/M5)
const SCOPE_KO = { all: "공통", shared_select: "선택", part1: "1편", part2: "2편" };

function shotUrl(shot) {
  return shot && shot.exists && shot.url ? `${shot.url}?t=${shot.mtime || 0}` : "";
}
function sceneShotThumb(shot) {
  if (shot && shot.status === "container") {
    return `<span class="scene-shot missing container" title="잔여 대사 컨테이너"></span>`;
  }
  const url = shotUrl(shot);
  if (!url) return `<span class="scene-shot missing" title="실화면 캡처 없음"></span>`;
  const stale = shot && shot.stale === true ? ' title="⚠빌드와 불일치(stale)" style="outline:2px solid var(--warn)"' : "";
  return `<img class="scene-shot" loading="lazy" decoding="async" src="${url}" alt=""${stale}>`;
}
function sceneShotCard(shot) {
  const url = shotUrl(shot);
  const meta = shot && shot.checkpoint ? `${shot.checkpoint} · ${shot.grade || ""}` : "스크린샷 없음";
  const preview = S.items && S.items.canvas_status === "ready" ? "대사 프리뷰 지원" : "정적 캡처";
  if (shot && shot.status === "container") {
    const note = shot.note || "고유 실화면 캡처가 없는 잔여 대사 bucket입니다.";
    return `<div class="scene-proof missing container"><div><strong>잔여 대사 컨테이너 · 고유 실화면 없음</strong><span>${esc(note)}</span></div></div>`;
  }
  if (!url) return `<div class="scene-proof missing"><div><strong>실화면 캡처 없음</strong><span>${esc(meta)}</span></div></div>`;
  // stale(빌드 ROM과 불일치) 경고 — codex major
  const stale = shot && shot.stale === true
    ? ` <span class="badge over">⚠stale(빌드와 불일치 — 재캡처 필요)</span>` : "";
  return `<div class="scene-proof${shot && shot.stale === true ? " missing" : ""}">
    <img src="${url}" alt="">
    <div><strong>헤드리스 mGBA ${preview}</strong>${stale}<span>${esc(meta)}</span></div>
  </div>`;
}
function sceneExtraShotsCard(shots) {
  if (!shots || !shots.length) return "";
  const cells = shots.map(shot => {
    const url = shotUrl(shot);
    const label = shot.label || shot.checkpoint || "";
    const stale = shot && shot.stale === true ? " stale" : "";
    if (!url) {
      return `<div class="extra-shot missing"><span>${esc(label)}</span></div>`;
    }
    return `<figure class="extra-shot${stale}">
      <img loading="lazy" decoding="async" src="${url}" alt="">
      <figcaption>${esc(label)}</figcaption>
    </figure>`;
  }).join("");
  return `<div class="scene-extra"><div class="extra-title">실화면 프레임</div><div class="extra-grid">${cells}</div></div>`;
}

function showSceneOverview() {
  const ed = $("#editor");
  if (!ed || !S.items) return;
  const dCount = (S.items.dialogue || []).length;
  const sCount = (S.items.sprites || []).length;
  const body = dCount || sCount
    ? `<div class="empty">왼쪽에서 이 화면의 대사·스프라이트 항목을 선택하세요.</div>`
    : `<div class="empty">이 화면에는 편집 항목이 없습니다.</div>`;
  ed.innerHTML = `<h3>${esc(S.items.title || "화면")}</h3>
    <div class="sub">대사 ${dCount} · 스프라이트 ${sCount}</div>
    ${sceneShotCard(S.items.screenshot || {})}
    ${sceneExtraShotsCard(S.items.extra_screenshots || [])}
    ${body}`;
}

function sceneCountText(s) {
  const c = s.counts || {};
  if (s.id === "99_unassigned_review" && (c.sprite_scan_lz77 || c.sprite_font || c.sprite_text_candidate)) {
    return `대${c.dialogue || 0}·텍${c.sprite_text_candidate || 0}·그래픽${c.sprite_scan_lz77 || 0}`;
  }
  const rel = c.related_dialogue ? `·관련대${c.related_dialogue}` : "";
  const role = s.scene_role === "container" ? "·잔여" : "";
  return `대${c.dialogue || 0}${rel}·스${c.sprite || 0}${role}`;
}

function isReviewScene(s) {
  return s && (s.scope === "review" || s.id === "98_extraction_noise_review" || s.id === "99_unassigned_review");
}
function isContainerScene(s) {
  return s && s.scene_role === "container";
}

// ── 좌측 LNB: 게임순 scene 목록(아코디언) ─────────────────────────────────
async function loadScenes() {
  const q = $("#q").value.trim();
  S._reqSeq++;
  let d;
  try { d = await api(`/api/scenes?scope=${S.scope}&q=${encodeURIComponent(q)}`); }
  catch (e) { toast("scene 목록 로드 실패: " + e, true); return; }
  if (!d || !d.scenes) { toast("scene 목록 로드 실패: " + ((d && d.error) || ""), true); return; }
  S.scenes = d.scenes; S.scene = null; S.items = null; S.item = null;
  // scope/검색으로 목록 갱신 시 우측 에디터도 초기화(stale 편집 상태 방지 — agy major)
  $("#editor").innerHTML = `<div class="empty">왼쪽에서 화면을 펼쳐 편집할 항목(대사·스프라이트)을 선택하세요.</div>`;
  const c = d.coverage || {};
  const missingText = (c.dialogue_unassigned || 0) + (c.sprites_unassigned_text_candidate || 0);
  const missingFont = c.sprites_unassigned_font || 0;
  const missingGraphic = c.sprites_unassigned_scan_lz77 || 0;
  $("#coverage").textContent =
    `scene ${d.scenes.length} · 대사그룹 ${c.dialogue_assigned}/${c.dialogue_groups_total} · ` +
    `텍스트 스프 ${c.sprites_assigned} · 미배정 텍${missingText}·폰트${missingFont}·그래픽${missingGraphic}`;
  const box = $("#scenelist"); box.innerHTML = "";
  if (!d.scenes.length) { box.innerHTML = `<div class="empty">검색 결과가 없습니다.</div>`; return; }
  for (const s of d.scenes) {
    const row = document.createElement("div");
    row.className = "scene-row" + (isReviewScene(s) ? " review" : "") + (isContainerScene(s) ? " container" : "");
    row.dataset.sceneId = s.id;
    const cv = s.canvas_status === "ready" ? " · preview" : "";
    const role = isContainerScene(s) ? ` <span class="chip container">잔여</span>` : "";
    row.innerHTML =
      `<div class="scene-head">
         <span class="tw">▶</span>
         ${sceneShotThumb(s.screenshot)}
         <span class="st"><span class="title">${esc(s.title)}</span>
           <span class="sub"><span class="chip scope">${SCOPE_KO[s.scope] || s.scope}</span>${role} ${esc(s.subtag)}${cv}</span></span>
         <span class="cnt">${sceneCountText(s)}</span>
       </div>
       <div class="scene-items" hidden></div>`;
    row.querySelector(".scene-head").onclick = () => toggleScene(s, row);
    box.appendChild(row);
  }
}

async function toggleScene(s, row) {
  const head = row.querySelector(".scene-head");
  const items = row.querySelector(".scene-items");
  if (head.classList.contains("open")) {  // 접기
    head.classList.remove("open"); head.querySelector(".tw").textContent = "▶";
    items.hidden = true; items.innerHTML = "";
    S.scene = null; S.items = null; S.item = null;
    Object.assign(SP, { id: null, item: null, orig: null, cur: null, os: null, bgUrl: null });
    $("#editor").innerHTML = `<div class="placeholder">왼쪽에서 장면을 선택하세요.</div>`;
    return;
  }
  // 다른 열린 scene 접기(단일 펼침)
  $$("#scenelist .scene-head.open").forEach(h => {
    h.classList.remove("open"); h.querySelector(".tw").textContent = "▶";
    const si = h.parentElement.querySelector(".scene-items"); si.hidden = true; si.innerHTML = "";
  });
  const myReq = ++S._reqSeq;  // 연속 클릭 경합 방지(m3)
  items.innerHTML = `<div class="row"><span class="ja">로딩…</span></div>`; items.hidden = false;
  let data;
  try { data = await api(`/api/scene/items?id=${encodeURIComponent(s.id)}&type=all`); }
  catch (e) { items.innerHTML = `<div class="row"><span class="ja">로드 실패: ${esc("" + e)}</span></div>`; return; }
  if (myReq !== S._reqSeq) return;
  if (!data || !data.dialogue) { items.innerHTML = `<div class="row"><span class="ja">로드 실패</span></div>`; return; }
  S.scene = s.id; S.items = data; S.item = null; S._limit = RENDER_LIMIT;
  head.classList.add("open"); head.querySelector(".tw").textContent = "▼";
  renderSceneItems(items);
  showSceneOverview();
}

function renderSceneItems(box) {
  box.innerHTML = "";
  const D = S.items.dialogue, SPR = S.items.sprites;
  const frag = document.createDocumentFragment();
  const proof = document.createElement("div");
  proof.innerHTML = sceneShotCard(S.items.screenshot || {}) + sceneExtraShotsCard(S.items.extra_screenshots || []);
  [...proof.children].forEach(ch => frag.appendChild(ch));
  if (!D.length && !SPR.length) {
    const empty = document.createElement("div");
    empty.className = "row";
    empty.innerHTML = `<span class="ja">편집 항목 없음</span>`;
    frag.appendChild(empty);
    box.appendChild(frag);
    return;
  }
  const limit = S._limit;
  // 스프라이트: 편집 대상 화면을 먼저 보여준다. 썸네일도 가능하면 raw 타일시트가 아닌
  // onscreen 재배치 PNG를 사용해 좌측 목록과 편집면의 모양이 어긋나지 않게 한다.
  if (SPR.length) {
    frag.appendChild(sep(`스프라이트 ${SPR.length}`));
    const shown = Math.min(SPR.length, limit);
    for (let i = 0; i < shown; i++) {
      const sp = SPR[i];
      const el = document.createElement("div"); el.className = "row"; el.dataset.kind = "s"; el.dataset.i = i;
      const rawUrl = `/api/sprite/render?id=${encodeURIComponent(sp.id)}&which=patched`;
      const thumbUrl = sp.has_onscreen ? `/api/sprite/onscreen?id=${encodeURIComponent(sp.id)}` : rawUrl;
      el.innerHTML = `<img class="thumb" loading="lazy" decoding="async" src="${thumbUrl}" onerror="if(!this.dataset.f){this.dataset.f=1;this.src='${rawUrl}'}else if(!this.dataset.o){this.dataset.o=1;this.src='/api/sprite/render?id=${encodeURIComponent(sp.id)}&which=orig'}else{this.style.display='none'}">
        <span class="ko">${esc(sp.desc)}${sp.has_onscreen ? `<span class="badge">출력배치</span>` : ""}</span>`;
      el.onclick = () => selectSprite(i, el);
      frag.appendChild(el);
    }
    if (SPR.length > shown) frag.appendChild(moreRow(SPR.length - shown, box));
  }
  // 대사
  if (D.length) {
    frag.appendChild(sep(`대사 ${D.length}`));
    const shown = Math.min(D.length, limit);
    for (let i = 0; i < shown; i++) {
      const g = D[i];
      const ko = g.members.map(m => m.ko).join(" ");
      const over = g.members.some(m => !m.budget.estimated && m.budget.fits === false);
      const el = document.createElement("div"); el.className = "row"; el.dataset.kind = "d"; el.dataset.i = i;
      el.innerHTML = `<span class="ja">${esc(g.assembled_ja || "")}</span>
        <span class="ko ${over ? "over" : ""}">${esc(ko || "(미번역)")}${g.linked_from ? `<span class="badge">관련: ${esc(g.linked_from)}</span>` : ""}${g.size > 1 ? `<span class="badge">${g.size}조각</span>` : ""}${over ? `<span class="badge over">초과</span>` : ""}</span>`;
      el.onclick = () => selectDialogue(i, el);
      frag.appendChild(el);
    }
    if (D.length > shown) frag.appendChild(moreRow(D.length - shown, box));
  }
  box.appendChild(frag);
}
function sep(text) { const d = document.createElement("div"); d.className = "row kindsep"; d.textContent = text; return d; }
function moreRow(n, box) {
  const m = document.createElement("div"); m.className = "row more"; m.textContent = `+ ${n}개 더 보기`;
  m.onclick = (e) => { e.stopPropagation(); S._limit += RENDER_LIMIT; renderSceneItems(box); };
  return m;
}
function markSel(el) { $$("#lnb .row").forEach(r => r.classList.remove("sel")); el.classList.add("sel"); }
function openItemsBox() {
  const h = $("#scenelist .scene-head.open");
  return h ? h.parentElement.querySelector(".scene-items") : null;
}
// 열린 scene의 항목 목록 재렌더 + 현재 선택 복원(저장/되돌리기 후 LNB 갱신)
function refreshSceneItems() {
  const box = openItemsBox(); if (!box) return;
  renderSceneItems(box);
  if (S.item) {
    const k = S.item.kind === "dialogue" ? "d" : "s";
    const sel = box.querySelector(`.row[data-kind="${k}"][data-i="${S.item.i}"]`);
    if (sel) sel.classList.add("sel");
  }
}

// ── 대사 편집(요구7: 줄당 바이트 예산 + 멀티라인) ─────────────────────────
function selectDialogue(i, el) {
  markSel(el);
  const g = S.items.dialogue[i]; S.item = { kind: "dialogue", g, i };
  const ed = $("#editor");
  let html = `<h3>대사 편집 — ${esc(S.items.title)}</h3>
    <div class="sub">${g.size}조각 · region ${g.region}${g.flagged ? " · ⚠flagged" : ""}</div>
    ${sceneShotCard(S.items.screenshot || {})}
    ${sceneExtraShotsCard(S.items.extra_screenshots || [])}`;
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
  const fitLen = Number.isFinite(m.budget.encoded_len) ? m.budget.encoded_len : total;
  const over = !m.budget.estimated && m.budget.fits === false && fitLen > slot;
  let txt = `합계 ${fitLen}/${slot}B`;
  if (fitLen !== total) txt += ` (원문 ${total}B, 빌드 fit L${m.budget.fit_level})`;
  else txt += ` (≤${m.budget.max_syllables}자)`;
  if (badAll.length) txt += ` · 미수록 ${[...new Set(badAll)].join("")}`;
  tb.textContent = txt;
  tb.className = "budget" + (over || badAll.length ? " over" : (total > slot * 0.85 ? " warn" : ""));
  fr._over = over; fr._bad = [...new Set(badAll)];
}

// 저장 성공=true / 실패=false 일관 반환(모달 '적용' 게이트가 의존 — M1/M7).
async function saveDialogue() {
  const g = S.item.g;
  let anyOver = false, anyBad = [];
  const writes = [];
  $$("#editor .frag:not(.readonly)").forEach((fr) => {
    if (fr._over) anyOver = true;
    if (fr._bad && fr._bad.length) anyBad = anyBad.concat(fr._bad);
    writes.push({ address: g.members[+fr.dataset.mi].address, ko: fragText(fr) });
  });
  if (!writes.length) { toast("편집 가능한 조각이 없습니다", true); return false; }
  if (anyOver) { toast("슬롯 초과 — 저장 불가(줄여 주세요)", true); return false; }
  if (anyBad.length) { toast("폰트 미수록 음절 — 저장 불가: " + [...new Set(anyBad)].join(""), true); return false; }
  let saved = 0;
  for (const w of writes) {
    const r = await api("/api/dialogue/line", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(w) });
    if (!r.ok) {
      // 부분 저장(M3): 이미 기록된 조각을 화면에 반영하고 사실을 알림
      if (saved > 0) { refreshState(); refreshSceneItems(); toast(`일부만 저장(${saved}/${writes.length}) — 나머지 거부: ${r.error || ""}`, true); }
      else toast("저장 실패: " + (r.error || ""), true);
      return false;
    }
    const m = g.members.find(x => x.address === w.address); if (m) m.ko = w.ko;
    saved++;
  }
  toast("저장됨(빌드 전까지 미반영)"); refreshState(); refreshSceneItems();
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
const SP = {
  id: null, w: 0, h: 0, cols: 0, grid: null, pal: null, sel: 1,
  origW: 0, origH: 0, origCols: 0, origGrid: null, origPal: null,
  zoom: 3, osZoom: 3, type: null, mode: "tile", hasOnscreen: false,
  os: null, bgUrl: "", bgImg: null, bgReady: false, showBg: true,
  painting: false, paintKey: "", activePaletteKey: null
};
async function selectSprite(i, el) {
  markSel(el);
  const sp = S.items.sprites[i]; S.item = { kind: "sprite", sp, i };
  const myReq = ++S._reqSeq;  // 연속 클릭 경합 방지(agy major): 뒤늦은 응답이 현재 선택 덮어쓰지 않게
  const [d, orig] = await Promise.all([
    api(`/api/sprite/tile?id=${encodeURIComponent(sp.id)}`),
    api(`/api/sprite/tile?id=${encodeURIComponent(sp.id)}&which=orig`),
  ]);
  if (myReq !== S._reqSeq) return;  // 더 최신 선택이 있으면 폐기
  if (!d.ok) { $("#editor").innerHTML = `<div class="empty">디코드 실패: ${esc(d.error || "")}</div>`; return; }
  if (d.readonly) { renderReadonlySprite(sp, d); return; }
  SP.id = sp.id; SP.w = d.width; SP.h = d.height; SP.cols = d.tile_cols; SP.grid = d.indices;
  SP.pal = d.palette; SP.type = d.type; SP.sel = 1; SP.os = null; SP.hasOnscreen = !!d.has_onscreen;
  SP.origW = orig && orig.ok ? orig.width : d.width;
  SP.origH = orig && orig.ok ? orig.height : d.height;
  SP.origCols = orig && orig.ok ? orig.tile_cols : d.tile_cols;
  SP.origGrid = orig && orig.ok ? orig.indices : d.indices;
  SP.origPal = orig && orig.ok ? orig.palette : d.palette;
  SP.activePaletteKey = null;
  SP.mode = SP.hasOnscreen ? "onscreen" : "tile";
  SP.bgUrl = shotUrl(S.items && S.items.screenshot); SP.showBg = false;
  SP.bgImg = null; SP.bgReady = false;
  const ed = $("#editor");
  const layoutLabel = SP.hasOnscreen ? "타일 그리드 · 출력 크기 배치" : "타일 그리드 · 출력 크기";
  ed.innerHTML = `<h3>스프라이트 편집 — ${esc(sp.desc)}</h3>
    <div class="sub">${esc(sp.type)} ${esc(sp.offset || "")} · <span id="spDims">${d.width}×${d.height}px</span>${d.edited ? " · 편집됨" : ""}${SP.hasOnscreen ? " · 실화면 레이아웃 있음" : ""}</div>
    ${sceneShotCard(S.items.screenshot || {})}
    ${sceneExtraShotsCard(S.items.extra_screenshots || [])}
    <div class="sprite-mode">
      <span class="mode-label">${layoutLabel}</span>
      ${SP.hasOnscreen ? `<label class="bgcheck"><input id="spBg" type="checkbox">배경</label>` : ""}
    </div>
    <div class="sprite-workbench">
      <figure class="sprite-pane">
        <figcaption>원본</figcaption>
        <div id="sporigwrap"><canvas id="sporigcv"></canvas></div>
      </figure>
      <figure class="sprite-pane edit">
        <figcaption>편집</figcaption>
        <div id="spwrap"><canvas id="spcv"></canvas></div>
      </figure>
    </div>
    <div class="swatches" id="swatches"></div>
    <div class="sphint" id="sphint"></div>
    <div class="btnrow">
      <button id="spZoomOut">−</button><button id="spZoomIn">+</button>
      <button id="spSave">저장</button>
      <button id="spRevert">되돌리기</button>
      <button id="spCompare">원본↔적용 비교</button>
    </div>`;
  renderSwatches();
  const bg = $("#spBg");
  if (bg) bg.onchange = e => { SP.showBg = e.target.checked; drawCurrentSprite(); };
  await setSpriteMode(SP.mode);
  $("#spZoomOut").onclick = () => { if (SP.mode === "onscreen") SP.osZoom = Math.max(1, SP.osZoom - 1); else SP.zoom = Math.max(1, SP.zoom - 1); drawCurrentSprite(); };
  $("#spZoomIn").onclick = () => { if (SP.mode === "onscreen") SP.osZoom = Math.min(8, SP.osZoom + 1); else SP.zoom = Math.min(12, SP.zoom + 1); drawCurrentSprite(); };
  $("#spSave").onclick = saveSprite;
  $("#spRevert").onclick = revertSprite;
  $("#spCompare").onclick = compareSprite;
}

function renderReadonlySprite(sp, d) {
  SP.id = sp.id; SP.w = d.width; SP.h = d.height; SP.type = d.type; SP.grid = [];
  SP.mode = "readonly"; SP.hasOnscreen = false; SP.os = null; SP.activePaletteKey = null;
  SP.origGrid = null; SP.origCols = null; SP.origPal = null; SP.bgImg = null; SP.bgReady = false;
  const ed = $("#editor");
  const stamp = Date.now();
  ed.innerHTML = `<h3>스프라이트 확인 — ${esc(sp.desc)}</h3>
    <div class="sub">${esc(d.type || sp.type || "")} ${esc(sp.offset || "")} · ${d.width}×${d.height}px · 읽기 전용</div>
    ${sceneShotCard(S.items.screenshot || {})}
    ${sceneExtraShotsCard(S.items.extra_screenshots || [])}
    <div class="sprite-mode">
      <span class="mode-label">실화면 비트맵 리소스</span>
    </div>
    <div class="sprite-workbench">
      <figure class="sprite-pane">
        <figcaption>원본</figcaption>
        <img src="${d.orig_url}&t=${stamp}" alt="">
      </figure>
      <figure class="sprite-pane edit">
        <figcaption>적용</figcaption>
        <img src="${d.patched_url}&t=${stamp}" alt="">
      </figure>
    </div>
    <div class="sphint">${esc(d.readonly_reason || "이 리소스는 현재 픽셀 편집 저장을 지원하지 않습니다.")}</div>
    <div class="btnrow">
      <button id="spCompareReadonly">원본↔적용 비교</button>
    </div>`;
  $("#spCompareReadonly").onclick = compareReadonlySprite;
}

function updateSpriteDimsMeta() {
  const el = $("#spDims");
  if (!el) return;
  if (SP.mode === "onscreen" && SP.os) {
    const box = onscreenViewBox();
    el.textContent = `출력 ${box.w}×${box.h}px · 타일시트 ${SP.w}×${SP.h}px`;
  } else {
    el.textContent = `${SP.w}×${SP.h}px`;
  }
}

async function setSpriteMode(mode) {
  if (mode === "onscreen" && !SP.hasOnscreen) mode = "tile";
  SP.mode = mode;
  if (SP.mode === "onscreen" && !SP.os) {
    const id = SP.id;  // 경합 가드(codex major): 응답 도착 시 여전히 같은 스프라이트인지
    const os = await api(`/api/sprite/onscreen_data?id=${encodeURIComponent(id)}`);
    if (SP.id !== id) return;  // 그새 다른 스프라이트 선택 → 폐기
    if (!os.ok) { toast(os.error || "실화면 레이아웃 로드 실패", true); SP.mode = "tile"; }
    else {
      SP.os = os;
      SP.pal = os.palette || SP.pal;
      SP.activePaletteKey = null;
      const editorW = Math.max(420, ($("#editor") && $("#editor").clientWidth) || 900);
      const paneTarget = Math.max(180, Math.min(560, Math.floor((editorW - 60) / 2)));
      SP.osZoom = Math.max(1, Math.min(3, Math.floor(paneTarget / Math.max(1, Number(os.w) || SP.w || 1))));
      if (os.build && !os.screen) {
        SP.showBg = false;
        const bg = $("#spBg");
        if (bg) bg.checked = false;
      }
      renderSwatches();
      prepareSceneBg();
    }
  }
  updateSpriteDimsMeta();
  drawCurrentSprite();
}
function renderSwatches() {
  const box = $("#swatches"); box.innerHTML = "";
  const pal = currentPalette();
  pal.forEach((c, i) => {
    const sw = document.createElement("div");
    sw.className = "sw" + (i === SP.sel ? " sel" : "");
    sw.style.background = `rgb(${c[0]},${c[1]},${c[2]})`;
    sw.title = "색 " + i;
    sw.onclick = () => { SP.sel = i; renderSwatches(); };
    box.appendChild(sw);
  });
}
function currentPalette() {
  if (SP.mode === "onscreen" && SP.os && SP.os.palettes && SP.activePaletteKey) {
    return SP.os.palettes[SP.activePaletteKey] || SP.pal;
  }
  return SP.pal || [];
}
function paletteForCell(cell, fallbackPal = SP.pal) {
  if (SP.os && SP.os.palettes && cell && cell.palette_key) {
    return SP.os.palettes[cell.palette_key] || fallbackPal;
  }
  return fallbackPal;
}
// 캔버스 변 ~1400px 상한(거대 스프라이트 프리즈/메모리 폭증 방지 — M4)
function effectiveZoom() {
  const fit = Math.max(1, Math.floor(1400 / Math.max(SP.w, SP.h, 1)));
  return Math.max(1, Math.min(SP.zoom, fit));
}
function drawCurrentSprite() {
  if (SP.mode === "onscreen" && SP.os) drawOnscreenSprite();
  else drawSprite();
}
function drawSprite() {
  const cv = $("#spcv"); const z = effectiveZoom();
  $("#sphint").textContent = `타일 그리드: 최신 편집/빌드 스프라이트 출력 크기 ${SP.w}×${SP.h}px 기준으로 편집합니다. 화면 배치 레이아웃은 아직 없음.`;
  // 네이티브 해상도 ImageData 1회 생성 후 스케일 드로(per-pixel fillRect 루프 제거 → O(W*H) 1회)
  const off = document.createElement("canvas"); off.width = SP.w; off.height = SP.h;
  const octx = off.getContext("2d"); octx.fillStyle = "#08090c"; octx.fillRect(0, 0, SP.w, SP.h);
  const img = octx.createImageData(SP.w, SP.h);
  for (let y = 0; y < SP.h; y++) for (let x = 0; x < SP.w; x++) {
    const idx = SP.grid[y][x] & 15;
    if (idx === 0) continue;
    const c = SP.pal[idx] || [0, 0, 0];
    const o = (y * SP.w + x) * 4;
    img.data[o] = c[0]; img.data[o + 1] = c[1]; img.data[o + 2] = c[2]; img.data[o + 3] = 255;
  }
  octx.putImageData(img, 0, 0);
  cv.width = SP.w * z; cv.height = SP.h * z;
  const ctx = cv.getContext("2d"); ctx.imageSmoothingEnabled = false;
  ctx.drawImage(off, 0, 0, cv.width, cv.height);
  drawReferenceSprite();
  SP._off = off;
  let painting = false;
  const paint = (e) => {
    const r = cv.getBoundingClientRect();
    const x = Math.floor((e.clientX - r.left) / z), y = Math.floor((e.clientY - r.top) / z);
    if (x < 0 || y < 0 || x >= SP.w || y >= SP.h) return;
    setSheetPixel(x, y, SP.sel);
    const c = SP.pal[SP.sel];
    ctx.fillStyle = SP.sel === 0 ? "#08090c" : `rgb(${c[0]},${c[1]},${c[2]})`; ctx.fillRect(x * z, y * z, z, z);
    const o2 = SP._off.getContext("2d");
    o2.fillStyle = SP.sel === 0 ? "#08090c" : `rgb(${c[0]},${c[1]},${c[2]})`; o2.fillRect(x, y, 1, 1);
  };
  cv.onmousedown = e => { painting = true; paint(e); window.addEventListener("mouseup", () => (painting = false), { once: true }); };
  cv.onmousemove = e => { if (painting) paint(e); };
}

function sheetCoord(tile, px, py) {
  return { x: (tile % SP.cols) * 8 + px, y: Math.floor(tile / SP.cols) * 8 + py };
}
function sheetCoordFor(cols, tile, px, py) {
  return { x: (tile % cols) * 8 + px, y: Math.floor(tile / cols) * 8 + py };
}
function localTileForCols(cell, tx, ty, cols) {
  if (!SP.os || SP.os.obj1d) return cell.tile_off + ty * cell.tw + tx;
  const baseCol = cell.tile_off % 32;
  const baseRow = Math.floor(cell.tile_off / 32);
  return (baseRow + ty) * cols + baseCol + tx;
}
function localTileFor(cell, tx, ty) {
  return localTileForCols(cell, tx, ty, SP.cols);
}
function sheetPixel(tile, px, py) {
  return sheetPixelFromGrid(SP.grid, SP.cols, tile, px, py);
}
function sheetPixelFromGrid(grid, cols, tile, px, py) {
  if (!grid || !cols) return 0;
  const p = sheetCoordFor(cols, tile, px, py);
  return (grid[p.y] && grid[p.y][p.x]) || 0;
}
function setSheetPixel(x, y, idx) {
  if (!SP.grid[y] || x < 0 || x >= SP.grid[y].length) return false;
  SP.grid[y][x] = idx & 15;
  return true;
}
function setTilePixel(tile, px, py, idx) {
  const p = sheetCoord(tile, px, py);
  return setSheetPixel(p.x, p.y, idx);
}

function paletteColor(pal, idx) {
  return (pal && pal[idx]) || [0, 0, 0];
}
function drawNativeGrid(ctx, grid, pal, w, h) {
  ctx.fillStyle = "#08090c";
  ctx.fillRect(0, 0, w, h);
  if (!grid || !w || !h) return;
  const img = ctx.createImageData(w, h);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const idx = (grid[y] && grid[y][x]) ? (grid[y][x] & 15) : 0;
    if (idx === 0) continue;
    const c = paletteColor(pal, idx);
    const o = (y * w + x) * 4;
    img.data[o] = c[0]; img.data[o + 1] = c[1]; img.data[o + 2] = c[2]; img.data[o + 3] = 255;
  }
  ctx.putImageData(img, 0, 0);
}
function drawReferenceSprite(box = null) {
  const cv = $("#sporigcv");
  if (!cv || !SP.origGrid) return;
  const onscreen = SP.mode === "onscreen" && SP.os;
  const z = onscreen ? SP.osZoom : effectiveZoom();
  const view = onscreen ? (box || onscreenViewBox()) : null;
  const nativeW = onscreen ? view.w : (SP.origW || SP.w);
  const nativeH = onscreen ? view.h : (SP.origH || SP.h);
  const off = document.createElement("canvas");
  off.width = Math.max(1, nativeW); off.height = Math.max(1, nativeH);
  const ctx = off.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  ctx.fillStyle = "#08090c";
  ctx.fillRect(0, 0, off.width, off.height);
  if (onscreen) drawOamCellsFor(ctx, view.x, view.y, SP.origGrid, SP.origCols || SP.cols, SP.origPal || SP.pal);
  else drawNativeGrid(ctx, SP.origGrid, SP.origPal || SP.pal, off.width, off.height);
  cv.width = off.width * z; cv.height = off.height * z;
  const cctx = cv.getContext("2d");
  cctx.imageSmoothingEnabled = false;
  cctx.drawImage(off, 0, 0, cv.width, cv.height);
}

function prepareSceneBg() {
  if (!SP.bgUrl || SP.bgImg) return;
  const id = SP.id, url = SP.bgUrl;  // 경합 가드(codex major)
  const im = new Image();
  im.onload = () => { if (SP.id !== id || SP.bgUrl !== url) return; SP.bgReady = true; if (SP.mode === "onscreen") drawOnscreenSprite(); };
  im.onerror = () => { if (SP.id !== id) return; SP.bgReady = false; };
  im.src = url;
  SP.bgImg = im;
}

function contentBBoxFromCellsFor(grid, cols) {
  const os = SP.os;
  if (!os || !grid || !cols) return null;
  const clipToScreen = !!os.screen && !(os.build && !os.screen);
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const cell of os.cells || []) {
    for (let ty = 0; ty < cell.th; ty++) for (let tx = 0; tx < cell.tw; tx++) {
      const tile = localTileForCols(cell, tx, ty, cols);
      const dx0 = cell.x + (cell.fh ? (cell.tw - 1 - tx) : tx) * 8;
      const dy0 = cell.y + (cell.fv ? (cell.th - 1 - ty) : ty) * 8;
      for (let yy = 0; yy < 8; yy++) for (let xx = 0; xx < 8; xx++) {
        const px = cell.fh ? 7 - xx : xx;
        const py = cell.fv ? 7 - yy : yy;
        if ((sheetPixelFromGrid(grid, cols, tile, px, py) & 15) === 0) continue;
        const sx = dx0 + xx, sy = dy0 + yy;
        if (clipToScreen && (sx < 0 || sy < 0 || sx >= 240 || sy >= 160)) continue;
        minX = Math.min(minX, sx);
        minY = Math.min(minY, sy);
        maxX = Math.max(maxX, sx + 1);
        maxY = Math.max(maxY, sy + 1);
      }
    }
  }
  if (!Number.isFinite(minX) || !Number.isFinite(minY)) return null;
  return { x: minX, y: minY, w: Math.max(1, maxX - minX), h: Math.max(1, maxY - minY), content: true };
}

function unionBox(a, b) {
  if (!a) return b;
  if (!b) return a;
  const x0 = Math.min(a.x, b.x);
  const y0 = Math.min(a.y, b.y);
  const x1 = Math.max(a.x + a.w, b.x + b.w);
  const y1 = Math.max(a.y + a.h, b.y + b.h);
  return { x: x0, y: y0, w: Math.max(1, x1 - x0), h: Math.max(1, y1 - y0), content: true };
}

function contentBBoxFromCells() {
  const current = contentBBoxFromCellsFor(SP.grid, SP.cols);
  const original = contentBBoxFromCellsFor(SP.origGrid, SP.origCols || SP.cols);
  return unionBox(current, original);
}

function onscreenViewBox() {
  const os = SP.os;
  if (os) {
    return {
      x: Number(os.x0) || 0,
      y: Number(os.y0) || 0,
      w: Math.max(1, Math.ceil(Number(os.w) || SP.w || 1)),
      h: Math.max(1, Math.ceil(Number(os.h) || SP.h || 1)),
      layout: true,
    };
  }
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const cell of os?.cells || []) {
    const x0 = Math.max(0, cell.x);
    const y0 = Math.max(0, cell.y);
    const x1 = Math.min(240, cell.x + cell.tw * 8);
    const y1 = Math.min(160, cell.y + cell.th * 8);
    if (x1 <= x0 || y1 <= y0) continue;
    minX = Math.min(minX, x0);
    minY = Math.min(minY, y0);
    maxX = Math.max(maxX, x1);
    maxY = Math.max(maxY, y1);
  }
  if (Number.isFinite(minX) && Number.isFinite(minY)) {
    return { x: minX, y: minY, w: Math.max(1, maxX - minX), h: Math.max(1, maxY - minY) };
  }
  return {
    x: 0,
    y: 0,
    w: Math.max(1, Math.ceil(Number(SP.w) || 1)),
    h: Math.max(1, Math.ceil(Number(SP.h) || 1)),
  };
}

function drawOnscreenSprite() {
  const cv = $("#spcv");
  const os = SP.os;
  const z = SP.osZoom;
  const box = onscreenViewBox();
  const originX = box.x, originY = box.y;
  const nativeW = box.w, nativeH = box.h;
  $("#sphint").textContent = `타일 그리드: 실제 화면 출력 크기 ${nativeW}×${nativeH}px 안에 OAM 배치를 재조립해 편집합니다. 화면 원점 ${originX},${originY}`;
  updateSpriteDimsMeta();

  const off = document.createElement("canvas"); off.width = nativeW; off.height = nativeH;
  const ctx = off.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  if (SP.showBg && SP.bgReady && SP.bgImg) {
    ctx.globalAlpha = 0.45;
    drawSceneBgCrop(ctx, originX, originY, nativeW, nativeH);
    ctx.globalAlpha = 1;
    maskOamBounds(ctx, originX, originY);
  } else {
    ctx.fillStyle = "#08090c";
    ctx.fillRect(0, 0, nativeW, nativeH);
  }
  drawOamCells(ctx, originX, originY);

  cv.width = nativeW * z; cv.height = nativeH * z;
  const cctx = cv.getContext("2d"); cctx.imageSmoothingEnabled = false;
  cctx.drawImage(off, 0, 0, cv.width, cv.height);
  drawReferenceSprite(box);

  const paint = (e) => {
    const r = cv.getBoundingClientRect();
    const vx = Math.floor((e.clientX - r.left) / z), vy = Math.floor((e.clientY - r.top) / z);
    if (vx < 0 || vy < 0 || vx >= nativeW || vy >= nativeH) return;
    const sx = originX + vx, sy = originY + vy;
    const hit = onscreenTargetAt(sx, sy);
    if (!hit) return;
    if (hit.palette_key && hit.palette_key !== SP.activePaletteKey) {
      SP.activePaletteKey = hit.palette_key;
      renderSwatches();
    }
    const key = `${hit.tile}:${hit.px}:${hit.py}`;
    if (key === SP.paintKey) return;
    SP.paintKey = key;
    setTilePixel(hit.tile, hit.px, hit.py, SP.sel);
    drawOnscreenSprite();
  };
  cv.onmousedown = e => { SP.painting = true; SP.paintKey = ""; paint(e); window.addEventListener("mouseup", () => (SP.painting = false), { once: true }); };
  cv.onmousemove = e => { if (SP.painting) paint(e); };
}

function drawSceneBgCrop(ctx, originX, originY, w, h) {
  ctx.fillStyle = "#08090c";
  ctx.fillRect(0, 0, w, h);
  const sx0 = Math.max(0, originX), sy0 = Math.max(0, originY);
  const sx1 = Math.min(240, originX + w), sy1 = Math.min(160, originY + h);
  if (sx1 <= sx0 || sy1 <= sy0) return;
  ctx.drawImage(SP.bgImg, sx0, sy0, sx1 - sx0, sy1 - sy0,
    sx0 - originX, sy0 - originY, sx1 - sx0, sy1 - sy0);
}

function drawOamCells(ctx, originX = 0, originY = 0) {
  drawOamCellsFor(ctx, originX, originY, SP.grid, SP.cols, SP.pal);
}
function drawOamCellsFor(ctx, originX, originY, grid, cols, fallbackPal) {
  const os = SP.os;
  for (const cell of os.cells) {
    for (let ty = 0; ty < cell.th; ty++) for (let tx = 0; tx < cell.tw; tx++) {
      const tile = localTileForCols(cell, tx, ty, cols || SP.cols);
      const dx0 = cell.x - originX + (cell.fh ? (cell.tw - 1 - tx) : tx) * 8;
      const dy0 = cell.y - originY + (cell.fv ? (cell.th - 1 - ty) : ty) * 8;
      for (let yy = 0; yy < 8; yy++) for (let xx = 0; xx < 8; xx++) {
        const px = cell.fh ? 7 - xx : xx;
        const py = cell.fv ? 7 - yy : yy;
        const idx = sheetPixelFromGrid(grid, cols || SP.cols, tile, px, py) & 15;
        if (idx === 0) continue;
        const pal = paletteForCell(cell, fallbackPal);
        const c = pal[idx] || [0, 0, 0];
        ctx.fillStyle = `rgb(${c[0]},${c[1]},${c[2]})`;
        ctx.fillRect(dx0 + xx, dy0 + yy, 1, 1);
      }
    }
  }
}

function maskOamBounds(ctx, originX = 0, originY = 0) {
  if (!SP.os) return;
  ctx.fillStyle = "#08090c";
  for (const cell of SP.os.cells) {
    ctx.fillRect(cell.x - originX, cell.y - originY, cell.tw * 8, cell.th * 8);
  }
}

function onscreenTargetAt(sx, sy) {
  return onscreenTargetAtPhase(sx, sy, false) || onscreenTargetAtPhase(sx, sy, true);
}

function onscreenTargetAtPhase(sx, sy, allowTransparent) {
  const os = SP.os;
  for (let ci = os.cells.length - 1; ci >= 0; ci--) {
    const cell = os.cells[ci];
    for (let ty = cell.th - 1; ty >= 0; ty--) for (let tx = cell.tw - 1; tx >= 0; tx--) {
      const dx0 = cell.x + (cell.fh ? (cell.tw - 1 - tx) : tx) * 8;
      const dy0 = cell.y + (cell.fv ? (cell.th - 1 - ty) : ty) * 8;
      if (sx < dx0 || sy < dy0 || sx >= dx0 + 8 || sy >= dy0 + 8) continue;
      const lx = sx - dx0, ly = sy - dy0;
      const px = cell.fh ? 7 - lx : lx;
      const py = cell.fv ? 7 - ly : ly;
      const tile = localTileFor(cell, tx, ty);
      if (!allowTransparent && (sheetPixel(tile, px, py) & 15) === 0) continue;
      return { tile, px, py, palette_key: cell.palette_key || null };
    }
  }
  return null;
}
async function saveSprite() {
  const r = await api("/api/sprite/save", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: SP.id, indices: SP.grid, palette: SP.pal }) });
  if (!r.ok) { toast("저장 실패: " + (r.error || ""), true); return false; }  // M8: 실패 시 false
  toast(`저장됨 (raw ${r.raw_len}B, fit=${r.fits_raw})${r.fits_raw === false ? " ⚠빌드서 누락 가능" : ""}`, r.fits_raw === false);
  refreshState();
  return true;
}
async function revertSprite() {
  const r = await api("/api/sprite/revert", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: SP.id }) });
  if (!r.ok) { toast("되돌리기 실패: " + (r.error || ""), true); return; }
  toast("되돌림");
  const fresh = await api(`/api/scene/items?id=${encodeURIComponent(S.scene)}&type=all`);
  if (fresh && fresh.dialogue) S.items = fresh;
  refreshSceneItems();  // 새 데이터로 재렌더 + 선택 복원
  const box = openItemsBox();
  const row = box && box.querySelector(`.row[data-kind="s"][data-i="${S.item.i}"]`);
  if (row) selectSprite(S.item.i, row);
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

async function compareReadonlySprite() {
  const c = await api(`/api/sprite/compare?id=${encodeURIComponent(SP.id)}`);
  if (!c.ok) return toast(c.error || "비교 실패", true);
  let g = `<figure><figcaption>원본(일본판)</figcaption><img src="${c.orig_url}&t=${Date.now()}"></figure>`;
  if (c.patched_url) g += `<figure><figcaption>적용(한글 빌드)</figcaption><img src="${c.patched_url}&t=${Date.now()}"></figure>`;
  S.applyAction = null;
  openModal("스프라이트 — 원본 ↔ 적용 비교", g);
  $("#modalNote").textContent = c.build_changed ? "빌드 ROM이 원본과 다름(한글화 반영됨)." : "빌드 ROM이 원본과 동일.";
  $("#modalApply").disabled = true;
}

// ── 모달 / 빌드(적용) / 다운로드 ─────────────────────────────────────────
function openModal(title, gridHtml) {
  $("#modalTitle").textContent = title; $("#modalGrid").innerHTML = gridHtml;
  $("#modalNote").textContent = "";
  $("#modalApply").disabled = true;  // M12: 콘텐츠 준비 후에만 활성화(재진입 잔존 방지)
  $("#modal").hidden = false;
}
function closeModal() { $("#modal").hidden = true; }
$("#modalClose").onclick = closeModal;
// M4(css_dom minor): 오버레이 클릭 / Escape 로 닫기
$("#modal").onclick = (e) => { if (e.target.id === "modal") closeModal(); };
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("#modal").hidden) closeModal(); });
$("#modalApply").onclick = async () => {
  // 적용 = (현재 편집 저장) → 전체 빌드. 저장 실패(false/undefined 모두)면 빌드 안 함(M1/M7/m13).
  $("#modalApply").disabled = true;  // 연타 방지
  if (S.applyAction) { const ok = await S.applyAction(); if (!ok) { closeModal(); return; } }
  closeModal(); applyBuild();
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
    // 'overflow'는 정상 로그에도 상존(cry-wolf) → 실제 스프라이트 편집 skip 마커만 경고(M11)
    const skipped = /재압축 초과|comp_size 초과|편집 skip|override skip/i.test(j.log_tail || "");
    toast(skipped ? "빌드 완료(일부 스프라이트 편집 skip — 로그 확인)" : "빌드 완료 — ROM 반영됨. 다운로드 가능.", skipped);
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

// ── 통일 사전 CRUD(Phase 4 잔여) ─────────────────────────────────────────
async function openDict() {
  const d = await api("/api/dict");
  if (!d || d.ok === false) return toast("사전 로드 실패", true);
  S.dict = d;
  const cats = Object.entries(d).filter(([k, v]) => Array.isArray(v));
  $("#dcat").innerHTML = cats.map(([k]) => `<option value="${esc(k)}">${esc(k)}</option>`).join("");
  const total = cats.reduce((n, [, v]) => n + v.length, 0);
  $("#dictInfo").textContent = `${cats.length}개 카테고리 · ${total}개 용어`;
  const box = $("#dictlist"); box.innerHTML = "";
  const frag = document.createDocumentFragment();
  for (const [cat, list] of cats) for (const e of list) frag.appendChild(dictRow(cat, e));
  box.appendChild(frag);
  $("#dictModal").hidden = false;
}
function dictRow(cat, e) {
  const row = document.createElement("div"); row.className = "dterm";
  const c = document.createElement("span"); c.className = "dcat"; c.textContent = cat;
  const ja = document.createElement("span"); ja.className = "dja"; ja.textContent = e.ja || "";
  const ko = document.createElement("input"); ko.value = e.ko || ""; ko.placeholder = "번역";
  const ed = document.createElement("input"); ed.value = e.edit || ""; ed.placeholder = "확정표기";
  const save = document.createElement("button"); save.textContent = "저장";
  const del = document.createElement("button"); del.className = "del"; del.textContent = "삭제";
  save.onclick = async () => {
    const r = await api("/api/dict", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "edit", category: cat, ja: e.ja, ko: ko.value, edit: ed.value }) });
    toast(r.ok ? `사전 저장: ${e.ja}` : "실패: " + (r.error || ""), !r.ok);
  };
  del.onclick = async () => {
    if (!confirm(`사전에서 삭제: ${e.ja}?`)) return;
    const r = await api("/api/dict", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "delete", category: cat, ja: e.ja }) });
    if (r.ok) { toast("삭제됨"); openDict(); } else toast("실패: " + (r.error || ""), true);
  };
  row.append(c, ja, ko, ed, save, del);
  return row;
}
$("#dictBtn").onclick = openDict;
$("#dictClose").onclick = () => ($("#dictModal").hidden = true);
$("#dictModal").onclick = (e) => { if (e.target.id === "dictModal") $("#dictModal").hidden = true; };
$("#dadd").onclick = async () => {
  const cat = $("#dcat").value, ja = $("#dja").value.trim();
  if (!ja) return toast("원문(JA) 입력", true);
  const r = await api("/api/dict", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "add", category: cat, ja, ko: $("#dko").value, edit: $("#dedit").value }) });
  if (r.ok) { toast("추가됨"); $("#dja").value = $("#dko").value = $("#dedit").value = ""; openDict(); }
  else toast("실패: " + (r.error || ""), true);
};
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("#dictModal").hidden) $("#dictModal").hidden = true; });

// 시작
loadSupported(); loadScenes(); refreshState(); setInterval(refreshState, 8000);
