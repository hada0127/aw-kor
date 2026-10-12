"""Audited Part 2 unit label mapping; validation only, no ROM writes.

Native compact accessor 0832ACC4 uses type -> 0815D88 u16 index ->
08466568 + (((index << 3) & 0x3FF) << 5). Static table and source atlas
bind the labels to the original Japan revision. Goldens describe the existing
Galmuri11-Condensed renderer before user sprite overrides; apply these checks before the
editor overlay, never to reject a later authorized user asset.
"""
from hashlib import sha256

SLOT_SIZE = 256
# address, approved Korean text, immutable original slot SHA, generated slot SHA
COMPACT_LABELS = (
    (0x466568, '보병',
     '46c59a80edc493d81a8a684b50d3bf8d1e9ebcf2beb5bcc5fb43d4c139c16e5e',
     '8d5f27b17fdd4e08ad095bc9a0d8da1c477d5eb535fab31cdcf443c69fb53010'),
    (0x466668, '바주카병',
     'b0626a85e3705a76e502fdd0114193ce77bba2e6d65cd141bcd7af2064337c70',
     '51dd739d858ddb756d36b6e33de450ec2ac0d1122cd2b893566c04528bc8ae38'),
    (0x466768, '중전차',
     '98f79d6ab168450d4f20184fda54bb1cda3b913a3859b578c897d4ec27464e54',
     '7d837be25aab572843a0564b53138139352726661c1f88e51ae8bb94547ce85a'),
    (0x466868, '신형전차',
     '211931a2f66073d0b592988f95a6d319c2b4664cee764b25ad559458babac8c3',
     'e23053b85d1986b7d9d15744a3033b0ca8cea78775b29eed94e83470b85cb1cb'),
    (0x466968, '경전차',
     '773ee0297a8df94e6df748d63e144ae80fb50bef12dc361155821af2dd3a63bb',
     'fa3341ae09b74fd2aa9a5915f59f7c89ae7143f56e046d22c755dd15979008dd'),
    (0x466A68, '정찰차',
     '1eff154e3806a3b9fb6e060c5869ad62bedfedd94594df8e3a498dbe7ec543ca',
     '6d0fd3a91a9f985e9a9669bad6714a81136b7ecdaeda318925126201ad602c0f'),
    (0x466B68, '보급차',
     '762fd8dfdee9bcc51a57363884a9cd30fa49b983d8eb66337974544f4c694f0b',
     '68210a1304a60f376081c0a5fb508626936458829c5d7ad851eb99eb243cff27'),
    (0x466C68, '자주포',
     '66afd9d5a776e0469fd9515d4bde5179fe4a7e023266f88e26958f5b477f0625',
     '948d5eae5f6e0f1bc4ff5272ab9cc5c2d64d4f2b8afd6a4a7696efccb37aa06d'),
    (0x466D68, '로켓포',
     'f347895073ddaeed13a6cde07cadd7bc587cff0b77d359893a12bc38b91f844b',
     '96d227a2e19eb80da6562cacfa8c5791a0e22c96fb769b3dbda27838e530f644'),
    (0x466E68, '대공전차',
     'a151043a0b429ec1870bafd2d42ea69c1bb2bcb396a6326b08d50e37d7042dbc',
     'a3461d660bc6c4b79b8eee8cbfa7208de71bbbd3d38450fb5579c99d43b69983'),
    (0x466F68, '미사일',
     '7742c6f21c958c75f6de87062d5f5d92dc63f797f65b53ea23500fca72f42ab7',
     '7c206cdc7a2251aad94457137d9eb2d6b823575f17685071a13e46fb00aef217'),
    (0x467068, '전투기',
     '7ecef3349a211005202a8a06c785620a2af6430b6b45ade526425111000aa8d9',
     '305393a88cc207fdd2b1d1ebd45e765c72d719b087ecea7cfb670a0f214320f8'),
    (0x467168, '폭격기',
     '070be5dc797497d444ebcf142cf5b0d993421fc08da47285b8481ecb4ae718bc',
     '59929b7b44a0fbcd2e1f4d20ac767a9f4dca7a75f7eef01a2e36a808be89ffbf'),
    (0x467268, '전투헬기',
     'bd5245989311804db73417aea6d42cf357ab16cb46f926c58f778ad228eb55a7',
     '1c9cd30ea10d2b46eacc6ed944605a70e936cfb30bd65606312adc497a77986b'),
    (0x467368, '수송헬기',
     '7d654f2e87adf1b9036d5190cbce739cacbcffdb6ee96f988b32fdaa5e203445',
     '91dedfb3aadd51a2defb0c6f9d9cedd8a902369fbafdd9243cc13285bc164d1d'),
    (0x467468, '전함',
     'b0a1112ca9a77ff0cf4429ffd348ab60d143728d90ac631469f67b5f5a6dc2fc',
     '17b2c257c205cf97f0819857123789e860427526b314b014e467fb1e272190a1'),
    (0x467568, '호위함',
     '6566540bc24026b1f089f6f1f8394afa9074ef38411f94de01b8668e615ee358',
     '646881359192801a16e3da5d037cebcf966adaf0e5a5a2ec091a5f954620a125'),
    (0x467668, '수송선',
     'e0a121bffcb032fb2f88960ec16ee7e5c01a5f8a2f64f2f6d040e32bd7f6fd71',
     '0dc72860c020f04ba3bafd53d4fb3fcb34efc3daf7795ed39426c3a26ac8bb32'),
    (0x467768, '잠수함',
     '01acdb86c6a84787bded815f8e64a22004415a6fba8e1296275c8dfba9474656',
     'a6799dac3538fd4a8119d7f09b1c1751926d06cfe74b092cfb29350d37f9bf3b'),
)

