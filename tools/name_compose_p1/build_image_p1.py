#!/usr/bin/env python3
"""1편 이름 조합 코드 이미지 빌드 → tools/part1_name_compose_blob.py 생성 (PLAN B T3, D8·D9).

절차: gen_tables_p1(tables.h·grid_p1.inc·p1_config.h) → clang(core.c·p1.c, Thumb-1)
      + clang 통합 어셈블러(tramp_p1.s) → ld.lld -T image_p1.ld (ELF) + ld.lld --oformat binary(raw)
      → 검사 → blob 모듈.
툴체인: 이 PC 는 GNU arm-none-eabi binutils·llvm-objcopy/objdump/readelf 가 없어(plan_B_approval: sudo 설치 금지)
      clang + ld.lld 만 쓴다. ELF·속성·Thumb-1 검사 함수는 Part 2 build_image.py 정본을 import 한다(2026-11-04 fixB).
검사: 재배치 섹션(SHT_REL/RELA) 0 · 미해결 심볼(SHN_UNDEF) 0 · 할당 섹션은 .image 하나(VMA 0x08F77800) ·
      크기 ≤ 8,192 · raw(--oformat binary) == ELF .image · .ARM.attributes(출력·모든 입력 .o)
      Tag_CPU_arch v4T / Tag_THUMB_ISA_use Thumb-1 · $t 구간 Thumb-1 명령 검사(자체 halfword 디코더 —
      32bit 는 bl 쌍만, v5T 이상 16bit 인코딩·low-low hi-register 연산 금지; capstone 을 import 할 수 있으면
      같은 구간을 capstone 으로도 전수 디코드해 교차 검사) · ARM 상태($a) 없음 · 함수 심볼 Thumb bit 1 ·
      공개 심볼 오프셋 4정렬 · nc_dense 절대 0x08F70000 · tramp_p1.s 의 런타임 주소 = gen_tables_p1.CONFIG.

일반 ROM 빌드는 생성된 blob 모듈만 import 한다(툴체인 불필요).
사용:
  python3 tools/name_compose_p1/build_image_p1.py            # blob 모듈 다시 쓰기
  python3 tools/name_compose_p1/build_image_p1.py --check    # 재생성 결과가 저장본과 같은지만(쓰지 않음)
  --work DIR  중간 산출물 폴더(기본 temp/name_compose_p1_build, 추적 안 함)
"""
import argparse
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(TOOLS, 'name_compose'))
sys.path.insert(0, TOOLS)

import gen_tables_p1 as g1  # noqa: E402
from build_image import (parse_elf, _run, _sha, _read, check_attributes, code_ranges,  # noqa: E402
                         verify_thumb1, verify_capstone)  # (Part 2 — 검사 함수는 build_image.py 정본)

IMAGE_RT = 0x08F77800
IMAGE_MAX = 0x2000
DENSE_RT = 0x08F70000
BLOB_PATH = os.path.join(TOOLS, 'part1_name_compose_blob.py')
DEFAULT_WORK = os.path.join(ROOT, 'temp', 'name_compose_p1_build')

FUNC_SYMBOLS = ('nc_press', 'nc_confirm', 'nc_backspace', 'nc1_tramp_press', 'nc1_tramp_confirm',
                'nc1_tramp_backspace', 'nc1_tramp_display', 'nc1_preview')
DATA_SYMBOLS = ('nc_sel_priv', 'nc_row_priv', 'nc1_host_tab', 'nc1_placeholders')
# SOURCE_SHA: CODE 를 결정하는 모든 입력(추적 파일) + 생성 include(작업 폴더 생성물)
SOURCE_FILES = ('tools/name_compose/core.c', 'tools/name_compose/gen_tables.py', 'tools/hangul_compose.py',
                'data/jamo_to_code_40.json',
                'tools/name_compose_p1/tramp_p1.s', 'tools/name_compose_p1/p1.c',
                'tools/name_compose_p1/image_p1.ld', 'tools/name_compose_p1/gen_tables_p1.py',
                'tools/name_compose_p1/build_image_p1.py')
