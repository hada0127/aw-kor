#!/usr/bin/env python3
"""OBJ VRAM 영역 표식 주입 — 좌측 그리드가 스프라이트인지 확인."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from hangul_glyph import render_tile

ROM_IN  = "output/v27_original_base.gba"
ROM_OUT = "output/v39_obj_probe.gba"

def main():
    rom = bytearray(open(ROM_IN, "rb").read())
    # OBJ VRAM은 런타임 메모리. ROM에서 그쪽으로 복사하는 소스가 어디 있는지 모름.
    # 대신: BG VRAM의 다른 영역도 시도 — 슬롯 0-287에 표식
    for slot in range(0, 288):
        digit = 'X'
        glyph = render_tile(digit, ink=10)
        # FONT_BASE 가 0xB974D0, 슬롯 0 = ROM 0xB974D0이지만 슬롯 0-127은 dialog 폰트
        # 좌측 그리드 슬롯이 어디일지 모르니 전체 0-287에 X 박기
        # 하지만 0-127은 dialog top/bottom 영역과 겹침 → 추후 RE
        pass
    # 위 의도는 위험. 대신 일단 RAM 추적이 필요.
    # 그러므로 ROM은 변경 없이 디버그용 스크린샷 (mode toggle 시도) 만 캡처
    open(ROM_OUT, "wb").write(rom)
    chk = (-(0x19 + sum(rom[0xA0:0xBD]))) & 0xFF
    rom[0xBD] = chk
    open(ROM_OUT, "wb").write(rom)
    print(f"[OK] {ROM_OUT}")

if __name__ == "__main__":
    main()
