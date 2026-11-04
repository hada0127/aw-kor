#!/usr/bin/env python3
"""2편 이름 조합 코드 이미지 빌드 → tools/part2_name_compose_blob.py 생성 (PLAN-v5 §1.6, T2).

절차: gen_tables(tables.h·grid.inc) → clang(core.c, Thumb-1) + clang 통합 어셈블러(tramp.s)
      → ld.lld -T image.ld (ELF) + ld.lld --oformat binary(raw) → 검사 → blob 모듈.
툴체인(2026-11-04 fixB, plan_C F): Apple clang + GNU arm-none-eabi binutils 핀에서 이 PC 의 clang 23 + ld.lld 로
      옮겼다(1편 build_image_p1.py 와 같은 방식, sudo 설치 금지). readelf/nm/objdump 검사는 아래 Python 검사로 대체.
검사: 재배치 섹션(SHT_REL/RELA) 0 · 미해결 심볼(SHN_UNDEF) 0 · 할당 섹션은 .image 하나(VMA 0x08F75800) ·
      크기 ≤ 8,192 · raw(--oformat binary) == ELF .image · .ARM.attributes(출력·모든 입력 .o)
      Tag_CPU_arch v4T / Tag_THUMB_ISA_use Thumb-1 · $t 구간 Thumb-1 명령 검사(자체 halfword 디코더 —
      32bit 는 bl 쌍만; capstone 을 import 할 수 있으면 같은 구간을 capstone 으로도 전수 디코드해 교차 검사) ·
      ARM 상태($a) 없음 · 함수 심볼 Thumb bit 1 · 공개 심볼 오프셋 4정렬 · nc_dense 절대 0x08F70000.
이 검사 함수들은 1편 build_image_p1.py 도 import 해 쓴다.

일반 ROM 빌드는 생성된 blob 모듈만 import 한다(툴체인 불필요).
사용:
  python3 tools/name_compose/build_image.py            # blob 모듈 다시 쓰기
  python3 tools/name_compose/build_image.py --check    # 재생성 결과가 저장본과 같은지만(쓰지 않음)
  --work DIR  중간 산출물 폴더(기본 temp/name_compose_build, 추적 안 함)
"""
import argparse
import hashlib
import os
import shutil
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, HERE)
sys.path.insert(0, TOOLS)

import gen_tables  # noqa: E402

IMAGE_RT = 0x08F75800
IMAGE_MAX = 0x2000
DENSE_RT = 0x08F70000
BLOB_PATH = os.path.join(TOOLS, 'part2_name_compose_blob.py')
DEFAULT_WORK = os.path.join(ROOT, 'temp', 'name_compose_build')

FUNC_SYMBOLS = ('nc_press', 'nc_confirm', 'nc_backspace', 'nc_tramp_press', 'nc_tramp_confirm',
                'nc_tramp_backspace', 'nc_tramp_display', 'nc_alloc')
DATA_SYMBOLS = ('nc_sel_priv', 'nc_row_priv')
# SOURCE_SHA: CODE 를 결정하는 모든 입력(추적 파일) + 생성 include(작업 폴더 생성물)
SOURCE_FILES = ('tools/name_compose/core.c', 'tools/name_compose/tramp.s',
                'tools/name_compose/image.ld', 'tools/name_compose/gen_tables.py',
                'tools/name_compose/build_image.py', 'tools/hangul_compose.py',
                'data/jamo_to_code_40.json')
GENERATED_FILES = ('tables.h', 'grid.inc')

TARGET_FLAGS = ('-target', 'armv4t-none-eabi', '-mcpu=arm7tdmi', '-mthumb')
CLANG_FLAGS = TARGET_FLAGS + ('-ffreestanding', '-fno-builtin', '-fno-stack-protector', '-fno-unwind-tables',
                              '-fno-asynchronous-unwind-tables', '-Os', '-Wall', '-Wextra', '-Werror')
AS_FLAGS = TARGET_FLAGS + ('-Wa,--fatal-warnings',)
LD_FLAGS = ('--no-undefined', '--fatal-warnings')

