"""Verified P2 script semantics, opt-in per message by native parser evidence.

A3 is a glyph-cache family; seeing its glyph entry alone does not prove the
0x31424C command parser. Never infer this consumer from a source address range.
"""
from pathlib import Path
import hashlib
import json
import re
import struct

GBA = 0x08000000
CONSUMER = 'part2_31424c_script'
KNOWN = {0x57:'same_row', 0x4B:'page', 0x09:'format_skip', 0x0A:'format_skip',
         0x30:'style', 0x31:'style', 0x32:'style', 0x33:'style'}
NATIVE_REGIONS = {'dispatch_first': {'start': 3228236, 'end': 3228272, 'sha256': '737b10e7f6b19d82274432e67449519794e63d0c19c02d794ff3d119c0458243'}, 'table_first': {'start': 3228272, 'end': 3228444, 'sha256': '2eb551ce8f586149cf5c545b61c3e49ac4a47d2095c8b112ff7b1621d29553ee'}, 'consume_and_style': {'start': 3228444, 'end': 3228466, 'sha256': 'd269b22cf97f38b66279ad83a60253cf4bb3d82fbcda2697c833e01a225d91a2'}, 'dispatch_second': {'start': 3228466, 'end': 3228488, 'sha256': '35db3466c574c65e2b774d5532368990849138e44cb83275955a2449e74e2835'}, 'table_second': {'start': 3228488, 'end': 3228968, 'sha256': 'dfd76941d2fddde41d6372db235cc43221007e13d109d5594bf4d177b75a4f17'}, 'page': {'start': 3229118, 'end': 3229216, 'sha256': 'b56ce1e6e3c0a2936fb18c38cf7bc55a8a2d064422d0c2de4e4ff37b712ffd04'}, 'wait': {'start': 3229270, 'end': 3229312, 'sha256': '8f981bd0e57a6e096aec9c79b240a0ed7efaac064ab3d78d75decbf3b98fc5af'}, 'handled_return': {'start': 3229660, 'end': 3229696, 'sha256': 'e7da4693f984d3895702159205088b9dabea57020082cf82cc40dcf7de4f9cae'}, 'parser_call': {'start': 3229924, 'end': 3229968, 'sha256': '3501dd6049773d5decec5ef654565206c8d3b2e4fd26674e66ee98612eb7b7cf'}, 'glyph_call': {'start': 3230022, 'end': 3230032, 'sha256': '8f93e4ff1340242a263886e79f094057740da96a7b20607b5992e924914ba435'}, 'message_init': {'start': 3230620, 'end': 3230736, 'sha256': 'c1b6ee6fa1ba2e752c1124b928501bcfe8d1e4dfe8b112ad2a54fbb7f419ecb7'}, 'wait_job_descriptor': {'start': 8408920, 'end': 8408944, 'sha256': 'd40c0c5026cbd44ecec1584bbd38f1189ad97f7766445d7d164187d2be898323'}, 'wait_callback': {'start': 3227652, 'end': 3227672, 'sha256': 'acd69b5ca132b31770639a2ef3d4a63706f75ba298aef64ce16f4cb353ee9b6d'}, 'job_init': {'start': 3233388, 'end': 3233504, 'sha256': 'b8a858169234b44f0f09ddfe21cd4e1575310cc88019af1ce5ae749f15b468e9'}, 'job_start': {'start': 3233592, 'end': 3233660, 'sha256': '37b88d6822b4d0b811ae9d481689f7b4bc69e0421487ccf792341316808c5d5c'}, 'job_alloc_and_end': {'start': 3233704, 'end': 3233848, 'sha256': '883b97bc0527353f5c010b9ec51822c8bbd858a07b40940dbb42fe14bcfe7557'}, 'job_dispatch': {'start': 3235564, 'end': 3235672, 'sha256': '2dec084cae29294e2c136d6cbcd0263ea3cb3fca15606e612eee68d0c8de7958'}, 'job_delay_and_callback_ops': {'start': 3236404, 'end': 3236484, 'sha256': '083f5247e340fd1c4bb18be48a553461175471daeee101a92a2375682283ae8b'}, 'job_end_op': {'start': 3236256, 'end': 3236272, 'sha256': '6991db16978388f8f87d9b9270e5143b858618095bc981d9aa9883da5c555fb2'}, 'job_op_table': {'start': 8412064, 'end': 8412096, 'sha256': '534f6b68449443abcdab796297f197c7a93b93df6f997e29234d1106e7f1ef59'}}

