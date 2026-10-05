"""Part 2 purchase-card caption prototype; native icons/palettes stay in place.

The confirmed 15 raw OBJ slots are guarded by their native family/size tables.
Caption edge masks require the accompanying before/after/mask visual review.
"""
from functools import lru_cache
import hashlib
import struct
import part1_unit_type_labels as class_labels

FONT = class_labels.FONT
FONT_SHA256 = class_labels.FONT_SHA256
ASSET_ID = 'objlabel_p2_purchase_captions'
# Left edge of the *visible caption layer*, rows 7..15. The eight move
# captions match exactly to the right of these edges; varying icon pixels
# (14,7),(15,7),(14,8),(14,15) remain outside the mask.
MOVE_LEFT = (16, 15, 12, 12, 12, 14, 14, 14, 15)
SIGHT_LEFT = (6, 5, 5, 5, 6, 7, 7, 7, 8)
SPECS = ((35, 0x454B94, 16, '시야'),) + tuple(
    (36+i, 0x454C94+i*256, 16, '이동') for i in range(8)) + tuple(
    (176+i, 0x45B134+i*512, 32, class_labels.LABELS[6+i]) for i in range(6))
SOURCE_SHA = {4541332: '261124c7466f2354906b5420fef58d725ad61d2708ab7f710e63ea038680f6cc', 4541588: 'd22c2c91816fb110b0bd37fc75121594c1a853c09cdef0bdaf51531ce9752c87', 4541844: '04b84a6b7c7a74d8e1c5e9bf6be0146a3d444111d95a6f57a14fd27e009b5aef', 4542100: '8e9ea4ab738bdb28bfd7776ce73c80ee2f71f9e149ce9bdd48911be9c1f5819e', 4542356: 'e8a523d7874507d48d1bebe0b91398691dbf72aa6b405519c8d44aa26c9b324c', 4542612: '2e3640a8f5db63f12e1f21dd3fa9d01619289ca0083ea79789564b79ddce7971', 4542868: '811af1c4c0d1cb11005231103d13c6d36c23196afe3e17a7542cee4363d98ac6', 4543124: 'a4fb2201ef2d73dd46b2bec8b8f894e1d41d35daf789caf74ff03d2af910255e', 4543380: '2e724a724fe170d6526e122e53e622c2b5ca51c690103b3b276d81657edd7db0', 4567348: '10a5da5241ea2996ebf9b938ac561c28fb56bf6a710c2eb1a4629afd3de1b4da', 4567860: '8c510141fc4034440eb032062ca50db85a59b193b05fd77c442e3c934a282a36', 4568372: '3d18973997c15033a67bd0176a8f9ce9d41016add3d19467ed65008f79107900', 4568884: 'fcbc6b02529d11d28864db4cc3148251b3438bfe5daa958fef6c438cb7ba7069', 4569396: '92e88199cac59dcef213719662c24518a06ad573aa07da2c707d1054c8be7518', 4569908: 'a74361a51635bb5f60474c8fa1b920b689e66f9b4a6dd23f82f20f0fbe01f4c2'}
GUARDS = ((3274316, 3274352, 'a6d8828114fd60b57efc68afd90d87af394517ab340acedb94e9b3040aa98ad1'), (3274964, 3275104, '46b169a18fcef103e07dbc277f657f4fefe61691c76961d20f776914a98716db'), (8417656, 8418456, '1feb2cbcebb5a6ae9ad51ad0c075ba18a9c58d9c3f7ac275b573cfa7f6551f98'), (4582260, 4582292, '718d8be2ab2918cbbca9bc12459a9a78ea3d2209003c59dd01a674327e0f6115'), (4582356, 4582388, 'f8719fbbd9b0e371fc6c29c2b8311350c0e35edede679d607f55caaeaeaa440a'))