STATUS_LABELS = (
    (0xB94810, '보병',
     'a89e0b83ee2983260094bf9748dc5b47def3024dbdd723f3161fdeed4d6ef782',
     '8d5f27b17fdd4e08ad095bc9a0d8da1c477d5eb535fab31cdcf443c69fb53010'),
    (0xB94910, '바주카병',
     'df496978d63b90dd517cd5a946ca8d81b5ff1def67f8a0c9298209d71f9c86c6',
     '51dd739d858ddb756d36b6e33de450ec2ac0d1122cd2b893566c04528bc8ae38'),
    (0xB94A10, '정찰차',
     '5796a314c505c58a9c44b7a6581980b9ac4b2042097995ceb829cdd8d4f47188',
     '6d0fd3a91a9f985e9a9669bad6714a81136b7ecdaeda318925126201ad602c0f'),
    (0xB94B10, '대공전차',
     'c88a6e876b88dc30ab600dda4f3fbf03ce85f432bbf79faeb526c0dbd6a15367',
     'a3461d660bc6c4b79b8eee8cbfa7208de71bbbd3d38450fb5579c99d43b69983'),
    (0xB94C10, '경전차',
     'df529e70410bdc9c6b39b3413d99ab3b7654b739d0e44128f90a5f7073ae0cc0',
     'fa3341ae09b74fd2aa9a5915f59f7c89ae7143f56e046d22c755dd15979008dd'),
    (0xB94D10, '중전차',
     '36416c9eb09b8e713185c611eec50397173fdb7d3535371743a961c6a92cc7b4',
     '7d837be25aab572843a0564b53138139352726661c1f88e51ae8bb94547ce85a'),
    (0xB94E10, '자주포',
     '96bf8b6a65b88aed7aa07018b5525187da651713f2c03e3e13643e13be8fa0e1',
     '948d5eae5f6e0f1bc4ff5272ab9cc5c2d64d4f2b8afd6a4a7696efccb37aa06d'),
    (0xB94F10, '로켓포',
     'b82d3e5db9f8d730afadf8180e6b34ff05975ef8beb4c3f9fb08c9b34ea62f5f',
     '96d227a2e19eb80da6562cacfa8c5791a0e22c96fb769b3dbda27838e530f644'),
    (0xB95010, '보급차',
     '08655ee6057aa656476359df4c2bb8c6333ac9ccb3b533b84690a6f3a15efc8b',
     '68210a1304a60f376081c0a5fb508626936458829c5d7ad851eb99eb243cff27'),
    (0xB95110, '미사일',
     '616caf6df5664dfe1b25b57ba3afd7111f3ce34295d8ea7529a491fe21b4c717',
     '7c206cdc7a2251aad94457137d9eb2d6b823575f17685071a13e46fb00aef217'),
    (0xB95210, '수송헬기',
     '7f869910fb8fbb36b46285753674548841a513ac6308d1aac3985d1733b34d55',
     '91dedfb3aadd51a2defb0c6f9d9cedd8a902369fbafdd9243cc13285bc164d1d'),
    (0xB95310, '전투헬기',
     '2435b582292ac9f70a9d95db68ddb06606e17fdc693313ec0a7bb04f050b6da8',
     '1c9cd30ea10d2b46eacc6ed944605a70e936cfb30bd65606312adc497a77986b'),
    (0xB95410, '전투기',
     'd559b2f5f88ffdd96f68153c748f615b1867e8da99a92984ed13149500bdf9b8',
     '305393a88cc207fdd2b1d1ebd45e765c72d719b087ecea7cfb670a0f214320f8'),
    (0xB95510, '폭격기',
     '8d0e147bb66a60ad5a403063349e507f2aef77607b863584afe4d07b5d8f2d39',
     '59929b7b44a0fbcd2e1f4d20ac767a9f4dca7a75f7eef01a2e36a808be89ffbf'),
    (0xB95610, '수송선',
     '7ce3c5b000f80569e050a80accb5125ce8caae5818101424d1d500ce9a513900',
     '0dc72860c020f04ba3bafd53d4fb3fcb34efc3daf7795ed39426c3a26ac8bb32'),
    (0xB95710, '전함',
     '4745c82071b37a4eeee5a27d4de4025ce6d5cc2f17e97e4755d6b8fb403fd851',
     '17b2c257c205cf97f0819857123789e860427526b314b014e467fb1e272190a1'),
    (0xB95810, '호위함',
     'c9cac137b9c516fb564914ac6877ed868a77b0a13d6ed1fd8f15070a22661043',
     '646881359192801a16e3da5d037cebcf966adaf0e5a5a2ec091a5f954620a125'),
    (0xB95910, '잠수함',
     '4ff01dd19b892dd0fde0ecaf88409a5547795487c49dfc8b4d5f151779f5b9f5',
     'a6799dac3538fd4a8119d7f09b1c1751926d06cfe74b092cfb29350d37f9bf3b'),
)

