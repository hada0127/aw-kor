"""Restore the reviewed polite return-to-mode question without changing its slots."""
import hashlib
import struct
TEXT='모드 선택으로 돌아갈까요?'
SOURCE_SHA='ba97e07752e4a2e8fb522e4c50d3f6037b6d4304204de9e5fb6b1abb30893e60'
ROWS=((0xDF2A64,0xDF2A8E,0xD8CA40),(0xA34CE8,0xA34D12,0xA38A04))

def verify(rom,original,encode_fit):
 for start,end,pointer in ROWS:
  if hashlib.sha256(original[start:end]).hexdigest()!=SOURCE_SHA or struct.unpack_from('<I',original,pointer)[0]!=start+0x08000000:
   raise ValueError('Return question original source/pointer changed')
  payload,level=encode_fit(TEXT,end-start,start)
  if payload is None or level!=0 or len(payload)>end-start:
   raise ValueError('Return question must preserve complete level-0 text')
  if bytes(rom[start:end])!=payload+b' '*(end-start-len(payload)):
   raise ValueError('Return question approved text/padding mismatch')
  if bytes(rom[end:end+3])!=bytes(original[end:end+3]) or struct.unpack_from('<I',rom,pointer)[0]!=start+0x08000000:
   raise ValueError('Return question control/pointer changed')
 return {'status':'PASS','text':TEXT,'addresses':[hex(s) for s,e,p in ROWS],'patched_live_pixels_verified':False}