# 72 resets the column, advances the row and consumes one command byte.
NATIVE_REGIONS['newline'] = {'start': 3229078, 'end': 3229118, 'sha256': 'e99c0b9a9e9304621b39842a11a35e5c88bec49b938be080e1ec92e1813b8fbb'}

PATCH_REGIONS = {'a3_glyph_trampoline': {'start': 10733544, 'end': 10733552, 'sha256': 'de24a9960f799c6bfbe64f9337e781b9ddfa49475b19ec86e385fd4ed581c585'}, 'a3_glyph_hook': {'start': 15925888, 'end': 15926080, 'sha256': 'ed6ef6982d315dcc00fe0c628d6f700c48718c9953665dd8963ed3a0d5c2fddf'}, 'space_313_trampoline': {'start': 3227606, 'end': 3227614, 'sha256': '63beb5da04a0fea4cf76f6bf6a1177a296eae18f9d9695990c3a75d14c2eebcc'}, 'space_313_hook': {'start': 15926112, 'end': 15926172, 'sha256': 'ef575db9896f1b6fecf7fbc0259244ee73e88effbc56b073198cc53ec7cb0132'}, 'space_b11_trampoline': {'start': 11607550, 'end': 11607558, 'sha256': 'a8feaf2a0c3210a6ce42c501812aed16618af7ee50033568046b8ae0ff4b9d1c'}, 'space_b11_hook': {'start': 15926176, 'end': 15926236, 'sha256': 'f1424c9eec9df0bb012e5b2ce0cb9098f07e1412ec8a334bcf3b9bafe8c0ae16'}}

class NativeConsumerError(ValueError):
    pass

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def verify_native(rom):
    """Bind both parser jump tables and reachable handlers/call/init code."""
    checks={}
    for name,spec in NATIVE_REGIONS.items():
        actual=sha(rom[spec['start']:spec['end']])
        if actual != spec['sha256']:
            raise NativeConsumerError('P2 native parser region changed: '+name)
        checks[name]=actual
    # Aliases and consume-only space are already inside the hashed tables;
    # retain explicit contracts for readable failure diagnostics.
    u32=lambda a:struct.unpack_from('<I',rom,a)[0]
    for a,value in [(0x3142CC,0x0831431C),(0x314348+0x57*4,0x08314656),
                    (0x314348+0x77*4,0x08314656),(0x314348+0x4B*4,0x083145BE),
                    (0x314348+0x6B*4,0x083145BE)]:
        if u32(a)!=value:raise NativeConsumerError('P2 native dispatch changed')
    return checks

def verify_patch_connections(rom, names=None):
    result={}
    for name in (names if names is not None else PATCH_REGIONS):
        spec=PATCH_REGIONS[name];actual=sha(rom[spec['start']:spec['end']])
        if actual!=spec['sha256']:raise NativeConsumerError('P2 patched hook changed: '+name)
        result[name]=actual
    return result

def _read_bound(path, expected):
    raw=Path(path).read_bytes()
    if sha(raw)!=expected:raise NativeConsumerError('Consumer evidence SHA mismatch: '+str(path))
    return raw

