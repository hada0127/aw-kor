#!/usr/bin/env python3
"""Fresh-render 캡처 엔진 — savestate stale-BG를 우회해 OBJ/BG ROM 변경을 인게임 시각 확증.

문제: savestate 캡처는 VRAM이 frozen이라 빌드로 바꾼 OBJ/BG(예: CO 이름 OBJ)가 화면에 반영
안 됨. provenance ROM SHA가 맞아도 VRAM은 patch 이전 상태(2026-06-24 A1에서 확정 입증:
ROM을 한글로 바꿔도 30f2 savestate는 가타카나 표시).

해법: savestate를 로드한 뒤 **refresh-nav**(스크롤/재진입 등 게임이 화면을 ROM에서 다시 그리게
하는 입력)를 수행하면 OBJ/BG가 현재 ROM에서 재렌더된다. 그 프레임을 캡처한다.

검증 사례(A1): CO 프로필에서 RIGHT/LEFT로 CO를 바꾸면 이름 OBJ가 ROM에서 재렌더 →
가타카나(ﾄﾞﾐﾉ) → 한글(맥스/도미노) 확인.

매니페스트: data/freshrender_checkpoints.json
  [{ "name", "state", "refresh": [["press","RIGHT",50], ...], "settle": 20 }]

사용:
  python3 tools/capture_freshrender.py                 # 매니페스트 전체
  python3 tools/capture_freshrender.py --name co_profile_scroll
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from qa_visual_regions import MGBADriver  # noqa: E402

MANIFEST = ROOT / "data" / "freshrender_checkpoints.json"
ROM = ROOT / "output" / "game_wars_korean_full.gba"
HARNESS = Path("/tmp/mgbah")
OUT = ROOT / "temp" / "freshrender"


def run_refresh(driver: MGBADriver, steps: list) -> None:
    for step in steps:
        op = step[0]
        if op == "press":
            driver.press(step[1], after=int(step[2]) if len(step) > 2 else 60,
                         hold=int(step[3]) if len(step) > 3 else 6)
        elif op == "frames":
            driver.frames(int(step[1]))
        else:
            raise ValueError(f"unknown refresh op: {op!r}")


def capture_one(cp: dict, rom: Path, harness: Path, out_dir: Path) -> Path:
    name = cp["name"]
    state = cp["state"]
    state_path = state if Path(state).is_absolute() else ROOT / state
    cdir = out_dir / name
    cdir.mkdir(parents=True, exist_ok=True)
    d = MGBADriver(rom, cdir, harness)
    try:
        d.loadstate(Path(state_path))
        d.frames(int(cp.get("settle", 20)))
        run_refresh(d, cp.get("refresh", []))
        img = d.shot("frame")
    finally:
        d.close()
    out_png = cdir / "frame.png"
    img.save(out_png)
    return out_png


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", action="append", default=[])
    ap.add_argument("--rom", default=str(ROM))
    ap.add_argument("--harness", default=str(HARNESS))
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    if not MANIFEST.exists():
        raise SystemExit(f"매니페스트 없음: {MANIFEST}")
    cps = json.loads(MANIFEST.read_text(encoding="utf-8")).get("checkpoints", [])
    if args.name:
        cps = [c for c in cps if c["name"] in args.name]
    rom = Path(args.rom)
    harness = Path(args.harness)
    if not rom.exists():
        raise SystemExit(f"ROM 없음: {rom}")
    if not harness.exists():
        raise SystemExit(f"하네스 없음: {harness}")
    out_dir = Path(args.out)
    for cp in cps:
        png = capture_one(cp, rom, harness, out_dir)
        print(f"[freshrender] {cp['name']} -> {png}")


if __name__ == "__main__":
    main()
