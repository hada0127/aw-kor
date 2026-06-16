#!/usr/bin/env python3
"""실캡처 서비스 — 임의 텍스트/스프라이트를 인게임 렌더로 헤드리스 캡처.

canvas-hijack 방식: 빠르게 도달 가능한 화면(canvas)의 텍스트 슬롯을 임의 문자열로 덮어쓴
ROM 복사본을 만들고, mgbah 헤드리스로 그 화면까지 네비게이션해 실제 렌더 픽셀을 PNG로 캡처한다.
풀 게임 진행 없이 임의 라인을 "실제 적용된 모습"으로 보여 준다(검증: 2026-06-16, research.md).

- 원본(ja): 원본 일본판 ROM 복사본의 canvas 슬롯에 JA(SJIS)를 써서 캡처(원본 폰트 글리프).
- 적용(ko): 패치 ROM 복사본의 canvas 슬롯에 KO(예약코드)를 써서 캡처(주입된 galmuri 글리프).

캐시: (canvas, lang, text) 해시로 PNG 재사용. 동일 입력은 에뮬 재실행 안 함.

CLI:
  python3 tools/preview_capture.py --text "캠페인 시작" --lang ko --canvas part2_menu
  python3 tools/preview_capture.py --text "ｷｬﾝﾍﾟｰﾝ" --lang ja --canvas part2_menu --orig
"""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

ORIG_ROM = ROOT / "original" / "Game Boy Wars Advance 1+2 (Japan).gba"
PATCHED_ROM = ROOT / "output" / "game_wars_korean_full.gba"
SYLCODE = ROOT / "data" / "syllable_to_code_2350.json"
HARNESS = Path("/tmp/mgbah")
CACHE = ROOT / "temp" / "preview_cache"

# ── Canvas 레지스트리 ──────────────────────────────────────────────────────
# 각 canvas: 빠르게 도달 가능한 화면 + 그 화면이 표시하는 텍스트 슬롯.
#   slot/len : ROM 파일 오프셋과 바이트 길이(슬롯에 덮어쓸 영역)
#   nav      : MGBADriver 네비 스텝(아래 _nav 참고). 콜드부트 후 실행.
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


def _syl_to_code():
    return {s: int(c, 0) for s, c in json.loads(SYLCODE.read_text(encoding="utf-8")).items()}


def encode_payload(text: str, lang: str, slot_len: int) -> bytes:
    """text를 canvas 슬롯 바이트로 인코딩. ko=예약코드, ja=SJIS. 0x00 종료 + 패딩."""
    out = bytearray()
    if lang == "ko":
        s2c = _syl_to_code()
        for ch in text:
            if ch in s2c:
                c = s2c[ch]; out += bytes([c >> 8, c & 0xFF])
            elif ch == "　":
                out += b"\x81\x40"
            elif ch == " ":
                out += b"\x20"
            elif 0x20 <= ord(ch) <= 0x7E:
                out += bytes([ord(ch)])
            else:
                # 2350 밖 음절/기호 → ? (인게임도 동일하게 깨지므로 프리뷰가 충실히 노출)
                out += b"\x81\x48"
    else:  # ja
        for ch in text:
            if ch == " ":
                out += b"\x20"
            else:
                try:
                    out += ch.encode("shift_jis")
                except Exception:
                    out += b"\x81\x48"
    truncated = len(out) + 1 > slot_len
    if truncated:
        # 슬롯 한계까지 자른다(2바이트 코드 경계 보존은 호출측 책임 — 여기선 단순 컷)
        out = out[: slot_len - 1]
    out += b"\x00"
    out += b"\x00" * (slot_len - len(out))
    return bytes(out[:slot_len]), truncated


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


def capture(text: str, lang: str = "ko", canvas: str = "part2_menu",
            base_rom: Path | None = None, out_name: str | None = None, use_cache: bool = True) -> dict:
    """canvas 슬롯에 text를 써서 실캡처. {png, truncated, cached} 반환."""
    if canvas not in CANVASES:
        raise ValueError(f"unknown canvas {canvas!r}; have {list(CANVASES)}")
    cv = CANVASES[canvas]
    if base_rom is None:
        base_rom = ORIG_ROM if lang == "ja" else PATCHED_ROM
    base_rom = Path(base_rom)
    payload, truncated = encode_payload(text, lang, cv["len"])
    CACHE.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(f"{canvas}|{lang}|{base_rom.name}|{text}".encode("utf-8")).hexdigest()[:16]
    png = CACHE / (out_name or f"{canvas}_{lang}_{key}.png")
    if use_cache and png.exists():
        return {"png": str(png), "truncated": truncated, "cached": True}

    from qa_visual_regions import MGBADriver  # noqa: E402
    work = CACHE / f"_rom_{key}.gba"
    shutil.copyfile(base_rom, work)
    b = bytearray(work.read_bytes())
    b[cv["slot"]: cv["slot"] + cv["len"]] = payload
    work.write_bytes(b)
    drv = MGBADriver(work, CACHE, HARNESS)
    try:
        _nav(drv, cv["nav"])
        img = drv.shot(png.stem)
    finally:
        drv.close()
    try:
        work.unlink()
    except OSError:
        pass
    return {"png": str(png), "truncated": truncated, "cached": False}


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