ACCESSOR = (0x32ACC4, 36, 'e5a90f0872396aab31005ce388e163bdd63f5f98deab826873f5ad9269396ae4')
TYPE_LOOKUP = (0x815D88, 100, '150a6c015066cc8a4b677301bd84435a0127d0a4b358fba99e92c54e20c366f5')


def validate_source(original, current):
    """Assert the audited immutable atlas and unchanged compact consumer."""
    for address, _, expected, _ in COMPACT_LABELS + STATUS_LABELS:
        if sha256(original[address:address + SLOT_SIZE]).hexdigest() != expected:
            raise AssertionError(f'Part 2 unit-label source changed at {address:06X}')
    for address, size, expected in (ACCESSOR, TYPE_LOOKUP):
        for rom in (original, current):
            if sha256(rom[address:address + size]).hexdigest() != expected:
                raise AssertionError(f'Part 2 unit-label consumer changed at {address:06X}')


def verify_generated(current):
    """Verify actual automatic renderer output for all 19 compact + 18 status slots."""
    for address, text, _, expected in COMPACT_LABELS + STATUS_LABELS:
        if sha256(current[address:address + SLOT_SIZE]).hexdigest() != expected:
            raise AssertionError(f'Part 2 unit-label mapping/render changed at {address:06X}: {text}')


def verify_metadata(groups):
    """Metadata and raster must describe the same approved unit labels."""
    for group, labels in (('objlabel_p2_unit_compact', COMPACT_LABELS),
                          ('objlabel_p2_unit_status', STATUS_LABELS)):
        expected = [(a, text, 4, 2) for a, text, *_ in labels]
        actual = [(entry['off'], entry['text'], entry['tw'], entry['th']) for entry in groups[group]]
        if actual != expected:
            raise AssertionError(f'Part 2 unit-label editor metadata changed: {group}')
