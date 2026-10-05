"""Owned result-badge ランク strip, proven by recorded public OAM/VRAM."""
import hashlib
START, END = 0xBEB0FC, 0xBEB17C
TABLE = 0xD8D7BC
SOURCE_SHA = '23aea7def0b22e9745803722468cd6c93227443a87d83955a48ec5fcf6e209f8'
GEOMETRY = bytes.fromhex('e601040103000000ea01040103000000')

def source_guard(rom):
 if hashlib.sha256(rom[START:END]).hexdigest()!=SOURCE_SHA or bytes(rom[TABLE:TABLE+16])!=GEOMETRY:
  raise ValueError('Result rank word source/geometry changed')
 if any(rom[END-32:END]):raise ValueError('Result rank invisible fourth tile changed')

def render(render_native):
 # OAM36 (16x8) + OAM37 (8x8) expose 24 pixels. The allocated
 # fourth tile is blank and not displayed. Reuse existing Galmuri7 font.
 raw=render_native('랭크',3,ink=1)
 if len(raw)!=96:raise ValueError('Result rank native renderer geometry changed')
 pixels=[[0]*24 for _ in range(8)]
 for y in range(8):
  for x in range(24):
   b=raw[(x//8)*32+y*4+(x%8)//2];v=(b>>(4*(x%2)))&15
   if v not in (0,1):raise ValueError('Result rank ink changed')
   pixels[y][x]=v
 if any(pixels[7]) or any(row[23] for row in pixels):
  raise ValueError("Result rank shadow would clip")
 result=[row[:] for row in pixels]
 # Keep the original white-on-black readable shadow palette; no font scaling.
 for y in range(8):
  for x in range(24):
   if pixels[y][x]:
    for dx,dy in ((1,0),(0,1),(1,1)):
     xx,yy=x+dx,y+dy
     if xx<24 and yy<8 and not pixels[yy][xx]:result[yy][xx]=5
 out=bytearray(128)
 for y in range(8):
  for x in range(24):out[(x//8)*32+y*4+(x%8)//2]|=result[y][x]<<(4*(x%2))
 return bytes(out)

def patch(rom,original,render_native):
 source_guard(original)
 if bytes(rom[START:END])!=bytes(original[START:END]) or bytes(rom[TABLE:TABLE+16])!=GEOMETRY:
  raise ValueError('Result rank active source/geometry changed')
 data=render(render_native);rom[START:END]=data
 return 1

def capture(rom):
 if bytes(rom[TABLE:TABLE+16])!=GEOMETRY or any(rom[END-32:END]):raise ValueError('Result rank final geometry/padding changed')
 return bytes(rom[START:END]),bytes(rom[TABLE:TABLE+16])

def verify(rom,evidence):
 if capture(rom)!=evidence:raise ValueError('Result rank late overwrite')
