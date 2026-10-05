#!/usr/bin/env python3
"""실캡처 서비스 — 임의 텍스트/스프라이트를 인게임 렌더로 헤드리스 캡처.

canvas-hijack 방식: 빠르게 도달 가능한 화면(canvas)의 텍스트 슬롯을 임의 문자열로 덮어쓴
ROM 복사본을 만들고, mgbah 헤드리스로 그 화면까지 네비게이션해 실제 렌더 픽셀을 PNG로 캡처한다.
대표 화면에서 글꼴을 확인하는 진단용 미리보기다. 원래 장면의 배치나 최종 빌드 인코딩을 보장하지 않는다.

- 원본(ja): 원본 일본판 ROM 복사본의 canvas 슬롯에 JA(SJIS)를 써서 캡처(원본 폰트 글리프).
- 적용(ko): 패치 ROM 복사본의 canvas 슬롯에 KO(예약코드)를 써서 캡처(주입된 galmuri 글리프).

캐시: (canvas, lang, text) 해시로 PNG 재사용. 동일 입력은 에뮬 재실행 안 함.

CLI:
  python3 tools/preview_capture.py --text "캠페인 시작" --lang ko --canvas part2_menu
  python3 tools/preview_capture.py --text "ｷｬﾝﾍﾟｰﾝ" --lang ja --canvas part2_menu --orig
"""
from __future__ import annotations
import argparse
import collections
import struct
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

ORIG_ROM = ROOT / "original" / "Game Boy Wars Advance 1+2 (Japan).gba"
PATCHED_ROM = ROOT / "output" / "game_wars_korean_full.gba"
SYLCODE = ROOT / "data" / "syllable_to_code_2350.json"
HARNESS = ROOT / "temp" / "mgbah"
CACHE = ROOT / "temp" / "preview_cache"

# ── Canvas 레지스트리 ──────────────────────────────────────────────────────
# 각 canvas: 빠르게 도달 가능한 화면 + 그 화면이 표시하는 텍스트 슬롯.
#   slot/len : ROM 파일 오프셋과 바이트 길이(슬롯에 덮어쓸 영역)
#   nav      : MGBADriver 네비 스텝(아래 _nav 참고). 콜드부트 후 실행.
#   sweep    : optional. nav 뒤 여러 frame을 캡처해 score_box의 ink가 가장 큰 프레임을 선택.
#   render   : 'a3' | 'dialog' (해당 화면의 렌더 경로 — 참고용)
#   note     : 설명
# ※ 슬롯 길이가 짧으면 긴 대사는 잘린다(canvas마다 한계). 더 긴 슬롯 canvas는 추가 예정.
CANVASES = {
    "part2_menu": {
        "slot": 0xA2C098,
        "len": 32,
        "render": "a3",
        "nav": [
            ["frames", 480],
            ["press", "A", 200], ["press", "START", 200], ["press", "DOWN", 120],
            ["press", "A", 240], ["press", "START", 240], ["press", "A", 240], ["press", "A", 240],
        ],
        "note": "Part2 메인 메뉴 캠페인 설명(A3 글리프캐시 렌더러). 짧은 시스템/메뉴 문구용(≤16자).",
    },
}

# 외부 레지스트리(data/preview_canvases.json)에서 canvas를 병합/확장(코드 수정 없이 추가 가능).
# JSON이 동일 key를 정의하면 덮어쓴다. slot은 hex 문자열도 허용.
_REGISTRY = ROOT / "data" / "preview_canvases.json"


def _load_registry():
    if not _REGISTRY.exists():
        return
    data = json.loads(_REGISTRY.read_text(encoding="utf-8"))
    for key, cv in (data.get("canvases") or {}).items():
        cv = dict(cv)
        if "slot" not in cv and "repoint_fixed" in cv:
            cv["slot"] = cv["repoint_fixed"]
        if isinstance(cv.get("slot"), str):
            cv["slot"] = int(cv["slot"], 16)
        if not all(field in cv for field in ("slot", "len", "nav")):
            raise ValueError(f"incomplete preview canvas: {key}")
        CANVASES[key] = cv