GENERATED_FILES = ('tables.h', 'grid_p1.inc', 'p1_config.h')

TARGET_FLAGS = ('-target', 'armv4t-none-eabi', '-mcpu=arm7tdmi', '-mthumb')
CLANG_FLAGS = TARGET_FLAGS + ('-ffreestanding', '-fno-builtin', '-fno-stack-protector', '-fno-unwind-tables',
                              '-fno-asynchronous-unwind-tables', '-Os', '-Wall', '-Wextra', '-Werror')
AS_FLAGS = TARGET_FLAGS + ('-Wa,--fatal-warnings',)
LD_FLAGS = ('--no-undefined', '--fatal-warnings')

from build_image import SHT_RELA, SHT_REL, SHN_UNDEF, SHN_ABS, TAG_CPU_ARCH, TAG_THUMB_ISA_USE  # noqa: E402
# tramp_p1.s .equ ↔ CONFIG
TRAMP_CONFIG_EQU = {'OBJ_PTR': 'obj_ptr', 'LIT_TILEMAP': 'tilemap_lit'}


def toolchain():
    """{'clang': path, 'ld.lld': path} 또는 None."""
    tools = {'clang': shutil.which('clang'), 'ld.lld': shutil.which('ld.lld')}
    return tools if all(tools.values()) else None


def toolchain_versions(tools):
    return {key: _run([tools[key], '--version'], ROOT).strip().splitlines()[0] for key in ('clang', 'ld.lld')}


def source_sha(generated=None):
    """SOURCE_SHA dict. generated = gen_tables_p1.generate() 결과(없으면 지금 생성)."""
    if generated is None:
        generated = g1.generate()
    out = {rel: _sha(_read(os.path.join(ROOT, rel))) for rel in SOURCE_FILES}
    for name in GENERATED_FILES:
        out[f'generated/{name}'] = _sha(generated[name])
    return out


def tramp_constants():
    src = _read(os.path.join(HERE, 'tramp_p1.s')).decode('utf-8')
    out = {}
    for name in TRAMP_CONFIG_EQU:
        m = re.search(rf'^\s*\.equ\s+{name},\s*(0x[0-9A-Fa-f]+)', src, re.M)
        if not m:
            raise ValueError(f'tramp_p1.s: .equ {name} missing')
        out[name] = int(m.group(1), 16)
    return out


