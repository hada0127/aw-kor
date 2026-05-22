import csv
terms = ['撓又箔迫悗','撥欄湯迫國','尨白鋳葺椒','囓盗髄燈屬','尸俣涛葺洟','尨亦荘薄屬','恙藍部蕗洟','尸部舶繭洟','剿部灯吏擒','恫白錘署縛','椢俣盗崇万','椢俣酎緒著','棘亦草瑞丁','囑盗緒諮慢','恬泊瑞崇理','尠衷緒署万','尠註庶誌筒','椢蕪荘葬万','棘蕪草蒼理','尢湯酎祷撻']
files=['data/translation_comprehensive.csv','data/translation_for_import.csv','data/translation_for_import_reviewed.csv','data/game_wars_found_texts.csv','data/translation_priority1.csv']
for term in terms:
    print('TERM', term)
    found=False
    for f in files:
        try:
            with open(f, encoding='utf-8-sig', newline='') as fp:
                reader=csv.reader(fp)
                for i,row in enumerate(reader,1):
                    if term in row:
                        print(f, i, row[:8])
                        found=True
        except Exception as e:
            print('ERR', f, e)
    if not found:
        print('NOT FOUND')
