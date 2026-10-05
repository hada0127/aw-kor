"""Part 2 terrain movement captions: original icons, Galmuri7, 40px body/BG tail.

Native parent wait1 cleanup preserves the last OBJ frame. No added OAM/proc/RAM.
Runtime source/phase evidence is recorded in the project research log; guards
and final verification reject allocation or consumer drift during a build.
"""
from pathlib import Path
from functools import lru_cache
import hashlib,struct,re
from bdf import load_bdf,glyph_grid
from part1_unit_type_labels import FONT,FONT_SHA256
ROOT=Path(__file__).resolve().parents[1]
ASM=ROOT/'tools/asm/part2_terrain_movement_labels.s'
ASSET_ID='objlabel_p2_terrain_movement'
LABELS=('전차','타이어','보병','바주카','수송선','함선','비행')
ORIGINAL_SHA='a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c'
CAVE=0xFFC000;CAPACITY=0x1100;ATLAS=CAVE+0x800
SITES=((0x3474F6,10,'init_bridge'),(0x3472B8,8,'draw_bridge'),(0x34769A,10,'frame_bridge'))
NATIVE_SPANS=((0x346D48,0x347710),(0x317E38,0x317E68),(0x318A5C,0x318A78),(0x31F5E8,0x31F960),(0x31C1D4,0x31C464),(0x313B00,0x313B10),(0x83E013,0x83E01A),(0x83E06C,0x83E08F),(0x807178,0x8071C0+182*4),(0x45EB74,0x45EB94),(0x454494,0x454B94),(0x814FC0,0x814FC4),(0x311C7C,0x311CA2),(0x3196D2,0x3196E2),(0x31970C,0x319714),(0x83E090,0x83E0D0),(0x347710,0x3477A0),(0x3157E4,0x315838),(0x315E9C,0x315F58),(0x316234,0x3162C0),(0x805BA0,0x805BCC),(0x814FB0,0x814FB4),(0x38B434,0x38B43C),(0x31BC38,0x31BC78),(0x315838,0x315874),(0x3160EC,0x316104),(0x83E0D0,0x83E118))

CODE=bytes.fromhex('f0b5104b00f0e0f80f4c14a507262000296840220d4b00f0d7f88020400024180435013ef3d1200009497022074b00f0cbf8f0bc08bc9e46064908680278064b1847000009f7310800c8ff0835b43808006800067c72480801753408e03e0106e03f0106e0400106e0410106e0430106e0420106e0440106f0b581b004000d001600069f009700231a4fbc4600f09df81c3c062c25d8072029003143014220d12035ed086d00f608b601ad1938a00e210288954203d004300139f9d111e00e482d182888290040310988084309d164000a4824182c80013440352c80084b00f073f801b0f0bc08bc9e4603980130054b1847000021f8310840bb010240a30000013b3108c1723408f0b504000d0000f023f820002900044b00f056f8f0bc08bc9e4601bc00470000c1703408f0b50648064980229200064b00f046f8054b00f043f8f0bc08bc184740db0102006800067d1c3108f5763408f0b50da41c25094e094f208880190188c91b0d2901d8002101800234013df4d1044b00f025f8f0bc08bc184740bb010240a30000013b3108ca020a03d60216034a038a0356039603ca030a04d60316044a048a04ea022a03f60236036a03aa037603b603ea032a04f60336046a04aa0418476047')
ASM_SHA='9eb4606dedfe97da62d187d4e292c4200bea85059c8f2494098a03361d2f03a1'
SYMBOLS={'init_bridge': 0, 'draw_bridge': 120, 'frame_bridge': 264, 'late_exit_bridge': 300, 'clear_cells': 344, 'cell_offsets': 400, 'obj_destinations': 92}
ATLAS_SHA='f4c2969cc30d9b68168556c5ddbc05ba2872226d14702fa4e7f89a94d0c92fb5'

_XREF_SITES=((0x3474f6,10),(0x3472b8,8),(0x34769a,10),(0x347700,8))
SPANS=_XREF_SITES+((0x3470c0,2),(0x83e06c,14),(0x83e081,14),
 (0x83e090,2),(0x83e0e8,2),(0x347350,2),(0x34735c,2),(0x347474,2))
