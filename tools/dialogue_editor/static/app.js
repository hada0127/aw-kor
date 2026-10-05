"use strict";
const $ = (s, r = document) => r.querySelector(s);
const el = (t, props = {}, ...kids) => {
  const e = document.createElement(t);
  Object.assign(e, props);
  for (const k of kids) e.append(k);
  return e;
};
const URLP = new URLSearchParams(location.search);
const SECTION = URLP.get("section") || "all";
const EMBED = URLP.get("embed") === "1";
const state = { filter: "", region: "", q: "", dict: {}, section: SECTION, view: "group" };
if (EMBED) document.documentElement.classList.add("embed");

function byteLen(s) {
  let n = 0;
  for (const c of s) { const o = c.codePointAt(0); n += o <= 0x7f ? 1 : 2; }
  return n;
}
function reload() { return state.view === "group" ? loadGroups() : loadDialogue(); }
function showView(v) {
  state.view = v;
  document.querySelectorAll(".viewtoggle button").forEach(b => b.classList.toggle("on", b.dataset.v === v));
  $("#grouplist").hidden = v !== "group";
  $("#linetable").hidden = v !== "line";
  reload();
}

async function loadGroups() {
  const p = new URLSearchParams({ q: state.q });
  if (state.section && state.section !== "all") p.set("section", state.section);
  const d = await jget("/api/groups?" + p);
  setStatus(`${d.count} 조립그룹 / ${d.total}`);
  const box = $("#grouplist"); box.textContent = "";
  for (const g of d.lines) box.append(groupCard(g));
}
function groupCard(g) {
  const memById = {}; for (const m of g.members) memById[m.address] = m;
  const jaWrap = el("div", { className: "gja" });
  const koWrap = el("div", { className: "gko" });
  const inputs = [];
  for (const s of g.segments) {
    const showKo = !g.ko_segments || g.ko_segments.some(k => k.kind === s.kind && k.address === s.address);
    if (s.kind === "frag") {
      const m = memById[s.address]; if (!m) continue;
      jaWrap.append(el("span", { className: "jfrag", textContent: m.ja || "" }));
      if (!showKo) continue;
      const ta = el("input", { className: "kfrag" + (m.bteam ? " bteam" : ""), value: m.ko || "" });
      ta.disabled = m.editable === false;
      if (ta.disabled) ta.title = m.reason || (m.owner_address !== m.address
        ? `합쳐진 문장: ${m.owner_address}에서 전체 문장을 편집하세요`
        : "빌드에 적용할 수 없는 추출 항목입니다");
      if (m.bteam && !ta.disabled) ta.title = "⚠ 짜옹이님(B팀) 권위 번역 — 저장 시 확인 필요";
      const cnt = el("span", { className: "bcnt" });
      const upd = () => { const b = byteLen(ta.value) + (m.layout_prefix_bytes || 0); cnt.textContent = `약 ${b}/${m.slot ?? "?"}B (저장 시 검증)`; cnt.classList.toggle("over", m.slot && b > m.slot); };
      ta.oninput = upd; upd();
      const cell = el("span", { className: "kcell" }, ta, cnt);
      if (m.bteam) cell.append(el("span", { className: "bteambadge", textContent: "⚠B팀", title: "짜옹이님(B팀) 권위 번역" }));
      koWrap.append(cell);
      if (!ta.disabled) inputs.push({ m, ta });
    } else if (s.kind === "var") {
      jaWrap.append(el("span", { className: "chip", textContent: "⟦" + (s.default || "var") + "⟧" }));
      if (showKo) koWrap.append(el("span", { className: "chip", textContent: "⟦" + (s.default || "var") + "⟧" }));
    } else if (s.kind === "newline") { jaWrap.append(el("br")); if (showKo) koWrap.append(el("br")); }
  }
  const applyCurrent = el("input", { type: "checkbox", className: "apply-current" });
  const applyLabel = el("label", { title: "수정하지 않은 조각도 모두 포함합니다. 자동 공백 보정 대신 표시된 문구 그대로 적용합니다" }, applyCurrent, document.createTextNode(`${inputs.length}개 조각 모두 그대로 적용`));
  const save = el("button", { className: "gsave", textContent: "저장" });
  save.disabled = inputs.length === 0;
  save.onclick = async () => {
      const lines = [];
      const warnings = new Set();
    save.disabled = true;
    try {
      const pending = inputs.filter(({ m, ta }) => applyCurrent.checked || ta.value !== (m.ko || ""));
      if (!pending.length) { setStatus("변경 사항 없음"); return; }
      for (const { m, ta } of pending) {
        const payload = { id: m.id, address: m.address, ko: ta.value, dry_run: true };
        const r = await saveLineConfirm(payload);
        if (!r.ok) {
          setStatus(`${g.group_id} 저장 안 됨 — ${r.cancelled ? "취소" : r.error || "검증 실패"}`);
          return;
        }
        if (r.warning) warnings.add(`${m.address}: ${r.warning}`);
        lines.push({ ...payload, dry_run: false, confirm_bteam: Boolean(r.bteam_confirmed), confirm_current: applyCurrent.checked });
      }
      const r = await jpost("/api/lines", { lines });
      if (r.ok) for (const item of r.warnings || []) warnings.add(`${item.address}: ${item.warning}`);
      if (r.ok) for (const line of lines) {
        const entry = inputs.find(({ m }) => m.address === line.address);
        if (entry) entry.m.ko = line.ko;
      }
      setStatus(r.ok ? `${g.group_id}: ${r.saved}개 수정, ${r.confirmed || 0}개 문구 확정, ${r.unchanged}개 변경 없음${warnings.size ? ' · ' + [...warnings].join(' ') : ''}`
        : `${g.group_id} 저장 안 됨 — ${r.error || "검증 실패"}`);
    } catch (e) {
      setStatus(`${g.group_id} 저장 오류 — ${e.message}`);
    } finally { save.disabled = inputs.length === 0; }
  };
  const cap = el("button", { className: "cap", textContent: "🎮", title: "대표 화면 글꼴 미리보기(첫 조각)" });
  cap.onclick = () => { const first = g.members[0]; const live = inputs.find(x => x.m.address === first?.address); const m = live ? live.m : first; if (m) previewLine({ id: m.id, region: g.region }, live ? live.ta.value : m.ko, cap); };
  const hd = el("div", { className: "ghd" }, el("b", { textContent: g.group_id }),
    el("span", { className: "gmeta", textContent: `${g.region} · ${g.size}조각` }), save, cap, applyLabel);
  if (g.flagged) hd.append(el("span", { className: "gflag", textContent: "⚠검토" }));
  return el("div", { className: "gcard" + (g.flagged ? " flagged" : "") }, hd,
    el("div", { className: "glbl", textContent: "원문(JA)" }), jaWrap,
    el("div", { className: "glbl", textContent: "번역(KO) · ⟦변수⟧는 엔진이 채움(고정)" }), koWrap);
}

