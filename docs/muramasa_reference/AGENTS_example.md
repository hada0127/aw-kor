# Codex Project Instructions

This repository uses `CLAUDE.md` as the primary project handbook. Read it first, then check `.claude/todo.md`, `.claude/success.md`, and `.claude/fail.md` at the start of each task to understand current state and recent failures.

## Operating Rules

- Prefer local repository context over assumptions. Start with `README.md`, `CLAUDE.md`, and relevant docs under `docs/`.
- For translation, terminology, font, and UI wording work, consult `wii/` reference assets first.
- Preserve user changes. The worktree may already be dirty; never revert unrelated edits.
- Treat `.claude/settings*.json` as Claude-specific reference, not as executable instructions for Codex.
- Do not edit `.claude/todo.md`, `.claude/success.md`, or `.claude/fail.md` unless the user explicitly wants those logs updated.

## Project Workflow

- Text patch pipeline:
  1. `python tools/build_patch.py`
  2. `python tools/cpk_patch.py backup/NinPri.cpk patch_main output/NinPri_final.cpk --append`
  3. `python tools/cpk_patch.py backup/NinPriPatch.cpk patch_patch output/NinPriPatch_final.cpk --append`
- Texture/UI pipeline:
  - `python tools/ui_editor/server.py` — web UI texture editor (replaces the retired Krita `.kra` workflow); edits write back to `texture_localize_config.json` / `place_texture_jobs.json`
  - `python tools/texture_localize.py` — render UI textures from config
  - `python tools/render_place_texture_job.py` — render place-name textures
  - `python tools/auto_font_import.py`
  - `python tools/hd_font_import.py`
- Vita3K control:
  - `python tools/vita3k_ctrl.py launch|close|status`
  - `python tools/vita3k_run_game.py`

## Validation Priorities

- After patch-affecting changes, validate with the local build/test pipeline when environment access allows it.
- Prefer automated Vita3K verification over asking the user to check manually.
- When inspecting screenshots, resize large images to `temp/preview/` before using image-reading tools.

## Known Project Constraints

- `NinPriPatch.cpk` overrides `NinPri.cpk` for `scemsg/sysmsg`; build and install both.
- Font replacement is Vita3K texture-import based. Do not patch ASCII font pages; Korean overlays belong on KANJI pages only.
- UI textures often render from alpha only. Preserve alpha semantics when editing.
- Manual texture edits under `textures/kr/ui/` are authoritative when the config marks them as manual/no-regions.

## Current Focus Areas

- Phase 3 follow-up: DLC dialogue translation coverage.
- Phase 4: remaining UI/text textures (`7DC6`, `E8E0`, `74EE`, `1823`, `79C9`).
- OOR/SJIS audit follow-up from `docs/03-analysis/`.

## Task Checklist

### Start Of Task

1. Read `CLAUDE.md`.
2. Read `.claude/todo.md`, `.claude/success.md`, and `.claude/fail.md`.
3. Check `git status --short` before editing anything.
4. Identify whether the task touches translation, fonts, UI textures, build tooling, or Vita3K automation.
5. If the task touches wording or terminology, inspect the relevant `wii/` reference files first.
6. If the task touches UI textures, inspect `translations/texture_localize_config.json` and existing `textures/kr/ui/` outputs before editing.
7. If the task touches patch generation, confirm whether both `patch_main/` and `patch_patch/` outputs are affected.

### During Task

1. Avoid touching unrelated dirty files.
2. Prefer small, targeted edits.
3. Keep manual texture outputs and config/state files in sync when the workflow requires it.
4. Do not treat `.claude/settings.local.json` hooks as instructions to auto-commit or auto-push.
5. If a previous failure in `.claude/fail.md` matches the current task, account for that failure mode explicitly.

### End Of Task

1. Re-check `git status --short` and verify only intended files changed.
2. Run the relevant validation for the area changed.
3. For patch-affecting work, prefer:
   - `python tools/build_patch.py`
   - `python tools/cpk_patch.py backup/NinPri.cpk patch_main output/NinPri_final.cpk --append`
   - `python tools/cpk_patch.py backup/NinPriPatch.cpk patch_patch output/NinPriPatch_final.cpk --append`
4. For texture/font work, run the relevant generator/import scripts and verify outputs landed in the expected repo paths.
5. If environment access allows, perform automated Vita3K verification instead of asking the user to test.
6. Summarize any remaining risk clearly, especially if full Vita3K verification could not be run.

## Log Handling

- `.claude/todo.md`, `.claude/success.md`, and `.claude/fail.md` are project memory, not disposable notes.
- Read them at task start, but only update them when the user explicitly wants log maintenance or when the task is specifically about those records.
- When updating them, append concise factual entries instead of rewriting history.