INTEREST={x for a,n in SPANS for x in range(a,a+n)}
# Exact immutable-source inventory, including the one non-executable pattern.
# 83DFAC is the little-endian data pointer 0883DB6A in a pointer table;
# its low halfword DB6A also decodes as a Thumb conditional branch to 83E084.
# Keep that data hit explicit, never exempt its whole source/target region.
ORIGINAL_REFS=frozenset((
 ('pointer',0x346e2c,0x83e06c),('pointer',0x346ee0,0x83e06c),
 ('pointer',0x3472dc,0x83e081),('pointer',0x34770c,0x83e0e8),
 ('pointer',0x347784,0x83e090),('pointer',0x347788,0x83e0e8),
 ('pointer',0x83e0a0,0x347351),('pointer',0x83e0a8,0x34735d),
 ('pointer',0x83e0f8,0x347475),('thumb_bl',0x347446,0x347700),
 ('thumb_bl',0x34769a,0x3470c0),('thumb_cond',0x83dfac,0x83e084)))

def overlap(a,n):return any(a<s+z and s<a+n for s,z in _XREF_SITES)
def inside(t):return any(a<t<a+n for a,n,_ in SITES)

def inventory(b):
 refs=set();length=len(b)
 # Absolute pointers at EVERY alignment, including callbacks outside native text.
 for target in INTEREST:
  needle=struct.pack('<I',0x08000000+target);start=0
  while True:
   a=b.find(needle,start)
   if a<0:break
   refs.add(('pointer',a,target));start=a+1
 # All Thumb BL candidates; raw data patterns remain in the review inventory.
 for m in re.finditer(rb'(?=([\x00-\xff][\xf0-\xf7][\x00-\xff][\xf8-\xff]))',b):
  a=m.start()
  if a&1:continue
  h,l=struct.unpack_from('<HH',b,a);d=((h&2047)<<12)|((l&2047)<<1);d=d-0x800000 if d&0x400000 else d;t=a+4+d
  if t in INTEREST:refs.add(('thumb_bl',a,t))
 # Short branch/PC-data instructions can only reach nearby addresses.
 near=set()
 for a,n in SPANS:near.update(range(max(0,(a-2052)&~1),min(length-2,a+n+2052),2))
 for a in near:
  h=struct.unpack_from('<H',b,a)[0];t=None;kind=None
  if h&0xf800==0xe000:
   d=(h&2047)<<1;t=a+4+(d-4096 if d&2048 else d);kind='thumb_b'
  elif h&0xf000==0xd000 and h&0x0f00<0x0e00:
   d=(h&255)<<1;t=a+4+(d-512 if d&256 else d);kind='thumb_cond'
  elif h&0xf800 in (0x4800,0xa000):
   t=((a+4)&~3)+(h&255)*4;kind='thumb_ldr'if h&0xf800==0x4800 else'thumb_adr'
  if t is not None and(t in INTEREST or kind=='thumb_ldr'and overlap(t,4)):refs.add((kind,a,t))
 # ARM B/BL, PC-relative literal load, and ADR ADD/SUB immediate at all word alignments.
 for a in range(0,length-3,4):
  w=struct.unpack_from('<I',b,a)[0]
  if w>>28==15:continue # ARMv4T has no cond=1111 BLX encoding.
  t=None;kind=None
  if w&0x0e000000==0x0a000000:
   d=(w&0xffffff)<<2;t=a+8+(d-0x4000000 if d&0x2000000 else d);kind='arm_bl'if w&0x1000000 else'arm_b'
  elif w&0x0f7f0000==0x051f0000:
   d=w&4095;t=a+8+(d if w&0x800000 else-d);kind='arm_ldr'
  elif w&0x0fef0000 in(0x028f0000,0x024f0000):
   value=w&255;rotate=((w>>8)&15)*2;d=((value>>rotate)|(value<<(32-rotate)))&0xffffffff if rotate else value
   t=(a+8+(d if w&0x800000 else-d))&0xffffffff;kind='arm_adr'
  if t is not None and(t in INTEREST or kind=='arm_ldr'and overlap(t,4)):refs.add((kind,a,t))
 return sorted(refs)

@lru_cache(maxsize=1)
def original_inventory(b):return inventory(b)

