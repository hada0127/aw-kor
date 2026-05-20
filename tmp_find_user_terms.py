import csv

terms = [
    "搆÷÷ｉ豫",
    "棡剿痩焔除",
    "粭珞葩珞蒟",
    "鞴聿粐跖韶",
    "砠跂褓鱇胝",
    "泗盗瑞葺洽",
    "椁酔括叶蔓",
    "棊窓轟黒圖",
    "摶総糾倦弌",
    "棡惧悄撩悄",
    "撩悗惧惧惠",
    "投雌嵐榕跏",
    "屏俣球活至",
    "椶剿拷脂虫",
    "棧囎視至総",
    "擒尢綜渚舞",
    "恣箔履崢矮",
    "棍恣涛蕗侶",
    "棍搗鋳曝亶",
    "屎將蒼曝劭",
]

files = [
    "data/translation_comprehensive.csv",
    "data/translation_for_import.csv",
    "data/translation_for_import_reviewed.csv",
    "data/game_wars_found_texts.csv",
    "data/translation_priority1.csv",
    "data/manual_translation_batch_001.csv",
    "data/manual_translation_batch_002.csv",
    "data/manual_translation_batch_003.csv",
    "data/manual_translation_batch_004.csv",
    "data/manual_translation_batch_005.csv",
    "data/manual_translation_batch_006.csv",
    "data/manual_translation_batch_007.csv",
    "data/manual_translation_batch_008.csv",
]

for term in terms:
    print("TERM", term)
    found = False
    for path in files:
        try:
            with open(path, encoding="utf-8-sig", newline="") as fp:
                for lineno, row in enumerate(csv.reader(fp), 1):
                    if any(term == cell or term in cell for cell in row):
                        print(path, lineno, row[:8])
                        found = True
        except Exception as exc:
            print("ERR", path, exc)
    if not found:
        print("NOT FOUND")
