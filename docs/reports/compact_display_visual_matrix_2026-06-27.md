# Compact Display Visual Matrix

- ROM SHA: `d48ba36c4db44589f05a8868ea26bdcc4e66023eb0931cf54c3ecd5d9aea0e7f`
- Contact sheet: `docs/screenshots/e12_compact_display_matrix_2026-06-27/current_representative_contact.png`

This report separates static byte/editor coverage from target-level runtime/source proof.
A current screen scene proves the scene was captured on this ROM, but does not by itself prove every table target is visible.

## Summary

| Group | Targets | Editor | Screen scene | Current capture | Container-only | Static ext ptr | Target runtime/source proof |
|---|---:|---:|---:|---:|---:|---:|---:|
| A2 CO power profile compact names | 36 | 36 | 1 | 0 | 35 | 36 | 0 |
| B84 compact CO power names | 11 | 11 | 0 | 0 | 11 | 11 | 0 |
| B8 compact display table bucket | 459 | 459 | 0 | 0 | 459 | 390 | 13 |

## Current Representative Screens

- `23_part2_main_menu`: current=False path=`temp/scene_screenshots/07_part2_main_menu_patched/frame.png` reason=rom_sha_mismatch
- `23a_part2_wars_shop`: current=False path=`temp/scene_screenshots/scene_23a_part2_wars_shop_patched/frame.png` reason=rom_sha_mismatch
- `86_common_compact_menu_tables`: current=False path=`temp/scene_screenshots/scene_86_common_compact_menu_tables_patched/frame.png` reason=rom_sha_mismatch
- `30f2_part2_co_profile_story`: current=False path=`temp/scene_screenshots/scene_30f2_part2_co_profile_story_patched/frame.png` reason=rom_sha_mismatch
- `26_part2_battle_labels`: current=False path=`temp/scene_screenshots/30_battle_attack_patched/frame.png` reason=rom_sha_mismatch
- `24a_part2_operation_select`: current=False path=`temp/scene_screenshots/10_part2_region_map_redstar_patched/frame.png` reason=rom_sha_mismatch
- `85_ui_common`: current=False path=`temp/scene_screenshots/scene_85_ui_common_patched/frame.png` reason=rom_sha_mismatch
- `87_common_rule_settings`: current=False path=`temp/scene_screenshots/scene_87_common_rule_settings_patched/frame.png` reason=rom_sha_mismatch

## Renderer Trace

- trace_present=True current=True rom_sha=`d48ba36c4db44589f05a8868ea26bdcc4e66023eb0931cf54c3ecd5d9aea0e7f` cases=10 hits=1758 direct=0 breakpoints=55 code_context=True path=`data/compact_display_renderer_trace.json`

## Static Code Context

- code_context_present=True current=True rom_sha=`d48ba36c4db44589f05a8868ea26bdcc4e66023eb0931cf54c3ecd5d9aea0e7f` path=`data/compact_display_code_context.json` literal_entries=695 breakpoint_candidates=24 function_candidates=18

## Manual Visual Evidence

