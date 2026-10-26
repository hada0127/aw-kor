# W11 read-only diagnosis: Part 2 Link ID 3251 (2026-10-26)

## Finding

The candidate does contain the approved Korean receive message. The Japanese seen in W7 is caused by its test ROM redirecting the host ticker pointer to the **old source slot** `0xA350B4`, while the candidate’s live Part 2 message table points to relocated Korean at `0xA5CBC8`. No later build stage overwrites `0xA350B4` with Japanese: the protected full-fidelity script stage itself restores the original bytes there because its 42-byte encoded text exceeds the 38-byte source span, then the repointer writes the Korean to free space and updates the pointer. This is a QA route artifact, not proof of Japanese on the native receive route. That native route remains (unverified).

## Evidence and stage trace

- `temp/encode_report.csv:85,317` records a 34/38 fit, but this is a fit estimate, not a final-write ledger. `tools/build_korean_full.py:14818-14830` imports fitted CSV Korean; `:15024-15040` applies the dialogue override. `data/dialogue_overrides.json:3257` and `data/bteam_baseline.json:1322,3384` hold the approved spacing. `tools/build_korean_full.py:2050` still has a shorter hand override, but the B-team restoration and explicit dialogue override take precedence.
- `data/bteam_round2_decisions.tsv:131` marks `0xA350B4` `RELOCATE` (historically 40/38 before the approved extra space). `tools/build_korean_full.py:12462` includes it in protected rows. In `patch_script_row`, `:16219-16226` requires full-fidelity text; `:16220-16224` and `:16264-16273` preserve `orig[faddr:fend]` for overflow and request relocation.
- `tools/build_korean_full.py:24400-24418` runs `repoint_messages`. `tools/dialogue_repoint.py:1263-1271` writes the new message and all pointer sites. The candidate-attested `temp/repoint_manifest.json` entry says `msg=0xA350B4`, `status=relocated`, `new_addr=0xA5CBC8`, `new_len=44`, `line_spans=42`, `ptr_sites=[0xA38A80]`. The candidate build receipt attests SHA-256 `7013de06…` for that manifest; the current manifest matches the full attested hash.
- Original `0xA38A80` pointer = `0x08A350B4`; candidate and b44 pointer = `0x08A5CBC8`. Candidate `0xA5CBC8..0xA5CBF3` is a Korean-encoded 44-byte message. Candidate and b44 old `0xA350B4..0xA350D9` 38-byte text slots equal the Japanese original. A raw-byte scan confirms the full 38-byte Japanese source occurs in the candidate at `0x929790`, `0x962428`, `0x99ACCC`, `0x9D3570`, `0xA350B4`, `0xEE26CC`.
- `tools/link_client_font.py:10-16,159-164,384-420` deliberately restores client-image copies outside its live-string set; these five extra addresses are in client/dead-copy ranges. A scan for literal ROM pointers to each found none. Whether a client can address one by relative offset remains (unverified). The sixth original duplicate at `0xB8301C` is not byte-identical in the candidate: it is also relocated. It is a separate message, not the source of W7’s frame.
- `temp/unseen_20261026/w7/cheat_messages.py:8` always writes `0x08000000 + target` into `0xA38A60`, so for ID 3251 it deliberately points to the stale source slot. W7’s own report labels that capture CHEAT; it does not establish native receive behavior.
- The checked candidate SHA-256 is `01f65b11d0dfa65c95b76558bd7997b761133aaf9abe68442bc608c4791b262e`, matching its build receipt. `tools/build_korean_full.py` is being edited concurrently and no longer matches the receipt input hash; its cited line numbers describe the current tree. The unchanged manifest, dialogue repointer, source data, and ROM bytes establish the candidate behavior.

## Requested Link sister rows