def _validate_original_inventory(refs):
 # Comparing current==original alone cannot prove an original entry was safe.
 # No branch/pointer enters a rewritten instruction interior, and no PC load
 # reads any rewritten instruction bytes (even if its word starts before it).
 for kind,source,target in refs:
  if inside(target) or (kind in ('thumb_ldr','arm_ldr') and
    any(target<a+n and a<target+4 for a,n,_ in SITES)):
   raise ValueError(f'original hook interior/PC-data reference unsupported: {(kind,source,target)}')
 if set(refs)!=ORIGINAL_REFS:
  raise ValueError('original coordinate/parent/init reference contexts unsupported')

def _verify_xrefs(o,c):
 base=original_inventory(o);actual=inventory(c)
 _validate_original_inventory(base)
 if o[0x83dfac:0x83dfb0]!=bytes.fromhex('6adb8308'):
  raise ValueError('reviewed pointer-table branch pattern changed')
 if base!=actual:
  added=sorted(set(actual)-set(base));removed=sorted(set(base)-set(actual));raise ValueError(f'global incoming branch/pointer/PC-reference changed: +{added[:4]} -{removed[:4]}')
 # Original ROM has only this direct cleanup caller and no entry callback pointer.
 cleanup=[v for v in actual if v[2]in(0x347700,0x347701)]
 if cleanup!=[('thumb_bl',0x347446,0x347700)]:raise ValueError(f'cleanup entry context unsupported: {cleanup}')
 # Native frame caller is unique too; no new direct/absolute consumer is accepted.
 frame=[v for v in actual if v[2]in(0x3470c0,0x3470c1)]
 if frame!=[('thumb_bl',0x34769a,0x3470c0)]:raise ValueError(f'frame consumer context unsupported: {frame}')
 return actual

