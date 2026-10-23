"""ROM 비의존 이름 조합 참조 모델. ROM 코드/표를 생성하거나 쓰지 않는다."""

from __future__ import annotations

from dataclasses import dataclass
import argparse
import json
from pathlib import Path

L_LIST = tuple('ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ')
V_LIST = tuple('ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ')
T_LIST = ('', *'ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ')
COMPOUND_VOWELS = dict(zip(
    [('ㅗ', 'ㅏ'), ('ㅗ', 'ㅐ'), ('ㅗ', 'ㅣ'), ('ㅜ', 'ㅓ'),
     ('ㅜ', 'ㅔ'), ('ㅜ', 'ㅣ'), ('ㅡ', 'ㅣ')], 'ㅘㅙㅚㅝㅞㅟㅢ'))
FINAL_CLUSTERS = dict(zip(
    [('ㄱ', 'ㅅ'), ('ㄴ', 'ㅈ'), ('ㄴ', 'ㅎ'), ('ㄹ', 'ㄱ'),
     ('ㄹ', 'ㅁ'), ('ㄹ', 'ㅂ'), ('ㄹ', 'ㅅ'), ('ㄹ', 'ㅌ'),
     ('ㄹ', 'ㅍ'), ('ㄹ', 'ㅎ'), ('ㅂ', 'ㅅ')], 'ㄳㄵㄶㄺㄻㄼㄽㄾㄿㅀㅄ'))
FINAL_TO_INITIAL = {t: L_LIST.index(t) for t in T_LIST[1:] if t in L_LIST}
SELECTABLE_JAMO = L_LIST + tuple('ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅛㅜㅠㅡㅣ')
PREVIEW_JAMO = L_LIST + V_LIST
SPACE_CODE = 0x8140  # 리서치 인용; 네이티브 저장·렌더 의미 UNVERIFIED.
MAX_SLOTS = 8
TABLE_PATH = Path(__file__).resolve().parents[1] / 'data' / 'syllable_to_code_2350.json'
_V_SPLIT = {v: pair for pair, v in COMPOUND_VOWELS.items()}
_T_SPLIT = {t: pair for pair, t in FINAL_CLUSTERS.items()}


@dataclass(frozen=True)
class Result:
    accepted: bool
    reason: str | None = None


@dataclass(frozen=True)
class Active:
    L: int | None = None
    V: int | None = None
    T: int = 0

    @property
    def complete(self):
        return self.L is not None and self.V is not None

    @property
    def char(self):
        if self.complete:
            return chr(0xAC00 + (self.L * 21 + self.V) * 28 + self.T)
        return L_LIST[self.L] if self.L is not None else V_LIST[self.V]


def code_for(table, L, V, T=0):
    """표에 없는 완성 음절은 None. 다른 음절로 대체하지 않는다."""
    return table.get(chr(0xAC00 + (L * 21 + V) * 28 + T))


def load_table(path=TABLE_PATH):
    raw = json.loads(Path(path).read_text(encoding='utf-8'))
    table = {char: int(code, 16) for char, code in raw.items()}
    if (len(table) != 2350 or len(set(table.values())) != 2350
            or any(len(c) != 1 or not 0xAC00 <= ord(c) <= 0xD7A3 for c in table)
            or any(not 1 <= code <= 0xFFFF for code in table.values())):
        raise ValueError('invalid 2350 syllable table')
    return table