def load_consumer_bindings(path, original, rom, messages):
    """Accept bounded historical in-place or exact-current relocated READs.

    Each current message is bound to revision/pointer/payload. Historical text
    may differ, but original table slot, parser/call/init bytes and native READ
    PC+caller must agree. Relocated reads require the exact current ROM,
    pointer, payload hash and audited message length. Historical relocated
    messages remain unsupported instead of guessing their old bounds.
    """
    if path is None:return {}
    document=json.loads(Path(path).read_text())
    if not isinstance(document,dict) or document.get('schema') != 1 or not isinstance(document.get('records'),list):
        raise NativeConsumerError('Consumer evidence schema/records invalid')
    if document.get('rom_sha256')!=sha(rom):raise NativeConsumerError('Current consumer evidence ROM mismatch')
    verify_native(original);verify_native(rom)
    verify_patch_connections(rom,('a3_glyph_trampoline','a3_glyph_hook'))
    by_source={int(m['source'],16):m for m in messages};result={};cache={}
    for record in document['records']:
        if not isinstance(record,dict):raise NativeConsumerError('Consumer evidence record must be an object')
        required=('source','pointer','target','payload_sha256','consumer','kind','trace_rom','trace_rom_sha256','trace','trace_sha256')
        if any(not isinstance(record.get(k),str) or not record[k] for k in required):
            raise NativeConsumerError('Consumer evidence record fields must be nonempty strings')
        source=int(record['source'],16)
        if source not in by_source or source in result:raise NativeConsumerError('Unknown/duplicate consumer source')
        m=by_source[source];pointer=int(m['pointer'],16)
        if record.get('consumer')!=CONSUMER or record.get('kind') not in (
                'historical-inplace-native-read-v1', 'current-relocated-native-read-v1'):
            raise NativeConsumerError('Unsupported consumer proof kind')
        if any(record.get(k)!=m[k] for k in ('pointer','target','payload_sha256')):
            raise NativeConsumerError('Current message consumer binding mismatch')
        rom_key=(record['trace_rom'],record['trace_rom_sha256'])
        if rom_key not in cache:
            previous=_read_bound(*rom_key);verify_native(previous);verify_patch_connections(previous,('a3_glyph_trampoline','a3_glyph_hook'));cache[rom_key]=previous
        previous=cache[rom_key]
        if len(previous)!=len(original):raise NativeConsumerError('Historical ROM size mismatch')
        u32=lambda b,a:struct.unpack_from('<I',b,a)[0]
        if u32(original,pointer)!=source+GBA:
            raise NativeConsumerError('Consumer proof original pointer mismatch')
        if record['kind']=='current-relocated-native-read-v1':
            target=int(m['target'],16);length=m.get('bound_bytes')
            if (record['trace_rom_sha256']!=document['rom_sha256']
                    or target==source or u32(previous,pointer)!=target+GBA
                    or type(length) is not int or not 0<length<=len(rom)
                    or not 0<=target<target+length<=len(rom)
                    or sha(previous[target:target+length])!=m['payload_sha256']):
                raise NativeConsumerError('Relocated proof requires exact current pointer/payload bounds')
            start,end=target,target+length
        else:
            if u32(previous,pointer)!=source+GBA:
                raise NativeConsumerError('Historical proof requires original in-place pointer')
            upper=u32(original,pointer+4)-GBA
            if not source<upper<=len(original):raise NativeConsumerError('Original source bound is not monotonic')
            start,end=source,original.find(b'\0',source,upper)
            if end<0:raise NativeConsumerError('Original source has no bounded terminator')
        trace=_read_bound(record['trace'],record['trace_sha256']).decode('utf-8')
        matched=[]
        for line in trace.splitlines():
            fields=dict(re.findall(r'\b(addr|pc|lr)=([0-9A-Fa-f]{8})\b',line))
            if set(fields)!={'addr','pc','lr'}:continue
            a,pc,lr=(int(fields[k],16) for k in ('addr','pc','lr'))
            if start+GBA<=a<end+GBA and pc in (0x0831425A,0x08314336) and lr==0x083148F3:
                matched.append(line)
        if not matched:raise NativeConsumerError('No bounded native script-parser READ with expected caller')
        result[source]={'consumer':CONSUMER,'proof_kind':record['kind'],'native_regions_verified':True,
                        'trace_sha256':record['trace_sha256'],'matched_reads':matched,
                        'inputs':{str(Path(record['trace_rom'])):record['trace_rom_sha256'],
                                  str(Path(record['trace'])):record['trace_sha256']}}
    return result

class NativeProfile:
    """Created from actual ROM bytes; cannot be loaded from a JSON label."""
    __slots__=('rom_sha256','regions','connections')
    def __init__(self,rom):
        self.rom_sha256=sha(rom)
        self.regions=verify_native(rom)
        self.connections=verify_patch_connections(rom,('a3_glyph_trampoline','a3_glyph_hook'))

def is_verified_consumer(consumer,profile):
    if consumer is None:return False
    if consumer!=CONSUMER:raise NativeConsumerError('Unsupported native command consumer')
    if not isinstance(profile,NativeProfile):raise NativeConsumerError('NativeProfile from ROM bytes required')
    return True
