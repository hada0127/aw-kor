"""B830AC source24 prewrite contract. No allocation or runtime claim."""
import array
import sys

START, TAIL, END, SITE = 0xB830AC, 0xB830C4, 0xB830C8, 0xD8D9B0
TEXT = '보낼 맵을 골라 줘!!'
ROW = bytes.fromhex('8d46895081408bd98f818140886a8adf81408ff181498149')
NATIVE = bytes.fromhex('919782e9837d8362837682f0914982f182c582cb8149814900000000')
OWNER = [START, 24, 24, ROW.hex(), 32, TEXT, 0, 'dialogue-override']
CALLERS = {
    0xb333a0: bytes.fromhex('0ee0000060d301024c460003e020c001009001970e20211c52462b1cdff7aefe80239b0299440124a0444546032d8fdddef7f6fa08b038bc9846a146aa46f0bc01bc004700b50a2005210c220a23e6f763fd0020fff77cfb01bc004770b582b0000409040d0c1204160c88421ed0dff711fb114c02200090b22040000190201c032111221a23ddf705fd0c49a80040180368c0208001009098204000019003201121221cdff764fa3a300670281c02b070bc02bc08470000442d010298d9d808f0b557464e464546'),
    0xb34d28: bytes.fromhex('02a91960c020c00458601c48986098681b4919605a601b48401a002800da03308010842109060843986098681648174c211cdbf749f946f0dfff07480078dff787fa03b038bc9846a146aa46f0bc01bc00470000b42f0003081d000348330003a43f0003442d010298d9d80808020004'),
    0xb34c80: bytes.fromhex('0068818809200840002828d01e21785e002824d14a461168087e00281fd1887f00281cd0394c02200090b22040000190201c032111221a23dcf7bcf8ddf7bafe3348836bc0208001009098204000019003201121221cddf7b3fd0120f8831e21785e012803d04a46106835f0abfe4946086836f039f9002837d02649002008800639254a101c08808021c9048020088000210291214b02a81860802292045a601f48986098680291'),
}
CANDIDATE_TABLE = bytes.fromhex('94d2a5086031b8083031b808b0d2a508d8d2a508fcd2a508ac30b8082cd3a50850d3a50878d3a508a4d3a5080030b808dc2fb808ac2fb8087c2fb808542fb808')


def preflight(original, rom, owner, authority, encoded):
    if owner != OWNER:
        raise AssertionError('B830AC exact owner/slot missing or changed')
    if authority != TEXT or bytes(encoded) != ROW:
        raise AssertionError('B830AC authority/encoding changed')
    if bytes(original[START:END]) != NATIVE:
        raise AssertionError('B830AC native28/source24/tail4 changed')
    if bytes(rom[TAIL:END]) != b'\0'*4:
        raise AssertionError('B830AC working tail4 changed')
    if bytes(rom[START:TAIL]) != ROW:
        raise AssertionError('B830AC prior owner payload changed')
    for start, raw in CALLERS.items():
        if bytes(original[start:start+len(raw)]) != raw or bytes(rom[start:start+len(raw)]) != raw:
            raise AssertionError('B830AC caller changed')
    # Already relocated candidate pointers, never the Japanese source table.
    if bytes(rom[0xD8D998:0xD8D9D8]) != CANDIDATE_TABLE:
        raise AssertionError('B830AC candidate table/pointer changed')
    for data in (original, rom):
        words = array.array('I'); words.frombytes(data[:len(data)//4*4])
        if sys.byteorder != 'little': words.byteswap()
        refs = [(i*4,w) for i,w in enumerate(words) if 0x08000000+START <= w < 0x08000000+END]
        if refs != [(SITE,0x08000000+START)]:
            raise AssertionError('B830AC aligned pointer set changed')


def final(rom, writes):
    owners = [r for r in writes if r[0] < END and START < r[0]+r[1]]
    expected = [START,24,24,ROW.hex(),32,'보낼　맵을　골라　줘！！',None,'bteam-round2-baseline']
    if not owners or owners[-1] != expected or bytes(rom[START:END]) != ROW+b'\0'*4:
        raise AssertionError('B830AC final source24 writer/bytes changed')