def build(work=DEFAULT_WORK, tools=None):
    """이미지를 빌드·검사하고 결과 dict 반환. 파일은 work 폴더에만 쓴다."""
    tools = tools or toolchain()
    if tools is None:
        raise RuntimeError('toolchain unavailable (clang + ld.lld)')
    for name, key in TRAMP_CONFIG_EQU.items():
        if tramp_constants()[name] != g1.CONFIG[key]:
            raise ValueError(f'tramp_p1.s {name} != CONFIG[{key!r}]')
    work = os.path.abspath(work)
    os.makedirs(work, exist_ok=True)
    generated = g1.generate()
    for name, data in generated.items():
        with open(os.path.join(work, name), 'wb') as f:
            f.write(data)
    objs = {n: os.path.join(work, f'{n}.o') for n in ('tramp', 'core', 'p1')}
    elf, binf, mapf = (os.path.join(work, n) for n in ('image.elf', 'image.bin', 'image.map'))
    ld_script = os.path.join(HERE, 'image_p1.ld')
    inputs = [objs['tramp'], objs['core'], objs['p1']]
    log = []
    cmds = [
        [tools['clang'], *CLANG_FLAGS, '-I', work, '-c', os.path.join(TOOLS, 'name_compose', 'core.c'),
         '-o', objs['core']],
        [tools['clang'], *CLANG_FLAGS, '-I', work, '-c', os.path.join(HERE, 'p1.c'), '-o', objs['p1']],
        [tools['clang'], *AS_FLAGS, '-I', work, '-c', os.path.join(HERE, 'tramp_p1.s'), '-o', objs['tramp']],
        [tools['ld.lld'], '-T', ld_script, *LD_FLAGS, f'-Map={mapf}', '-o', elf, *inputs],
        [tools['ld.lld'], '-T', ld_script, *LD_FLAGS, '--oformat', 'binary', '-o', binf, *inputs],
    ]
    for cmd in cmds:
        log.append((cmd, _run(cmd, work)))
    raw_elf, raw_bin = _read(elf), _read(binf)
    sections, symbols = parse_elf(raw_elf)

    rel = [s['name'] for s in sections if s['type'] in (SHT_REL, SHT_RELA)]
    if rel:
        raise ValueError(f'relocation sections present: {rel}')
    undef = sorted(n for n, ents in symbols.items() for e in ents if e['shndx'] == SHN_UNDEF)
    if undef:
        raise ValueError(f'undefined symbols: {undef}')
    attrs = {'image.elf': check_attributes(raw_elf, 'image.elf')}
    for n, path in objs.items():
        attrs[f'{n}.o'] = check_attributes(_read(path), f'{n}.o')
        o_sections, o_symbols = parse_elf(_read(path))
        if any(k.split('.', 1)[0] == '$a' for k in o_symbols):
            raise ValueError(f'{n}.o: ARM-state mapping symbol present')

    alloc = [s for s in sections if s['flags'] & 2]     # SHF_ALLOC
    if [s['name'] for s in alloc] != ['.image']:
        raise ValueError(f'alloc sections != [.image]: {[s["name"] for s in alloc]}')
    image = alloc[0]
    if image['addr'] != IMAGE_RT:
        raise ValueError(f'.image VMA 0x{image["addr"]:08X} != 0x{IMAGE_RT:08X}')
    if image['size'] > IMAGE_MAX:
        raise ValueError(f'.image size {image["size"]} > {IMAGE_MAX}')
    code = raw_elf[image['offset']:image['offset'] + image['size']]
    if raw_bin != code:
        raise ValueError('ld.lld --oformat binary != ELF .image bytes')
    dense = symbols.get('nc_dense', [])
    if len(dense) != 1 or dense[0]['value'] != DENSE_RT or dense[0]['shndx'] != SHN_ABS:
        raise ValueError(f'nc_dense must be ABS 0x{DENSE_RT:08X}: {dense}')

    ranges = code_ranges(symbols, IMAGE_RT, len(code))
    insn_count = verify_thumb1(code, ranges)
    cs_count, cs_label = verify_capstone(code, ranges, IMAGE_RT)
    if cs_count is not None and cs_count != insn_count:
        raise ValueError(f'capstone count {cs_count} != decoder count {insn_count}')

    syms = {}
    for name in FUNC_SYMBOLS + DATA_SYMBOLS:
        ent = [e for e in symbols.get(name, []) if e['bind'] == 1]   # GLOBAL
        if len(ent) != 1:
            raise ValueError(f'symbol {name}: {ent}')
        value = ent[0]['value']
        if name in FUNC_SYMBOLS:
            if ent[0]['type'] != 2 or not value & 1:
                raise ValueError(f'{name} is not a Thumb FUNC (value 0x{value:08X})')
            value &= ~1
            if not any(s <= value - IMAGE_RT < e for s, e in ranges):
                raise ValueError(f'{name} is not inside a $t range')
        off = value - IMAGE_RT
        if not 0 <= off < len(code) or off % 4:
            raise ValueError(f'{name} offset {off} out of range or not 4-aligned')
        syms[name] = off
    _check_data(code, syms, generated)
    return {'code': code, 'symbols': syms, 'source_sha': source_sha(generated),
            'toolchain': toolchain_versions(tools), 'insn_count': insn_count,
            'capstone': (cs_count, cs_label), 'ranges': ranges, 'attributes': attrs, 'log': log,
            'elf': elf, 'bin': binf}


def _check_data(code, syms, generated):
    """이미지 안 데이터 심볼 바이트 = 생성기 출력(grid_p1.inc 를 다시 해석하지 않고 생성 함수와 대조)."""
    codes = g1.load_jamo_codes()
    grid = g1.gen_tables.selection_grid(codes)
    sel = b''.join(c.to_bytes(2, 'big') for row in grid for c in row)
    rows = b''.join(g1.display_rows_p1(grid, codes))
    for name, want in (('nc_sel_priv', sel), ('nc_row_priv', rows), ('nc1_host_tab', g1.host_tab_bytes()),
                       ('nc1_placeholders', g1.placeholders_bytes())):
        off = syms[name]
        if code[off:off + len(want)] != want:
            raise ValueError(f'{name} bytes differ from generator output')


