#!/usr/bin/env python3
"""자동진행 화면 수집기 (auto_playthrough).

세이브스테이트 또는 콜드부트에서 시작해 입력 정책(A 위주 + 주기적 방향/START)으로
게임을 진행시키며, **프레임 해시로 구분되는 새 화면만** 캡처한다. 깊은 화면(전투
대사/결과/저장/상점/엔딩 등)을 사람/codex 시각 리뷰용 필름스트립으로 모은다.

핵심: 정적 화면이 stale인 savestate 문제를 회피한다 — 실제로 게임을 '진행'시키므로
모든 화면이 현재 ROM으로 새로 렌더된다.

사용
  python3 tools/auto_playthrough.py --state temp/.../final.ss0 --steps 200 --out temp/auto_battle
  python3 tools/auto_playthrough.py --fresh --nav-part2-menu --steps 200 --out temp/auto_p2
"""
from __future__ import annotations
import argparse, hashlib, sys, os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qa_visual_regions import MGBADriver, raw_to_png  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
KEYS = {"A": 1, "B": 2, "SELECT": 4, "START": 8, "RIGHT": 16, "LEFT": 32, "UP": 64, "DOWN": 128}

# 입력 정책: A(대사/확인/유닛선택/공격) 위주 + 전투 진전용 이동 매크로 + 주기적 턴종료(START).
# 전투에서 유닛 선택→이동→공격/대기를 흉내내 진군시키고, 막히면 START로 턴을 넘긴다.
POLICY = ["A", "A", "RIGHT", "A", "A", "DOWN", "A", "A", "START", "A",
          "A", "LEFT", "A", "A", "UP", "A", "A", "START", "A", "B"]
# 막힘 감지 시(같은 화면 반복) 강제로 시도할 탈출 입력
UNSTICK = ["START", "A", "A", "B", "DOWN", "A"]


def frame_sig(img: Image.Image):
    """32x24 grayscale 시그니처(바이트). 화면 유사도 비교용."""
    return img.resize((32, 24)).convert("L").tobytes()


def mean_diff(a: bytes, b: bytes) -> float:
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def label_font(size=13):
    for p in ("/Library/Fonts/NanumGothic.ttf", "/System/Library/Fonts/Supplemental/AppleGothic.ttf"):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def montage(shots, out_path, cols=6):
    if not shots:
        print("no distinct screens"); return
    cw, ch, hd, pad = 240, 160, 16, 4
    rows = (len(shots) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (cw + pad) + pad, rows * (ch + hd + pad) + pad), (16, 16, 18))
    dr = ImageDraw.Draw(sheet); f = label_font()
    for i, (label, img) in enumerate(shots):
        r, c = divmod(i, cols)
        x = pad + c * (cw + pad); y = pad + r * (ch + hd + pad)
        dr.text((x, y), label, font=f, fill=(230, 230, 230))
        sheet.paste(img, (x, y + hd))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)
    print(f"[montage] {out_path}  ({len(shots)} distinct screens)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", help="시작 세이브스테이트")
    ap.add_argument("--fresh", action="store_true", help="콜드부트 시작")
    ap.add_argument("--prenav", default="", help="시작 전 키 시퀀스(쉼표구분, 예 'frames600,A,START')")
    ap.add_argument("--steps", type=int, default=160)
    ap.add_argument("--per-step-frames", type=int, default=40)
    ap.add_argument("--diff", type=float, default=11.0, help="새 화면 판정 평균픽셀차 임계")
    ap.add_argument("--save-states", action="store_true", help="새 화면마다 .ss0 저장(진행 세이브 생성)")
    ap.add_argument("--dump-state", action="store_true", help="새 화면마다 VRAM/OAM/팔레트/IO 덤프(레이아웃 추출용)")
    ap.add_argument("--out", default=str(ROOT / "temp" / "auto_play"))
    ap.add_argument("--harness", default="/tmp/mgbah")
    args = ap.parse_args()

    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    drv = MGBADriver(Path(ROOT / "output" / "game_wars_korean_full.gba"), out, Path(args.harness))
    sigs = []; shots = []
    try:
        drv.frames(1)
        if args.state:
            drv.loadstate(Path(args.state) if Path(args.state).is_absolute() else ROOT / args.state)
            drv.frames(20)
        for tok in [t for t in args.prenav.split(",") if t]:
            if tok.startswith("frames"):
                drv.frames(int(tok[6:]))
            elif tok in KEYS:
                drv.cmd(f"keys {KEYS[tok]}"); drv.frames(6); drv.cmd("keys 0"); drv.frames(120)
        stuck = 0
        for step in range(args.steps):
            key = UNSTICK[stuck % len(UNSTICK)] if stuck >= 6 else POLICY[step % len(POLICY)]
            drv.cmd(f"keys {KEYS[key]}"); drv.frames(6); drv.cmd("keys 0"); drv.frames(args.per_step_frames)
            img = drv.shot(f"s{step:03d}")
            sig = frame_sig(img)
            if all(mean_diff(sig, s) > args.diff for s in sigs):
                sigs.append(sig)
                shots.append((f"{step:03d}:{key}", img.copy()))
                if args.save_states:
                    drv.cmd(f"savestate {out / ('state_%03d.ss0' % len(shots))}")
                if args.dump_state:
                    tag = "scr_%03d" % len(shots)
                    drv.cmd(f"dumpvram {out / (tag + '.vram')}")
                    drv.cmd(f"dumpmem 7000000 0x400 {out / (tag + '.oam')}")
                    drv.cmd(f"dumpmem 5000000 0x400 {out / (tag + '.pal')}")
                    drv.cmd(f"dumpmem 4000000 0x60 {out / (tag + '.io')}")
                stuck = 0
            else:
                stuck += 1
        print(f"steps={args.steps} distinct_screens={len(shots)}  states_saved={len(shots) if args.save_states else 0}")
    finally:
        drv.close()
    montage(shots, out / "filmstrip.png")


if __name__ == "__main__":
    main()
