#!/usr/bin/env python3
"""2편 이름 조합 코드 이미지 빌드 → tools/part2_name_compose_blob.py 생성 (PLAN-v5 §1.6, T2).

절차: gen_tables(tables.h·grid.inc) → clang(core.c, Thumb-1) + arm-none-eabi-as(tramp.s)
      → arm-none-eabi-ld -T image.ld → objcopy .image → 검사 → blob 모듈.
검사: relocation 0 · 미해결 심볼 0 · 할당 섹션은 .image 하나(VMA 0x08F75800) · 크기 ≤ 8,192 ·
      raw == ELF .image · Tag_CPU_arch v4T / Tag_THUMB_ISA_use Thumb-1 · 32bit 명령은 bl 뿐 ·
      ARM 상태 코드($a) 없음 · 함수 심볼 Thumb bit 1 · 공개 심볼 오프셋 4정렬 · nc_dense 절대 0x08F70000.

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

CLANG_FLAGS = ('-target', 'armv4t-none-eabi', '-mcpu=arm7tdmi', '-mthumb', '-ffreestanding',
               '-fno-builtin', '-fno-stack-protector', '-fno-unwind-tables',
               '-fno-asynchronous-unwind-tables', '-Os', '-Wall', '-Wextra', '-Werror')
AS_FLAGS = ('-mcpu=arm7tdmi', '-mthumb', '--fatal-warnings')


def _tool(name):
    for cand in (shutil.which(name), f'/opt/homebrew/bin/{name}'):
        if cand and os.path.exists(cand):
            return cand
    return None


def toolchain():
    """{'clang': path, 'as': ..., 'ld': ..., 'objcopy': ..., 'nm': ..., 'readelf': ..., 'objdump': ...} 또는 None."""
    tools = {'clang': _tool('clang')}
    for t in ('as', 'ld', 'objcopy', 'nm', 'readelf', 'objdump'):
        tools[t] = _tool(f'arm-none-eabi-{t}')
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


def _verify_objdump(text):
    """32bit 명령은 bl 만 허용, Thumb-2/ARMv5 명령 금지. 검사한 명령 수 반환."""
    count = 0
    for line in text.splitlines():
        parts = line.split('\t')
        if len(parts) < 3 or not parts[0].strip().endswith(':'):
            continue
        hexpart, mnem = parts[1].strip(), parts[2].strip().split(' ')[0]
        if not mnem or mnem.startswith('.'):
            continue                        # 리터럴·데이터($d)
        count += 1
        if mnem.endswith('.w') or mnem in ('blx', 'cbz', 'cbnz', 'bkpt') or mnem.startswith('it'):
            raise ValueError(f'non Thumb-1 instruction: {line.strip()}')
        if ' ' in hexpart and mnem != 'bl':
            raise ValueError(f'32-bit instruction other than bl: {line.strip()}')
    if count == 0:
        raise ValueError('objdump produced no instructions')
    return count


def build(work=DEFAULT_WORK, tools=None):
    """이미지를 빌드·검사하고 결과 dict 반환. 파일은 work 폴더에만 쓴다."""
    tools = tools or toolchain()
    if tools is None:
        raise RuntimeError('toolchain unavailable (clang + arm-none-eabi binutils)')
    work = os.path.abspath(work)
    os.makedirs(work, exist_ok=True)
    generated = gen_tables.generate()
    for name, data in generated.items():
        with open(os.path.join(work, name), 'wb') as f:
            f.write(data)
    core_o, tramp_o = os.path.join(work, 'core.o'), os.path.join(work, 'tramp.o')
    elf, binf, mapf = (os.path.join(work, n) for n in ('image.elf', 'image.bin', 'image.map'))
    log = []
    cmds = [
        [tools['clang'], *CLANG_FLAGS, '-I', work, '-c', os.path.join(HERE, 'core.c'), '-o', core_o],
        [tools['as'], *AS_FLAGS, '-I', work, os.path.join(HERE, 'tramp.s'), '-o', tramp_o],
        [tools['ld'], '-T', os.path.join(HERE, 'image.ld'), '--no-undefined', '--fatal-warnings',
         f'-Map={mapf}', '-o', elf, tramp_o, core_o],
        [tools['objcopy'], '-O', 'binary', '--only-section=.image', elf, binf],
    ]
    for cmd in cmds:
        log.append((cmd, _run(cmd, work)))
    raw_elf, code = _read(elf), _read(binf)
    sections, symbols = parse_elf(raw_elf)

    relocs = _run([tools['readelf'], '-r', '-W', elf], work)
    if 'There are no relocations in this file.' not in relocs:
        raise ValueError(f'relocations present:\n{relocs}')
    undef = _run([tools['nm'], '-u', elf], work)
    if undef.strip():
        raise ValueError(f'undefined symbols:\n{undef}')
    attrs = _run([tools['readelf'], '-A', elf], work)
    for tag in ('Tag_CPU_arch: v4T', 'Tag_THUMB_ISA_use: Thumb-1'):
        if tag not in attrs:
            raise ValueError(f'missing attribute {tag}:\n{attrs}')
    objdump = _run([tools['objdump'], '-d', elf], work)
    insn_count = _verify_objdump(objdump)

    alloc = [s for s in sections if s['flags'] & 2]     # SHF_ALLOC
    if [s['name'] for s in alloc] != ['.image']:
        raise ValueError(f'alloc sections != [.image]: {[s["name"] for s in alloc]}')
    image = alloc[0]
    if image['addr'] != IMAGE_RT:
        raise ValueError(f'.image VMA 0x{image["addr"]:08X} != 0x{IMAGE_RT:08X}')
    if image['size'] > IMAGE_MAX:
        raise ValueError(f'.image size {image["size"]} > {IMAGE_MAX}')
    if raw_elf[image['offset']:image['offset'] + image['size']] != code:
        raise ValueError('objcopy raw != ELF .image bytes')
    if any(n == '$a' or n.startswith('$a.') for n in symbols):
        raise ValueError('ARM-state mapping symbol present')
    dense = symbols.get('nc_dense', [])
    if len(dense) != 1 or dense[0]['value'] != DENSE_RT or dense[0]['shndx'] != 0xFFF1:
        raise ValueError(f'nc_dense must be ABS 0x{DENSE_RT:08X}: {dense}')

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
        off = value - IMAGE_RT
        if not 0 <= off < len(code) or off % 4:
            raise ValueError(f'{name} offset {off} out of range or not 4-aligned')
        syms[name] = off
    return {'code': code, 'symbols': syms, 'source_sha': source_sha(generated),
            'toolchain': toolchain_versions(tools), 'insn_count': insn_count, 'log': log,
            'elf': elf, 'bin': binf}


def toolchain_versions(tools):
    out = {}
    for key in ('clang', 'as', 'ld', 'objcopy'):
        text = _run([tools[key], '--version'], ROOT)
        out[key] = text.strip().splitlines()[0]
    return out


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
    print(f'image {len(result["code"])}B sha {_sha(result["code"])} insns {result["insn_count"]}')
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