CELL_OFFSETS=tuple(v for side in(0,16) for i in range(7) for v in ((11+2*(i//2))*64+(side+5+6*(i%2))*2,(12+2*(i//2))*64+(side+5+6*(i%2))*2))

def obj_destinations(b):
 # Native 3474A8 resets banks, 3474B4 initializes bank0 at base + cursor*32.
 # 31F624 resets count=0 and sets the first cursor; every 31F708 load adds w*h.
 if b[0x3474b0:0x3474b4]!=bytes.fromhex('00201623'):raise ValueError('bank init args changed')
 base,cursor=struct.unpack_from('<II',b,0x347528)
 if (base,cursor)!=(0x06010000,0x1f7):raise ValueError('bank base/cursor changed')
 sequence=[]
 for a in range(0x3474b8,0x3474fa,6):
  if struct.unpack_from('<H',b,a)[0]&0xff00!=0x2000:raise ValueError('native load is not immediate ID')
  h,l=struct.unpack_from('<HH',b,a+2);d=((h&0x7ff)<<12)|((l&0x7ff)<<1);d=d-0x800000 if d&0x400000 else d
  if h&0xf800!=0xf000 or l&0xf800!=0xf800 or a+6+d!=0x31f708:raise ValueError('native load call changed')
  sequence.append(b[a])
 if sequence!=[28,29,30,31,33,32,34,44,45,46,57]:raise ValueError('bank loading order changed')
 result={}
 for native_id in sequence:
  if native_id>61:raise ValueError('not native family0')
  w,h=b[0x8071c0+native_id*4:0x8071c0+native_id*4+2]
  if native_id in range(28,35) and (w,h)!=(4,2):raise ValueError('movement dimensions changed')
  result[native_id]=base+(cursor&1023)*32;cursor+=w*h
 if cursor>1024:raise ValueError('native bank wraps')
 return tuple(result[i]for i in range(28,35))

def validate_parent_script(b):
 expected=((0x0833548d,0,2),(0,1,0),(0x08347351,0,2),(0x0834735d,0,1),(0,1,0),(0x083476f5,0,2),(0x0833549d,0,2),(0,0,7))
 actual=tuple(struct.unpack_from('<IHH',b,0x83e090+i*8)for i in range(8))
 if actual!=expected:raise ValueError('parent lifecycle script changed')
 # Destructor clears exactly1024 halfwords of BG0shadow before returning.
 if struct.unpack_from('<I',b,0x3476f0)[0]!=1023 or struct.unpack_from('<I',b,0x814fb0)[0]!=0x0201bb40:raise ValueError('native BG0 destructor layout changed')

def validate(o,c):
 if len(o)!=0x1000000 or len(c)!=len(o)or hashlib.sha256(o).hexdigest()!=ORIGINAL_SHA:raise ValueError('wrong original/current ROM extent or original hash')
 for a,z in NATIVE_SPANS:
  if o[a:z]!=c[a:z]:raise ValueError(f'native source/consumer changed {a:06X}')
 if any(o[CAVE:CAVE+CAPACITY])or any(c[CAVE:CAVE+CAPACITY]):raise ValueError('private region not pristine')
 validate_parent_script(o);validate_parent_script(c)
 if obj_destinations(o)!=obj_destinations(c):raise ValueError('OBJ destination drift')
 if struct.unpack_from('<I',o,0x31970c)[0]!=0x08814fc0 or struct.unpack_from('<I',o,0x814fc0)[0]!=0x0201db40:raise ValueError('native source literal chain changed')
 # Normal-domain CO/power/weather source and 7x32 movement tables are immutable.
 pointers=set()
 for co in range(19):
  for power in range(3):
   for weather in range(3):
    a=0x9FC418+260*co+68*power+4*weather+0x50
    if o[a:a+4]!=c[a:a+4]:raise ValueError('movement pointer changed')
    pointers.add(struct.unpack_from('<I',o,a)[0]-0x08000000)
 if len(pointers)!=7:raise ValueError('unexpected movement table count')
 for a in pointers:
  if not 0<=a<=len(o)-224 or o[a:a+224]!=c[a:a+224]or not set(o[a:a+224])<={1,2,3,4,255}:raise ValueError('movement cost source changed')
 _verify_xrefs(o,c)


LEFTS=((7,6,7,7,7,7,7,8,9),(13,13,12,11,12,13,14,14,15),(12,11,11,11,11,11,10,11,12),(6,7,7,6,6,6,6,6,7),(12,12,12,12,14,11,11,11,12),(17,17,17,19,21,18,18,18,19),(13,13,13,13,13,13,14,14,15))
EXTRA_TOP={31:20,32:25,33:24,34:25}
def caption_mask(native):
 mask={(x,y)for y,left in enumerate(LEFTS[native-28],7)for x in range(left,32)}
 if native in EXTRA_TOP:mask|={(x,6)for x in range(EXTRA_TOP[native],32)}
 return mask

def render(original):
 if len(original)!=0x1000000 or hashlib.sha256(original).hexdigest()!=ORIGINAL_SHA:raise ValueError('wrong immutable original')
 if hashlib.sha256(FONT.read_bytes()).hexdigest()!=FONT_SHA256:raise ValueError('Galmuri7 font changed')
 font=load_bdf(str(FONT))[0];blobs=[]
 for i,label in enumerate(LABELS):
  a=0x454494+i*256
  old=[[original[a+((y//8)*4+x//8)*32+(y%8)*4+(x%8)//2]>>(4*(x%2))&15 for x in range(32)]for y in range(16)]
  new=[row+[0]*8 for row in old];mask=caption_mask(28+i)
  for x,y in mask:new[y][x]=0
  glyphs=[glyph_grid(font[ord(c)])for c in label];width=sum(g[1]for g in glyphs)+len(glyphs)-1;cursor=39-width;ink=set()
  for bitmap,w,h,xoff,yoff in glyphs:
   if xoff!=0:raise ValueError('reviewed Galmuri7 bearing changed')
   ink|={(cursor+x,8+y+7-h-yoff)for y in range(h)for x in range(w)if bitmap[y][x]};cursor+=w+1
  edge={(x+dx,y+dy)for x,y in ink for dx in(-1,0,1)for dy in(-1,0,1)}
  if not ink or any(not(0<=x<40 and 0<=y<16)for x,y in edge):raise ValueError('movement caption clipped')
  if any(x<32 and(x,y)not in mask and old[y][x]for x,y in edge):raise ValueError('movement caption overlaps protected icon')
  for x,y in edge:new[y][x]=4
  for x,y in ink:new[y][x]=1
  if any(new[y][x]!=old[y][x]for y in range(16)for x in range(32)if(x,y)not in mask and old[y][x]):raise ValueError('protected icon changed')
  def pack(x0,width):
   return bytes(new[ty*8+y][x0+tx*8+x]|new[ty*8+y][x0+tx*8+x+1]<<4 for ty in range(2)for tx in range(width//8)for y in range(8)for x in range(0,8,2))
  blobs.append((pack(0,32),pack(32,8)))
 atlas=b''.join(body for body,tail in blobs)+b''.join(tail for body,tail in blobs)
 if len(atlas)!=2240 or hashlib.sha256(atlas).hexdigest()!=ATLAS_SHA:raise ValueError('reviewed movement atlas changed')
 return atlas

def expected_writes(original):
 if hashlib.sha256(ASM.read_bytes()).hexdigest()!=ASM_SHA:raise ValueError('movement ASM source changed; reassemble/review embedded code')
 if struct.unpack_from('<7I',CODE,SYMBOLS['obj_destinations'])!=obj_destinations(original):raise ValueError('OBJ destinations differ from reviewed code')
 writes=[(CAVE,CODE),(ATLAS,render(original)),(0x83e0b8,struct.pack('<I',0x08000000+CAVE+SYMBOLS['late_exit_bridge']+1))]
 for a,n,name in SITES:
  payload=(b'\xc0\x46'if a%4 else b'')+b'\x00\x4b\x18\x47'+struct.pack('<I',0x08000000+CAVE+SYMBOLS[name]+1)
  if len(payload)!=n:raise ValueError('invalid trampoline extent')
  writes.append((a,payload))
 coords=bytearray(original[0x83e081:0x83e08f]);costs=bytearray(original[0x83e06c:0x83e07a])
 if coords!=bytes([6,88,62,88,6,104,62,104,6,120,62,120,6,136]) or costs!=bytes([5,11,12,11,5,13,12,13,5,15,12,15,5,17]):raise ValueError('terrain coordinate table changed')
 for i in(2,6,10):coords[i]=54
 for i in(0,4,8,12):costs[i]=6
 writes.extend(((0x83e081,bytes(coords)),(0x83e06c,bytes(costs))))
 writes.sort()
 if len(CODE)>ATLAS-CAVE or ATLAS+2240>CAVE+CAPACITY:raise ValueError('private cave capacity exceeded')
 if any(a+len(x)>z for (a,x),(z,y)in zip(writes,writes[1:])):raise ValueError('movement writes overlap')
 return writes

def patch(rom,original):
 original=bytes(original);validate(original,rom);writes=expected_writes(original)
 for address,payload in writes:rom[address:address+len(payload)]=payload
 return {'labels':7,'additional_oam':0,'code_bytes':len(CODE),'atlas_bytes':2240,'reservation':[hex(CAVE),hex(CAVE+CAPACITY)],'writes':[{'address':hex(a),'size':len(v),'sha256':hashlib.sha256(v).hexdigest()}for a,v in writes]}

def _verify_fixed(rom,original):
 original=bytes(original);writes=expected_writes(original);normalized=bytearray(rom)
 for address,payload in writes:
  if address!=ATLAS and bytes(rom[address:address+len(payload)])!=payload:raise ValueError(f'movement fixed writer overwritten at {address:06X}')
  normalized[address:address+len(payload)]=original[address:address+len(payload)]
 # Entire private reservation is guarded, including holes between code and atlas.
 validate(original,normalized)
 return writes

def verify_generated(rom,original):
 for address,payload in _verify_fixed(rom,original):
  if bytes(rom[address:address+len(payload)])!=payload:raise ValueError('movement generated atlas overwritten before editor')

def capture_regions(rom,original):
 writes=_verify_fixed(rom,original)
 regions={a:bytes(rom[a:a+len(v)])for a,v in writes}
 for a,z in((CAVE+len(CODE),ATLAS),(ATLAS+2240,CAVE+CAPACITY)):regions[a]=bytes(rom[a:z])
 return regions

def verify_regions(rom,original,regions):
 writes=_verify_fixed(rom,original);sizes={a:len(v)for a,v in writes}
 sizes.update({CAVE+len(CODE):ATLAS-CAVE-len(CODE),ATLAS+2240:CAVE+CAPACITY-ATLAS-2240})
 if set(regions)!=set(sizes)or any(len(regions[a])!=n for a,n in sizes.items()):raise ValueError('movement final snapshot extents changed')
 for a,n in sizes.items():
  if bytes(rom[a:a+n])!=regions[a]:raise ValueError(f'movement final writer changed at {a:06X}')

def editor_labels():
 # One40x112 visual atlas, permuting the same70 tiles from7 bodies+7 tails.
 perm=[tile for i in range(7)for y in range(2)for tile in(*range(i*8+y*4,i*8+y*4+4),56+i*2+y)]
 return [{'text':' / '.join(LABELS),'off':ATLAS,'tw':5,'th':14,'perm':perm}]