async function jget(u) { return (await fetch(u)).json(); }
async function jpost(u, b) {
  return (await fetch(u, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) })).json();
}
// C5: 짜옹이님(B팀) 권위 번역 — 서버가 confirm 요구 시 명시 승인 후 재전송.
async function saveLineConfirm(payload) {
  let r = await jpost("/api/line", payload);
  if (!r.ok && r.bteam_confirm_required) {
    const base = r.bteam_baseline || "(baseline 없음)";
    const ok = confirm(
      "⚠ 짜옹이님(B팀) 권위 번역 주소입니다.\n\n기준(baseline):\n  " + base +
      "\n\n변경(제안):\n  " + payload.ko +
      "\n\n정말 변경하시겠습니까?\n(우발 변형은 qa_bteam_drift 게이트가 빌드/배포에서 차단합니다.)"
    );
    if (!ok) return { ok: false, cancelled: true };
    r = await jpost("/api/line", { ...payload, confirm_bteam: true });
    if (r.ok) r.bteam_confirmed = true;
  }
  return r;
}
function setStatus(s) { $("#status").textContent = s; }

async function loadDialogue() {
  const p = new URLSearchParams({ region: state.region, q: state.q, filter: state.filter });
  if (state.section && state.section !== "all") p.set("section", state.section);
  const data = await jget("/api/dialogue?" + p);
  const sel = $("#region");
  if (sel.options.length <= 1 && data.regions) {
    for (const r of data.regions) if (r) sel.append(el("option", { value: r, textContent: r }));
  }
  setStatus(`${data.count} / ${data.total}행`);
  const tb = $("#rows"); tb.textContent = "";
  for (const ln of data.lines) tb.append(rowFor(ln));
}