SHT_RELA, SHT_REL, SHN_UNDEF, SHN_ABS = 4, 9, 0, 0xFFF1
TAG_CPU_ARCH, TAG_THUMB_ISA_USE = 6, 9
CPU_ARCH_V4T, THUMB_ISA_THUMB1 = 2, 1


def toolchain():
    """{'clang': path, 'ld.lld': path} 또는 None."""
    tools = {'clang': shutil.which('clang'), 'ld.lld': shutil.which('ld.lld')}
    return tools if all(tools.values()) else None


def _run(cmd, cwd):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f'{" ".join(cmd)}\nexit {p.returncode}\n{p.stdout}{p.stderr}')
    return p.stdout + p.stderr


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _read(path):
    with open(path, 'rb') as f:
        return f.read()


def source_sha(generated=None):
    """SOURCE_SHA dict. generated = gen_tables.generate() 결과(없으면 지금 생성)."""
    if generated is None:
        generated = gen_tables.generate()
    out = {rel: _sha(_read(os.path.join(ROOT, rel))) for rel in SOURCE_FILES}
    for name in GENERATED_FILES:
        out[f'generated/{name}'] = _sha(generated[name])
    return out


# ---- ELF32 little-endian 최소 파서 ----
def parse_elf(raw):
    if raw[:6] != b'\x7fELF\x01\x01':
        raise ValueError('not ELF32 LE')
    shoff = struct.unpack_from('<I', raw, 32)[0]
    shentsize, shnum, shstrndx = struct.unpack_from('<HHH', raw, 46)
    hdrs = [struct.unpack_from('<10I', raw, shoff + i * shentsize) for i in range(shnum)]
    names = hdrs[shstrndx]
    strtab_names = raw[names[4]:names[4] + names[5]]

    def nm(off, tab):
        return tab[off:].split(b'\0', 1)[0].decode()

    sections = []
    for h in hdrs:
        sections.append({'name': nm(h[0], strtab_names), 'type': h[1], 'flags': h[2],
                         'addr': h[3], 'offset': h[4], 'size': h[5], 'link': h[6],
                         'entsize': h[9]})
    symbols = {}
    for s in sections:
        if s['type'] != 2:          # SHT_SYMTAB
            continue
        strsec = sections[s['link']]
        tab = raw[strsec['offset']:strsec['offset'] + strsec['size']]
        for i in range(s['size'] // 16):
            name_off, value, size, info, other, shndx = struct.unpack_from(
                '<IIIBBH', raw, s['offset'] + i * 16)
            name = nm(name_off, tab)
            if name:
                symbols.setdefault(name, []).append(
                    {'value': value, 'size': size, 'type': info & 15, 'bind': info >> 4,
                     'shndx': shndx})
    return sections, symbols


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


def verify_capstone(code, ranges, base):
    """capstone 이 있으면 같은 구간을 전수 디코드(틈 없이)해 교차 검사. (명령 수, 설명) 또는 (None, 사유)."""
    cs_mod, label = _import_capstone()
    if cs_mod is None:
        return None, 'capstone unavailable — Thumb-1 check by built-in decoder only'
    md = cs_mod.Cs(cs_mod.CS_ARCH_ARM, cs_mod.CS_MODE_THUMB)
    count = 0
    for start, end in ranges:
        pos = start
        for ins in md.disasm(code[start:end], base + start):
            if ins.address - base != pos:
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


def build(work=DEFAULT_WORK, tools=None):
    """이미지를 빌드·검사하고 결과 dict 반환. 파일은 work 폴더에만 쓴다."""
    tools = tools or toolchain()
    if tools is None:
        raise RuntimeError('toolchain unavailable (clang + ld.lld)')
    work = os.path.abspath(work)
    os.makedirs(work, exist_ok=True)
    generated = gen_tables.generate()
    for name, data in generated.items():
        with open(os.path.join(work, name), 'wb') as f:
            f.write(data)
    objs = {n: os.path.join(work, f'{n}.o') for n in ('tramp', 'core')}
    elf, binf, mapf = (os.path.join(work, n) for n in ('image.elf', 'image.bin', 'image.map'))
    ld_script = os.path.join(HERE, 'image.ld')
    inputs = [objs['tramp'], objs['core']]
    log = []
    cmds = [
        [tools['clang'], *CLANG_FLAGS, '-I', work, '-c', os.path.join(HERE, 'core.c'), '-o', objs['core']],
        [tools['clang'], *AS_FLAGS, '-I', work, '-c', os.path.join(HERE, 'tramp.s'), '-o', objs['tramp']],
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
        _o_sections, o_symbols = parse_elf(_read(path))
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
    return {'code': code, 'symbols': syms, 'source_sha': source_sha(generated),
            'toolchain': toolchain_versions(tools), 'insn_count': insn_count,
            'capstone': (cs_count, cs_label), 'ranges': ranges, 'attributes': attrs, 'log': log,
            'elf': elf, 'bin': binf}


def toolchain_versions(tools):
    return {key: _run([tools[key], '--version'], ROOT).strip().splitlines()[0] for key in ('clang', 'ld.lld')}


def render_blob(result):
    code = result['code']
    hexs = code.hex()
    lines = [hexs[i:i + 96] for i in range(0, len(hexs), 96)]
    body = '\n'.join(f"    '{ln}'" for ln in lines)
    sym = ''.join(f"    '{k}': 0x{v:04X},\n" for k, v in result['symbols'].items())
    src = ''.join(f"    '{k}': '{v}',\n" for k, v in result['source_sha'].items())
    tc = ''.join(f"    '{k}': {v!r},\n" for k, v in result['toolchain'].items())
    rows = gen_tables.row_lengths()
    return f'''"""생성 파일 — python3 tools/name_compose/build_image.py 로만 다시 만든다. 손으로 고치지 않는다.

2편 이름 입력 두벌식 조합 코드 이미지(PLAN-v5 §1.6, T2). ROM 파일 0x{IMAGE_RT - 0x08000000:06X}
(버스 IMAGE_RT)에 CODE 를 그대로 둔다. nc_dense 표는 이미지 밖 DENSE_RT(파일 0x{DENSE_RT - 0x08000000:06X})에
gen_jamo_assets.dense_table() 22,344B 를 둔다. SYMBOLS 는 CODE 안 바이트 오프셋(Thumb bit 없음)이고,
함수 진입 리터럴은 entry(name) = IMAGE_RT + SYMBOLS[name] | 1 이다.
툴체인 없이 쓰는 검증: verify_code(), check_sources(), entry(), sel_priv(), row_priv().
"""
import hashlib
import os

IMAGE_RT = 0x{IMAGE_RT:08X}
IMAGE_MAX = 0x{IMAGE_MAX:04X}
DENSE_RT = 0x{DENSE_RT:08X}
DENSE_BYTES = 22344
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
    """사설 표시행 6개(bytes 목록, native 형식)."""
    off, rows = SYMBOLS['nc_row_priv'], []
    for n in ROW_LENGTHS:
        rows.append(CODE[off:off + n])
        off += n
    return rows


def check_sources():
    """추적 소스·생성 include 의 현재 해시가 SOURCE_SHA 와 같은지(컴파일 없이). 다른 항목 목록 반환."""
    import sys
    sys.path.insert(0, os.path.join(_ROOT, 'tools', 'name_compose'))
    sys.path.insert(0, os.path.join(_ROOT, 'tools'))
    import gen_tables
    generated = gen_tables.generate()
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
        print('OK blob byte-identical' if same else 'MISMATCH tools/part2_name_compose_blob.py')
        raise SystemExit(0 if same else 1)
    with open(BLOB_PATH, 'wb') as f:
        f.write(text)
    print(f'wrote {os.path.relpath(BLOB_PATH, ROOT)} ({len(text)}B)')


if __name__ == '__main__':
    main()
