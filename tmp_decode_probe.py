texts = [
    '悁俣錘丱',
    '攪虫賜岔',
    '泝劍劒悛',
    '礦鉗鞳玻',
    '矣珈硼贐',
    '裄玳琿鰤',
    '玻玻銖鰥',
    '鴉鈑籟胱',
    '蒄蓴赭鉗',
    '靼粹鈔鴉',
    '釐粹釿鉉',
    '鰊粱葯裼',
    '萼冐聹鱧',
    '靼褓鈕鞴',
    '赧鉈裝鱶',
    '賍蓆趙韜',
    '獺韵鈬鞴',
    '恍劍濠打',
    '卵又葬梶',
    '鱠蓍葢籟',
]

encs = ['big5', 'cp950', 'gbk', 'gb18030', 'shift_jis', 'cp932', 'euc_jp', 'euc_kr', 'cp949']
decs = ['utf-8', 'cp949', 'euc_kr', 'shift_jis', 'cp932', 'big5', 'cp950', 'gbk', 'gb18030', 'latin1']

for e in encs:
    print('ENC', e)
    for d in decs:
        outs = []
        ok = True
        for s in texts[:5]:
            try:
                outs.append(s.encode(e).decode(d))
            except Exception:
                ok = False
                break
        if ok:
            print(' ', d, [o.encode('unicode_escape').decode() for o in outs])
    print()

import csv
seen = {}
with open('data/game_wars_found_texts.csv', encoding='utf-8', newline='') as f:
    for row in csv.reader(f):
        if len(row) >= 3 and row[2] in texts and row[2] not in seen:
            seen[row[2]] = row

print('ROWS')
for i, s in enumerate(texts, 1):
    row = seen.get(s)
    print(i, None if row is None else [x.encode('unicode_escape').decode() for x in row])