function rowFor(ln) {
  const ta = el("textarea", { value: ln.ko || "" });
  ta.disabled = ln.editable === false;
  if (ta.disabled) ta.title = ln.reason || "편집할 수 없는 항목입니다";
  const miss = el("span", { className: "miss" });
  const applyCurrent = el("input", { type: "checkbox", disabled: ta.disabled });
  const applyLabel = el("label", { title: "기존 문구도 자동 공백 보정 대신 현재 표시된 그대로 적용합니다" }, applyCurrent, document.createTextNode("현재 문구 그대로 적용"));
  const save = el("button", { className: "save", textContent: "저장" });
  save.disabled = ta.disabled;
  save.onclick = async () => {
    if (save.disabled) return;
    const r = await saveLineConfirm({ id: ln.id, address: ln.address, ko: ta.value, confirm_current: applyCurrent.checked });
    if (r.ok) { setStatus((r.saved || r.confirmed ? `문구 저장·확정 #${ln.id}` : "변경 사항 없음") + (r.warning ? ' · ' + r.warning : '')); showMiss(miss, tr, r.check); }
    else if (r.cancelled) setStatus("B팀 번역 저장 취소");
    else setStatus("오류: " + r.error);
  };
  ta.onkeydown = (e) => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") save.onclick(); };
  const cap = el("button", { className: "cap", textContent: "🎮", title: "대표 화면 글꼴 미리보기" });
  cap.onclick = () => previewLine(ln, ta.value, cap);
  const tr = el("tr", {},
    el("td", { textContent: ln.id }),
    el("td", { textContent: (ln.address || "").replace("0x", "") }),
    el("td", { textContent: ln.region || "" }),
    el("td", { className: "ja", textContent: ln.ja || "" }),
    el("td", { className: "ko" }, ta, miss),
    el("td", {}, save, cap, applyLabel));
  if (ln.is_noise) tr.className = "noise";
  return tr;
}

let _capBusy = false;
async function previewLine(ln, koLive, btn) {
  if (_capBusy) { setStatus("이미 캡처 중…"); return; }
  _capBusy = true; const old = btn.textContent; btn.textContent = "…"; btn.disabled = true;
  setStatus(`#${ln.id} 실캡처 중… (헤드리스 에뮬 진행, 수십초 소요)`);
  try {
    const r = await jpost("/api/preview", { id: ln.id, ko: koLive });
    if (!r.ok) { setStatus("캡처 오류: " + r.error); return; }
    const bust = "?t=" + Date.now();
    $("#capOrig").src = r.orig.url + bust;
    $("#capAppl").src = r.applied.url + bust;
    $("#capOrigT").textContent = "JA: " + (r.orig.text || "");
    $("#capApplT").textContent = "KO: " + (r.applied.text || "");
    $("#capInfo").textContent = `#${ln.id} · ${r.region || ln.region || ""} · canvas=${r.canvas}`;
    const trunc = (r.orig.truncated || r.applied.truncated);
    $("#capNote").textContent = trunc
      ? "대표 화면 글꼴 미리보기입니다. ⚠ 미리보기 슬롯을 초과한 부분은 잘렸습니다. 원래 장면의 배치·줄바꿈·최종 적용 결과는 게임에서 확인하세요."
      : "대표 화면에 문구를 넣은 에뮬레이터 미리보기입니다. 원래 장면의 배치·줄바꿈·최종 적용 결과는 게임에서 확인해야 합니다.";
    $("#capModal").hidden = false;
    setStatus(`#${ln.id} 캡처 완료`);
  } catch (e) { setStatus("캡처 실패: " + e); }
  finally { _capBusy = false; btn.textContent = old; btn.disabled = false; }
}
function showMiss(span, tr, issues) {
  if (issues && issues.length) {
    span.textContent = "⚠ 사전: " + issues.map(i => `${i.ja}→${i.expected_ko}`).join(", ");
    tr.classList.add("mismatch");
  } else { span.textContent = ""; tr.classList.remove("mismatch"); }
}

function dictCategories(d) {
  return Object.keys(d || {}).filter(k => Array.isArray(d[k]));
}
function dictSource(e) {
  return (e._source || e.ja || e.ja_note || e.term || "").trim();
}
function dictCurrent(e) {
  return (e._current || e.current || e.ko || "").trim();
}
function dictCanonical(e) {
  return (e._canonical || e.edit || e.ko || e.chosen_ko || e.term || "").trim();
}
function dictStatus(e) {
  return e._status || (dictCanonical(e) ? "확정" : "미확정");
}

