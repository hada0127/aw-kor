# b44 참조 ROM 복구 기록

트랙: bounded — 기존 적용기로 자산만 복구. 완료 기준: 입력/결과 manifest SHA·CRC·bytes 일치, BPS 내부 CRC 일치, 기존 대시 게이트 exit 0.

## 출처 입력 검증

```text
$ shasum -a 256 'original/Game Boy Wars Advance 1+2 (Japan).gba' dist/game_wars_korean_full_2026-10-21.bps dist/manifest.json dist/apply_patch.py
a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c  original/Game Boy Wars Advance 1+2 (Japan).gba
61fedf2b767df34443a811491e39c04c45612375070d58a9115d54c008775bb3  dist/game_wars_korean_full_2026-10-21.bps
b98f7363dcfc9a5ebc8e21b88f5bb26dc3943a775f5629a66983531f9ed7b88d  dist/manifest.json
254124e6f19c5b8d03a40a33fb5b3d70f3412918f6dcecdba1953aa150764673  dist/apply_patch.py
exit=0
```

## 적용 명령과 실제 출력

```text
$ python3 dist/apply_patch.py "original/Game Boy Wars Advance 1+2 (Japan).gba" output/game_wars_korean_b44_reference_20261023.gba --patch dist/game_wars_korean_full_2026-10-21.bps
=== Game Boy Wars Advance 1+2 한글 패치 적용기 ===

패치 파일 : dist/game_wars_korean_full_2026-10-21.bps
  - 패치 SHA-256 검증: OK
원본 ROM  : original/Game Boy Wars Advance 1+2 (Japan).gba
  - 원본 SHA-256 검증: OK
  - 결과 SHA-256 검증: OK

=== 완료 ===
한글 ROM 저장: output/game_wars_korean_b44_reference_20261023.gba
이제 mGBA 등 에뮬레이터나 실기 플래시카트에서 실행하세요.
exit=0
```

## SHA·CRC·bytes 독립 대조

명령: `python3 -` (아래 읽기 전용 검증식; 파일 수정 없음)

```python
import hashlib, json, struct, zlib
from pathlib import Path
m = json.loads(Path('dist/manifest.json').read_text())
paths = [('source_rom', 'original/Game Boy Wars Advance 1+2 (Japan).gba'), ('bps_patch', 'dist/game_wars_korean_full_2026-10-21.bps'), ('patched_rom', 'output/game_wars_korean_b44_reference_20261023.gba')]
blobs = {}
for key, name in paths:
    b = Path(name).read_bytes()
    blobs[key] = b
    got = {'size': len(b), 'crc32': f'{zlib.crc32(b) & 0xffffffff:08x}', 'sha256': hashlib.sha256(b).hexdigest()}
    print(f'{name}: bytes={got["size"]} crc32={got["crc32"]} sha256={got["sha256"]}')
    assert all(got[k] == m[key][k] for k in got), f'{key}: manifest mismatch'
    print(f'{key}: manifest size/CRC32/SHA256 MATCH')
p = blobs['bps_patch']
expected = struct.unpack('<III', p[-12:])
actual = tuple(zlib.crc32(b) & 0xffffffff for b in (blobs['source_rom'], blobs['patched_rom'], p[:-4]))
for label, want, got in zip(('source', 'target', 'patch body'), expected, actual):
    print(f'BPS {label} CRC32: stored={want:08x} actual={got:08x} match={want == got}')
assert actual == expected
assert m['patched_rom']['sha256'] == '1ac68443d8fa48ef50a5a73290f94d65ff90997b4e6f38bc60410c9d424c6f02'
assert m['output_rom']['sha256'] == m['patched_rom']['sha256']
print('PASS b44 expected SHA256 / manifest / bytes / CRC32 / BPS trailer')
```

```text
original/Game Boy Wars Advance 1+2 (Japan).gba: bytes=16777216 crc32=49ee1fdd sha256=a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c
source_rom: manifest size/CRC32/SHA256 MATCH
dist/game_wars_korean_full_2026-10-21.bps: bytes=1289515 crc32=2144df1c sha256=61fedf2b767df34443a811491e39c04c45612375070d58a9115d54c008775bb3
bps_patch: manifest size/CRC32/SHA256 MATCH
output/game_wars_korean_b44_reference_20261023.gba: bytes=16777216 crc32=8064dd7b sha256=1ac68443d8fa48ef50a5a73290f94d65ff90997b4e6f38bc60410c9d424c6f02
patched_rom: manifest size/CRC32/SHA256 MATCH
BPS source CRC32: stored=49ee1fdd actual=49ee1fdd match=True
BPS target CRC32: stored=8064dd7b actual=8064dd7b match=True
BPS patch body CRC32: stored=0d14a59a actual=0d14a59a match=True
PASS b44 expected SHA256 / manifest / bytes / CRC32 / BPS trailer
exit=0
```

## 기존 대시 게이트

```text
$ python3 tools/qa_part2_name_grid_shared_glyph.py output/game_wars_korean_b44_reference_20261023.gba
PASS shared Part 2 dash 0x815B pixels: be419dc0b96ddc2fa1d67385f46909c1ea950eafaeba5fa59816cde935bc2bba
exit=0
```

## 변경 범위 확인

```text
$ git status --short
exit=0
$ git diff --exit-code
exit=0
```

PLAN 이탈: 없음. 새 참조 ROM과 이 보고서만 생성. 코드 파일 작성·수정, default full/final/title_test 갱신, 전체 빌드, commit/push, 하위 워커 실행 없음.

남은 위험: 이 검증은 b44 바이트 복원과 공유 대시 64바이트 보존만 입증한다. 실화면·실기·이름 조합 ROM 통합은 (unverified).

후속 반영: 정본 문서는 수정하지 않음 — 이 작업은 지정 참조 자료 복구만 허용하며 복구 상태·출처는 이 보고서를 총괄에게 인계한다.

## 세션 정리 검사

```text
$ harness-session-check status
세션 codex-01a16741-f255-7401-a4e5-253dbb4c616d · mode=block · D1(막음) 0건 · 보고 0건 · D1 검사 실패 → 막지 않음: B10(증거 읽기 실패:wt_seq lock) · 보고 검사 일부 실패: evidence(windows.log 공유 락 실패) · 참고: 프로세스 검사 불가(ps 실행 거부 errno=1 — 샌드박스로 추정)
exit=0
```

정리 검사 일부는 샌드박스/공유 락으로 (unverified). 이 작업은 프로세스·브라우저·워크트리·stash·하위 작업을 생성하지 않았다. 요청 산출물 2개는 총괄 인계용으로 보존한다.