- manual_present=True path=`data/compact_display_manual_visual_evidence.json` current=13 accepted=13 invalid=0 stale=0 note=Manual visual evidence is target-level only when the entry is for the current ROM SHA, has a positive pixel diff, has a durable contact sheet, and the group/address matches a matrix target. Mutation proof establishes live source provenance, not full visual-integrity coverage.
- accepted_by_group_scene={'b8_compact_display_table_all::15_part1_operation_logos': 13}
- accepted_by_checkpoint={'41_part1_operation_room': 4, '41_part1_operation_room_plus_10steps_288ebbc326': 3, '41_part1_operation_room_plus_13steps_eba0d9ed13': 1, '41_part1_operation_room_plus_press_DOWN_120_press_DOWN_120_press_DOWN_120_press_DOWN_120': 2, '41_part1_operation_room_plus_press_DOWN_120_press_DOWN_120_press_DOWN_120_press_DOWN_120_press_DOWN_120_press_DOWN_120': 1, '41_part1_operation_room_plus_press_DOWN_120_press_DOWN_120_press_DOWN_120_press_DOWN_120_press_DOWN_120_press_DOWN_120_press_DOWN_120': 2}
- `0x00B81F38` b8_compact_display_table_all: current=True accepted=True errors=[] type=single_address_mutation_pixel_diff checkpoint=41_part1_operation_room_plus_13steps_eba0d9ed13 diff_pixels=58 contact=`docs/screenshots/e12_compact_display_matrix_2026-06-27/b8_compact_display_table_all_00B81F38_mutation_contact.png`
- `0x00B81F40` b8_compact_display_table_all: current=True accepted=True errors=[] type=single_address_mutation_pixel_diff checkpoint=41_part1_operation_room_plus_10steps_288ebbc326 diff_pixels=67 contact=`docs/screenshots/e12_compact_display_matrix_2026-06-27/b8_compact_display_table_all_00B81F40_mutation_contact.png`
- `0x00B81F4C` b8_compact_display_table_all: current=True accepted=True errors=[] type=single_address_mutation_pixel_diff checkpoint=41_part1_operation_room_plus_10steps_288ebbc326 diff_pixels=77 contact=`docs/screenshots/e12_compact_display_matrix_2026-06-27/b8_compact_display_table_all_00B81F4C_mutation_contact.png`
- `0x00B81F5C` b8_compact_display_table_all: current=True accepted=True errors=[] type=single_address_mutation_pixel_diff checkpoint=41_part1_operation_room_plus_10steps_288ebbc326 diff_pixels=70 contact=`docs/screenshots/e12_compact_display_matrix_2026-06-27/b8_compact_display_table_all_00B81F5C_mutation_contact.png`
- `0x00B81F70` b8_compact_display_table_all: current=True accepted=True errors=[] type=single_address_mutation_pixel_diff checkpoint=41_part1_operation_room_plus_press_DOWN_120_press_DOWN_120_press_DOWN_120_press_DOWN_120_press_DOWN_120_press_DOWN_120_press_DOWN_120 diff_pixels=43 contact=`docs/screenshots/e12_compact_display_matrix_2026-06-27/b8_compact_display_table_all_00B81F70_mutation_contact.png`
- `0x00B81F80` b8_compact_display_table_all: current=True accepted=True errors=[] type=single_address_mutation_pixel_diff checkpoint=41_part1_operation_room_plus_press_DOWN_120_press_DOWN_120_press_DOWN_120_press_DOWN_120_press_DOWN_120_press_DOWN_120 diff_pixels=82 contact=`docs/screenshots/e12_compact_display_matrix_2026-06-27/b8_compact_display_table_all_00B81F80_mutation_contact.png`
- `0x00B81F98` b8_compact_display_table_all: current=True accepted=True errors=[] type=single_address_mutation_pixel_diff checkpoint=41_part1_operation_room_plus_press_DOWN_120_press_DOWN_120_press_DOWN_120_press_DOWN_120_press_DOWN_120_press_DOWN_120_press_DOWN_120 diff_pixels=246 contact=`docs/screenshots/e12_compact_display_matrix_2026-06-27/b8_compact_display_table_all_00B81F98_mutation_contact.png`
- `0x00B81FAC` b8_compact_display_table_all: current=True accepted=True errors=[] type=single_address_mutation_pixel_diff checkpoint=41_part1_operation_room_plus_press_DOWN_120_press_DOWN_120_press_DOWN_120_press_DOWN_120 diff_pixels=47 contact=`docs/screenshots/e12_compact_display_matrix_2026-06-27/b8_compact_display_table_all_00B81FAC_mutation_contact.png`
- `0x00B81FC4` b8_compact_display_table_all: current=True accepted=True errors=[] type=single_address_mutation_pixel_diff checkpoint=41_part1_operation_room_plus_press_DOWN_120_press_DOWN_120_press_DOWN_120_press_DOWN_120 diff_pixels=267 contact=`docs/screenshots/e12_compact_display_matrix_2026-06-27/b8_compact_display_table_all_00B81FC4_mutation_contact.png`
- `0x00B81FDC` b8_compact_display_table_all: current=True accepted=True errors=[] type=single_address_mutation_pixel_diff checkpoint=41_part1_operation_room diff_pixels=77 contact=`docs/screenshots/e12_compact_display_matrix_2026-06-27/b8_compact_display_table_all_00B81FDC_mutation_contact.png`
- `0x00B81FF4` b8_compact_display_table_all: current=True accepted=True errors=[] type=single_address_mutation_pixel_diff checkpoint=41_part1_operation_room diff_pixels=49 contact=`docs/screenshots/e12_compact_display_matrix_2026-06-27/b8_compact_display_table_all_00B81FF4_mutation_contact.png`
- `0x00B8200C` b8_compact_display_table_all: current=True accepted=True errors=[] type=single_address_mutation_pixel_diff checkpoint=41_part1_operation_room diff_pixels=66 contact=`docs/screenshots/e12_compact_display_matrix_2026-06-27/b8_compact_display_table_all_00B8200C_mutation_contact.png`
- `0x00B82018` b8_compact_display_table_all: current=True accepted=True errors=[] type=single_address_mutation_pixel_diff checkpoint=41_part1_operation_room diff_pixels=54 contact=`docs/screenshots/e12_compact_display_matrix_2026-06-27/b8_compact_display_table_all_00B82018_mutation_contact.png`

## Static Pointer Xrefs