| ID | Source slot | Candidate slot vs original | Manifest active target | Result |
|---:|---|---|---|---|
| 3250 | `0x00A3508C` | changed from original | `0xA5CB9C` | Korean at active target or in-place; W7 CHEAT PASS |
| 3251 | `0x00A350B4` | Japanese original | `0xA5CBC8` | Korean at active target; W7 forced old Japanese slot |
| 3252 | `0x00A350DC` | changed from original | `source slot` | Korean at active target or in-place; W7 CHEAT PASS |
| 3253 | `0x00A350F8` | changed from original | `source slot` | Korean at active target or in-place; W7 CHEAT PASS |
| 3254 | `0x00A3511C` | changed from original | `0xA5CBF4` | Korean at active target or in-place; W7 CHEAT PASS |
| 3255 | `0x00A3514C` | changed from original | `0xA5CC28` | Korean at active target or in-place; W7 CHEAT PASS |
| 3256 | `0x00A3517C` | changed from original | `source slot` | Korean at active target or in-place; W7 CHEAT PASS |

## Other listed protected Link/UI source slots

| Source slot | Candidate source | Active destination |
|---|---|---|
| `0x00A34E98` | original Japanese | `0xA5C9F0` |
| `0x00A34F98` | changed | `in place` |
| `0x00A34FEC` | original Japanese | `0xA5CAFC` |
| `0x00A350B4` | original Japanese | `0xA5CBC8` |
| `0x00A35228` | changed | `in place` |
| `0x00A35258` | original Japanese | `0xA5CC88` |
| `0x00A35280` | original Japanese | `0xA5CCBC` |

For the complete `BTEAM_RESTORE_BASELINE_ROWS` list (`tools/build_korean_full.py:12440-12504`), all 485 addresses had a found-text slot and Korean override/baseline. Exactly 221 source slots are byte-identical to Japanese original, and **all 221** have `status=relocated` in the attested manifest; zero identical Japanese slots lacked a relocation record. Another 64 relocated source slots differ from original; 199 non-relocated slots differ from original. This is a source-byte comparison and does not by itself prove every native route reaches its relocated target. The 220 other retained source addresses follow (all have Korean translations and relocated manifest entries):

