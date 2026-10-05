"""Source-bound Part 1 ship introductions; no live-pixel approval implied."""
import hashlib
import struct
from dialogue_repoint import normalize_text_segment
from sprite_relocations import SPRITE_STORAGE_START

MESSAGES=(
 dict(name='battleship',source=0xDEE914,end=0xDEE958,pointer=0xDEFA10,
      sha='fc1850328934432bd7bbebc3022a940dbfb5007f8d7142083da91a1013006373',
      rows=((0xDEE916,0xDEE922,'해상 유닛.'),(0xDEE926,0xDEE930,'로켓포'),
            (0xDEE931,0xDEE93F,'보다 넓은 공격'),(0xDEE942,0xDEE954,'범위를 갖는다.')),
      visible=('해상 유닛。','로켓포보다 넓은 공격','범위를 갖는다。')),
 dict(name='escort',source=0xDEEB60,end=0xDEEBBC,pointer=0xDEFA50,
      sha='47899d5aa1fac782e7754f3e95bca274e989092e0b37001730f18559bfee1b77',
      rows=((0xDEEB62,0xDEEB6E,'해상 유닛.'),(0xDEEB6F,0xDEEB75,'잠수함'),
            (0xDEEB76,0xDEEB78,'과'),(0xDEEB7B,0xDEEB8D,'공중 유닛에 강함.'),
            (0xDEEB90,0xDEEBA0,'그 밖에, 헬기를'),(0xDEEBA3,0xDEEBB9,'두 유닛 탑재 가능')),
      visible=('해상 유닛。잠수함과','공중 유닛에 강함。','그 밖에、 헬기를','두 유닛 탑재 가능')),
 dict(name='lander',source=0xDEECDC,end=0xDEED44,pointer=0xDEFA90,
      sha='9b3cd29ff19680c53d6d96f6e47de325e92b921fe7e79871398abae0e637cc83',
      rows=((0xDEECDE,0xDEECF6,'해상 유닛.지상 유닛을'),(0xDEECF9,0xDEED0F,'두 유닛 탑재 가능.'),
            (0xDEED12,0xDEED2A,'수송 중 파괴되면 안의'),(0xDEED2D,0xDEED41,'유닛도 함께 사라진다.')),
      visible=('해상 유닛。지상 유닛을','두 유닛 탑재 가능。','수송 중 파괴되면 안의','유닛도 함께 사라진다。')),
)
ROWS=tuple(row for message in MESSAGES for row in message['rows'])

def source_guard(original):
 for m in MESSAGES:
  if hashlib.sha256(original[m['source']:m['end']]).hexdigest()!=m['sha'] or struct.unpack_from('<I',original,m['pointer'])[0]!=0x08000000+m['source']:
   raise ValueError('Ship help original source/pointer changed: '+m['name'])

def expected_payload(original,encode,m):
 source_guard(original)
 result=bytearray();cur=m['source']
 for start,end,text in m['rows']:
  result+=original[cur:start]
  result+=normalize_text_segment(encode(text,start),True,start)
  cur=end
 result+=original[cur:m['end']]
 return bytes(result)

def verify(rom,original,manifest,encode):
 result=[]
 for m in MESSAGES:
  expected=expected_payload(original,encode,m)
  entries=[entry for entry in manifest if int(entry['msg'],16)==m['source']]
  if len(entries)!=1 or entries[0]['status']!='relocated':raise ValueError('Ship help relocation missing/duplicate: '+m['name'])
  entry=entries[0];target=int(entry['new_addr'],16)
  if (int(entry['ptr_off'],16)!=m['pointer'] or entry['old_len']!=m['end']-m['source'] or entry['new_len']!=len(expected)
      or target%4 or not 0xA3D000<=target<target+len(expected)<=SPRITE_STORAGE_START):
   raise ValueError('Ship help relocation bounds/ownership changed: '+m['name'])
  if struct.unpack_from('<I',rom,m['pointer'])[0]!=target+0x08000000:raise ValueError('Ship help final pointer changed: '+m['name'])
  if bytes(rom[target:target+len(expected)])!=expected:raise ValueError('Ship help text/control/style changed: '+m['name'])
  result.append({'name':m['name'],'source':hex(m['source']),'target':hex(target),'rows':m['visible']})
 return {'status':'PASS','messages':result,'native_consumer_verified':False,'pixels_verified':False}
