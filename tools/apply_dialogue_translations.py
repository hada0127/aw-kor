#!/usr/bin/env python3
"""미번역 채움 번역(워크플로 산출 {ja,ko})을 dialogue_overrides.json에 주소별로 병합.

입력: --translations <json> ({"translations":[{"ja","ko"}]} 또는 [{"ja","ko"}]).
매핑: temp/untranslated_dialogue.json(items: ja→addresses)로 각 ja의 모든 미번역 주소에 ko 적용.
출력: data/dialogue_overrides.json 병합(기존 편집기 편집 보존, 빈 ko는 건너뜀).
빌드는 dialogue_overrides를 최종 오버레이로 읽어 ROM에 반영(build_korean_full.py).
"""
import argparse
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(BASE, "temp", "untranslated_dialogue.json")
OV = os.path.join(BASE, "data", "dialogue_overrides.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--translations", required=True)
    args = ap.parse_args()
    tr = json.load(open(args.translations, encoding="utf-8"))
    if isinstance(tr, dict):
        tr = tr.get("translations", [])
    ja2ko = {}
    for t in tr:
        ja = (t.get("ja") or "").strip()
        ko = (t.get("ko") or "").strip()
        if ja and ko:
            ja2ko[ja] = ko
    items = json.load(open(WORK, encoding="utf-8"))["items"]
    ja2addr = {it["ja"]: it["addresses"] for it in items}
    ov = {}
    if os.path.exists(OV):
        try:
            ov = json.load(open(OV, encoding="utf-8"))
        except Exception:
            ov = {}
    applied = 0; strings = 0
    for ja, ko in ja2ko.items():
        addrs = ja2addr.get(ja)
        if not addrs:
            continue
        strings += 1
        for a in addrs:
            if not ov.get(a):  # 기존 편집기 편집 보존(이미 ko 있으면 유지)
                ov[a] = ko
                applied += 1
    json.dump(ov, open(OV, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"applied {applied} addresses from {strings} translated strings → {OV} (total overrides {len(ov)})")


if __name__ == "__main__":
    main()