class Composer:
    def __init__(self, table: dict[str, int]):
        self.table = dict(table)
        self.reset()

    def reset(self):
        self.committed = []
        self.active = None

    def snapshot(self):
        return tuple(self.committed), self.active

    def _apply(self, committed, active):
        # 모든 후보를 검사한 뒤 한 번만 갱신해 종성 이동을 원자적으로 적용한다.
        if len(committed) + (active is not None) > MAX_SLOTS:
            return Result(False, 'no_slot')
        if active is not None and active.complete and active.char not in self.table:
            return Result(False, 'not_in_2350')
        self.committed = committed
        self.active = active
        return Result(True)

    def _advance(self, active):
        return self._apply(self.committed + [self.table[self.active.char]], active)

    def press(self, jamo: str) -> Result:
        if jamo not in SELECTABLE_JAMO:
            raise ValueError('expected a selectable compatibility jamo')
        a = self.active
        consonant = jamo in L_LIST
        if a is None:
            return self._apply(self.committed.copy(),
                               Active(L=L_LIST.index(jamo)) if consonant
                               else Active(V=V_LIST.index(jamo)))
        if not a.complete:
            if consonant:
                return Result(False, 'incomplete')
            if a.L is not None:
                return self._apply(self.committed.copy(), Active(a.L, V_LIST.index(jamo)))
            combined = COMPOUND_VOWELS.get((V_LIST[a.V], jamo))
            if combined is None:
                return Result(False, 'invalid_transition')
            return self._apply(self.committed.copy(), Active(V=V_LIST.index(combined)))
        if consonant:
            if a.T:
                combined = FINAL_CLUSTERS.get((T_LIST[a.T], jamo))
                if combined is not None:
                    return self._apply(self.committed.copy(), Active(a.L, a.V, T_LIST.index(combined)))
                return self._advance(Active(L=L_LIST.index(jamo)))
            if jamo in T_LIST:
                return self._apply(self.committed.copy(), Active(a.L, a.V, T_LIST.index(jamo)))
            return self._advance(Active(L=L_LIST.index(jamo)))
        if not a.T:
            combined = COMPOUND_VOWELS.get((V_LIST[a.V], jamo))
            if combined is not None:
                return self._apply(self.committed.copy(), Active(a.L, V_LIST.index(combined)))
            return self._advance(Active(V=V_LIST.index(jamo)))
        final = T_LIST[a.T]
        remaining, moving = _T_SPLIT.get(final, ('', final))
        front_code = code_for(self.table, a.L, a.V, T_LIST.index(remaining))
        following = Active(FINAL_TO_INITIAL[moving], V_LIST.index(jamo))
        if front_code is None or following.char not in self.table:
            return Result(False, 'not_in_2350')
        return self._apply(self.committed + [front_code], following)

    def backspace(self) -> Result:
        a = self.active
        if a is None:
            if not self.committed:
                return Result(False, 'empty')
            return self._apply(self.committed[:-1], None)
        if a.T:
            first = _T_SPLIT.get(T_LIST[a.T], ('', ''))[0]
            return self._apply(self.committed.copy(), Active(a.L, a.V, T_LIST.index(first)))
        if a.V is not None and V_LIST[a.V] in _V_SPLIT:
            return self._apply(self.committed.copy(), Active(a.L, V_LIST.index(_V_SPLIT[V_LIST[a.V]][0])))
        if a.complete:
            return self._apply(self.committed.copy(), Active(L=a.L))
        return self._apply(self.committed.copy(), None)

    def confirm(self) -> Result:
        if self.active is None:
            return Result(True)
        if not self.active.complete:
            return Result(False, 'incomplete')
        return self._advance(None)

    def space(self) -> Result:
        codes = self.committed.copy()
        if self.active is not None:
            if not self.active.complete:
                return Result(False, 'incomplete')
            codes.append(self.table[self.active.char])
        return self._apply(codes + [SPACE_CODE], None)

    def preview(self):
        slots = [('code', code) for code in self.committed]
        if self.active is not None:
            slots.append(('active', self.active.char))
        return slots

    def serialize(self) -> bytes:
        return b''.join(code.to_bytes(2, 'big') for code in self.committed).ljust(16, b'\0')

    def load(self, codes):
        """16바이트 또는 최대 8개 16bit 정수. 0은 종료자이며 이후 값은 무시한다."""
        if isinstance(codes, bytes):
            if len(codes) != 16:
                raise ValueError('expected exactly 16 bytes')
            values = [int.from_bytes(codes[i:i + 2], 'big') for i in range(0, 16, 2)]
        elif isinstance(codes, list):
            values = codes.copy()
        else:
            raise ValueError('expected bytes16 or list[int]')
        if (len(values) > MAX_SLOTS
                or any(type(v) is not int or not 0 <= v <= 0xFFFF for v in values)):
            raise ValueError('expected at most eight 16bit codes')
        end = values.index(0) if 0 in values else len(values)
        self.committed, self.active = values[:end], None


def reachability_report(table=None):
    """지원 음절의 표준 두벌식 키열에서 누락된 중간 후보를 열거한다."""
    if table is None:
        table = load_table()
    unreachable = {}
    for char in sorted(table):
        n = ord(char) - 0xAC00
        L, V, T = n // 588, (n // 28) % 21, n % 28
        vowels = _V_SPLIT.get(V_LIST[V], (V_LIST[V],))
        finals = _T_SPLIT.get(T_LIST[T], (T_LIST[T],)) if T else ()
        candidates = [chr(0xAC00 + (L * 21 + V_LIST.index(vowels[0])) * 28),
                      chr(0xAC00 + (L * 21 + V) * 28)]
        if finals:
            candidates.append(chr(0xAC00 + (L * 21 + V) * 28 + T_LIST.index(finals[0])))
        candidates.append(char)
        missing = tuple(dict.fromkeys(c for c in candidates if c not in table))
        if missing:
            unreachable[char] = missing
    return {'mapped': len(table), 'reachable': len(table) - len(unreachable),
            'unreachable': unreachable}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', action='store_true')
    args = parser.parse_args()
    if args.report:
        report = reachability_report()
        print(f"mapped={report['mapped']} reachable={report['reachable']} unreachable={len(report['unreachable'])}")
        for char, missing in report['unreachable'].items():
            print(f"{char}: missing {','.join(missing)}")


if __name__ == '__main__':
    main()