_load_registry()


def _parse_int(value):
    try:
        return int(str(value).strip(), 16) if isinstance(value, str) else int(value)
    except (TypeError, ValueError):
        return None


def _resolve_slot(cv: dict, rom: bytes | None = None) -> int:
    fixed = _parse_int(cv.get("repoint_fixed"))
    message = _parse_int(cv.get("repoint_msg"))
    if fixed is None:
        fixed = _parse_int(cv.get("slot"))
        if fixed is None:
            raise ValueError("canvas slot is missing")
        message = fixed
    if rom is None or message is None or fixed < message:
        raise ValueError("repoint canvas requires the actual ROM and source message")
    original = ORIG_ROM.read_bytes()
    needle = struct.pack('<I', 0x08000000 + message)
    references = []
    pos = 0
    while True:
        pos = original.find(needle, pos)
        if pos < 0:
            break
        references.append(pos)
        pos += 1
    targets = {struct.unpack_from('<I', rom, off)[0] - 0x08000000 for off in references}
    if len(targets) != 1:
        raise ValueError("canvas message has missing or conflicting live pointers")
    target = targets.pop()
    delta = fixed - message
    if not 0 <= target < len(rom) or rom[target:target + delta] != original[message:fixed]:
        raise ValueError("canvas message prefix changed")
    slot = target + delta
    size = int(cv["len"])
    expected_tail = bytes.fromhex(cv.get("expected_tail_hex", ""))
    if expected_tail and rom[slot + size:slot + size + len(expected_tail)] != expected_tail:
        raise ValueError("canvas text boundary changed; refusing to overwrite control bytes")
    return slot


def _syl_to_code():
    codes = {s: int(c, 0) for s, c in json.loads(SYLCODE.read_text(encoding="utf-8")).items()}
    if any(not (0x81 <= code >> 8 <= 0x9f or 0xe0 <= code >> 8 <= 0xef)
           for code in codes.values()):
        raise ValueError("preview dictionary contains an invalid two-byte lead")
    return codes


def encode_payload(text: str, lang: str, slot_len: int,
                   add_terminator: bool = True, pad_byte: int = 0x00,
                   address: int | None = None) -> tuple[bytes, bool]:
    """Encode diagnostic text and truncate only at complete character boundaries."""
    if slot_len <= 0 or not 0 <= pad_byte <= 255:
        raise ValueError("invalid canvas size or padding")
    if lang == "ko":
        import build_korean_full as build
        dropped = collections.Counter()
        out = build.encode_text(text, _syl_to_code(), dropped, address)
        if dropped:
            raise ValueError("렌더 불가 문자: " + ''.join(dropped))
        out = build._fw_before_ascii(out, slot_len - int(add_terminator), address)
    elif lang == "ja":
        out = text.encode('shift_jis')
    else:
        raise ValueError("unknown language")
    capacity = slot_len - int(add_terminator)
    cursor = 0
    while cursor < len(out):
        width = 2 if 0x81 <= out[cursor] <= 0x9f or 0xe0 <= out[cursor] <= 0xef else 1
        if cursor + width > capacity:
            break
        cursor += width
    truncated = cursor < len(out)
    payload = bytes(out[:cursor]) + (b'\0' if add_terminator else b'')
    return payload + bytes([pad_byte]) * (slot_len - len(payload)), truncated


def _nav(drv, nav):
    drv.frames(1)
    for step in nav:
        if step[0] == "frames":
            drv.frames(int(step[1]))
        elif step[0] == "press":
            key = step[1]; after = int(step[2]) if len(step) > 2 else 120
            drv.press(key, 6, after)
        elif step[0] == "loadstate":
            drv.loadstate(Path(step[1]) if Path(step[1]).is_absolute() else ROOT / step[1])
            drv.frames(20)
        elif step[0] == "keys":
            drv.cmd(f"keys {int(step[1])}"); drv.frames(6); drv.cmd("keys 0"); drv.frames(60)
        else:
            raise ValueError(f"unknown preview navigation step: {step!r}")


