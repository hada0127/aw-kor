▶ codex research-external: model=gpt-6-luna effort=low sandbox=read-only out=/home/taro1/.agent-harness/state/out/20261023-130802-research-external.md
# External research: Hangul name entry on retro consoles

**Scope:** Public external sources only; checked 2026-10-23. Published sources rarely document the exact grid, automaton, backspace, and storage implementation together. I distinguish what the sources state from what remains unverified. I found one closely relevant, source-published GBA implementation with unusually detailed implementation notes. The official Korean Pokémon Gold/Silver release provides a second useful reference for character coverage and encoding, but its composition internals are not documented in the sources I found.

## Examples

### DigiCommunication 2 Korean patch (GBA, fan translation)

The public project documents a Hangul name-entry patch, including a follow-up that added final consonants. It is a particularly relevant comparison because it keeps an existing GBA name buffer and adds a second-page final-consonant entry mode.

- **Grid:** Source notes say the second page has 27 final-consonant cells (`ㄱ ㄲ ㄳ … ㅎ`) across the top-left/right cells. The first-page full grid layout, number of pages beyond the documented second page, and whether it offers tense initials, compound vowels, space, delete, or cancel as grid cells are **unverified**.
- **Composition:** Enter a syllable without a final, then select a final-consonant token to replace that prior syllable; e.g. `나 + ㄲ → 낚`. The token itself is not stored. This is a two-step final attachment, rather than a full Dubeolsik automaton. Compound vowel composition and final-cluster entry rules are **unverified**.
- **Backspace:** The existing back action deletes a whole completed syllable. Jamo-level editing is not documented.
- **Missing glyphs:** The generated final-combination table is checked against the name-entry font map; the project reports all 1,996 generated combinations have a glyph. Behavior for a requested combination outside that table is **unverified**.
- **Storage and limit:** Existing 16-byte name buffer remains unchanged: two-byte CP932 stand-in per Hangul syllable, up to eight characters.
- **Implementation:** Input-handler patch at ROM address `0x080500C4`, connected through a Thumb trampoline to new handler code at `0x08FDF800`; a generated 1,996-entry `(base syllable, final) → completed syllable` table is stored after `0xFDFA80`. Name rendering and the base buffer format are reused.
- **Source and license:** [Project source repository](https://github.com/TAMTAMQ/digicomm-2-korean-translation-patch), [implementation notes in STATUS.md](https://github.com/TAMTAMQ/digicomm-2-korean-translation-patch/blob/main/STATUS.md), [MIT license](https://github.com/TAMTAMQ/digicomm-2-korean-translation-patch/blob/main/LICENSE). The repo states that its tools are MIT-licensed. Its public documentation contains implementation details; I could not verify the exact current source-file contents through the browser fetch.  
  **Trust:** project primary source; exact code path details from project notes.

### Official Pokémon Gold/Silver Korean release (GBC)

The Korean release is a strong reference for a shipped handheld name-entry system, although the sources available here describe character coverage rather than its internal UI or composition code.

- **Grid:** Korean Gold/Silver name-entry accepts Hangul blocks and 40 jamo. Exact grid arrangement, page count, and placement of delete/space/confirmation controls are **unverified**.
- **Composition:** The encoding includes 40 jamo and 2,353 syllable blocks: the 2,350 KS X 1001 set with five additional syllables and several substitutions. The list says there are no jamo used exclusively as finals in the encoding. How the game composes initial + medial + final, handles compound vowels/final clusters, or edits an in-progress syllable is **unverified**.
- **Missing glyphs:** The documented set is finite. It does not establish whether the UI blocks or skips unrepresentable compositions.
- **Storage and limit:** A secondary Korean hardware write-up says the game uses two tiles per Hangul character and extra VRAM/WRAM; a Korean wiki reports a five-character player/Pokémon naming limit. These are secondary sources; the exact internal name-buffer encoding and byte count are **unverified**.
- **Implementation:** Official game code; no source code or documented hook location found.
- **Sources:** [Bulbapedia: Text entry in Pokémon games](https://bulbapedia.bulbagarden.net/wiki/Text_entry_in_the_Pok%C3%A9mon_games) (coverage summary), [Bulbapedia: Korean Generation II character encoding](https://bulbapedia.bulbagarden.net/wiki/Korean_character_encoding_%28Generation_II%29) (encoded repertoire), [Korean GBC technical overview](https://mgaver.tistory.com/122) (tile and memory notes), [K-Wiki: Pokémon Gold/Silver](https://www.k-wiki.org/wiki/%ED%8F%AC%EC%BC%93%EB%AA%AC%EC%8A%A4%ED%84%B0_%EA%B8%88%C2%B7%EC%9D%80) (five-character limit).  
  **Trust:** Bulbapedia is secondary; technical UI details are secondary and do not reveal the automaton.

### Korean Pokémon Gold/Silver disassembly

This is a community disassembly of the official Korean Game Boy Color games. Its README identifies the project and character map source, but does not describe name-entry behavior.

- **Grid, composition, editing, missing-glyph handling, name-buffer limit, and input-handler location:** **unverified from the README**.
- **Reusable code:** It is a disassembly, but I did not verify whether a name-input implementation is present or reusable. Do not assume the Japanese/Western `pret/pokegold` input code applies to the Korean build.
- **Sources:** [Repository README](https://github.com/Narishma-gb/pokegold-kr), which credits the upstream [pret/pokegold](https://github.com/pret/pokegold) structure and says its Korean character map comes from Bulbapedia.  
  **Trust:** repository is primary for its own scope; no specific name-entry claim.

### Other Korean GBA patches checked

I found Korean GBA patch repositories for *Fire Emblem*, *Super Robot Wars J*, and *Nobunaga’s Ambition*, but no source documentation establishing a Hangul-composing name-entry replacement. One *Nobunaga’s Ambition* patch explicitly says it leaves the original hiragana name grid intact because its UI is character-at-a-time. *Super Robot Wars J* documents a 2,350-syllable font substitution, but not a name-entry rewrite.

- [Nobunaga’s Ambition GBA Korean patch](https://github.com/snake7594/gba-nobunaga-korean-patch): original name grid retained; its README says the grid is character-level, so Hangul composition is unavailable. Exact delete/length behavior is **unverified**.
- [Super Robot Wars J GBA Korean patch](https://github.com/snake759494/srwj-korean-patch): source documents a 2,350-syllable font transfer, not a name-input implementation.
- **Fire Emblem, Mother 3, Golden Sun, Harvest Moon/Rune Factory, SNES/PS1:** I did not find a public source that reliably documents a Korean jamo-composing name-entry patch for these examples. This is a search limitation, not proof none exists.

## Composition and repertoire references

Unicode specifies a systematic composition/decomposition model for modern Hangul: 19 initial consonants × 21 vowels × 28 final states (including no final), producing 11,172 syllables. This is a useful correctness reference for a Dubeolsik-style automaton, but not evidence of how any particular ROM implements it. [Unicode Core Specification §3.12](https://www.unicode.org/versions/Unicode18.0.0/core-spec/chapter-3/)

KS X 1001 covers 2,350 precomposed Hangul syllables, not all 11,172 modern combinations. [Unicode Technical Note L2/17-080](https://www.unicode.org/L2/L2017/17080-three-hangul-syl.pdf) describes the 2,350 KS X 1001 set and the broader modern Hangul repertoire.

## Recommendation for an 8-character GBA field

**DECISION NEEDED:** Whether the user experience must support full Dubeolsik composition, or whether a simpler two-page base-syllable-plus-final workflow is acceptable.

For full composition, retain the game’s existing two-byte syllable storage and render only completed syllables. Track a small composition state (`initial`, `medial`, optional `final`) separately from the committed name buffer. After each key, map the candidate syllable through the ROM’s 2,350-syllable table. If there is no glyph, reject that key without changing the current candidate or committed name; don’t substitute a visually unrelated syllable. Backspace should first undo the current composition state, then remove a committed syllable when the state is empty. Commit only on a new initial, explicit confirm, or another clearly defined boundary. Store at most eight encoded syllables (16 bytes), counting characters rather than jamo.

A simpler approach with a similar GBA precedent is a base-syllable page plus a final-consonant page. It preserves two-byte storage and whole-syllable backspace, but it cannot freely compose arbitrary names unless the base page exposes every needed initial+medial syllable. Either approach needs explicit handling for the finite font: test all generated candidates against the actual name-entry glyph map, and make unsupported combinations visibly unavailable or reject them cleanly.

**Pitfalls:** Dubeolsik input must distinguish consonants used as initials from those that can be finals. A following vowel can move a previously typed final consonant to the next syllable’s initial (e.g. `한 + ㄱ + ㅏ` becomes `하나` under normal IME behavior), and compound vowels/final clusters need split-and-reprocess behavior when another jamo arrives. A naïve “append jamo until complete” state machine will mishandle these cases. The 2,350-font limit also means valid modern Hangul combinations can be unrenderable; never store an unrenderable code merely because the composition arithmetic succeeded.

## Evidence inventory

- DigiCommunication 2 implementation claims: [STATUS.md](https://github.com/TAMTAMQ/digicomm-2-korean-translation-patch/blob/main/STATUS.md), checked 2026-10-23, **official project source**.
- DigiCommunication 2 project code license: [LICENSE](https://github.com/TAMTAMQ/digicomm-2-korean-translation-patch/blob/main/LICENSE), checked 2026-10-23, **official project source**.
- Korean Pokémon name-entry repertoire: [Text entry overview](https://bulbapedia.bulbagarden.net/wiki/Text_entry_in_the_Pok%C3%A9mon_games), checked 2026-10-23, **secondary**.
- Korean Pokémon character encoding: [Generation II encoding](https://bulbapedia.bulbagarden.net/wiki/Korean_character_encoding_%28Generation_II%29), checked 2026-10-23, **secondary**.
- Pokémon Korean hardware details: [GBC overview](https://mgaver.tistory.com/122), checked 2026-10-23, **secondary**.
- Hangul composition and repertoire: [Unicode §3.12](https://www.unicode.org/versions/Unicode18.0.0/core-spec/chapter-3/), checked 2026-10-23, **official**; [Unicode L2/17-080](https://www.unicode.org/L2/L2017/17080-three-hangul-syl.pdf), checked 2026-10-23, **official**.

I couldn’t write the requested report file: the workspace filesystem is read-only, and creating `temp/user_report-2026-10-23/` failed. This report is provided here only.

RECEIPT: model=unknown effort=unknown role=research-external