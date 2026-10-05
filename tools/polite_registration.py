"""Two protected registration messages; preserve native choice/wait controls."""
import hashlib
import struct
ROWS=(
 (0xDF9654,0xDF9656,0xDF966E,0xDF9674,0xDF9D0C,'그럼, 힘내요!','c9683089e72c0cb956f4b9e961b7681d0231ffc95b8cde3bb826e8b274a5ec8e'),
 (0xDF9674,0xDF9676,0xDF9690,0xDF9698,0xDF9A1C,'이름을 저장해도 될까요?','f97dd3ac63a379130071f3b2b2e71919a4ab4434b20f29219431d1eb0116bf13'),
)
def verify(rom,original,encode):
 for start,address,text_end,end,pointer,text,digest in ROWS:
  reference=struct.pack('<I',start+0x08000000)
  if (hashlib.sha256(original[start:end]).hexdigest()!=digest or original[pointer:pointer+4]!=reference
      or original.count(reference)!=1):raise ValueError('Registration original source/pointer changed')
  payload=encode(text,address)
  if len(payload)>text_end-address or not payload:raise ValueError('Registration full text exceeds original slot')
  if bytes(rom[address:text_end])!=payload+b' '*(text_end-address-len(payload)):
   raise ValueError('Registration approved polite text mismatch')
  if (bytes(rom[start:address])!=bytes(original[start:address]) or bytes(rom[text_end:end])!=bytes(original[text_end:end])
      or bytes(rom[pointer:pointer+4])!=reference):raise ValueError('Registration native controls/pointer changed')
 return {'status':'PASS','addresses':[hex(row[1]) for row in ROWS],'live_pixels_verified':False}
