#!/usr/bin/env python3
"""Run the release QA gate set with a small local/CI split."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from localization_evidence import snapshot_inputs, verify_build_receipt, write_json, sha

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "temp" / "release_qa_report.json"
PREPACKAGE_REPORT = ROOT / "temp" / "release_prepackage_qa.json"
SOURCE_ROM = ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba'
TARGET_ROM = ROOT / 'output/game_wars_korean_full.gba'


def cmd(*parts: str) -> list[str]:
    return [sys.executable, *parts]


def visual_region_cmd() -> list[str]:
    harness = ROOT / "temp" / "mgbah"
    if harness.exists():
        return cmd("tools/qa_visual_regions.py", "--harness", str(harness), "--action-menu-save", "")
    return cmd("tools/qa_visual_regions.py")


BASE_GATES: list[tuple[str, list[str]]] = [
    ("csv-integrity", cmd("tools/qa_csv_integrity.py", "--fail-on-rom-japanese")),
    ("translation-lint", cmd("tools/lint_translation.py", "--severity", "error")),
    ("text-fit", cmd("tools/qa_text_fit.py")),
    ("placeholder-residuals", cmd("tools/qa_placeholder_residuals.py")),
    ("japanese-residuals", cmd("tools/qa_japanese_residuals.py", "--min-score", "13")),
    ("address-overrides", cmd("tools/audit_address_text_overrides.py", "--strict")),
    ("csv-override-shadow", cmd("tools/audit_csv_override_shadow.py", "--strict")),
    ("repoint-punctuation", cmd("tools/audit_repoint_punctuation.py", "--strict")),
    ("repoint-integrity", cmd("tools/qa_repoint_integrity.py")),
    ("glyph-dictionary", cmd("tools/qa_glyph_dictionary_tables.py")),
    ("part1-compact-help", cmd("tools/qa_part1_compact_help.py")),
    ("part1-operation-dialogue", cmd("tools/qa_part1_operation_dialogue.py")),
    ("part1-dialogue-punctuation", cmd("tools/qa_part1_dialogue_punctuation.py")),
    ("transient-overlays", cmd("tools/qa_transient_overlays.py")),
    ("scene-catalog", cmd("tools/audit_scene_catalog.py", "--strict")),
    ("scene-screenshot-sanity", cmd("tools/qa_scene_screenshot_sanity.py")),
    ("scene-semantics", cmd("tools/audit_scene_semantics.py", "--strict")),
    ("scene-residuals", cmd("tools/audit_scene_residual_scans.py", "--strict")),
    ("visual-regions", visual_region_cmd()),
    ("phase6-basic", cmd("tools/phase6_basic_test.py", "output/game_wars_korean_full.gba")),
    ("dist-integrity", cmd("tools/verify_dist_integrity.py")),
]
REQUIRED_PREPACKAGE_GATES = ['py-compile'] + [name for name, _ in BASE_GATES if name != 'dist-integrity']

PY_COMPILE_FILES = [
    "tools/build_korean_full.py",
    "tools/dialogue_repoint.py",
    "tools/verify_dist_integrity.py",
    "tools/audit_csv_override_shadow.py",
    "tools/audit_repoint_punctuation.py",
    "tools/qa_part1_compact_help.py",
    "tools/qa_part1_operation_dialogue.py",
    "tools/qa_part1_dialogue_punctuation.py",
    "tools/qa_transient_overlays.py",
    "tools/qa_scene_screenshot_sanity.py",
    "tools/run_release_qa.py",
]

def editor_gates(server: str, password: str | None = None) -> list[tuple[str, list[str]]]:
    password_args = ["--password", password] if password else []
    return [
        ("editor-apply-state", cmd("tools/verify_scene_editor_apply_state.py", "--server", server, *password_args)),
        (
            "editor-roundtrip-dry",
            cmd(
                "tools/verify_scene_editor_roundtrip.py",
                "--server", server,
                "--no-actual-sample",
                "--no-build-sample",
                *password_args,
            ),
        ),
    ]

CDP_GATES: list[tuple[str, list[str]]] = [
    ("editor-cdp", cmd("tools/verify_scene_editor_cdp.py")),
]


def run_one(label: str, argv: list[str], *, timeout: int | None) -> dict:
    start = time.monotonic()
    display_argv = [('[redacted]' if i and argv[i - 1] == '--password' else part)
                    for i, part in enumerate(argv)]
    print(f"[run] {label}: {' '.join(display_argv)}", flush=True)
    try:
        res = subprocess.run(
            argv,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        rc = res.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        rc = 124
        timed_out = True
        res = exc
    elapsed = time.monotonic() - start
    stdout = getattr(res, "stdout", "") or ""
    stderr = getattr(res, "stderr", "") or ""
    if isinstance(stdout, bytes):
        stdout = stdout.decode('utf-8', errors='replace')
    if isinstance(stderr, bytes):
        stderr = stderr.decode('utf-8', errors='replace')
    status = "OK" if rc == 0 else "FAIL"
    print(f"[{status}] {label} rc={rc} {elapsed:.1f}s", flush=True)
    if rc != 0:
        if stdout:
            print(stdout[-4000:])
        if stderr:
            print(stderr[-4000:], file=sys.stderr)
    return {
        "label": label,
        "argv": display_argv,
        "returncode": rc,
        "timed_out": timed_out,
        "elapsed_sec": round(elapsed, 3),
        "stdout_tail": stdout[-4000:],
        "stderr_tail": stderr[-4000:],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", action="store_true", help="run build_korean_full.py before QA")
    parser.add_argument("--dist-date", help="package DATE only after prepackage QA passes")
    parser.add_argument("--editor", action="store_true", help="include editor API gates")
    parser.add_argument("--editor-server", default="http://127.0.0.1:8782",
                        help="scene editor base URL for --editor gates")
    parser.add_argument("--editor-password", default=None,
                        help="scene editor password for authenticated --editor gates")
    parser.add_argument("--cdp", action="store_true", help="include Chrome CDP browser gate")
    parser.add_argument("--only-editor", action="store_true", help="run only editor/CDP gates")
    parser.add_argument("--timeout", type=int, default=300, help="per-command timeout seconds")
    parser.add_argument("--build-timeout", type=int, default=3600, help="build timeout seconds")
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    args = parser.parse_args()
    report_path = Path(args.report)
    if not report_path.is_absolute():
        report_path = ROOT / report_path
    if args.only_editor and (args.build or args.dist_date):
        parser.error('--only-editor cannot build or package a release')
    if args.only_editor and not (args.editor or args.cdp):
        parser.error('--only-editor requires --editor or --cdp')

    gates: list[tuple[str, list[str]]] = []
    results = []
    before = None
    if not args.only_editor:
        if args.build:
            results.append(run_one('build', cmd('tools/build_korean_full.py'), timeout=args.build_timeout))
        try:
            if any(row['returncode'] != 0 for row in results):
                raise ValueError('Build failed; downstream QA and packaging were not run')
            before = snapshot_inputs()
            verify_build_receipt(TARGET_ROM, SOURCE_ROM, before)
            rom_before, source_before = sha(TARGET_ROM), sha(SOURCE_ROM)
        except (OSError, ValueError) as error:
            write_json(report_path, {'failed_count': 1, 'stage': 'build_provenance',
                                          'error': str(error), 'results': results})
            print(f'FAIL: {error}', file=sys.stderr)
            return 1
        gates.append(("py-compile", [sys.executable, "-m", "py_compile", *PY_COMPILE_FILES]))
        gates.extend((name, argv) for name, argv in BASE_GATES if name != 'dist-integrity')
    if args.editor:
        gates.extend(editor_gates(args.editor_server, args.editor_password))
    if args.cdp:
        gates.extend(CDP_GATES)

    results.extend(run_one(label, argv, timeout=args.timeout) for label, argv in gates)
    if not args.only_editor:
        after = snapshot_inputs()
        if after != before:
            results.append({'label': 'input-stability', 'returncode': 1, 'timed_out': False,
                            'stderr_tail': 'Inputs changed during QA'})
        if (sha(TARGET_ROM), sha(SOURCE_ROM)) != (rom_before, source_before):
            results.append({'label': 'artifact-stability', 'returncode': 1, 'timed_out': False,
                            'stderr_tail': 'ROM/source changed during QA'})
        try:
            verify_build_receipt(TARGET_ROM, SOURCE_ROM, after)
        except (OSError, ValueError) as error:
            results.append({'label': 'build-evidence-stability', 'returncode': 1,
                            'timed_out': False, 'stderr_tail': str(error)})
        prepackage = {'schema': 1, 'stage': 'prepackage_qa',
                      'rom_sha256': sha(TARGET_ROM), 'source_sha256': sha(SOURCE_ROM),
                      'inputs_before': before, 'inputs_after': after,
                      'failed_count': sum(row['returncode'] != 0 for row in results),
                      'results': results.copy(),
                      'runtime_scope': 'only listed checks; full campaign and character voice are not implied'}
        write_json(PREPACKAGE_REPORT, prepackage)
        if prepackage['failed_count'] == 0:
            if args.dist_date:
                results.append(run_one('prepare-dist', cmd('tools/prepare_patch_distribution.py',
                                       '--date', args.dist_date), timeout=args.timeout))
            if not any(row['returncode'] != 0 for row in results):
                results.append(run_one('dist-integrity', cmd('tools/verify_dist_integrity.py'), timeout=args.timeout))
    failed = [item for item in results if item["returncode"] != 0]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "build": args.build,
        "dist_date": args.dist_date,
        "editor": args.editor,
        "editor_server": args.editor_server,
        "editor_password_supplied": bool(args.editor_password),
        "cdp": args.cdp,
        "only_editor": args.only_editor,
        "failed_count": len(failed),
        "results": results,
    }
    write_json(report_path, report)
    print(f"release QA report: {report_path}")
    print("release QA result: " + ("PASS" if not failed else "FAIL"))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
