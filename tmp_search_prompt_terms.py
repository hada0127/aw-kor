import csv

terms = """漱劔泗劔漱勦漱
褐巨風擅泱暑憲
ｏ俣嶋悴睡棧蕩
鱚瞻裴獵粡聶鉋
泅莱燈葬犯鈞鴕
沮涛囈涛禿鈞鋏
椈藍葡演糾賜衍
沱尹鮪克誌答泪
沱悁剿白錘濠沸
沱尹剿蕪註庶密
沱尹剿部註庶張
沱悍囹劍末封粕
沱尸藍箔湯樗劼
撕泊詞給月走悗
尢盗豪糾月走孱
椢舞詞糾褐賜万
撕舞渚給牛藷理
恫泊渚血克装辧
泝濫聡麹克嵩麿
撓俣随詩諮瀦劑""".splitlines()

files = [
    "data/game_wars_found_texts.csv",
    "data/translation_comprehensive.csv",
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

for idx, term in enumerate(terms, 1):
    hx = term.encode("cp932").hex()
    print(idx, term, hx)
    found = False
    for path in files:
        try:
            with open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as fp:
                for line_no, row in enumerate(csv.reader(fp), 1):
                    joined = "\t".join(row)
                    if term in joined or hx in joined:
                        print(" ", path, line_no, row[:8])
                        found = True
        except Exception as exc:
            print("ERR", path, exc)
    if not found:
        print("  NOT FOUND")
