"""Source roles shared by extraction, editors and text QA."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / 'data/glyph_dictionary_sources.json').read_text(encoding='utf-8'))
SOURCES = tuple((int(row['address'], 16), int(row['length']), row)
                for row in CATALOG['sources'])
GLYPH_DICTIONARY_TEXT_ADDRS = frozenset(start for start, _, _ in SOURCES)


def glyph_dictionary_owner(address):
    if not isinstance(address, int):
        return None
    return next((start for start, size, _ in SOURCES if start <= address < start + size), None)


def is_glyph_dictionary_address(address):
    return glyph_dictionary_owner(address) is not None
