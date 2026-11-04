#!/usr/bin/env python3
"""1편 이름 조합 코드 이미지 빌드 → tools/part1_name_compose_blob.py 생성 (PLAN B T3, D8·D9).

절차: gen_tables_p1(tables.h·grid_p1.inc·p1_config.h) → clang(core.c·p1.c, Thumb-1)
      + clang 통합 어셈블러(tramp_p1.s) → ld.lld -T image_p1.ld (ELF) + ld.lld --oformat binary(raw)
      → 검사 → blob 모듈.
툴체인: 이 PC 는 GNU arm-none-eabi binutils·llvm-objcopy/objdump/readelf 가 없어(plan_B_approval: sudo 설치 금지)
      clang + ld.lld 만 쓴다. Part 2 의 readelf/nm/objdump 검사는 아래 Python 검사로 대체했다.
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
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(TOOLS, 'name_compose'))
sys.path.insert(0, TOOLS)

import gen_tables_p1 as g1  # noqa: E402
from build_image import parse_elf, _run, _sha, _read  # noqa: E402  (Part 2 — import 만)

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

SHT_RELA, SHT_REL, SHN_UNDEF, SHN_ABS = 4, 9, 0, 0xFFF1
TAG_CPU_ARCH, TAG_THUMB_ISA_USE = 6, 9
CPU_ARCH_V4T, THUMB_ISA_THUMB1 = 2, 1
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


# ---- .ARM.attributes (aeabi, File 범위) ----
def _uleb(data, i):
    val = shift = 0
    while True:
        b = data[i]
        i += 1
        val |= (b & 0x7F) << shift
        shift += 7
        if not b & 0x80:
            return val, i


def parse_arm_attributes(data):
    """aeabi File 범위 {tag: 값}. 문자열 태그(4·5·67, 32 초과 홀수)는 str."""
    if not data or data[0] != 0x41:
        raise ValueError('.ARM.attributes: bad format version')
    out, i = {}, 1
    while i < len(data):
        sec_len = struct.unpack_from('<I', data, i)[0]
        end = i + sec_len
        vendor_end = data.index(b'\0', i + 4)
        vendor = data[i + 4:vendor_end].decode()
        j = vendor_end + 1
        while vendor == 'aeabi' and j < end:
            tag, k = _uleb(data, j)
            size = struct.unpack_from('<I', data, k)[0]
            sub_end = j + size
            k += 4
            while tag == 1 and k < sub_end:            # Tag_File
                at, k = _uleb(data, k)
                if at in (4, 5, 67) or (at > 32 and at % 2 == 1):
                    z = data.index(b'\0', k)
                    out[at] = data[k:z].decode()
                    k = z + 1
                elif at == 32:                          # Tag_compatibility: uleb + NTBS
                    out[at], k = _uleb(data, k)
                    k = data.index(b'\0', k) + 1
                else:
                    out[at], k = _uleb(data, k)
            j = sub_end
        i = end
    return out


def check_attributes(raw, label):
    sections, _ = parse_elf(raw)
    att = [s for s in sections if s['name'] == '.ARM.attributes']
    if len(att) != 1:
        raise ValueError(f'{label}: .ARM.attributes missing')
    a = parse_arm_attributes(raw[att[0]['offset']:att[0]['offset'] + att[0]['size']])
    if a.get(TAG_CPU_ARCH) != CPU_ARCH_V4T or a.get(TAG_THUMB_ISA_USE) != THUMB_ISA_THUMB1:
        raise ValueError(f'{label}: attributes not v4T/Thumb-1: {a}')
    return a


# ---- Thumb-1 명령 검사 ----
def code_ranges(symbols, base, size):
    """매핑 심볼 $t/$d 로 나눈 [(start_off, end_off)] Thumb 코드 구간. $a 가 있으면 ValueError."""
    marks = []
    for name, ents in symbols.items():
        kind = name.split('.', 1)[0]
        if kind == '$a':
            raise ValueError('ARM-state mapping symbol present')
        if kind in ('$t', '$d'):
            for e in ents:
                if e['shndx'] not in (SHN_UNDEF, SHN_ABS) and base <= e['value'] < base + size:
                    marks.append((e['value'] - base, kind))
    marks.sort()
    if not marks or marks[0] != (0, '$t'):
        raise ValueError(f'image must start with $t mapping symbol: {marks[:2]}')
    out = []
    for n, (off, kind) in enumerate(marks):
        end = marks[n + 1][0] if n + 1 < len(marks) else size
        if kind == '$t' and end > off:
            out.append((off, end))
    return out


def _thumb1_halfword_ok(h):
    """16bit Thumb 명령 h 가 ARMv4T Thumb-1 로 유효하면 None, 아니면 이유."""
    if (h >> 12) == 0xB:                                    # misc: add/sub sp, push, pop 만 v4T
        if (h >> 8) not in (0xB0, 0xB4, 0xB5, 0xBC, 0xBD):
            return 'misc encoding not in ARMv4T (cbz/it/bkpt/sxt/rev/cps…)'
    if (h & 0xFF80) == 0x4780:
        return 'blx register (ARMv5T)'
    if (h >> 10) == 0x11 and (h >> 8) != 0x47 and (h & 0xC0) == 0:
        return 'hi-register add/cmp/mov with two low registers (ARMv6)'
    if (h >> 8) in (0xDE, 0xDF):
        return 'udf/swi'
    return None


def verify_thumb1(code, ranges):
    """자체 디코더: $t 구간을 halfword 로 훑는다. 32bit 는 bl(F000+F800) 쌍만. 검사 명령 수 반환."""
    count = 0
    for start, end in ranges:
        if start % 2 or end % 2:
            raise ValueError(f'odd Thumb range {start:#x}..{end:#x}')
        i = start
        while i < end:
            h = struct.unpack_from('<H', code, i)[0]
            top = h >> 11
            if top == 0x1E:
                if i + 4 > end:
                    raise ValueError(f'+0x{i:04X}: bl prefix at range end')
                h2 = struct.unpack_from('<H', code, i + 2)[0]
                if (h2 >> 11) != 0x1F:
                    raise ValueError(f'+0x{i:04X}: 32-bit instruction other than bl ({h:04x} {h2:04x})')
                i += 4
            elif top in (0x1D, 0x1F):
                raise ValueError(f'+0x{i:04X}: Thumb-2 / orphan 32-bit halfword {h:04x}')
            else:
                why = _thumb1_halfword_ok(h)
                if why:
                    raise ValueError(f'+0x{i:04X}: {h:04x} {why}')
                i += 2
            count += 1
    if count == 0:
        raise ValueError('no Thumb instructions found')
    return count


CAPSTONE_DENY = ('blx', 'cbz', 'cbnz', 'bkpt', 'sxth', 'sxtb', 'uxth', 'uxtb', 'rev', 'rev16', 'revsh',
                 'cpsie', 'cpsid', 'setend', 'nop', 'yield', 'wfe', 'wfi', 'sev', 'udf', 'svc')


def _import_capstone():
    try:
        import capstone
        return capstone, 'capstone (site)'
    except ImportError:
        pass
    alt = os.path.join(ROOT, 'temp', 'b37_deps')
    if os.path.isdir(os.path.join(alt, 'capstone')):
        sys.path.insert(0, alt)
        try:
            import capstone
            return capstone, f'capstone (temp/b37_deps {capstone.__version__})'
        except ImportError:
            pass
        finally:
            sys.path.remove(alt)
    return None, None


def verify_capstone(code, ranges):
    """capstone 이 있으면 같은 구간을 전수 디코드(틈 없이)해 교차 검사. (명령 수, 설명) 또는 (None, 사유)."""
    cs_mod, label = _import_capstone()
    if cs_mod is None:
        return None, 'capstone unavailable — Thumb-1 check by built-in decoder only'
    md = cs_mod.Cs(cs_mod.CS_ARCH_ARM, cs_mod.CS_MODE_THUMB)
    count = 0
    for start, end in ranges:
        pos = start
        for ins in md.disasm(code[start:end], IMAGE_RT + start):
            if ins.address - IMAGE_RT != pos:
                raise ValueError(f'capstone gap at +0x{pos:04X}')
            mn = ins.mnemonic.split('.')[0]
            if ins.size == 4 and mn != 'bl':
                raise ValueError(f'capstone: 32-bit {ins.mnemonic} {ins.op_str} at +0x{pos:04X}')
            if mn in CAPSTONE_DENY or mn.startswith('it') or ins.mnemonic.endswith('.w'):
                raise ValueError(f'capstone: non Thumb-1 {ins.mnemonic} {ins.op_str} at +0x{pos:04X}')
            pos += ins.size
            count += 1
        if pos != end:
            raise ValueError(f'capstone stopped at +0x{pos:04X} (range end +0x{end:04X})')
    return count, label


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
    cs_count, cs_label = verify_capstone(code, ranges)
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
