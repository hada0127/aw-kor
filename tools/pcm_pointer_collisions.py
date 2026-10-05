"""일본판 DCE8F0 포인터 모양 PCM 3건의 제한된 비포인터 분류.

원본의 song 209 -> track 2 BD6B -> voice 107 -> wave -> signed-byte mixer
소비 경로로 입증된 세 (target, site) 쌍만 다룬다. 샘플 범위 무시 규칙이
아니다. 원본/현재 소비 코드 또는 연결 데이터가 다르면 아무것도 제외하지
않아 호출자의 기존 미인식 포인터 가드가 적용된다. ROM은 변경하지 않는다.
"""
from hashlib import sha256
import struct

GBA = 0x08000000
TARGET = 0xDCE8F0
REAL_SITE = 0xDE4324
SOURCE_SHA256 = 'a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c'
SAMPLE_SHA256 = '79b1b026ac4ba24bd2ab8e6a5316cc7e3ea5a5c183bd05ac8795ddb557a4ad90'
SAMPLE_SIZE = 12369
# header, collision, voice bank, song table, song header, track 2, command table,
# voice command handler. Addresses are file offsets, never runtime addresses.
CASES = (
    (0x11F470, 0x1202F0, 0x039370, 0x03A74C, 0x25ACA0, 0x25A0A9, 0x038680, 0x00C12C),
    (0x6A2BE8, 0x6A3A68, 0x5BCAE8, 0x5BDEC4, 0x7DE418, 0x7DD821, 0x52F684, 0x370778),
    (0xCFCC50, 0xCFDAD0, 0xC444F4, 0xC45150, 0xD6EE68, 0xD6E271, 0xC43CD0, 0xB78C98),
)
SITES = frozenset(case[1] for case in CASES)
# Whole native driver regions include dispatch branches, song/voice loading,
# wave+12 size / wave+16 cursor initialization and LDRSB/MUL/ADD sample mixer.
# Guarding only the final LDRSB instructions would miss a redirected consumer.
CONSUMERS = (
    (0x00BBA8, 0x00D134, '6a060838ac2267df514795f4b3de55d15958cc1816b7b73a0208d7bffaeef132'),
    (0x3701F4, 0x371780, '7686094302ba75da02dba0e253206ae11e5fa42ca2b2cdf5e19f0f0d3cba251b'),
    (0xB78714, 0xB79CA0, 'c815f80e0f16df00fba49fc84db244debc8613088584fa8a665545418cd60da6'),
)


def _guard(rom):
    """Return the first failed evidence link, or None; called on both ROMs."""
    pointer = struct.pack('<I', GBA + TARGET)
    if rom[REAL_SITE - 4:REAL_SITE + 4] != b'\x19\0\0\0' + pointer:
        return 'typed_text_reference'
    # Current writers can introduce new references absent from the immutable
    # source scan. Those must also retain the old ambiguous-pointer rejection.
    pos = 0
    while True:
        site = rom.find(pointer, pos)
        if site < 0:
            break
        if site % 4 == 0 and site not in SITES and site != REAL_SITE:
            return f'unrecognized_reference_{site:06X}'
        pos = site + 1
    for start, end, digest in CONSUMERS:
        if sha256(rom[start:end]).hexdigest() != digest:
            return f'consumer_{start:06X}'
    for header, site, bank, song_table, song, track, commands, handler in CASES:
        prefix = f'wave_{header:06X}'
        if rom[header:header + 16] != struct.pack('<HHIII', 0, 0, 13700096, 0, SAMPLE_SIZE):
            return prefix + '_header'
        start, end = header + 16, header + 16 + SAMPLE_SIZE
        if site != start + 3696 or site + 4 > end or rom[site:site + 4] != pointer:
            return prefix + '_collision'
        if sha256(rom[start:end]).hexdigest() != SAMPLE_SHA256:
            return prefix + '_samples'
        voice = bank + 107 * 12
        if rom[voice:voice + 12] != b'\x00\x3c\0\0' + struct.pack('<I', GBA + header) + b'\xff\0\xff\0':
            return prefix + '_voice107'
        song_entry = song_table + 209 * 8
        if rom[song_entry:song_entry + 4] != struct.pack('<I', GBA + song):
            return prefix + '_song209'
        if rom[song:song + 1] != b'\x08' or rom[song + 4:song + 8] != struct.pack('<I', GBA + bank):
            return prefix + '_song_bank'
        if rom[song + 16:song + 20] != struct.pack('<I', GBA + track):
            return prefix + '_track2'
        if rom[track:track + 4] != b'\xbc\0\xbd\x6b':
            return prefix + '_voice_opcode'
        entry = commands + (0xBD - 0xB1) * 4
        if rom[entry:entry + 4] != struct.pack('<I', GBA + handler + 1):
            return prefix + '_voice_dispatch'
    return None


def classify_pointer_sites(message, sites, original, current):
    """Return (retained sites, evidence). Unknown targets/sites remain intact.

    Evidence is metadata for the existing relocation/skip row. A rejected guard
    is not an exclusion. The current mutable ROM is checked afresh on each call.
    """
    retained = list(sites)
    known = SITES.intersection(retained)
    if message != TARGET or not known:
        return retained, None
    reason = None
    if len(original) != 0x1000000 or sha256(original).hexdigest() != SOURCE_SHA256:
        reason = 'original_revision'
    elif len(current) != len(original):
        reason = 'current_size'
    else:
        for name, rom in (('original', original), ('current', current)):
            failure = _guard(rom)
            if failure:
                reason = name + ':' + failure
                break
    evidence = {'kind': 'verified_pcm_collision', 'status': 'guard_rejected' if reason else 'classified',
                'excluded_sites': [] if reason else [f'0x{s:06X}' for s in sorted(known)],
                'source_sha256': SOURCE_SHA256, 'sample_sha256': SAMPLE_SHA256}
    if reason:
        evidence['reason'] = reason
        return retained, evidence
    return [site for site in retained if site not in SITES], evidence
