#!/usr/bin/env python3
"""대사 메시지 재배치(repoint) 엔진 — 쪼롱이님 문구 불변, 단어붙음/축약 해소.

배경(2026-06-23 RE):
- Part2 캠페인 대사는 **메시지 포인터 테이블**(0x08A357B4, 3315엔트리, 단조 증가)로 참조된다.
  메시지 중간으로 들어오는 포인터는 없다(순차 읽기). 각 메시지는 라인(0x0A/제어로 구분) +
  종단 제어(예 6B 00..)로 구성.
- 빌드는 한글을 **원본 슬롯에 in-place**로 쓴다. 슬롯이 빠듯하면 encode_fit이 공백/부호를 제거
  (단어붙음 level>=10). 504행(거의 전부 쪼롱이님 대사)이 이렇게 열화된다.
- 바로 뒤 0x00A3CF14~0x00B00000(799KB)이 미사용(0xFF) 여유공간.

해결(외부 서양판과 동일 기법): 열화가 생기는 메시지를 **스켈레톤(제어코드) 보존 재구성**해
여유공간에 전체로 기록하고, 테이블 포인터만 갱신한다. 라인 텍스트는 쪼롱이님 원문을
**완전 충실(level0)** 인코딩 → 단어붙음/축약 없음. 제어 바이트는 한 바이트도 안 바뀐다.

안전장치:
- 각 메시지는 ROM 내 포인터가 정확히 1개(테이블 엔트리)일 때만 재배치(중간참조/다중참조 skip+보고).
- 메시지가 (라인 span + 제어 gap)으로 **정확 분해**될 때만 재배치(분해 불일치 skip+보고).
- 재구성된 메시지의 제어 바이트(라인 외 전부) == 원본 == 보존 검증.
- 여유공간 범위 초과/현재 비어있지 않으면 중단.
"""
import struct, json, os, collections

GBA = 0x08000000


def _read_table(orig, tbl_off):
    """단조 증가하며 한 스크립트 영역(상위 바이트 동일대)을 가리키는 포인터 테이블 범위."""
    def ptr(o):
        return struct.unpack_from('<I', orig, o)[0]
    first = ptr(tbl_off)
    if not (GBA <= first < GBA + len(orig)):
        return []
    region_hi = (first - GBA) >> 16
    entries = []
    o = tbl_off
    while o + 4 <= len(orig):
        v = ptr(o)
        if not (GBA <= v < GBA + len(orig)):
            break
        tgt = v - GBA
        # 같은 스크립트 영역(±2개 상위블록 허용: 0xA0~0xA3 등)
        if not (region_hi - 0 <= (tgt >> 16) <= region_hi + 4):
            break
        entries.append((o, tgt))
        o += 4
    return entries


def scan_command_messages(orig, lo=0x08B80000, hi=0x08E10000, opcode=0x19, scan_lo=0xD80000, scan_hi=0xE00000):
    """Part1 커맨드 스트림의 show-message 명령(opcode 0x19) 뒤에 오는 메시지 포인터를 수집.
    (2026-06-23 런타임 트레이싱으로 확증: 캐서린 대사 0xDF5D60 등이 0x19 뒤 포인터로 로드됨.)
    반환: {msg_addr: [ptr_offset...]}. 각 ptr_offset은 ROM 내 4바이트 포인터 워드 위치.
    """
    out = {}
    o = scan_lo
    n = min(len(orig), scan_hi)
    while o + 8 <= n:
        if struct.unpack_from('<I', orig, o)[0] == opcode:
            v = struct.unpack_from('<I', orig, o + 4)[0]
            if lo <= v < hi:
                out.setdefault(v - GBA, []).append(o + 4)
        o += 4
    return out


def _line_index(found_csv):
    import csv
    idx = {}
    with open(found_csv, encoding='utf-8', errors='ignore') as f:
        for r in csv.DictReader(f):
            try:
                a = int((r.get('address') or '').strip(), 16)
                L = int(r.get('length') or 0)
            except (ValueError, TypeError):
                continue
            if L > 0:
                idx[a] = (L, (r.get('text') or '').strip())
    return idx