`0x00A0237C` `0x00A043A8` `0x00A05454` `0x00A05E68` `0x00A06974` `0x00A07330` `0x00A074AC` `0x00A08470` `0x00A08930` `0x00A08B98` `0x00A090A4` `0x00A0922C`
`0x00A10EDC` `0x00A152F0` `0x00A153F0` `0x00A1597C` `0x00A16094` `0x00A1C104` `0x00A1C75C` `0x00A1C8E8` `0x00A1CA1C` `0x00A1CC5C` `0x00A1D294` `0x00A20F38`
`0x00A22708` `0x00A229CC` `0x00A24784` `0x00A24804` `0x00A24AAC` `0x00A24B68` `0x00A259CC` `0x00A262B0` `0x00A26704` `0x00A26BEC` `0x00A2AA08` `0x00A2C238`
`0x00A2C440` `0x00A2C45C` `0x00A2C5AC` `0x00A2C5C8` `0x00A2C644` `0x00A2C950` `0x00A2C9B4` `0x00A2CA10` `0x00A2CABC` `0x00A2D5C8` `0x00A2D650` `0x00A2D684`
`0x00A2D6AC` `0x00A2D6F0` `0x00A2D72C` `0x00A2D73C` `0x00A302AC` `0x00A304A8` `0x00A30620` `0x00A30640` `0x00A30860` `0x00A3088C` `0x00A30904` `0x00A30930`
`0x00A30968` `0x00A30A6C` `0x00A30D5C` `0x00A30DCC` `0x00A30E74` `0x00A30EDC` `0x00A313FC` `0x00A34E98` `0x00A34FEC` `0x00A35258` `0x00A35280` `0x00B81884`
`0x00B81A20` `0x00B81E08` `0x00B81E1C` `0x00B81E50` `0x00B81E78` `0x00B81E8C` `0x00B81E98` `0x00B81F04` `0x00B81F40` `0x00B81F70` `0x00B81F80` `0x00B81FAC`
`0x00B81FC4` `0x00B81FF4` `0x00B828E4` `0x00B83DB0` `0x00B84298` `0x00B84A48` `0x00B84BA0` `0x00B84BB4` `0x00D82364` `0x00D823C8` `0x00D82424` `0x00D824B0`
`0x00D8F55E` `0x00D8FE8A` `0x00D903BA` `0x00D9219E` `0x00D9287C` `0x00D94552` `0x00D95EF2` `0x00D965DE` `0x00D96F66` `0x00D98136` `0x00D9B210` `0x00D9C4B2`
`0x00D9EB86` `0x00D9EDB6` `0x00D9F3E2` `0x00DA0616` `0x00DA0802` `0x00DC2ECA` `0x00DC3822` `0x00DC3B1E` `0x00DC3C63` `0x00DC4466` `0x00DC50C2` `0x00DC611A`
`0x00DC6F06` `0x00DC7E9A` `0x00DCB1BE` `0x00DCBA1A` `0x00DCBB36` `0x00DCC622` `0x00DCC63A` `0x00DCCE86` `0x00DCD9C2` `0x00DCD9DA` `0x00DCDEEB` `0x00DCEA43`
`0x00DD0036` `0x00DD010A` `0x00DD054A` `0x00DE9D8E` `0x00DE9F4A` `0x00DEA136` `0x00DEA376` `0x00DEA54A` `0x00DEB85E` `0x00DEB93A` `0x00DED00A` `0x00DED38A`
`0x00DED65A` `0x00DEE3EA` `0x00DEE442` `0x00DEE496` `0x00DEE7AA` `0x00DEEFF6` `0x00DEF0B2` `0x00DEF3E2` `0x00DF1EEE` `0x00DF2026` `0x00DF207A` `0x00DF217E`
`0x00DF21AE` `0x00DF21EE` `0x00DF228E` `0x00DF239E` `0x00DF25FA` `0x00DF266E` `0x00DF26FE` `0x00DF2806` `0x00DF285A` `0x00DF28C2` `0x00DF2966` `0x00DF2DA6`
`0x00DF3287` `0x00DF332A` `0x00DF33B7` `0x00DF369F` `0x00DF3AFA` `0x00DF422E` `0x00DF437A` `0x00DF44F6` `0x00DF587B` `0x00DF58DB` `0x00DF59CF` `0x00DF6146`
`0x00DF6E0E` `0x00DF7032` `0x00DF77DE` `0x00DF8DB2` `0x00DF8E16` `0x00DF8E6E` `0x00DF92CA` `0x00DFA616` `0x00DFA79A` `0x00DFA7BE` `0x00DFA8AA` `0x00DFA8EA`
`0x00DFA90A` `0x00DFA926` `0x00DFB4F2` `0x00DFB56A` `0x00DFB982` `0x00DFCFDE` `0x00DFD0B6` `0x00DFD1B2` `0x00E0112E` `0x00E0374E` `0x00E03852` `0x00E05A32`
`0x00E0630A` `0x00E07CA6` `0x00E08DFC` `0x00E0A028` `0x00E0B0CC` `0x00E0C0F2` `0x00E0C2D4` `0x00E0D378` `0x00E0E592` `0x00E0E614` `0x00E0EFD2` `0x00E0F6E2`
`0x00E0F772` `0x00E0FF0C` `0x00E10D7A` `0x00EC3192`

## Minimal correction proposed; not applied

In `temp/unseen_20261026/w7/cheat_messages.py:8`, for the **candidate** resolve each `target` through the candidate-attested `repoint_manifest.json`: when its message has `status=relocated`, redirect `0xA38A60` to `0x08000000 + new_addr`; for the original, keep the original source address. Record both requested source address and actual redirected address in the test receipt. Re-capture ID 3251 (and any other relocated test targets) to test the active bytes. Do not modify `tools/build_korean_full.py` or overwrite the old source slot to satisfy this forced-pointer test. A native receive-state capture is still needed for gameplay reachability.

## Verification performed

- Read-only SHA-256 comparison of original/candidate/b44 source slots and pointer words; Python exited 0.
- Parsed all 485 protected addresses, found-text lengths, Korean override/baseline, and attested repoint manifest; Python exited 0.
- Scanned candidate ROM for the exact 38-byte Japanese source and literal pointer references; Python exited 0.
- No build, emulator run, tracked-file edit, or commit was performed.
