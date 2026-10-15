# Replayable scene routes

Each verified route belongs in `tools/scene_routes/<scene_id>/`. W2b6-C verified `28_part2_result_status` from a cold-boot cartridge save on b32r5; ten of its 11 requested scenes still lack routes. Do not treat an attempted input sequence or a same-ROM savestate as a route to the required text.

A route needs small tracked text files recording:

1. Candidate ROM path and full SHA-256.
2. Cold-boot cartridge save path, exact SHA-256, size, source ROM SHA-256, and save receipt/classification. Recheck the save SHA before every replay. Do not transfer savestates between ROMs.
3. Recorder input file in execution order, including every `cheat`/`freeze`/`unfreeze` write. The recorder's `actions.jsonl` and `frames.jsonl` must show those writes and `cheat_tainted: true` at and after intervention.
4. Target core frame, checkpoint, selected PNG SHA-256, exact Korean read directly from that PNG, and the corresponding script text. Mark a mismatch as a possible defect.
5. Recorder exit status and command that reproduces the capture on the named candidate. For a later candidate, rerun from the same verified SRAM bytes and input sequence, then inspect its new PNG; do not relabel the old screenshot.

The W2b6-C diagnostic attempts and blockers are in `temp/release_C/w2b6c_report.md`. They are not scene evidence.