- xref_present=True path=`data/compact_display_xref_analysis.json`
- `a2_co_power_profile_display_overrides`: targets=36 ptr_targets=36 external_ptr_targets=36 second_level_targets=0
- `b84_compact_power_display_overrides`: targets=11 ptr_targets=11 external_ptr_targets=11 second_level_targets=1
- `b8_compact_display_table_all`: targets=459 ptr_targets=406 external_ptr_targets=390 second_level_targets=8

## Read-Watch Probes

- probes_present=True probes=25 current=0 stale=25 cases=0 hits=0 direct_reads=0
- hit/direct_read totals are event counts, not unique target counts; multi-step probes can include reads from earlier redraws on the same route.
- `data/compact_display_read_watch_a2_profile_coid_current.json`: current=False groups=['a2_co_power_profile_display_overrides'] cases=18 hits=967 direct_reads=967 targets=36 proof_mode=synthetic_ram_field_read_watch
- `data/compact_display_read_watch_a2_profile_domino_max_current.json`: current=False groups=['a2_co_power_profile_display_overrides'] cases=4 hits=204 direct_reads=204
- `data/compact_display_read_watch_a2_profile_down3_current.json`: current=False groups=['a2_co_power_profile_display_overrides', 'b84_compact_power_display_overrides'] cases=1 hits=68 direct_reads=68
- `data/compact_display_read_watch_a2_profile_down_current.json`: current=False groups=['a2_co_power_profile_display_overrides', 'b84_compact_power_display_overrides'] cases=1 hits=34 direct_reads=34
- `data/compact_display_read_watch_a2_profile_right_current.json`: current=False groups=['a2_co_power_profile_display_overrides', 'b84_compact_power_display_overrides'] cases=1 hits=68 direct_reads=68
- `data/compact_display_read_watch_a2_profile_selector_0200d63e_current.json`: current=False groups=['a2_co_power_profile_display_overrides'] cases=10 hits=618 direct_reads=618
- `data/compact_display_read_watch_action_menu_a30_b8_exact.json`: current=False groups=['b8_compact_display_table_all'] cases=1 hits=0 direct_reads=0 targets=7
- `data/compact_display_read_watch_action_menu_a30_b8_range.json`: current=False groups=['b8_compact_display_table_all'] cases=1 hits=0 direct_reads=0
- `data/compact_display_read_watch_action_menu_from_after_a36_b8_exact.json`: current=False groups=['b8_compact_display_table_all'] cases=1 hits=0 direct_reads=0 targets=7
- `data/compact_display_read_watch_b83268_comm.json`: current=False groups=['b8_compact_display_table_all'] cases=1 hits=0 direct_reads=0 targets=1
- `data/compact_display_read_watch_b84_power_title_20260628.json`: current=False groups=['b84_compact_power_display_overrides'] cases=1 hits=1 direct_reads=1 targets=1
- `data/compact_display_read_watch_b84_power_titles_coid_current.json`: current=False groups=['b84_compact_power_display_overrides'] cases=11 hits=11 direct_reads=11 targets=11
- `data/compact_display_read_watch_b8_fresh_menu_sweep_subset.json`: current=False groups=['b8_compact_display_table_all'] cases=1 hits=0 direct_reads=0 targets=7
- `data/compact_display_read_watch_b8_map_territory_current.json`: current=False groups=['b8_compact_display_table_all'] cases=1 hits=0 direct_reads=0 targets=2
- `data/compact_display_read_watch_b8_operation_positive_control.json`: current=False groups=['b8_compact_display_table_all'] cases=1 hits=66 direct_reads=66 targets=4
- `data/compact_display_read_watch_current_exact.json`: current=False groups=['a2_co_power_profile_display_overrides', 'b84_compact_power_display_overrides', 'b8_compact_display_table_all'] cases=4 hits=43 direct_reads=43 targets=12
- `data/compact_display_read_watch_probe.json`: current=False groups=['a2_co_power_profile_display_overrides', 'b84_compact_power_display_overrides'] cases=3 hits=0 direct_reads=0
- `data/compact_display_read_watch_probe_a2_b84_profile_refresh_states.json`: current=False groups=['a2_co_power_profile_display_overrides', 'b84_compact_power_display_overrides'] cases=5 hits=0 direct_reads=0
- `data/compact_display_read_watch_probe_a2_b84_profile_states.json`: current=False groups=['a2_co_power_profile_display_overrides', 'b84_compact_power_display_overrides'] cases=5 hits=0 direct_reads=0
- `data/compact_display_read_watch_probe_b8.json`: current=False groups=['b8_compact_display_table_all'] cases=2 hits=0 direct_reads=0
- `data/compact_display_read_watch_probe_b8_battle_range.json`: current=False groups=['b8_compact_display_table_all'] cases=1 hits=0 direct_reads=0
- `data/compact_display_read_watch_probe_b8_battle_subset.json`: current=False groups=['b8_compact_display_table_all'] cases=3 hits=0 direct_reads=0 targets=7
- `data/compact_display_read_watch_probe_b8_shop_states.json`: current=False groups=['b8_compact_display_table_all'] cases=5 hits=0 direct_reads=0
- `data/compact_display_read_watch_probe_b8_subset.json`: current=False groups=['b8_compact_display_table_all'] cases=3 hits=0 direct_reads=0 targets=7
- `data/compact_display_read_watch_rule_settings_map_names.json`: current=False groups=['b8_compact_display_table_all'] cases=1 hits=0 direct_reads=0 targets=4
- stale probe files ignored in current summary: `data/compact_display_read_watch_a2_profile_coid_current.json`, `data/compact_display_read_watch_a2_profile_domino_max_current.json`, `data/compact_display_read_watch_a2_profile_down3_current.json`, `data/compact_display_read_watch_a2_profile_down_current.json`, `data/compact_display_read_watch_a2_profile_right_current.json`, `data/compact_display_read_watch_a2_profile_selector_0200d63e_current.json`, `data/compact_display_read_watch_action_menu_a30_b8_exact.json`, `data/compact_display_read_watch_action_menu_a30_b8_range.json`, `data/compact_display_read_watch_action_menu_from_after_a36_b8_exact.json`, `data/compact_display_read_watch_b83268_comm.json`, `data/compact_display_read_watch_b84_power_title_20260628.json`, `data/compact_display_read_watch_b84_power_titles_coid_current.json`, `data/compact_display_read_watch_b8_fresh_menu_sweep_subset.json`, `data/compact_display_read_watch_b8_map_territory_current.json`, `data/compact_display_read_watch_b8_operation_positive_control.json`, `data/compact_display_read_watch_current_exact.json`, `data/compact_display_read_watch_probe.json`, `data/compact_display_read_watch_probe_a2_b84_profile_refresh_states.json`, `data/compact_display_read_watch_probe_a2_b84_profile_states.json`, `data/compact_display_read_watch_probe_b8.json`, `data/compact_display_read_watch_probe_b8_battle_range.json`, `data/compact_display_read_watch_probe_b8_battle_subset.json`, `data/compact_display_read_watch_probe_b8_shop_states.json`, `data/compact_display_read_watch_probe_b8_subset.json`, `data/compact_display_read_watch_rule_settings_map_names.json`