def _frame_list(sweep: dict) -> list[int]:
    if isinstance(sweep.get("frames"), list):
        return sorted({int(v) for v in sweep["frames"]})
    start = int(sweep.get("start", 0))
    end = int(sweep.get("end", start))
    step = max(1, int(sweep.get("step", 1)))
    return list(range(start, end + 1, step))


def _ink_score(img, box: list[int], threshold: int = 1200) -> int:
    crop = img.crop(tuple(int(v) for v in box)).convert("RGB")
    colors = crop.getcolors(maxcolors=1_000_000)
    if not colors:
        return 0
    dominant = max(colors)[1]
    score = 0
    for px in crop.getdata():
        dist = sum((px[i] - dominant[i]) ** 2 for i in range(3))
        if dist > threshold:
            score += 1
    return score


def _capture_sweep(drv, final_png: Path, sweep: dict) -> dict:
    frames = _frame_list(sweep)
    if not frames:
        raise ValueError("sweep frames empty")
    score_box = sweep.get("score_box")
    if not score_box or len(score_box) != 4:
        raise ValueError("sweep requires score_box=[x0,y0,x1,y1]")
    threshold = int(sweep.get("threshold", 1200))
    min_score = int(sweep.get("min_score", 1))
    keep_all = bool(sweep.get("keep_all"))
    best = None
    last = 0
    candidates = []
    for frame in frames:
        delta = frame - last
        if delta < 0:
            raise ValueError("sweep frames must be sorted")
        if delta:
            drv.frames(delta)
        last = frame
        stem = f"{final_png.stem}_f{frame:04d}"
        img = drv.shot(stem)
        score = _ink_score(img, score_box, threshold)
        rec = {"frame": frame, "score": score, "png": str(final_png.with_name(stem + ".png"))}
        candidates.append(rec)
        if best is None or score > best["score"]:
            best = {"frame": frame, "score": score, "image": img, "png": rec["png"]}
    if best is None or best["score"] < min_score:
        raise AssertionError(f"sweep failed: best={best} min_score={min_score}")
    best["image"].save(final_png)
    if not keep_all:
        for rec in candidates:
            p = Path(rec["png"])
            raw = p.with_suffix(".raw")
            try:
                p.unlink()
            except OSError:
                pass
            try:
                raw.unlink()
            except OSError:
                pass
    return {
        "sweep": {
            "selected_frame": best["frame"],
            "selected_score": best["score"],
            "score_box": score_box,
            "candidates": [{"frame": r["frame"], "score": r["score"]} for r in candidates],
        }
    }


