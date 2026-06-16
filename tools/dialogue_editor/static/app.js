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
const state = { filter: "", region: "", q: "", dict: {}, section: SECTION };
if (EMBED) document.documentElement.classList.add("embed");

async function jget(u) { return (await fetch(u)).json(); }
async function jpost(u, b) {
  return (await fetch(u, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) })).json();
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
  const miss = el("span", { className: "miss" });
  const save = el("button", { className: "save", textContent: "저장" });
  save.onclick = async () => {
    const r = await jpost("/api/line", { id: ln.id, ko: ta.value });
    if (r.ok) { setStatus(`저장됨 #${ln.id}`); showMiss(miss, tr, r.check); }
    else setStatus("오류: " + r.error);
  };
  ta.onkeydown = (e) => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") save.onclick(); };
  const cap = el("button", { className: "cap", textContent: "🎮", title: "원본↔적용 실캡처" });
  cap.onclick = () => previewLine(ln, ta.value, cap);
  const tr = el("tr", {},
    el("td", { textContent: ln.id }),
    el("td", { textContent: (ln.address || "").replace("0x", "") }),
    el("td", { textContent: ln.region || "" }),
    el("td", { className: "ja", textContent: ln.ja || "" }),
    el("td", { className: "ko" }, ta, miss),
    el("td", {}, save, cap));
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
      ? "⚠ 이 canvas 슬롯 길이를 초과해 텍스트가 잘렸습니다(긴 대사용 dialog-box canvas는 추가 예정)."
      : "실기 헤드리스 캡처(가짜 합성 아님). 좌=원본 일본판, 우=적용 한글.";
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

async function loadDict() {
  state.dict = await jget("/api/dict");
  const cats = Object.keys(state.dict).filter(k => Array.isArray(state.dict[k]));
  const dcat = $("#dcat"); dcat.textContent = "";
  for (const c of cats) dcat.append(el("option", { value: c, textContent: c }));
  const box = $("#dictlist"); box.textContent = "";
  for (const c of cats) {
    box.append(el("div", { className: "dcat", textContent: `${c} (${state.dict[c].length})` }));
    for (const e of state.dict[c]) box.append(dentry(c, e));
  }
}
function dentry(cat, e) {
  const ko = el("input", { value: e.edit || e.ko || "" });
  const save = el("button", { textContent: "✓", title: "수정" });
  const del = el("button", { textContent: "✕", title: "삭제" });
  save.onclick = async () => {
    const r = await jpost("/api/dict", { action: "edit", category: cat, ja: e.ja, edit: ko.value });
    setStatus(r.ok ? `사전 수정: ${e.ja}` : "오류: " + r.error);
    if (r.ok) loadDict();
  };
  del.onclick = async () => {
    if (!confirm(`삭제: ${e.ja}?`)) return;
    const r = await jpost("/api/dict", { action: "delete", category: cat, ja: e.ja });
    if (r.ok) loadDict();
  };
  return el("div", { className: "dentry" }, el("span", { className: "ja", textContent: e.ja }), ko, save, del);
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
  for (const b of document.querySelectorAll(".filters button"))
    b.onclick = () => {
      state.filter = b.dataset.f;
      document.querySelectorAll(".filters button").forEach(x => x.classList.toggle("on", x === b));
      loadDialogue();
    };
  $("#region").onchange = (e) => { state.region = e.target.value; loadDialogue(); };
  let t; $("#q").oninput = (e) => { clearTimeout(t); t = setTimeout(() => { state.q = e.target.value; loadDialogue(); }, 250); };
  $("#checkAll").onclick = checkAll;
  for (const b of document.querySelectorAll(".tabs button")) b.onclick = () => switchTab(b.dataset.tab);
  $("#dadd").onclick = async () => {
    const r = await jpost("/api/dict", { action: "add", category: $("#dcat").value, ja: $("#dja").value, ko: $("#dko").value });
    if (r.ok) { $("#dja").value = $("#dko").value = ""; loadDict(); setStatus("사전 추가됨"); }
    else setStatus("오류: " + r.error);
  };
  $("#capClose").onclick = () => { $("#capModal").hidden = true; };
  $("#capModal").onclick = (e) => { if (e.target.id === "capModal") $("#capModal").hidden = true; };
}

wire();
loadDict();
loadDialogue();
