▶ codex review: model=gpt-6-astra effort=medium sandbox=read-only out=/home/taro1/.agent-harness/state/out/20261023-124240-review.md
Revision: `44b43c4d505b90ce0ce2664012847909ecd6ad14`  
Delta: `fa74c95..44b43c4`. Subsequent code changes invalidate this review.

## Summary

**CHANGES-REQUIRED.** One confirmed shared-glyph regression. Read-only inspection; no builds, tests, or emulators executed.

Previous review B1 remains **fixed**; its metadata/audit changes are untouched.

## Blocking

### B1 — Mandatory: Name-grid replacement overwrites the shared dialogue dash

**Location:** `tools/build_korean_full.py:5233`.

The `ー → 으` replacement writes 64 bytes at `0x809CD6`. This is the pixel payload of the **shared A3 `0x815B` node at `0x809CD0`**, not a grid-exclusive asset.

Concrete existing consumers:

- `tools/renderer_text.py:61` converts Part 2 hyphens to `ー`.
- `tools/test_dialogue_script_safety.py:322–346` identifies that exact node and establishes that `준비됐어-.` at source `0xA0A833` encodes its dash as `0x815B`.
- The new writer therefore replaces that dialogue punctuation with `으`. Runtime appearance remains **(unverified)**, but the conflicting producer/consumer contract is explicit.

The original-byte guard detects earlier writes; it does not establish exclusive ownership. Unchanged B-team text bytes likewise do not preserve visible wording when their glyph changes.

**Basis:** Explicit request to exclude shared consumers and keep B-team untouched; concrete regression in established dialogue punctuation rendering.

**Prescription:** Restore the shared `0x815B` picture and remove that replacement first. Any Korean replacement for this selectable cell must be isolated to the name-entry and saved-name consumers. Audit the remaining 55 nodes before claiming grid exclusivity.

**Change together:** Glyph mapping/counts, affected documentation, final-ROM dash regression coverage, and name-entry/persistence evidence if the mapping changes.

## Findings

- **Mapping:** Small-kana duplicates are consistent visual aliases with distinct stored codes; no independent blocker found. `ー → 으` is unsafe for the shared consumer above.
- **Guarded writes:** Fixed 64-byte writes preserve node headers. Missing rendered glyphs fail explicitly.
- **Evidence correction:** The persistence sheet’s original column shows `アアアアア`, not `?????` as stated in `docs/research.md`, `SWEEP3_REPORT.md`, and related claims. Correct the description. **Change together:** Those evidence summaries.
- **Cross-consistency:** Supplied logs report 1,802 changed bytes confined to 56 regions and 14 unchanged screens. Those checks do not establish consumer isolation. Button captures support unchanged readable labels. Other name/link consumers remain **(unverified)**.

## Needs verification

After fixing B1:

```sh
python3 -m unittest discover -s tools -p 'test_dialogue_script_safety.py'
```

Add a final-ROM assertion preserving the shared dash pixels; existing encoding tests alone cannot detect this regression. Capture the affected M4 dialogue, then repeat name selection, confirmation, save, and cold reload. Provide consumer tracing for the remaining modified nodes.

**Verdict: CHANGES-REQUIRED.**

RECEIPT: model=unknown effort=unknown role=review