## Read-Watch Positive Controls

- controls_present=True probes=1 cases=0 hits=0 note=Positive controls are not E12 target evidence. They prove the same fresh-route ROM read-watch mechanism can hit a known visible text.
- `data/compact_display_read_watch_positive_control_a01970.json`: current=False targets=['0x00A01970'] cases=1 hits=8

## Remaining E12 Gap

- Target runtime/source proof count is currently 13; this includes provenance such as trace, read-watch, or mutation proof, and is still far from full target coverage.
- Static pointer xrefs are provenance only: they show table reachability candidates, not screen rendering.
- Current renderer-trace probes now include observed B8 operation-room reader breakpoints and therefore have breakpoint hits, but direct target register hits remain 0. The hits are a trace positive control for that Part1 path, not A2/B84/Part2-B8-HUD evidence.
- A fresh-route general-text positive control (`0x00A01970`) produced ROM read-watch hits, and the Part1 operation-room B8 live-source probe also produced target reads. The remaining 0-hit routes are therefore not a blanket harness failure.
- A2 now has 0 target runtime/source proof(s) from a selected-record CO-id RAM-field probe. This is synthetic source provenance, not natural all-CO route coverage or 36 per-power screen captures.
- B84 now has 0 target runtime/source proof(s) from the AW1 power-title CO-id selector route. This closes B84 target/source coverage, but the RAM-field route is still not a natural playthrough for every CO.
- B8 now has 13 target runtime/source proof(s), currently from Part1 operation-title mutation source proofs, but this does not prove full visual layout quality, and most B8 targets still lack target-level provenance.
- Current read-watch probes over the fresh main route, B8 battle/menu/shop/comm candidates, and external shop/profile state candidates still leave Part2-B8-HUD target reads unresolved; these are route/subset negatives, not global non-use proof.
- The remaining 0-hit pattern also leaves source-address/dead-copy hypotheses unresolved for the unproven B8 targets; additional B8 runtime renders must be tied back through target reads, mutation diffs, or WRAM/VRAM/DMA write chains.
- B8 entries are editor-visible through container scene `23d_part2_b8_compact_display_tables`, but need real screen entrypoints or corrected renderer PCs that exercise unit/weapon/shop/break labels.
- A2 CO power names now have 36/36 synthetic RAM-field source proof plus one current representative profile screen, but not natural-route 36 per-power screen captures.

