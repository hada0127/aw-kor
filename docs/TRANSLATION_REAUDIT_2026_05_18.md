# Translation Re-Audit - 2026-05-18

## Corrected Status
- Total extracted text rows: 28,347
- Meaningful Korean translations: 11,383 (40.16%)
- Needs real translation: 16,226
- Needs manual review: 738
- Remaining rows total: 16,964
- Remaining unique source strings: 12,434

## Why Previous 100% Was Wrong
- Placeholder coverage was counted as completion.
- `미상` was used for many rows that still contain readable Japanese source text.
- The current import CSV is complete only in the technical sense that every address has a value; it is not semantically translated.

## Audit Reason Counts
- placeholder_or_unknown: 16,226
- has_korean_translation: 11,383
- no_hangul_in_korean: 738

## Previous Note Counts
- audit: placeholder/unknown; previous=reviewed: unreadable source fallback: 15,208
- audit: meaningful Korean translation; previous=reviewed: existing address translation: 6,216
- audit: meaningful Korean translation; previous=reviewed: repeated source text: 2,223
- batch audit: reviewed batch translation; source=manual_translation_batch_001.csv: 1,010
- audit: placeholder/unknown; previous=reviewed: existing address translation: 657
- batch audit: reviewed batch translation; source=manual_translation_batch_002.csv: 402
- audit: no Hangul in Korean field; previous=reviewed: repeated source text: 367
- audit: no Hangul in Korean field; previous=reviewed: existing address translation: 364
- audit: placeholder/unknown; previous=reviewed: repeated source text: 361
- batch audit: reviewed batch translation; source=manual_translation_batch_005.csv: 356
- batch audit: reviewed batch translation; source=manual_translation_batch_004.csv: 345
- batch audit: reviewed batch translation; source=manual_translation_batch_006.csv: 285
- batch audit: reviewed batch translation; source=manual_translation_batch_003.csv: 251
- batch audit: reviewed batch translation; source=manual_translation_batch_007.csv: 172
- batch audit: reviewed batch translation; source=manual_translation_batch_008.csv: 126
- batch audit: no Hangul in Korean field; source=manual_translation_batch_005.csv: 4

## Top Remaining Repeated Source Strings
- 33x: 、、∪
- 31x: ，，∪
- 26x: 　　∪
- 24x: 宇巽妲
- 24x: 。。∪
- 24x: 　、∪
- 23x: ・・・・・・
- 21x: 劔劔劔劔
- 18x: 　、、。
- 16x: ：！｀￣ヾ〃仝々浦〆〇〇
- 16x: ￣〇／”〕」＋
- 16x: 謁〉…―¨；　
- 16x: 色宇В
- 15x: υυυ
- 15x: ；：∪
- 13x: ・・・・。
- 12x: ，゜¨ヽ
- 12x: 　ァ　　　
- 12x: 　　ψ
- 12x: 『∂『
- 12x: 、　　∪
- 11x: А　　
- 10x: 、。∪
- 10x: τττχ
- 10x: 劔劔劔劔劔劔劔劔
- 9x: 劔劔劔劔囮劔囮劔
- 9x: 。．∪
- 9x: 劔劔囮劔
- 9x: 囮劔劔劔飭劔
- 9x: 　・！！？．

## Generated Files
- Rework list: `data/translation_needs_rework.csv`