def capture(text: str, lang: str = "ko", canvas: str = "part2_menu",
            base_rom: Path | None = None, out_name: str | None = None, use_cache: bool = True) -> dict:
    """canvas 슬롯에 text를 써서 실캡처. {png, truncated, cached} 반환."""
    if canvas not in CANVASES:
        raise ValueError(f"unknown canvas {canvas!r}; have {list(CANVASES)}")
    cv = CANVASES[canvas]
    if base_rom is None:
        base_rom = ORIG_ROM if lang == "ja" else PATCHED_ROM
    base_rom = Path(base_rom)
    source_bytes = base_rom.read_bytes()
    slot = _resolve_slot(cv, source_bytes)
    if slot < 0 or slot + cv["len"] > len(source_bytes):
        raise ValueError("canvas is outside ROM")
    terminator = (cv.get("terminator") or "nul").lower()
    pad_raw = cv.get("pad", "0x00")
    pad_byte = int(pad_raw, 0) if isinstance(pad_raw, str) else int(pad_raw)
    payload, truncated = encode_payload(
        text, lang, cv["len"],
        add_terminator=(terminator != "none"),
        pad_byte=pad_byte, address=_parse_int(cv.get("repoint_fixed")) or _parse_int(cv.get("slot")),
    )
    CACHE.mkdir(parents=True, exist_ok=True)
    # 캐시 키에 canvas 정의(slot/len/nav)와 base_rom 식별(크기+mtime)을 포함 — nav/슬롯/ROM이
    # 바뀌면 캐시 무효화(codex 지적: 기존 key는 base_rom.name+text뿐이라 stale 재사용 위험).
    rom_id = hashlib.sha256(source_bytes).hexdigest()
    encoder_id = hashlib.sha256(Path(__file__).read_bytes() +
                                (ROOT / 'tools/build_korean_full.py').read_bytes() +
                                SYLCODE.read_bytes() + HARNESS.read_bytes()).hexdigest()
    state_hashes = {}
    for step in cv.get("nav", []):
        if step[0] == "loadstate":
            state = Path(step[1])
            if not state.is_absolute():
                state = ROOT / state
            state_hashes[str(state)] = hashlib.sha256(state.read_bytes()).hexdigest()
    cv_sig = json.dumps({"slot": slot, "configured_slot": cv.get("slot"), "len": cv.get("len"),
                         "terminator": terminator, "pad": pad_byte,
                         "nav": cv.get("nav"), "state_hashes": state_hashes, "sweep": cv.get("sweep")},
                        ensure_ascii=False, sort_keys=True)
    key = hashlib.sha1(f"{canvas}|{lang}|{rom_id}|{encoder_id}|{cv_sig}|{text}".encode("utf-8")).hexdigest()[:16]
    if out_name and Path(out_name).name != out_name:
        raise ValueError("out_name must be a filename inside the preview cache")
    # A caller-supplied label must not erase the content identity. Distinct
    # requests publish distinct files even when they share the same label.
    png = CACHE / (f"{Path(out_name).stem}_{key}.png" if out_name else f"{canvas}_{lang}_{key}.png")
    meta_path = png.with_suffix(".json")
    if use_cache and png.exists() and meta_path.exists():
        meta = {}
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                meta = {}
        if meta.get("cache_key") == key:
            return {"png": str(png), "truncated": truncated, "cached": True, **meta}

    from qa_visual_regions import MGBADriver  # noqa: E402
    from editor_storage import atomic_write_bytes, save_json
    # Different editor processes may request the same text simultaneously.
    # Each emulator owns its ROM, raw frames and log; publish only complete PNGs.
    run = Path(tempfile.mkdtemp(prefix=f"run_{key}_", dir=CACHE))
    work = run / "preview.gba"
    captured = run / png.name
    drv = None
    meta = {}
    try:
        b = bytearray(source_bytes)
        b[slot: slot + cv["len"]] = payload
        work.write_bytes(b)
        drv = MGBADriver(work, run, HARNESS)
        _nav(drv, cv["nav"])
        if cv.get("sweep"):
            meta = _capture_sweep(drv, captured, cv["sweep"])
            if cv["sweep"].get("keep_all"):
                for candidate in meta["sweep"]["candidates"]:
                    name = f"{png.stem}_f{candidate['frame']:04d}.png"
                    atomic_write_bytes(CACHE / name, (run / name).read_bytes())
                    candidate["png"] = str(CACHE / name)
        else:
            drv.shot(captured.stem)
        meta["cache_key"] = key
        atomic_write_bytes(png, captured.read_bytes())
        save_json(meta_path, meta)
    finally:
        try:
            if drv is not None:
                drv.close()
        finally:
            shutil.rmtree(run)

    return {"png": str(png), "truncated": truncated, "cached": False, **meta}


def compare(text_ja: str, text_ko: str, canvas: str = "part2_menu", use_cache: bool = True) -> dict:
    """원본(ja)↔적용(ko) 한 쌍 캡처."""
    orig = capture(text_ja, "ja", canvas, use_cache=use_cache)
    appl = capture(text_ko, "ko", canvas, use_cache=use_cache)
    return {"canvas": canvas, "orig": orig, "applied": appl}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True)
    ap.add_argument("--lang", choices=["ko", "ja"], default="ko")
    ap.add_argument("--canvas", default="part2_menu")
    ap.add_argument("--orig", action="store_true", help="원본 ROM 사용(ja 기본)")
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()
    base = ORIG_ROM if (args.orig or args.lang == "ja") else PATCHED_ROM
    r = capture(args.text, args.lang, args.canvas, base_rom=base, use_cache=not args.no_cache)
    print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