def repoint_messages(rom, orig, *, fixable, fixed_bytes, fit_level_dlg, decode_text,
                     cell_width, slots, line_index, table_offsets, free_start, free_end,
                     extra_messages=None, min_level=6, max_cells=50, max_header_gap=16,
                     align=4, log=None):
    """rom(bytearray)에 재배치 적용. 반환: (manifest list, stats dict).

    **안전 설계(쪼롱이님 per-line 대사만 복원)**:
    - 고칠 라인 = `fixable(a)`(=dialogue_overrides에 있는 쪼롱이님 라인) AND
      `fit_level_dlg(a) >= min_level`(in-place에서 축약/단어붙음됨).
    - 그 외 모든 라인(미열화 / CSV 병합 라인 등)은 **현재 빌드 바이트(rom)를 그대로 보존**
      → 중복/오정렬/회귀 없음.
    - 메시지는 (라인 span + 제어 gap)으로 원본과 정확 분해될 때만, 그리고 고칠 라인이
      ≥1개일 때만 재배치한다. 포인터는 ROM 내 정확히 1개(테이블)일 때만.
    """
    stats = collections.Counter()
    manifest = []
    free = free_start

    # 현재 여유공간이 정말 비어있는지(0xFF) 확인
    if any(b != 0xFF for b in rom[free_start:free_end]):
        raise AssertionError('repoint free-space not empty (0xFF expected)')

    # 모든 테이블의 (ptr_off -> msg_addr) 수집 + 메시지 span
    all_targets = set()
    table_entries = []  # (ptr_off, msg_addr, table_off)
    for tbl in table_offsets:
        ents = _read_table(orig, tbl)
        for off, tgt in ents:
            table_entries.append((off, tgt, tbl))
            all_targets.add(tgt)
        stats[f'table_0x{tbl:06X}_entries'] = len(ents)
    # Part1: 0x19(show-message) 커맨드로 참조되는 메시지(2026-06-23 런타임 트레이싱으로 확증).
    # extra_messages = {msg_addr: [ptr_offset...]}. 테이블이 아니라 흩어진 포인터지만 같은 로직으로 처리.
    # 전체 메시지를 sorted_t에 넣어야 span(=다음 메시지 시작)이 정확하다.
    extra_messages = extra_messages or {}
    for msg, offs in extra_messages.items():
        for off in offs:
            table_entries.append((off, msg, None))
        all_targets.add(msg)
    if extra_messages:
        stats['extra_messages'] = len(extra_messages)
    sorted_t = sorted(all_targets)

    def span_of(msg):
        # 메시지 끝 = 다음 메시지 시작. 마지막 메시지는 ROM 끝 또는 자신 뒤의 포인터 테이블 시작
        # (스크립트 영역은 그 포인터 테이블 앞에서 끝남) 중 가까운 쪽. 테이블 오프셋에만 의존하면
        # 향후 영역 확장 시 nxt<=msg가 되어 분해검증이 무조건 깨지는 취약점이 있어 견고화(codex/agy 리뷰).
        i = sorted_t.index(msg)
        if i + 1 < len(sorted_t):
            nxt = sorted_t[i + 1]
        else:
            nxt = len(orig)
            for t in table_offsets:
                if msg < t < nxt:
                    nxt = t
        # 2026-06-25 terminator 세분화(A5c): 0x19 메시지는 sparse라 'next 메시지 시작'까지의 span이
        # 다음 0x19 미참조 메시지들까지 grab → 거대블록·거짓 merged 유발. SJIS 본문엔 0x00 없으므로
        # 첫 0x00이 실제 메시지 종단. min(next, terminator+1)로 실제 메시지에 한정(merged 오탐 제거).
        term = msg
        while term < nxt and orig[term] != 0x00:
            term += 1
        if term < nxt:
            # 0x00 런 끝까지 포함(연속 패딩 0x00). 다음 라인은 0x00 뒤부터.
            e = term
            while e < nxt and orig[e] == 0x00:
                e += 1
            nxt = e
        return nxt

    # msg_addr -> 그 메시지의 라인 [(addr,len)] (정렬)
    msg_lines = collections.defaultdict(list)
    import bisect
    for a, (L, _t) in line_index.items():
        i = bisect.bisect_right(sorted_t, a) - 1
        if i < 0:
            continue
        ms = sorted_t[i]
        if ms <= a < span_of(ms):
            msg_lines[ms].append((a, L))
    for ms in msg_lines:
        msg_lines[ms].sort()

    # 포인터 인덱스: msg_addr -> ROM 내 4바이트 정렬 포인터 위치 목록.
    # Part1 extra_messages는 0x19 스캔으로 위치를 이미 알므로 그걸 쓴다(우연매치 회피 + 빠름).
    def ptr_sites(msg_addr):
        needle = struct.pack('<I', GBA + msg_addr)
        sites = []
        pos = 0
        while True:
            i = orig.find(needle, pos)
            if i < 0:
                break
            if i % 4 == 0:
                sites.append(i)
            pos = i + 1
        if msg_addr in extra_messages:
            # ROM 전체에서 찾은 실제 포인터들이 0x19 스캔된 오프셋의 부분집합인지 확인.
            # 만약 다른 곳에서도 이 주소를 참조한다면 다중 참조가 있는 것이므로
            # sites 전체를 반환하여 len(sites) != 1 가드에 걸려 안전하게 skip되도록 함.
            expected = set(extra_messages[msg_addr])
            found = set(sites)
            if not found.issubset(expected):
                return sites
        return sites

    table_off_set = set()
    for tbl in table_offsets:
        for off, _tgt in _read_table(orig, tbl):
            table_off_set.add(off)
    for offs in extra_messages.values():
        table_off_set.update(offs)

    # 고아 포인터 방지(agy 리뷰 2026-06-25): 대사/스크립트 영역(0xA00000~0xE10000) 정렬 포인터가 가리키는
    # **텍스트 엔트리 타깃 주소** 집합. 전역 워드 스캔은 그래픽/압축데이터 안의 pointer-shaped 값을
    # 많이 잡으므로, 라인 시작 또는 알려진 메시지 시작이 아닌 본문 중간 바이트는 고아 위험으로 보지 않는다.
    # 실제 중간 라인 주소를 참조하는 포인터가 따로 있으면 재배치 시 시작 포인터만 갱신되고 중간 포인터는
    # 구주소에 남아(고아) 불일치 → 그런 메시지는 skip.
    import array as _arr
    _w = _arr.array('I')
    _w.frombytes(orig[:(len(orig) // 4) * 4])
    entry_targets = set(line_index) | set(all_targets)
    referenced_targets = set()
    for _i, _v in enumerate(_w):
        if 0x08A00000 <= _v < 0x08E10000:
            _tgt = _v - GBA
            if _tgt not in entry_targets:
                continue
            _o = _i * 4
            if 0xA00000 <= _o < 0xE10000:
                referenced_targets.add(_tgt)
    _sorted_ref = sorted(referenced_targets)

    # 재배치 대상: 라인 중 하나라도 완전충실 인코딩이 슬롯 초과(=in-place 열화) + 한글 포함
    _relocated_msgs = set()   # 다중포인터 메시지 중복 재배치 방지(1회 재배치 + 전 site 갱신)
    for ptr_off, msg, _tbl in sorted(table_entries, key=lambda e: (e[0], e[1], -1 if e[2] is None else e[2])):
        if msg in _relocated_msgs:
            continue
        lines = msg_lines.get(msg, [])
        if not lines:
            continue
        # 고아 포인터 가드(agy 2026-06-25): 메시지 **span 내 임의 중간주소**(시작 외)를 참조하는 포인터가
        # 따로 있으면 재배치 시 그 포인터가 구주소에 남아 불일치(고아) → skip. bisect로 (msg, me) 범위 검사.
        # (시작 주소 참조 ptr_off는 new_addr로 갱신됨. 라인 시작뿐 아니라 라인 내부 주소도 포함해 보수적.)
        _me_chk = span_of(msg)
        _ri = bisect.bisect_right(_sorted_ref, msg)
        if _ri < len(_sorted_ref) and _sorted_ref[_ri] < _me_chk:
            stats['skip_mid_ref'] = stats.get('skip_mid_ref', 0) + 1
            manifest.append({'msg': f'0x{msg:06X}', 'status': 'skip_mid_ref'})
            continue
        # 구조 가드(2026-06-23 Part1 RE 교훈): 진짜 대사 메시지는 첫 라인이 메시지 시작 근처(헤더갭 작음,
        # Part2 실측 최대 12)에서 시작한다. struct/이벤트 테이블은 텍스트 라인 앞에 큰 비-텍스트 헤더
        # (실측 178~195B)가 있어 decompose는 통과해도 대사가 아니다. 헤더갭이 크면 비-대사로 보고 skip
        # → 잘못된 테이블을 넘겨도 struct 재배치(게임 손상)를 차단한다.
        if lines[0][0] - msg > max_header_gap:
            stats['skip_struct_header'] += 1
            continue
        # 고칠 라인(쪼롱이님 per-line 대사 + in-place 열화) 존재?
        # 폭 가드: 단어붙음은 공백을 지워 폭을 줄였을 수 있다. un-jam(공백 복원) 후 시각 폭이
        # 박스 한계(max_cells, 원본 대사 최대폭 50 관측)를 넘으면 잘림 위험 → 그 라인은 수정 제외
        # (in-place 단어붙음 유지가 폭 안전). repoint가 새 잘림을 만들지 않게 한다.
        fix_addrs = set()
        skipped_wide = 0
        for a, L in lines:
            if fixable(a) and fit_level_dlg(a) >= min_level:
                if cell_width(a) > max_cells:
                    skipped_wide += 1
                    continue
                fix_addrs.add(a)
        if skipped_wide:
            stats['skip_wide_line'] += skipped_wide
        if not fix_addrs:
            # 2026-06-25 render-jam 허용: fixable 라인이 없어도 **content 사이 반각공백(0x20)**이 있으면
            # 재배치 블롭의 interior 변환(0x20→0x8140)이 화면 단어붙음을 해소하므로 재배치한다.
            # (클린소스 없는 잼=무포인터 외 단일포인터분 커버). 2바이트 코드 lead는 건너뛰어 오탐 방지.
            _has_jam = False
            for a, L in lines:
                seg = rom[a:a + L]
                i = 0
                while i < len(seg) - 1:
                    b = seg[i]
                    if 0x81 <= b <= 0xE2:
                        i += 2
                        continue
                    if b == 0x20 and (0x81 <= seg[i + 1] <= 0xE2 or 0x21 <= seg[i + 1] <= 0x7E):
                        _has_jam = True
                        break
                    i += 1
                if _has_jam:
                    break
            if not _has_jam:
                continue
            stats['relocate_renderjam'] = stats.get('relocate_renderjam', 0) + 1

        # 안전 가드: **실제 렌더 텍스트** 기준 라인 간 중첩 검사.
        # 각 라인의 effective 텍스트 = fixed면 override(새 텍스트), 아니면 현재 rom 바이트 디코드.
        # 한 라인의 텍스트가 다른 라인 텍스트의 부분문자열(공백제거 길이>=4)이면, 미션 목표처럼
        # 멀티라인 병합 저장된 케이스 → 재배치 시 중복 노출 위험 → 메시지 전체 skip(회귀 0).
        def nosp(s):
            return ''.join(c for c in (s or '') if c not in ' 　')
        eff = []
        for a, L in lines:
            if a in fix_addrs:
                eff.append(nosp(decode_text(fixed_bytes(a))))
            else:
                eff.append(nosp(decode_text(bytes(rom[a:a + L]))))
        merged = False
        for ii in range(len(eff)):
            for jj in range(len(eff)):
                if ii != jj and len(eff[jj]) >= 4 and eff[jj] in eff[ii]:
                    merged = True
                    break
            if merged:
                break
        if merged:
            stats['skip_merged_fragment'] += 1
            manifest.append({'msg': f'0x{msg:06X}', 'status': 'skip_merged'})
            continue

        me = span_of(msg)
        # 과확장 span 가드(2026-06-23 Part1): 메시지의 참조 포인터가 자기 span 안에 있으면
        # span이 메시지 종단을 넘어 (다음 0x19 시작까지) 커맨드-스트림/타 메시지를 포함한 것.
        # 재배치 시 그 포인터를 갱신하면 구위치가 바뀌고(렌더는 종단서 멈춰 무해하나) 여유공간 낭비·
        # 검증 복잡. 정상 메시지는 참조 포인터가 텍스트 앞(span 밖)이다 → 안쪽이면 skip(보수적).
        if any(msg <= off < me for off in ptr_sites(msg)):
            stats['skip_overextended'] += 1
            manifest.append({'msg': f'0x{msg:06X}', 'status': 'skip_overextended'})
            continue
        # 안전: 포인터가 1개 이상 & **전부** 테이블 안(2026-06-25 다중포인터 지원: 모든 site가 인식된
        # 포인터테이블 엔트리면 1회 재배치 후 전 site를 새 주소로 갱신 → 고아 없음. 우연/미인식 포인터가
        # 섞이면 보수적 skip).
        sites = ptr_sites(msg)
        if len(sites) < 1 or not all(s in table_off_set for s in sites):
            stats['skip_ptr_ambiguous'] += 1
            manifest.append({'msg': f'0x{msg:06X}', 'status': 'skip_ptr', 'sites': [hex(s) for s in sites]})
            continue

        # 스켈레톤 분해 검증: 라인 span + 제어 gap == 원본
        rebuilt_orig = bytearray()
        cur = msg
        ok = True
        for a, L in lines:
            if a < cur or a + L > me:
                ok = False
                break
            rebuilt_orig += orig[cur:a]
            rebuilt_orig += orig[a:a + L]
            cur = a + L
        if not ok:
            stats['skip_decompose'] += 1
            manifest.append({'msg': f'0x{msg:06X}', 'status': 'skip_decompose'})
            continue
        rebuilt_orig += orig[cur:me]
        if bytes(rebuilt_orig) != bytes(orig[msg:me]):
            stats['skip_decompose'] += 1
            manifest.append({'msg': f'0x{msg:06X}', 'status': 'skip_decompose'})
            continue

        # 재구성: 고칠 쪼롱이님 라인만 완전충실 한글로 교체, 나머지는 현재 빌드 바이트(rom) 보존.
        # 제어 gap도 현재 빌드(rom) 그대로(=orig와 동일, 빌드가 슬롯 외엔 안 씀).
        new_msg = bytearray()
        cur = msg
        for a, L in lines:
            new_msg += rom[cur:a]                 # control gap (현 빌드 보존)
            if a in fix_addrs:
                new_msg += fixed_bytes(a)         # 쪼롱이님 원문 완전충실(단어붙음 해소)
            else:
                new_msg += rom[a:a + L]           # 미열화/CSV 라인은 현재 바이트 그대로
            cur = a + L
        new_msg += rom[cur:me]                    # 종단 제어 보존

        # ★2026-06-25 전각공백 변환: 대사 렌더러는 반각공백(0x20)을 글리프 폭 0으로 스킵(화면 잼)하므로,
        # free space(폭 여유)인 재배치 블롭은 **content 사이 0x20을 전각(0x8140)으로** 바꿔 화면에 공백이
        # 보이게 한다. 비-fixed 라인(클린소스 없는 잼)까지 정상화. (다음이 content가 아닌 0x20=trailing 패딩,
        # 제어코드 앞 0x20은 미변환=무해 스킵.) 2바이트 코드 lead는 건너뛰어 코드 내부 0x20 오변환 방지.
        _conv = bytearray(); _i = 0
        while _i < len(new_msg):
            _b = new_msg[_i]
            if 0x81 <= _b <= 0xE2 and _i + 1 < len(new_msg):
                _conv += new_msg[_i:_i + 2]; _i += 2
            elif _b == 0x20:
                _nx = new_msg[_i + 1] if _i + 1 < len(new_msg) else 0
                if 0x81 <= _nx <= 0xE2 or 0x21 <= _nx <= 0x7E:   # 다음이 content → interior space
                    _conv += b'\x81\x40'
                else:
                    _conv += b'\x20'
                _i += 1
            else:
                _conv += bytes([_b]); _i += 1
        new_msg = _conv

        # terminator 보존 검증(2026-06-25, codex/agy 보수화): **원본이 0x00 종단인 메시지만** 재배치하고,
        # 그 경우 new_msg도 0x00 종단이어야 함. 원본 비-0x00 종단(다음 메시지까지 span)은 엔진 소비범위 불명
        # → 재배치 시 run-off 위험이므로 보수적 skip. patch_script_row류(라인이 종단 삼킴)도 여기서 차단.
        if me <= msg or orig[me - 1] != 0 or (not new_msg or new_msg[-1] != 0):
            stats['skip_no_terminator'] = stats.get('skip_no_terminator', 0) + 1
            manifest.append({'msg': f'0x{msg:06X}', 'status': 'skip_no_terminator'})
            continue

        # 제어 바이트 보존 검증(라인 외 전부 동일)
        # (분해가 검증됐고 gap은 orig 복사이므로 자명하지만 명시 확인)
        nlen = len(new_msg)
        if free + nlen > free_end:
            raise AssertionError('repoint free-space exhausted')
        new_addr = free
        rom[new_addr:new_addr + nlen] = new_msg
        free += nlen
        if free % align:
            free += align - (free % align)
        # 포인터 갱신 — 다중포인터면 전 site 갱신(고아 방지)
        for _s in sites:
            struct.pack_into('<I', rom, _s, GBA + new_addr)
        if len(sites) > 1:
            stats['relocated_multi'] = stats.get('relocated_multi', 0) + 1
        _relocated_msgs.add(msg)
        stats['relocated'] += 1
        stats['lines_fixed'] += len(fix_addrs)
        manifest.append({
            'msg': f'0x{msg:06X}', 'status': 'relocated',
            'ptr_off': f'0x{ptr_off:06X}', 'new_addr': f'0x{new_addr:06X}',
            'old_len': me - msg, 'new_len': nlen, 'lines': len(lines),
            'fixed': sorted(f'0x{a:06X}' for a in fix_addrs),
        })

    stats['free_used'] = free - free_start
    stats['free_avail'] = free_end - free_start
    return manifest, dict(stats)
