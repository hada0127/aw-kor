"""Dialogue payload ranges established by native consumers; strict pair UI excluded."""

PART1_DIALOG_RANGES = ((0xD80000, 0xE10000), (0xE10D34, 0xE11314))
# The second range is the separate victory/rank/graduation dialogue block:
# first message header E10D34=0A09; last text E11304..E11310, then 6B0A0000.

# Part 2 prologue messages: pointer entries A357B4..A357E4; the next
# entry A357E8 points to the first mission briefing at A01C90.
# Cold playback proves ASCII punctuation overwrites preceding cached glyphs.
# This predicate is for text payloads, never for scanning whole command streams.
PART2_PROLOGUE_RANGE = (0xA01970, 0xA01C90)
# Story messages end with A29377's encouragement and 6B0000. Unit-name
# UI starts at A29388; abilities, map names and editor labels are outside.
PART2_STORY_RANGE = (0xA01970, 0xA29388)
# The 42 mission blurbs A01C90..A024A0 share the A3 dialogue consumer:
# tables A357E8..A3588C, SJIS row + single 72 + row + NUL. Cold ROM-read
# trace for A01D24/A01D41 reaches F30280/F30282 (LR=0831BBED).
# Strict pair mission titles are the separate A2D000..A2D8B0 region.
PART2_MISSION_BLURB_RANGE = (0xA01C90, 0xA024A0)
# Map-menu victory conditions are a separate dialogue block, not unit/help UI.
# Pointer entries A38938..A389DC reference its 42 messages. A389E0 points
# to A34B6C's yes/no UI. Cold original/candidate traces read the objective
# through the same A3 glyph consumer at 03006082 (LR=0831BBED).
PART2_OBJECTIVE_DIALOGUE_RANGE = (0xA3408C, 0xA34B6C)
# Native artillery R-help: pointer A38798 -> A32278; three text spans
# separated by 72, ending at A322BA (NUL). The observed comma at A322AC
# desynchronizes the two-byte glyph consumer. Include only this evidenced
# message, not the surrounding unit UI/table. Lossless repoint is required
# because the last 22-byte slot needs 24 bytes with both punctuation marks.
PART2_ARTILLERY_HELP_RANGE = (0xA32278, 0xA322BA)
# CO biography and power descriptions are one contiguous 0xA357B4 table group
# (entries 2421..2496).  The text uses 0x72 row controls, unlike the preceding
# compact option labels; entry 2497 starts mode-selection help text.
PART2_CO_INFO_RANGE = (0xA2A33C, 0xA2C040)
# Shop speech and unlock announcements are the next contiguous native message
# table group (entries 2800..2885).  Its payloads use the same 0x6B page and
# 0x72 line controls as the CO quotes; stop before the CO table group begins.
PART2_SHOP_UNLOCK_RANGE = (0xA2D8B8, 0xA2FE70)
# CO victory/power quotes: table entries A384CC..A386DC point to A2FE70..
# A313FC (all NUL terminated); A386E0 points to A31444, the first unit-help
# message (2/3/0 operand controls), which stays outside. Playthrough frames on
# e4963765 (Snake A30E40, Asuka A308B0) show ASCII '...' vanishing and the
# following Hangul turning into '?' glyphs in this consumer, as in the
# prologue. Shop/unlock messages before A2FE70 are not covered (no evidence).
PART2_CO_QUOTE_RANGE = (0xA2FE70, 0xA31444)
# Yes/no system prompts A389E4..A38A04 -> A34B80..A34CE8 (save, delete,
# surrender, mode select). A34B6C is the strict pair yes/no UI and stays out;
# A34D18 starts the defeat banners (not observed). e4963765 frame 3978 shows
# the ASCII '.'/'?' in the save prompt rendering as nothing.
PART2_SYSTEM_PROMPT_RANGE = (0xA34B80, 0xA34D18)
# Five defeat messages immediately follow the prompts (entries 3221..3225).
# They are NUL-terminated text ending in 0x77 wait controls.  A34DD8 starts
# battle animation settings; it is outside this text-only group.
PART2_DEFEAT_RANGE = (0xA34D18, 0xA34DD8)
PART2_STORY_RANGES = (PART2_PROLOGUE_RANGE, PART2_MISSION_BLURB_RANGE,
                      (0xA024A0, 0xA29388),
                      PART2_ARTILLERY_HELP_RANGE,
                      PART2_CO_INFO_RANGE,
                      PART2_OBJECTIVE_DIALOGUE_RANGE,
                      PART2_SHOP_UNLOCK_RANGE,
                      PART2_CO_QUOTE_RANGE,
                      PART2_SYSTEM_PROMPT_RANGE,
                      PART2_DEFEAT_RANGE)


def is_part2_story_address(address):
    return address is not None and any(start <= address < end for start, end in PART2_STORY_RANGES)


def renderer_safe_symbol(pair, address):
    """Map a proven text symbol to a glyph present in its game's renderer.

    Part 2's A3 linked glyph table has 0x815B at 0x809CD0, but no 0x815C;
    the latter falls back to '?'. Both are the same horizontal mark in Part 1.
    Call only for individual encoded characters, never scan command streams.
    """
    if pair == b'\x81\x5c' and is_part2_story_address(address):
        return b'\x81\x5b'
    return pair


def needs_safe_dialogue_punctuation(address):
    return is_part1_dialog_address(address) or is_part2_story_address(address)


def is_part1_dialog_address(address):
    return address is not None and any(start <= address < end
                                       for start, end in PART1_DIALOG_RANGES)