def render_blob(result):
    code = result['code']
    hexs = code.hex()
    lines = [hexs[i:i + 96] for i in range(0, len(hexs), 96)]
    body = '\n'.join(f"    '{ln}'" for ln in lines)
    sym = ''.join(f"    '{k}': 0x{v:04X},\n" for k, v in result['symbols'].items())
    src = ''.join(f"    '{k}': '{v}',\n" for k, v in result['source_sha'].items())
    tc = ''.join(f"    '{k}': {v!r},\n" for k, v in result['toolchain'].items())

    def cval(v):
        return f'0x{v:08X}' if isinstance(v, int) else repr(v)
    cfg = ''.join(f"    '{k}': {cval(v)},\n" for k, v in g1.CONFIG.items())
    rows = g1.row_lengths_p1()
    return f'''"""생성 파일 — python3 tools/name_compose_p1/build_image_p1.py 로만 다시 만든다. 손으로 고치지 않는다.

1편 이름 입력 두벌식 조합 코드 이미지(PLAN B T3). ROM 파일 0x{IMAGE_RT - 0x08000000:06X}(버스 IMAGE_RT)에 CODE 를
그대로 둔다. nc_dense 표는 2편과 공유하는 이미지 밖 DENSE_RT(파일 0x{DENSE_RT - 0x08000000:06X})다.
SYMBOLS 는 CODE 안 바이트 오프셋(Thumb bit 없음)이고, 함수 진입 리터럴은 entry(name) = IMAGE_RT + SYMBOLS[name] | 1.
훅: H1 nc1_tramp_press · H2 nc1_tramp_confirm · H3 nc1_tramp_backspace · H4 nc1_tramp_display · H5 nc1_preview.
CONFIG 는 gen_tables_p1.CONFIG(T0 런타임 값) 사본 — 빌더가 자기 상수와 대조한다.
툴체인 없이 쓰는 검증: verify_code(), check_sources(), entry(), sel_priv(), row_priv(), host_tab(), placeholders().
"""
import hashlib
import os

IMAGE_RT = 0x{IMAGE_RT:08X}
IMAGE_MAX = 0x{IMAGE_MAX:04X}
DENSE_RT = 0x{DENSE_RT:08X}
CODE = bytes.fromhex(
{body}
)
CODE_SHA = '{_sha(code)}'
SYMBOLS = {{
{sym}}}
FUNC_SYMBOLS = {FUNC_SYMBOLS!r}
DATA_SYMBOLS = {DATA_SYMBOLS!r}
GRID_W, GRID_H = 15, 6
ROW_LENGTHS = {rows!r}
HOST_COUNT = {len(g1.HOST_CODES)}
PLACEHOLDER_COUNT = {len(g1.PLACEHOLDERS)}
CONFIG = {{
{cfg}}}
SOURCE_SHA = {{
{src}}}
TOOLCHAIN = {{
{tc}}}

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def verify_code():
    """CODE 해시·크기·심볼 오프셋(범위·4정렬) 검사. 실패 시 ValueError."""
    if hashlib.sha256(CODE).hexdigest() != CODE_SHA:
        raise ValueError('CODE sha mismatch')
    if len(CODE) > IMAGE_MAX:
        raise ValueError(f'CODE {{len(CODE)}}B > IMAGE_MAX')
    if set(SYMBOLS) != set(FUNC_SYMBOLS) | set(DATA_SYMBOLS):
        raise ValueError('SYMBOLS names changed')
    for name, off in SYMBOLS.items():
        if not 0 <= off < len(CODE) or off % 4:
            raise ValueError(f'{{name}} offset {{off}} invalid')
    ends = {{'nc_sel_priv': GRID_W * GRID_H * 2, 'nc_row_priv': sum(ROW_LENGTHS),
             'nc1_host_tab': 4 * HOST_COUNT, 'nc1_placeholders': 2 * PLACEHOLDER_COUNT}}
    for name, n in ends.items():
        if SYMBOLS[name] + n > len(CODE):
            raise ValueError(f'{{name}} runs past CODE')
    return True


def entry(name):
    """훅 사이트에 쓸 Thumb 진입 주소(|1). 데이터 심볼은 거부."""
    if name not in FUNC_SYMBOLS:
        raise KeyError(f'{{name}} is not a function symbol')
    return IMAGE_RT + SYMBOLS[name] | 1


def sel_priv():
    """사설 선택표 90셀(u16 BE) 바이트."""
    off = SYMBOLS['nc_sel_priv']
    return CODE[off:off + GRID_W * GRID_H * 2]


def row_priv():
    """사설 표시행 6개(bytes 목록, 1편 형식 0A 09 + 쌍 + 0A 00 00 00)."""
    off, rows = SYMBOLS['nc_row_priv'], []
    for n in ROW_LENGTHS:
        rows.append(CODE[off:off + n])
        off += n
    return rows


def host_tab():
    """[(자모 index, host 코드)] 33개 (엔트리 {{u8 index, u8 0, u16 host LE}})."""
    off = SYMBOLS['nc1_host_tab']
    return [(CODE[off + 4 * i], int.from_bytes(CODE[off + 4 * i + 2:off + 4 * i + 4], 'little'))
            for i in range(HOST_COUNT)]


def placeholders():
    """NAME 박스 칸 i 의 placeholder 코드 8개."""
    off = SYMBOLS['nc1_placeholders']
    return tuple(int.from_bytes(CODE[off + 2 * i:off + 2 * i + 2], 'little') for i in range(PLACEHOLDER_COUNT))


def check_sources():
    """추적 소스·생성 include 의 현재 해시가 SOURCE_SHA 와 같은지(컴파일 없이). 다른 항목 목록 반환."""
    import sys
    for sub in ('tools', os.path.join('tools', 'name_compose'), os.path.join('tools', 'name_compose_p1')):
        p = os.path.join(_ROOT, sub)
        if p not in sys.path:
            sys.path.insert(0, p)
    import gen_tables_p1
    generated = gen_tables_p1.generate()
    bad = []
    for key, want in SOURCE_SHA.items():
        if key.startswith('generated/'):
            data = generated[key.split('/', 1)[1]]
        else:
            with open(os.path.join(_ROOT, key), 'rb') as f:
                data = f.read()
        if hashlib.sha256(data).hexdigest() != want:
            bad.append(key)
    return bad
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--check', action='store_true', help='재생성 blob 이 저장본과 같은지만 확인')
    ap.add_argument('--work', default=DEFAULT_WORK)
    args = ap.parse_args()
    result = build(args.work)
    text = render_blob(result).encode('utf-8')
    cs_count, cs_label = result['capstone']
    print(f'image {len(result["code"])}B sha {_sha(result["code"])} insns {result["insn_count"]} '
          f'(built-in Thumb-1 decoder, {len(result["ranges"])} $t ranges)')
    print(f'capstone: {cs_label}' + (f' insns {cs_count} == decoder' if cs_count is not None else ''))
    print('attributes: ' + ', '.join(f'{k} CPU_arch={v[TAG_CPU_ARCH]} THUMB_ISA={v[TAG_THUMB_ISA_USE]}'
                                     for k, v in result['attributes'].items()))
    for k, v in result['symbols'].items():
        print(f'  {k} +0x{v:04X} rt 0x{IMAGE_RT + v:08X}')
    if args.check:
        same = os.path.exists(BLOB_PATH) and _read(BLOB_PATH) == text
        print('OK blob byte-identical' if same else f'MISMATCH {os.path.relpath(BLOB_PATH, ROOT)}')
        raise SystemExit(0 if same else 1)
    with open(BLOB_PATH, 'wb') as f:
        f.write(text)
    print(f'wrote {os.path.relpath(BLOB_PATH, ROOT)} ({len(text)}B)')


if __name__ == '__main__':
    main()
