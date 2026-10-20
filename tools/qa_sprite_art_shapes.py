"""Audit final art-text tiles and reference stroke runs for every changed family.

A PASS verifies the listed glyph column topology and exact renderer payload.
It is not proof of all game assets or human-readable semantics of every jamo.
"""
import sys,json,hashlib,struct
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter


def compact_hada_shape(char, raw):
 """Independent Hada topology oracle in the approved 20x22/19px cell.

 The font outlines supply the reference ink. The declared 23-to-19 cell
 sampling only places that ink; no production glyph or compact_glyph output
 supplies expected pixels or topology.
 """
 import aw_fonts
 import qa_sprite_shape as shape
 from aw_fonts import obj_canvas
 layers=[]
 for path in (aw_fonts.hadasans_path(),aw_fonts.hadasans_black_path()):
  high=Image.new('L',(768,768))
  ImageDraw.Draw(high).text((40,0),char,font=ImageFont.truetype(path,384),fill=255)
  layers.append(high)
 boxes=[layer.point(lambda v:255 if v>=128 else 0).getbbox() for layer in layers]
 if None in boxes:raise AssertionError('missing pinned Hada outline: '+char)
 box=tuple(fn(b[i] for b in boxes) for i,fn in enumerate((min,min,max,max)))
 face=layers[0].crop(box).resize((20,22),Image.Resampling.LANCZOS).point(lambda v:255 if v>=128 else 0)
 guide=layers[1].crop(box).resize((20,22),Image.Resampling.LANCZOS)
 font_face=Image.new('L',(32,32));font_face.paste(face,(1,3))
 rim=Image.new('L',(32,32));rim.paste(guide,(1,3));rim=rim.filter(ImageFilter.MaxFilter(3))
 edge=rim.point(lambda v:255 if v>=128 else 0).getbbox()
 if edge is None:raise AssertionError('blank pinned Hada outline: '+char)
 # The rim's native one-pixel shadow extends the source cell by one pixel.
 left,right=edge[0],edge[2]
 width=right-left+1;target=min(19,width);start=min(left,19-target)
 reference=Image.new('L',(32,32))
 for x in range(target):
  source_x=left+min(width-1,(2*x+1)*width//(2*target))
  for y in range(32):reference.putpixel((start+x,y),font_face.getpixel((source_x,y)))
 actual_grid=obj_canvas(raw,1,4,4)
 actual=Image.new('L',(32,32))
 actual.putdata([255 if value==6 else 0 for row in actual_grid for value in row])
 full_ink=[(x,y) for y,row in enumerate(actual_grid) for x,value in enumerate(row) if value]
 failures=[]
 if not full_ink or max(x for x,_ in full_ink)>=19 or max(y for _,y in full_ink)>=32:
  failures.append('compact mission-title ink outside 19px cell or blank')
 if actual.getbbox() is None:
  failures.append('compact mission-title face blank')
  return dict(character=char,failures=failures,gap_columns=0)
 result=shape.compare(char,actual,reference)
 failures.extend(result['failures'])
 # Each reference jamo component must retain its own strokes. This also
 # catches a dropped attached stroke that leaves the component count intact.
 ref_pixels=shape._cells(reference);actual_pixels=shape._cells(actual)
 for component in shape.components(reference):
  if len(component & actual_pixels)<.9*len(component):
   failures.append('Hada component stroke missing')
   break
 def strokes(cells,axis,n):
  values=[(n,y) in cells for y in range(32)] if axis=='x' else [(x,n) in cells for x in range(32)]
  return sum(value and (i==0 or not values[i-1]) for i,value in enumerate(values))
 gaps=[]
 for axis in ('x','y'):
  for n in range(32):
   expected=strokes(ref_pixels,axis,n)
   if expected>=2 and strokes(actual_pixels,axis,n)<expected:gaps.append((axis,n))
 if gaps:failures.append('Hada jamo stroke gap removed')
 result.update(failures=failures,gap_columns=sum(strokes(ref_pixels,'x',x)>=2 for x in range(32)),closed_lines=gaps[:8],reference='independent pinned Hada Sans Bold/Black topology; approved 20x22 raster and 19px cell')
 return result
import argparse
parser=argparse.ArgumentParser()
parser.add_argument('rom',type=Path)
parser.add_argument('--report',type=Path,required=True)
parser.add_argument('--shape',action='store_true')
parser.add_argument('--baseline', type=Path, required=True,
                    help='Explicit comparison ROM used only to select changed mission-title art')
parser.add_argument('--baseline-sha256', required=True,
                    help='Expected SHA-256 of the comparison ROM; mismatch fails closed')
args=parser.parse_args()
C=Path(__file__).resolve().parents[1];ROOT=C;OUT=args.report.parent;sys.path.insert(0,str(C/'tools'))
import qa_sprite_shape as shape
import hangul_pixel_fit as fit
import build_title_hangul as t
from qa_visual_regions import assert_title_logo_golden
import build_korean_full as b
import part1_mission_titles as mt
import part1_m19_title as m19
import part1_m20_title as m20
import part1_supply_popup as bubbles
import part2_power_title_glyphs as power2
from test_hangul_sprite_gaps import BIG,SMALL
from aw_fonts import obj_canvas
from lz77_scan import lz77_decompress
rom=args.rom.read_bytes(); before=args.baseline.read_bytes();original=(ROOT/'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
if hashlib.sha256(before).hexdigest() != args.baseline_sha256.lower():
 parser.error('baseline SHA-256 mismatch')
if len(rom) != len(original) or hashlib.sha256(original).hexdigest() != power2.ORIGINAL_SHA256:
 parser.error('candidate length or immutable Japan ROM identity changed')
rows=[];failures=[];unverified=[];assets=set()
# Pinned, user-approved plate geometry (b20, 2026-10-13); independent of the generator.
PLATE_PROFILE=json.loads((ROOT/'data/part2_mode_plate_geometry.json').read_text(encoding='utf-8'))
for _t,_want in PLATE_PROFILE['labels'].items():
 if fit.plate_width_scale(_t)!=_want['width_scale']:failures.append(dict(asset=_want['asset'],reason='plate scale differs from pinned profile'))
 if hashlib.sha256(lz77_decompress(rom,int(_want['asset'],16))[0]).hexdigest()!=_want['decompressed_plate_sha256']:
  failures.append(dict(asset=_want['asset'],reason='final plate differs from pinned approved profile'))
def image(g):
 im=Image.new('L',(len(g[0]),len(g)));im.putdata([v for r in g for v in r]);return im
def audit_hada_mission_glyph(asset,ch,raw):
 # Raster consistency at the user-approved 20x22 Bold/Black union geometry.
 # This check does not establish topology preservation through resizing.
 import aw_fonts
 layers=[]
 for path in (aw_fonts.hadasans_path(),aw_fonts.hadasans_black_path()):
  font=ImageFont.truetype(path,384)
  layer=Image.new('L',(768,768));ImageDraw.Draw(layer).text((40,0),ch,font=font,fill=255)
  layers.append(layer)
 boxes=[layer.point(lambda v:255 if v>=128 else 0).getbbox() for layer in layers]
 box=(min(z[0] for z in boxes),min(z[1] for z in boxes),max(z[2] for z in boxes),max(z[3] for z in boxes))
 ref=layers[0].crop(box).resize((20,22),Image.Resampling.LANCZOS).point(lambda v:255 if v>=128 else 0)
 actual=image(obj_canvas(raw,1,4,4)).point(lambda v:255 if v==6 else 0)
 actual=actual.crop(actual.getbbox())
 ref=ref.crop(ref.getbbox())
 if args.shape:result=shape.compare(ch,actual,reference=ref)
 else:result=dict(character=ch,gap_columns=sum(sum(v for v,_,_ in fit.runs([ref.getpixel((x,y)) for y in range(ref.height)]))>=2 for x in range(ref.width)),failures=[] if actual.size==ref.size and actual.tobytes()==ref.tobytes() else ['Hada Bold face differs from pinned outline'])
 result.update(asset=asset,label=ch,reference='pinned Hada Sans Bold 20x22 raster consistency')
 rows.append(result);assets.add(asset)
 if result['failures']:failures.append(result)
def audit(asset,text,img,records,inks):
 assets.add(asset)
 for ch,box in records:
  if not args.shape and not fit.dense_syllable(ch):continue
  crop=img.crop(box);mask=Image.new('L',crop.size);mask.putdata([255 if v in inks else 0 for v in crop.getdata()])
  big = asset in {hex(off) for off,_ in BIG}
  if args.shape and big: result=shape.compare_plate(ch,mask,PLATE_PROFILE['labels'][text]['width_scale'])
  else: result=(shape.compare(ch,mask) if args.shape else fit.verify_glyph(ch,mask))
  if not args.shape and asset in {hex(off) for off,_ in BIG}:
   ref=fit.plate_glyph(ch,fit.plate_width_scale(text))
   result=dict(character=ch,gap_columns=sum(sum(v for v,_,_ in fit.runs([ref.getpixel((x,y)) for y in range(ref.height)]))>=2 for x in range(ref.width)),failures=[] if mask.size==ref.size and mask.tobytes()==ref.tobytes() else ['final plate differs from full glyph with open counters'])
  result.update(asset=asset,label=text,box=box)
  rows.append(result)
  if result['failures']:failures.append(result)
def same(asset,actual,expected):
 if actual!=expected:failures.append(dict(asset=asset,reason='final ROM differs from renderer'))
def bitmap_audit(asset,ch,actual,grid):
 ref=image([[255 if v else 0 for v in r] for r in grid])
 if args.shape:
  result=shape.compare(ch,actual,ref);result.update(asset=asset,label=ch,reference='native Galmuri BDF')
  rows.append(result)
  if result['failures']:failures.append(result)
for _,off,text,size in t.PART1_MODE_OPTION_BLOCKS:
 raw=lz77_decompress(rom,off)[0];render=t.make_part1_option_block(text,size)
 same(hex(off),raw,t.option_layer_to_tiles(render));_,records=t.part1_option_body(text,size)
 audit(hex(off),text,image(obj_canvas(raw,2,8,4)),records,set(range(1,7)))
# Regenerate the ENTIRE indexed plate payload from immutable source, including
# spacing, background, native borders, and caption strips. No glyph-only mask.
plates=bytearray(original);b.patch_part2_mode_menu_obj_labels(plates)
for off,text in BIG+SMALL:
 same(hex(off),lz77_decompress(rom,off)[0],lz77_decompress(plates,off)[0])
 assets.add(hex(off))
link_plates=bytearray(original);b.patch_part2_link_mode_residual_labels(link_plates)
same('0x54e538',lz77_decompress(rom,0x54E538)[0],lz77_decompress(link_plates,0x54E538)[0])
assets.add('0x54e538')
if args.shape:
 from part2_link_plates import canvas,draw_hada_main
 link_raw=lz77_decompress(rom,0x54E538)[0]
 for link_off,link_text in ((0,'1팩 대전'),(0x800,'멀티팩 대전'),(0x1000,'맵 교환')):
  actual=canvas(link_raw,link_off,64,32)
  _,glyph_boxes=draw_hada_main(link_text,with_records=True)
  for ch,box in glyph_boxes:
   mask=actual.crop(box).point(lambda v:255 if v==1 else 0)
   result=shape.compare(ch,mask,shape.hada_uniform_reference(ch,23))
   result.update(asset=f'0x54e538+0x{link_off:x}',label=link_text,box=box,
                 reference='independent Hada Sans outline and glyph topology')
   rows.append(result)
   if result['failures']:failures.append(result)
for off,text in BIG:
 im=image(obj_canvas(lz77_decompress(rom,off)[0],2,8,4));_,records=fit.plate_line(text)
 try:fit.verify_plate_ink(im,text)
 except AssertionError as exc:failures.append(dict(asset=hex(off),reason=str(exc)))
 if any(im.getpixel((x,y))!=5 for y in range(23,30) for x in range(4,124)):
  failures.append(dict(asset=hex(off),reason='caption strip is not blank'))
 ox,oy=fit.PLATE_ORIGIN;records=[(c,(a+ox,y+oy,d+ox,e+oy)) for c,(a,y,d,e) in records];audit(hex(off),text,im,records,set(fit.PLATE_BODY_INDICES))
# The whole title layer is packed through its real sprite list and compared
# with the final ROM. The approved OkDanDan logo is rendered as one resized
# mask, so the old per-glyph fit.line() boxes do not describe its final ink.
# Pinned crop hashes and footprints cover all five approved logo placements.
repro=bytearray(original);b.patch_title_hangul_assets(repro)
for off,func,logos in [(t.TITLE_OBJ_LZ77_OFF,t.make_title_index_layer,(('shared','어드밴스워즈',(23,24,211,53)),)),(t.SELECT_OBJ_LZ77_OFF,t.make_select_index_layer,(('select_top','어드밴스 워즈',(17,14,204,52)),('select_bottom','어드밴스 워즈',(25,91,212,124)))),(t.PART1_TITLE_OBJ_LZ77_OFF,t.make_part1_index_layer,(('part1','어드밴스 워즈',(17,18,207,60)),)),(t.PART2_TITLE_OBJ_LZ77_OFF,t.make_part2_index_layer,(('part2','어드밴스 워즈',(19,21,207,52)),))]:
 same(hex(off),lz77_decompress(rom,off)[0],lz77_decompress(repro,off)[0]);im=func()
 for name,text,box in logos:
  try:
   evidence=assert_title_logo_golden(name,im)
  except AssertionError as exc:
   failures.append(dict(asset=hex(off),label=text,box=box,reason=str(exc)))
  else:
   rows.append(dict(asset=hex(off),label=text,box=box,reference='approved OkDanDan logo footprint and crop SHA-256',evidence=evidence,gap_columns=0,failures=[]))
  assets.add(hex(off))
# Recover per-glyph coordinates from the same native baseline operation;
# validate the final ROM's ink, after outline/shadow composition.
old_native=fit.native_mask;captures=[]
def capture(*args,**kwargs):
 mask,records=old_native(*args,**kwargs);captures.append((mask.copy(),records));return mask,records
fit.native_mask=capture
for source,*_ in mt.TITLES:
 raw=lz77_decompress(rom,source)[0]
 if raw==lz77_decompress(before,source)[0]:continue
 expected=mt.render(source);same(hex(source),raw,expected);size=mt.chosen_size(source);text=mt._text(source)
 if size is None:
  unverified.append(dict(asset=hex(source),reason='Galmuri fallback changed; separate component oracle required'));continue
 width=160 if source==mt.EXTENSION_OWNER else 128;captures.clear();mt._ink_okdandan(text,width,size)
 im=image(mt._pixels(text,width,size));mask,records=captures[-1]
 actual=image([[255 if v==10 else 0 for v in r] for r in mt._pixels(text,width,size)]).getbbox();bb=mask.getbbox();dx=actual[0]-bb[0];dy=actual[1]-bb[1]
 audit(hex(source),text,im,[(ch,(a+dx,bb+dy,c+dx,d+dy)) for ch,(a,bb,c,d) in records],{10})
for module in (m19,m20):
 raw=lz77_decompress(rom,module.SOURCE)[0];same(hex(module.SOURCE),raw,module.render())
 # Byte comparison binds the production fitted mask; dense glyph audit is
 # collected below from independently reconstructed final ink coordinates.
 captures.clear();ink,_=b.aw_fonts.okdandan_ink(module.TEXT,(2,2,126,30),0,size=20)
 im=image(obj_canvas(raw,2,8,4));mask,records=captures[-1];actual=im.point(lambda v:255 if v==10 else 0).getbbox();bb=mask.getbbox();dx=actual[0]-bb[0];dy=actual[1]-bb[1]
 audit(hex(module.SOURCE),module.TEXT,im,[(ch,(a+dx,bb+dy,c+dx,d+dy)) for ch,(a,bb,c,d) in records],{10})
# The denominator comes from the adopted, delivered population, never from
# candidate terminators or pointers. Compare every field and the terminator.
from part2_mission_title_fit import TABLE, GLYPHS, END, BASE as COMPACT_BASE, compact_glyph
codes={int(v,16):k for k,v in json.loads((C/'data/syllable_to_code_2350.json').read_text()).items()}
population=json.loads((C/'data/sprite_audit_population.json').read_text())
tables={}
for name,start,limit in [('private',b.MISSION_TITLE_TABLE_FILE,b.MISSION_TITLE_GLYPH_FILE),('compact',TABLE,GLYPHS)]:
 spec=population['tables'][name];entries=spec['entries']
 if spec['offset']!=start or not entries or start+12*(len(entries)+1)>limit:
  raise AssertionError('invalid authoritative table population: '+name)
 if len({e[0] for e in entries})!=len(entries):raise AssertionError('duplicate expected code')
 expected=b''.join(struct.pack('<HHII',*e) for e in entries)+bytes(12)
 same(name+' table (codes/pointers/advances/terminator)',rom[start:start+len(expected)],expected)
 tables[name]=entries
# Every native entry must retain the immutable Japan table record. Every
# private entry must fit its reserved arena and use the authored advance.
native={}
for pos in range(b.MISSION_TITLE_TABLE_ORIG_FILE,b.MISSION_TITLE_TABLE_ORIG_FILE+0x2000,12):
 entry=struct.unpack_from('<HHII',original,pos)
 if not (0x08000000<=entry[2]<0x09000000 and entry[3]<0x100):break
 native[entry[0]]=entry
base_entries={}
for code,reserved,ptr,adv in tables['private']:
 if code in native:
  if (code,reserved,ptr,adv)!=native[code]:raise AssertionError('expected native entry changed')
 else:
  if not b.MISSION_TITLE_GLYPH_RT<=ptr<0x08000000+COMPACT_BASE or reserved!=0:
   raise AssertionError('expected private pointer outside reserved arena')
  import unicodedata
  char=unicodedata.normalize('NFKC',code.to_bytes(2,'big').decode('shift_jis')) if code not in codes else codes[code]
  expected_adv=b.MISSION_TITLE_SPACE_ADVANCE if code==0x8140 else b.MISSION_TITLE_HANGUL_ADVANCE if code in codes or (len(char)==1 and char.isascii() and char.isalnum()) else 26
  if adv!=expected_adv:raise AssertionError('expected private advance changed')
 base_entries[code]=(ptr,adv)
 off=ptr-0x08000000
 raw=lz77_decompress(rom,off)[0]
 if code in native:
  same(hex(off),raw,lz77_decompress(original,off)[0]);assets.add(hex(off));continue
 if off+lz77_decompress(rom,off)[1]>COMPACT_BASE:raise AssertionError('private glyph exceeds arena')
 if code not in codes:
  import unicodedata
  ch=unicodedata.normalize('NFKC',code.to_bytes(2,'big').decode('shift_jis'))
  expected=b._mission_title_hangul_glyph(ch) if len(ch)==1 and ch.isascii() and ch.isalnum() else b._mission_title_blank_glyph()
  same(hex(off),raw,expected);assets.add(hex(off));continue
 ch=codes[code];off=ptr-0x8000000;raw=lz77_decompress(rom,off)[0];expected=b._mission_title_hangul_glyph(ch);same(hex(off),raw,expected)
 audit_hada_mission_glyph(hex(off),ch,raw)
# Compact long-title copies retain whole source columns, including every y gap.
if [e[0] for e in tables['compact']] != [e[0] for e in tables['private']]:
 raise AssertionError('expected compact population differs from base')
for code,reserved,ptr,adv in tables['compact']:
 off=ptr-0x8000000
 if not GLYPHS<=off<END:
  if (ptr,adv)!=base_entries[code] or reserved!=0:raise AssertionError('expected compact pointer outside arenas')
  continue
 if off+lz77_decompress(rom,off)[1]>END:raise AssertionError('compact glyph exceeds arena')
 sourceptr,sourceadv=base_entries[code]
 assert sourceadv==adv
 source=lz77_decompress(rom,sourceptr-0x8000000)[0];actual=lz77_decompress(rom,off)[0]
 same(hex(off),actual,compact_glyph(source));assets.add(hex(off))
 ch=codes.get(code)
 if ch and args.shape:
  result=compact_hada_shape(ch,actual)
  result.update(asset=hex(off),label=ch)
  rows.append(result)
  if result['failures']:failures.append(result)
 if not ch or not fit.dense_syllable(ch):continue
 grid=obj_canvas(source,1,4,4);out=obj_canvas(actual,1,4,4)
 xs=[x for row in grid for x,v in enumerate(row) if v]
 left,right=min(xs),max(xs);width=right-left+1;target=min(19,width);start=min(left,19-target)
 pairs=[(x,x) for x in range(32)] if right<19 else [(left+min(width-1,(2*x+1)*width//(2*target)),start+x) for x in range(target)]
 bad=[];checked=0
 for sx,dx in pairs:
  expect=[r[sx]==6 for r in grid];observed=[r[dx]==6 for r in out]
  checked+=sum(v for v,_,_ in fit.runs(expect))>=2
  if observed!=expect:bad.append(dict(source_x=sx,dest_x=dx,reason='compact glyph lost source-column gap'))
 result=dict(asset=hex(off),label=ch,character=ch,gap_columns=checked,failures=bad,reference='audited base glyph; exact whole-column projection')
 rows.append(result)
 if bad:failures.append(result)
fit.native_mask=old_native
# Native fixed-size CO glyph cells.
syllables={ch:code for code,ch in codes.items()}
names={int(a,16):name for a,name in b.load_dialogue_overrides(str(C/'data/dialogue_overrides.json')).items()}
dictionary=b.b84_full_power_dictionary(names)
if not dictionary:raise AssertionError('authoritative CO1 dictionary empty')
expected_dict=b''.join(syllables[ch].to_bytes(2,'big') for ch in dictionary)+b'\x81\x40'+bytes(2)
same('CO1 dictionary pointer',rom[0xB3C1F8:0xB3C1FC],struct.pack('<I',0x08000000+b.B84_POWER_DICTIONARY_RELOCATED))
same('CO1 dictionary population',rom[b.B84_POWER_DICTIONARY_RELOCATED:b.B84_POWER_DICTIONARY_RELOCATED+len(expected_dict)],expected_dict)
same('CO1 atlas pointer',rom[0xB3C1F4:0xB3C1F8],struct.pack('<I',0x08000000+b.B84_POWER_GLYPH_LZ77_RELOCATED))
raw=lz77_decompress(rom,b.B84_POWER_GLYPH_LZ77_RELOCATED)[0]
expected_co=bytearray(lz77_decompress(original,b.B84_POWER_GLYPH_LZ77_OFF)[0])
required=(len(dictionary)+1)*256
if len(expected_co)<required:expected_co.extend(bytes(required-len(expected_co)))
for i,ch in enumerate(dictionary):expected_co[i*256:(i+1)*256]=b._b84_power_title_glyph_block(ch)
expected_co[len(dictionary)*256:required]=bytes(256)
same('CO1 complete atlas including blank space',raw,bytes(expected_co))
for i,ch in enumerate(dictionary):
 cell=raw[i*256:(i+1)*256];same('CO1:'+ch,cell,b._b84_power_title_glyph_block(ch));assets.add('CO1:'+ch)
 from bdf import load_bdf,glyph_grid
 font,_=load_bdf(str(C/'reference/fonts/Galmuri11.bdf'));grid,w,h,xo,yo=glyph_grid(font[ord(ch)])
 im=image(obj_canvas(cell,1,2,4));mask=im.point(lambda v:255 if v in (7,2) else 0)
 bitmap_audit('CO1:'+ch,ch,mask,grid)
dictionary=power2.bind_dictionary(rom,b.load_display_overrides(),syllables)
raw=lz77_decompress(rom,power2.OFFSET)[0];same(hex(power2.OFFSET),raw,power2.render(power2.source(original),''.join(dictionary)))
for i,ch in enumerate(dictionary):audit(hex(power2.OFFSET)+':'+ch,ch,image(power2.decode_cell(raw,i)),[(ch,(8,4,24,28))],{1})
# Small plate final pixels: separate native-grid regression suite also checks
# every glyph and the clean outer band rows, not only these gap witnesses.
from bdf import load_bdf,glyph_grid
font,_=load_bdf(str(C/'reference/fonts/Galmuri9.bdf'))
for off,text in SMALL:
 g=obj_canvas(lz77_decompress(rom,off)[0],4,4,2);chars=[glyph_grid(font[ord(c)]) for c in text];w=sum(v[1] for v in chars)+len(chars)-1;h=max(v[2]+v[4] for v in chars);x=4+(120-w)//2;y=3+(9-h)//2;assets.add(hex(off))
 for ch,(grid,w,hh,xo,yo) in zip(text,chars):
  if True:
   actual=image([[255 if g[y+h-hh-yo+rr][x+cc+xo]==1 else 0 for cc in range(w)] for rr in range(hh)])
   bitmap_audit(hex(off),ch,actual,grid)
   bad=[];checked=0
   for col in range(w):
    expect=[r[col] for r in grid];actual=[g[y+h-hh-yo+row][x+col+xo]==1 for row in range(hh)];n=sum(v for v,_,_ in fit.runs(expect));checked+=n>=2
    if actual!=expect:bad.append({'x':col,'reason':'native bitmap mismatch'})
   row=dict(asset=hex(off),label=text,character=ch,gap_columns=checked,failures=bad,reference='Galmuri9 native BDF');rows.append(row)
   if bad:failures.append(row)
  x+=w+1
for off,text,box,_ in bubbles.BUBBLES:
 raw=rom[off:off+1024];same(hex(off),raw,bubbles.bubble(original,off));assets.add(hex(off))
 ink,width=bubbles._ink(text);x0,y0,x1,y1=box;left=x0+(x1-x0-(width+1))//2
 for x,y in ink:
  if bubbles.pixel(raw,left+x,y0+y)!=bubbles.INK:failures.append(dict(asset=hex(off),reason='popup final ink mismatch'))
 font,_=load_bdf(str(C/'reference/fonts/Galmuri7.bdf'));cursor=0
 for ch in text:
  grid,w,h,xo,yo=glyph_grid(font[ord(ch)]);top=7-h-yo
  actual=image([[255 if bubbles.pixel(raw,left+cursor+x+xo,y0+top+y)==bubbles.INK else 0 for x in range(w)] for y in range(h)])
  bitmap_audit(hex(off),ch,actual,grid);cursor+=w+1
for off,capacity,pointers in bubbles.LZ_COPIES:
 same(hex(off),lz77_decompress(rom,off)[0],b''.join(rom[a:a+1024] for a,*_ in bubbles.BUBBLES));assets.add(hex(off))
# Unit-name slots use the native condensed BDF, with one blank column at
# each 8px advance. Read final ROM pixels rather than re-rendered previews.
import part2_compact_unit_labels as units
font,_=load_bdf(str(C/'reference/fonts/Galmuri11-Condensed.bdf'))
for off,text,source_sha,generated_sha in units.COMPACT_LABELS+units.STATUS_LABELS:
 if hashlib.sha256(rom[off:off+units.SLOT_SIZE]).hexdigest()!=generated_sha:
  failures.append(dict(asset=hex(off),reason='complete unit-label payload differs from authoritative generated SHA-256'))
 g=obj_canvas(rom[off:off+256],1,4,2);x=(32-len(text)*8)//2;assets.add(hex(off))
 for ch in text:
  grid,w,h,xo,yo=glyph_grid(font[ord(ch)])
  if True:
   actual=image([[255 if g[2+rr][x+cc+xo]==1 else 0 for cc in range(w)] for rr in range(h)])
   bitmap_audit(hex(off),ch,actual,grid)
   bad=[];checked=0
   for col in range(w):
    expected=[r[col] for r in grid];actual=[g[2+y][x+col+xo]==1 for y in range(h)];checked+=sum(v for v,_,_ in fit.runs(expected))>=2
    if expected!=actual:bad.append({'x':col,'reason':'native condensed glyph mismatch'})
   result=dict(asset=hex(off),label=text,character=ch,gap_columns=checked,failures=bad,reference='Galmuri11-Condensed native BDF');rows.append(result)
   if bad:failures.append(result)
  x+=8
# Result atlases: production paint routine audits final palette ink for each
# dense syllable. Byte-match the independently regenerated entire final sheet.
old_paint=fit.paint_native
context=''
def checked_paint(layer,text,font,origin,fill,*args,**kwargs):
 records=old_paint(layer,text,font,origin,fill,*args,**kwargs)
 audit(context,text,layer,records,{fill})
 return records
fit.paint_native=checked_paint
old_bitmap=fit.paint_bitmap
def checked_bitmap(layer,text,font,origin,fill,*a,**kw):
 records=old_bitmap(layer,text,font,origin,fill,*a,**kw)
 from PIL import ImageDraw
 ref=Image.new('L',layer.size);draw=ImageDraw.Draw(ref);draw.fontmode='1';draw.text(origin,text,font=font,fill=255)
 if args.shape:
  for ch,box in records:
   actual=layer.crop(box).point(lambda v:255 if v==fill else 0)
   result=shape.compare(ch,actual,ref.crop(box));result.update(asset=context,label=text,box=box,reference=Path(font.path).name+':'+str(font.size));rows.append(result)
   if result['failures']:failures.append(result)
 return records
fit.paint_bitmap=checked_bitmap
for name,offsets in [('patch_part2_result_failure_overlay_obj',[0xBFBB54,0xEE8F68]),('patch_part2_result_success_overlay_obj',[0x930520,0x9691A8,0x9A1A4C,0x9DA2F0,0xEE8A64]),('patch_part2_result_congratulations_obj',[0xBFB45C]),('patch_part2_result_summary_obj',[0x59DA5C])]:
 context=name;repro=bytearray(original);getattr(b,name)(repro)
 for off in offsets:
  assets.add(hex(off));same(hex(off),lz77_decompress(rom,off)[0],lz77_decompress(repro,off)[0])
fit.paint_native=old_paint
fit.paint_bitmap=old_bitmap
# Native small Galmuri lines embedded in the reworked title/result sheets.
# Their font raster is independent of the production palette composition.
# Full-sheet comparisons above bind these composed layers to the final ROM.
from PIL import ImageDraw
small_calls=[]
old_text=ImageDraw.ImageDraw.text
context=''
def record_small(draw,xy,text,*a,**kw):
 result=old_text(draw,xy,text,*a,**kw)
 font=kw.get('font');fill=kw.get('fill')
 if font is not None and 'Galmuri' in str(getattr(font,'path','')) and fill in (1,6):
  small_calls.append((context,draw._image,xy,text,font,fill,{fill},getattr(draw,'fontmode','L')))
 return result
ImageDraw.ImageDraw.text=record_small
for name in ['patch_part2_result_congratulations_obj','patch_part2_result_summary_obj']:
 context=name;getattr(b,name)(bytearray(original))
ImageDraw.ImageDraw.text=old_text
# AA prompt compositor: the final layer and its font's exact fractional advances.
old_prompt=t.paint_index_text_aa
context=''
def record_prompt(layer,xy,text,font,fill_idx,stroke_idx,stroke_width,aa_idx=None):
 result=old_prompt(layer,xy,text,font,fill_idx,stroke_idx,stroke_width,aa_idx)
 if fill_idx in (1,10):small_calls.append((context,layer,xy,text,font,fill_idx,{fill_idx,aa_idx or fill_idx},'L'))
 return result
t.paint_index_text_aa=record_prompt
for render in (t.make_title_index_layer,t.make_select_index_layer,t.make_part1_index_layer,t.make_part2_index_layer):
 context=render.__name__;render()
t.paint_index_text_aa=old_prompt
for asset,layer,xy,text,font,fill,inks,fontmode in small_calls:
 ref=Image.new('L',layer.size);d=ImageDraw.Draw(ref);d.fontmode=fontmode
 d.text(xy,text,font=font,fill=255)
 ref=ref.point(lambda v:255 if v >= (96 if len(inks)>1 else 128) else 0)
 x,y=xy
 for i,ch in enumerate(text):
  if ch.isspace():continue
  px=x+font.getlength(text[:i]);bb=d.textbbox((px,y),ch,font=font)
  box=(round(px),int(bb[1]),round(x+font.getlength(text[:i+1])),int(bb[3]))
  actual=layer.crop(box).point(lambda v:255 if v in inks else 0)
  expected=ref.crop(box)
  if args.shape:
   result=shape.compare(ch,actual,expected);result.update(asset=asset,label=text,box=box,reference=Path(font.path).name+':'+str(font.size))
   rows.append(result)
   if result['failures']:failures.append(result)
report=dict(baseline_sha256=args.baseline_sha256,expected_table_entries={k:len(v) for k,v in tables.items()},rom_sha256=hashlib.sha256(rom).hexdigest(),assets_checked=len(assets),checked_assets=sorted(assets),glyph_checks=len(rows),gap_columns=sum(r['gap_columns'] for r in rows),failures=failures,unverified=unverified,checks=rows,limits='Independent Hada compact topology and other uniform-outline/BDF comparison when --shape; approved 20x22 Hada base raster consistency and final raster column gaps otherwise. Exact full-payload binding to final ROM. Human recognition and runtime palette/animation variants still require visual review.')
args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps({k:v if k not in ('failures','unverified') else len(v) for k,v in report.items() if k not in ('checks','checked_assets')},ensure_ascii=False));raise SystemExit(bool(failures or unverified))