def pixels(raw, height):
    if len(raw) != 32 * height // 2:
        raise AssertionError('purchase caption raw size changed')
    return [[(raw[((y//8)*4+x//8)*32+(y%8)*4+(x%8)//2] >> (4*(x%2))) & 15
             for x in range(32)] for y in range(height)]


def pack(grid):
    height = len(grid)
    result = bytearray(32*height//2)
    for y in range(height):
        for x in range(0,32,2):
            result[((y//8)*4+x//8)*32+(y%8)*4+(x%8)//2] = grid[y][x] | grid[y][x+1]<<4
    return bytes(result)


def caption_mask(native_id, height):
    if height == 32:
        return {(x,y) for y in range(21,30) for x in range(32)}
    left = SIGHT_LEFT if native_id == 35 else MOVE_LEFT
    return {(x,y) for y,l in enumerate(left,7) for x in range(l,32)}


def validate_source(original, current=None):
    if len(original) != 0x1000000 or (current is not None and len(current) != len(original)):
        raise AssertionError('purchase captions require full matching ROM sizes')
    for address,end,digest in GUARDS:
        raw = original[address:end]
        if hashlib.sha256(raw).hexdigest() != digest:
            raise AssertionError(f'purchase native source guard changed: {address:08X}')
        if current is not None and current[address:end] != raw:
            raise AssertionError(f'purchase native consumer/palette guard changed: {address:08X}')
    for native_id,address,height,_ in SPECS:
        family = 0 if native_id < 44 else 3
        base,palette,start = struct.unpack_from('<III',original,0x807178+family*12)
        expected = base-0x08000000
        for index in range(start,native_id):
            w,h = struct.unpack_from('<BB',original,0x8071C0+index*4)
            expected += w*h*32
        w,h = struct.unpack_from('<BB',original,0x8071C0+native_id*4)
        if (expected,w*8,h*8,palette) != (address,32,height,0x0845EB74 if family==0 else 0x0845EBD4):
            raise AssertionError('purchase native family/ID/extent mismatch')
        raw=original[address:address+height*16]
        if hashlib.sha256(raw).hexdigest()!=SOURCE_SHA[address]:
            raise AssertionError(f'purchase caption source changed: {address:08X}')


@lru_cache(maxsize=1)
def font():
    from bdf import load_bdf
    if hashlib.sha256(FONT.read_bytes()).hexdigest()!=FONT_SHA256:
        raise AssertionError('purchase Galmuri7 font changed')
    return load_bdf(str(FONT))[0]


def render(original):
    from bdf import glyph_grid
    validate_source(original)
    # Guard both the position and native colors of the common move caption.
    sources = [pixels(original[a:a+256],16) for _,a,h,_ in SPECS[1:9]]
    mask = caption_mask(36,16)
    if any(len({g[y][x] for g in sources})!=1 for x,y in mask):
        raise AssertionError('move caption shared mask no longer matches all eight icons')
    result={}
    for native_id,address,height,text in SPECS:
        grid=pixels(original[address:address+height*16],height)
        mask=caption_mask(native_id,height)
        allowed={0,1,3,4} if height==16 else {0,1,2,3,4,5}
        if any(grid[y][x] not in allowed for x,y in mask):
            raise AssertionError('caption mask contains a native icon color')
        for x,y in mask:grid[y][x]=0
        glyphs=[glyph_grid(font()[ord(c)]) for c in text]
        width=sum(g[1] for g in glyphs)+len(glyphs)-1
        cursor=16 if height==16 else (32-width)//2
        top=8 if height==16 else 22
        if width > (15 if height == 16 else 30):
            raise AssertionError('purchase caption too wide')
        ink=set()
        for bitmap,w,h,xoff,yoff in glyphs:
            for y in range(h):
                for x in range(w):
                    if bitmap[y][x]:ink.add((cursor+x+xoff,top+y+7-h-yoff))
            cursor+=w+1
        if not ink or not ink<=mask:
            raise AssertionError('purchase caption foreground clipped by icon protection')
        outline=4 if height==16 else 5
        for x,y in ink:
            for dx in (-1,0,1):
                for dy in (-1,0,1):
                    if (x+dx,y+dy) in mask:grid[y+dy][x+dx]=outline
        for x,y in ink:grid[y][x]=1
        result[address]=pack(grid)
    return result


def patch(rom, original):
    validate_source(original,rom)
    expected=render(original)
    for address,payload in expected.items():
        if rom[address:address+len(payload)]!=original[address:address+len(payload)]:
            raise AssertionError('purchase caption already changed by another writer')
    for address,payload in expected.items():rom[address:address+len(payload)]=payload
    return {'labels':len(expected),'raw_bytes':sum(map(len,expected.values()))}


def verify_generated(rom, original):
    validate_source(original,rom)
    for address,payload in render(original).items():
        if rom[address:address+len(payload)]!=payload:
            raise AssertionError('generated purchase caption overwritten before editor')


def capture_regions(rom, original):
    validate_source(original,rom)
    return {address:bytes(rom[address:address+height*16]) for _,address,height,_ in SPECS}


def verify_regions(rom, regions):
    for address,end,digest in GUARDS:
        if hashlib.sha256(rom[address:end]).hexdigest() != digest:
            raise AssertionError('purchase native consumer/palette changed after editor')
    expected={a:h*16 for _,a,h,_ in SPECS}
    if set(regions)!=set(expected) or any(len(regions[a])!=n for a,n in expected.items()):
        raise AssertionError('purchase final snapshot has wrong extents')
    for address,payload in regions.items():
        if rom[address:address+len(payload)]!=payload:
            raise AssertionError('accepted purchase caption overwritten after editor')


def editor_labels():
    return [{'text':text,'off':address,'tw':4,'th':height//8} for _,address,height,text in SPECS]
