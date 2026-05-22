s = """漱劔泗劔漱勦漱
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
撓俣随詩諮瀦劑"""
for line in s.splitlines():
    print("LINE", line)
    for enc in ["cp932", "shift_jis", "gbk", "gb18030", "big5", "cp950"]:
        try:
            b = line.encode(enc)
        except Exception:
            continue
        print(" ", enc, b.hex())
        for dec in ["cp949", "euc_kr", "utf-8", "gbk", "gb18030", "cp932"]:
            try:
                out = b.decode(dec)
                print("   ", dec, repr(out))
            except Exception:
                pass
