"""Preserve source-bound native choice controls while restoring two protected lines."""
import hashlib
import struct
from dialogue_repoint import normalize_text_segment,text_segment_cells
from sprite_relocations import SPRITE_STORAGE_START
FIRST='혹시, 이 게임은 처음이신가요?'
CANCEL='어머, 역시 그만두시나요?'
SPECS=((0xDF8EAC,0xDF8ED8,0xDF9CAC,'952df6e4e1205f6df11f8cab7fcbea83c503610b356749e2d043791910cc35d4'),
       (0xDF9698,0xDF96BC,0xDF9AFC,'20c3a432dd48b7f5527893208056c270d9bd4d01e8750ce1a5a4e140e6bc96c1'))
def source_guard(original):
 for start,end,pointer,digest in SPECS:
  ref=struct.pack('<I',start+0x08000000)
  if hashlib.sha256(original[start:end]).hexdigest()!=digest or original[pointer:pointer+4]!=ref or original.count(ref)!=1:
   raise ValueError('Polite choice original source/pointer changed')
def cancel_payload(original,encode):
 source_guard(original)
 text=normalize_text_segment(encode(CANCEL,0xDF969A),True,0xDF9698)
 if text_segment_cells(text)>50:raise ValueError('Polite cancel full text exceeds width')
 return original[0xDF9698:0xDF969A]+text+original[0xDF96B2:0xDF96BC]
def verify(rom,original,encode):
 expected=cancel_payload(original,encode)
 first=encode(FIRST,0xDF8EAE)
 if len(first)!=34 or bytes(rom[0xDF8EAE:0xDF8ED0])!=first:raise ValueError('Polite first-game question mismatch')
 for a,e in ((0xDF8EAC,0xDF8EAE),(0xDF8ED0,0xDF8ED8),(0xDF9CAC,0xDF9CB0),(0xDF96B2,0xDF96BC)):
  if bytes(rom[a:e])!=bytes(original[a:e]):raise ValueError('Polite choice native controls/pointer changed')
 target=struct.unpack_from('<I',rom,0xDF9AFC)[0]-0x08000000
 if target%4 or not 0xA3D000<=target<target+len(expected)<=SPRITE_STORAGE_START:raise ValueError('Polite cancel requires bounded relocation')
 if bytes(rom[target:target+len(expected)])!=expected:raise ValueError('Polite cancel text/choice controls mismatch')
 return {'status':'PASS','cancel_target':hex(target),'live_pixels_verified':False}
