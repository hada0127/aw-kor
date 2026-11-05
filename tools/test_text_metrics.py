#!/usr/bin/env python3
"""text_metrics syllable coverage regression."""
import os, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, 'tools'))
import text_metrics as TM


def test_unmapped():
    """unmapped_syllables: 2350 폰트에 없는 음절을 잡는다(빈 입력/정상 입력은 빈 목록)."""
    sset = TM.syllable_set()
    assert sset, '2350 음절셋 로드 실패'
    assert TM.unmapped_syllables('안녕하세요', sset) == []
    assert TM.unmapped_syllables('', sset) == []
    assert TM.unmapped_syllables('힣뷁힣 안녕', sset) == ['힣', '뷁']
    assert TM.has_unmapped_syllables('힣', sset)
    assert not TM.has_unmapped_syllables('안녕', sset)
    print('  ✓ unmapped_syllables 동작')


if __name__ == '__main__':
    print('test_text_metrics:')
    test_unmapped()
    print('ALL PASS')
