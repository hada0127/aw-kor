"""Empirical SJIS→font-slot formula for Game Wars (Japan).
Font base ROM 0x08B974D0.
Char-fixed: same SJIS char always reads same ROM slot.

Hiragana pages (top tiles, slots verified via BP trace):
  page 0 (slots 0-15):  あいうえお かきくけこ さしすせそ た
  page 1 (slots 32-47): ちつてと なにぬねの はひふへほ まみ
  page 2 (slots 64-77): むめも やゆよ らりるれろ わをん

Slots 16-31, 48-63, etc: variants (small/dakuten/handakuten) - to be measured.
Katakana/kanji: partial mappings in data/empirical_sjis_to_slot.json.
"""

HIRAGANA_PAGES=[
 ['あ','い','う','え','お','か','き','く','け','こ','さ','し','す','せ','そ','た'],
 ['ち','つ','て','と','な','に','ぬ','ね','の','は','ひ','ふ','へ','ほ','ま','み'],
 ['む','め','も','や','ゆ','よ','ら','り','る','れ','ろ','わ','を','ん'],
]

def hiragana_top_slot(ch):
    for page,chars in enumerate(HIRAGANA_PAGES):
        if ch in chars:
            return page*32 + chars.index(ch)
    return None

if __name__=="__main__":
    # verification against measured
    measured={'あ':0,'う':2,'え':3,'お':4,'こ':9,'し':11,'そ':14,'た':15,
              'て':34,'な':36,'ね':39,'の':40,'へ':44,'よ':69,'を':76}
    for ch,s in measured.items():
        p=hiragana_top_slot(ch)
        assert s==p, "mismatch %s: expected %d got %d"%(ch,s,p)
    print("Formula verified against 15 measured points")