async function loadDict() {
  state.dict = await jget("/api/dict");
  const cats = dictCategories(state.dict);
  const dcat = $("#dcat"); dcat.textContent = "";
  for (const c of cats) dcat.append(el("option", { value: c, textContent: c }));
  const box = $("#dictlist"); box.textContent = "";
  for (const c of cats) {
    box.append(el("div", { className: "dcat", textContent: `${c} (${state.dict[c].length})` }));
    box.append(dhead());
    for (const e of state.dict[c]) box.append(dentry(c, e));
  }
}
function dhead() {
  return el("div", { className: "dentry dhead" },
    el("span", { textContent: "원문/출처" }),
    el("span", { textContent: "현재/관측" }),
    el("span", { textContent: "확정 표기" }),
    el("span", { textContent: "상태" }),
    el("span", { textContent: "저장" }),
    el("span", { textContent: "삭제" }));
}
function dentry(cat, e) {
  const current = el("input", { value: dictCurrent(e), placeholder: "현재" });
  const canonical = el("input", { value: dictCanonical(e), placeholder: "확정" });
  const save = el("button", { textContent: "✓", title: "수정" });
  const del = el("button", { textContent: "✕", title: "삭제" });
  const row = el("div", { className: "dentry" + (e._readonly ? " readonly" : "") + (!dictCanonical(e) ? " missing" : "") },
    el("span", { className: "source", textContent: dictSource(e) || "원문 없음" }),
    current,
    canonical,
    el("span", { className: "status", textContent: dictStatus(e) }),
    save,
    del);
  if (e._note) row.append(el("span", { className: "note", textContent: e._note }));
  if (e._readonly) {
    current.disabled = canonical.disabled = save.disabled = del.disabled = true;
    save.title = del.title = "자동 검토 결과라 직접 편집하지 않습니다";
  }
  save.onclick = async () => {
    const r = await jpost("/api/dict", { action: "edit", category: cat, key: e._key, source: dictSource(e), current: current.value, canonical: canonical.value });
    setStatus(r.ok ? `사전 수정: ${dictSource(e)}` : "오류: " + r.error);
    if (r.ok) loadDict();
  };
  del.onclick = async () => {
    if (!confirm(`삭제: ${dictSource(e)}?`)) return;
    const r = await jpost("/api/dict", { action: "delete", category: cat, key: e._key, source: dictSource(e) });
    if (r.ok) loadDict();
  };
  return row;
}

async function checkAll() {
  setStatus("검사 중…");
  const r = await jget("/api/check_all");
  switchTab("check");
  const box = $("#checklist"); box.textContent = "";
  box.append(el("div", { className: "dcat", textContent: `사전 불일치 ${r.count}건` }));
  for (const m of r.mismatches) {
    const d = el("div", { className: "chk" });
    d.append(el("b", { textContent: `#${m.id} ` }),
      el("span", { textContent: m.issues.map(i => `${i.ja}→${i.expected_ko}`).join(", ") }),
      el("div", { className: "ja", textContent: m.ja }),
      el("div", { textContent: "KO: " + (m.ko || "") }));
    box.append(d);
  }
  setStatus(`사전 불일치 ${r.count}건`);
}

function switchTab(t) {
  for (const b of document.querySelectorAll(".tabs button")) b.classList.toggle("on", b.dataset.tab === t);
  $("#tab-dict").hidden = t !== "dict";
  $("#tab-check").hidden = t !== "check";
}

function wire() {
  for (const b of document.querySelectorAll(".viewtoggle button")) b.onclick = () => showView(b.dataset.v);
  for (const b of document.querySelectorAll(".filters button"))
    b.onclick = () => {
      state.filter = b.dataset.f;
      document.querySelectorAll(".filters button").forEach(x => x.classList.toggle("on", x === b));
      reload();
    };
  $("#region").onchange = (e) => { state.region = e.target.value; reload(); };
  let t; $("#q").oninput = (e) => { clearTimeout(t); t = setTimeout(() => { state.q = e.target.value; reload(); }, 250); };
  $("#checkAll").onclick = checkAll;
  for (const b of document.querySelectorAll(".tabs button")) b.onclick = () => switchTab(b.dataset.tab);
  $("#dadd").onclick = async () => {
    const r = await jpost("/api/dict", { action: "add", category: $("#dcat").value, source: $("#dja").value, current: $("#dko").value, canonical: $("#dedit").value });
    if (r.ok) { $("#dja").value = $("#dko").value = $("#dedit").value = ""; loadDict(); setStatus("사전 추가됨"); }
    else setStatus("오류: " + r.error);
  };
  $("#capClose").onclick = () => { $("#capModal").hidden = true; };
  $("#capModal").onclick = (e) => { if (e.target.id === "capModal") $("#capModal").hidden = true; };
}

wire();
loadDict();
showView("group");
