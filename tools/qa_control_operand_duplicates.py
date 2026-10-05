#!/usr/bin/env python3
"""Find translated names repeated beside a preserved Japanese control operand."""
import argparse
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORDS = {'歩兵': '보병', '攻撃': '공격', '待機': '대기', '終了': '종료',
         '戦車': '전차', '輸送車': '수송차', '補給': '보급', '占領': '점령', '合流': '합류',
         '搭載': '탑재', '爆撃機': '폭격기', '偵察車': '정찰차', '戦艦': '전함', '戦闘機': '전투기'}


def find_duplicates(original, patched, codes, *, relocated=False):
    issues = []
    for japanese, korean in WORDS.items():
        source = japanese.encode('shift_jis')
        encoded = b''.join(codes[ch].to_bytes(2, 'big') for ch in korean)
        if not relocated and len(source) != len(encoded):
            raise ValueError('In-place operand width requires explicit handling: ' + japanese)
        for control in (b'\x32', b'\x33'):
            token = control + source + b'\x30'
            live = control + encoded + b'\x30'
            search = patched if relocated else original
            pattern = live if relocated else token
            if relocated and token not in original:
                continue
            start = 0
            while (address := search.find(pattern, start)) >= 0:
                start = address + len(pattern)
                # In-place tokens retain their source address. Relocated
                # tokens are searched within a pointer-verified text message
                # whose original message contains the corresponding operand.
                if patched[address:address + len(live)] != live:
                    continue
                tail = address + len(live)
                while patched[tail:tail + 1] == b' ' or patched[tail:tail + 2] == b'\x81\x40':
                    tail += 1 if patched[tail:tail + 1] == b' ' else 2
                if patched[tail:tail + len(encoded)] == encoded:
                    issues.append({'operand_address': '0x%08X' % address,
                                   'fragment_address': '0x%08X' % tail, 'word': korean})
                head = address
                while head and (patched[head - 1:head] == b' ' or
                                patched[max(0, head - 2):head] == b'\x81\x40'):
                    head -= 1 if patched[head - 1:head] == b' ' else 2
                for particle in ('', '을', '를', '은', '는', '이', '가', '의', '와', '과', '도', '에'):
                    if any(ch not in codes for ch in particle):
                        continue
                    preceding = encoded + b''.join(codes[ch].to_bytes(2, 'big') for ch in particle)
                    if head >= len(preceding) and patched[head - len(preceding):head] == preceding:
                        issues.append({'operand_address': '0x%08X' % address,
                                       'fragment_address': '0x%08X' % (head - len(preceding)),
                                       'word': korean, 'direction': 'before'})
                        break
    return sorted(issues, key=lambda issue: issue['operand_address'])


def check_rom(original, patched, codes, manifest):
    relocated = []
    for row in manifest:
        if row.get('status') != 'relocated':
            continue
        old, new, pointer = (int(row[key], 16) for key in ('msg', 'new_addr', 'ptr_off'))
        old_len, new_len = row['old_len'], row['new_len']
        if not (0 <= old < old + old_len <= len(original) and
                0 <= new < new + new_len <= len(patched) and
                0 <= pointer <= len(patched) - 4):
            raise ValueError('Repoint manifest contains an invalid range')
        if struct.unpack_from('<I', patched, pointer)[0] != 0x08000000 + new:
            raise ValueError('Repoint manifest does not match the ROM pointer at %08X' % pointer)
        relocated.append((old, new, old_len, new_len))
    issues = [item for item in find_duplicates(original, patched, codes)
              if not any(old <= int(item['operand_address'], 16) < old + size
                         for old, _, size, _ in relocated)]
    for old, new, old_len, new_len in relocated:
        for item in find_duplicates(original[old:old + old_len], patched[new:new + new_len],
                                    codes, relocated=True):
            for key in ('operand_address', 'fragment_address'):
                item[key] = '0x%08X' % (new + int(item[key], 16))
            item['original_message'] = '0x%08X' % old
            issues.append(item)
    return sorted(issues, key=lambda item: item['operand_address'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--original', type=Path, default=ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba')
    parser.add_argument('--manifest', type=Path, required=True, help='Repoint manifest from this ROM build')
    args = parser.parse_args()
    codes = {ch: int(value, 16) for ch, value in
             json.loads((ROOT / 'data/syllable_to_code_2350.json').read_text()).items()}
    issues = check_rom(args.original.read_bytes(), args.rom.read_bytes(), codes,
                       json.loads(args.manifest.read_text()))
    print(json.dumps({'rom': str(args.rom), 'manifest': str(args.manifest),
                      'scope': 'adjacent repetitions of preserved control operands for %d named units/commands, including relocated messages' % len(WORDS),
                      'issues': issues, 'count': len(issues)}, ensure_ascii=False, indent=2))
    return bool(issues)


if __name__ == '__main__':
    raise SystemExit(main())
