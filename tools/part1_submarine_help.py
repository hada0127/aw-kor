"""Source-bound four-row submarine help; patched live pixels remain unverified."""
import hashlib
import struct
from dialogue_repoint import normalize_text_segment
from sprite_relocations import SPRITE_STORAGE_START
SOURCE=0xDEEDD8
END=0xDEEE4C
POINTER=0xDEFAD0
SOURCE_SHA='c6d00c9879522062ff4a73a76bb3247c9beab855dc933d593e23b567d1fdb2b1'
ROWS=(
 (0xDEEDDA,0xDEEDE8,'해상 유닛。「'),
 (0xDEEDE9,0xDEEDEF,'잠수'),
 (0xDEEDF0,0xDEEDF4,'」하면'),
 (0xDEEDF8,0xDEEDFE,'잠수함,'),
 (0xDEEE02,0xDEEE08,'호위함'),
 (0xDEEE09,0xDEEE13,'에만'),
 (0xDEEE16,0xDEEE2E,'공격받는다. 인접한'),
 (0xDEEE31,0xDEEE49,'적이 없으면 안 보인다'),
)
VISIBLE_ROWS=('해상 유닛。”잠수”하면','잠수함、 호위함에만','공격받는다。 인접한','적이 없으면 안 보인다')

def source_guard(original):
 if hashlib.sha256(original[SOURCE:END]).hexdigest()!=SOURCE_SHA or struct.unpack_from('<I',original,POINTER)[0]!=0x08000000+SOURCE:
  raise ValueError('Submarine help original source/pointer changed')

def expected_payload(original,encode):
 source_guard(original)
 result=bytearray();cur=SOURCE
 for start,end,text in ROWS:
  result+=original[cur:start]
  result+=normalize_text_segment(encode(text,start),True,start)
  cur=end
 result+=original[cur:END]
 return bytes(result)

def verify(rom,original,manifest,encode):
 expected=expected_payload(original,encode)
 entries=[m for m in manifest if int(m['msg'],16)==SOURCE]
 if len(entries)!=1 or entries[0]['status']!='relocated':raise ValueError('Submarine help relocation missing/duplicate')
 m=entries[0];target=int(m['new_addr'],16)
 if (int(m['ptr_off'],16)!=POINTER or m['old_len']!=END-SOURCE or m['new_len']!=len(expected)
     or target%4 or not 0xA3D000<=target<target+len(expected)<=SPRITE_STORAGE_START):
  raise ValueError('Submarine help relocation bounds/ownership changed')
 if struct.unpack_from('<I',rom,POINTER)[0]!=target+0x08000000:raise ValueError('Submarine help final pointer changed')
 if bytes(rom[target:target+len(expected)])!=expected:raise ValueError('Submarine help text/control/style changed')
 return {'status':'PASS','source':hex(SOURCE),'target':hex(target),'rows':VISIBLE_ROWS,
         'native_consumer_verified':False,'pixels_verified':False,
         'scope':'Exact source/pointer, four-row text and native style/control skeleton; live pixels pending'}
