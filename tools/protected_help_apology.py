"""Two individually reviewed protected sentences with distinct native contracts."""
import hashlib
import struct
from dialogue_repoint import normalize_text_segment, text_segment_cells
from sprite_relocations import SPRITE_STORAGE_START
HELP='만드는 방법은 「도움말」에 적혀 있어요.'
APOLOGY='미안해요'
SPECS=((0xD82058,0xD82080,0xD7EDD4,'6f354effccdda336d3b70a756656dda038ec9d4cf7ead8608ed61374ea52100a'),
       (0xD8F6FC,0xD8F711,0xDA4CB8,'13b08b1b54ca0e87928993e62b6676e5edd92d88d9a26c1360f214ef7321dd94'))

def source_guard(original):
 for start,end,pointer,digest in SPECS:
  needle=struct.pack('<I',start+0x08000000)
  if (hashlib.sha256(original[start:end]).hexdigest()!=digest
      or bytes(original[pointer:pointer+4])!=needle or original.count(needle)!=1):
   raise ValueError('Protected help/apology original source/pointer changed')

def help_payload(original,encode):
 source_guard(original)
 text=normalize_text_segment(encode(HELP,0xD82058),True,0xD82058)
 if text_segment_cells(text)>50:raise ValueError('Map help full text exceeds width')
 return text+original[0xD8207C:0xD82080]

def verify(rom,original,encode):
 expected=help_payload(original,encode)
 target=struct.unpack_from('<I',rom,0xD7EDD4)[0]-0x08000000
 if target%4 or not 0xA3D000<=target<target+len(expected)<=SPRITE_STORAGE_START:
  raise ValueError('Map help requires bounded native relocation')
 # In-place text is an orphan translated by earlier writers; it need not equal
 # Japanese source. Its native terminator must still be untouched.
 if bytes(rom[0xD8207C:0xD82080])!=bytes(original[0xD8207C:0xD82080]):
  raise ValueError('Map help original control changed')
 if bytes(rom[target:target+len(expected)])!=expected:
  raise ValueError('Map help approved text/control mismatch')
 apology=encode(APOLOGY,0xD8F6FE)
 if len(apology)!=8:raise ValueError('Apology must preserve complete approved text')
 # Existing encode_fit writer fills unused slot bytes with ASCII spaces;
 # these are padding after the complete text, not replacement glyphs.
 if bytes(rom[0xD8F6FE:0xD8F70E])!=apology+b' '*8:
  raise ValueError('Apology approved polite text mismatch')
 for start,end in ((0xD8F6FC,0xD8F6FE),(0xD8F70E,0xD8F711),(0xDA4CB8,0xDA4CBC)):
  if bytes(rom[start:end])!=bytes(original[start:end]):raise ValueError('Apology native control/pointer changed')
 return {'status':'PASS','help_target':hex(target),'apology_source':'0xD8F6FE','live_pixels_verified':False}
