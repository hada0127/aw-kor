#!/usr/bin/env python3
"""Verify scene-editor dialogue saveability without bulk-mutating project data.

This covers the C6 gap that browser opening alone does not prove: every editable
dialogue member exposed by the scene editor must pass the same server-side save
gate that a real save uses.  The verifier performs:

1. GET every scene and scene item from the live :8782 server.
2. POST /api/dialogue/line with dry_run=true for every editable member.
3. For every editable B-team member where a safe alternate text can be found,
   verify that an unconfirmed dry-run asks for confirmation and a confirmed
   dry-run succeeds.
4. Optionally perform a tiny real write/restore sample, with JSON backups
   restored in a finally block.

The full all-line check is dry-run by design: mass-writing thousands of current
values would add override entries and make the test itself a source of churn.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import http.client
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROM = ROOT / "output" / "game_wars_korean_full.gba"
OVERRIDES = ROOT / "data" / "dialogue_overrides.json"
DIALOGUE_MAP = ROOT / "data" / "dialogue_map.json"
DEFAULT_OUT = ROOT / "data" / "scene_editor_roundtrip_verify.json"
BUILD_SAMPLE_ROM = ROOT / "temp" / "scene_editor_roundtrip_direct_script.gba"
BUILD_SAMPLE_REPORT = ROOT / "temp" / "scene_editor_roundtrip_encode_report.csv"
INTEGRITY_MAP = ROOT / "temp" / "integrity_map.json"
SPRITE_BUILD_LAYOUTS = ROOT / "data" / "sprite_build_layouts.json"
OBJLABEL_SPRITES = ROOT / "data" / "objlabel_sprites.json"
CLASSIFIED_BLANK_STATUSES = {"symbol_table", "script_blank", "excluded", "intentional_blank"}
EDITOR_PASSWORD_FILE = ROOT / "temp" / "editor_password.txt"

sys.path.insert(0, str(ROOT / "tools"))
import build_korean_full as B  # noqa: E402
import text_metrics as TM  # noqa: E402


_HTTP_CLIENTS: dict[str, tuple[urllib.parse.ParseResult, http.client.HTTPConnection]] = {}
_AUTH_COOKIE = ""


def default_editor_password() -> str:
    value = os.environ.get("SCENE_EDITOR_PASSWORD") or os.environ.get("AW_EDITOR_PASSWORD")
    if value:
        return value
    if EDITOR_PASSWORD_FILE.exists():
        return EDITOR_PASSWORD_FILE.read_text(encoding="utf-8").strip()
    return ""


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _http_connection(base_url: str) -> tuple[urllib.parse.ParseResult, http.client.HTTPConnection]:
    key = base_url.rstrip("/")
    rec = _HTTP_CLIENTS.get(key)
    if rec is not None:
        return rec
    parsed = urllib.parse.urlparse(key)
    if parsed.scheme != "http" or not parsed.hostname:
        raise ValueError("only http://host[:port] scene editor URLs are supported")
    conn = http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=30)
    rec = (parsed, conn)
    _HTTP_CLIENTS[key] = rec
    return rec


def _close_http_connection(base_url: str) -> None:
    rec = _HTTP_CLIENTS.pop(base_url.rstrip("/"), None)
    if rec is not None:
        rec[1].close()


def http_json(base_url: str, path: str, payload: dict | None = None) -> dict:
    body = None
    headers = {"Accept": "application/json", "Connection": "keep-alive"}
    if _AUTH_COOKIE:
        headers["Cookie"] = _AUTH_COOKIE
    method = "GET"
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
        method = "POST"
    last_exc = None
    for attempt in range(2):
        _parsed, conn = _http_connection(base_url)
        try:
            conn.request(method, path, body=body, headers=headers)
            res = conn.getresponse()
            data = res.read()
            if res.status < 200 or res.status >= 300:
                raise RuntimeError(f"HTTP {res.status} {res.reason}: {data[:300]!r}")
            return json.loads(data.decode("utf-8"))
        except Exception as exc:
            last_exc = exc
            _close_http_connection(base_url)
            if attempt == 0:
                time.sleep(0.05)
                continue
            raise
    raise AssertionError(f"unreachable http_json failure: {last_exc!r}")


def login(base_url: str, password: str) -> None:
    global _AUTH_COOKIE
    payload = {"password": password}
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    _parsed, conn = _http_connection(base_url)
    conn.request(
        "POST",
        "/api/login",
        body=body,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "Connection": "keep-alive",
        },
    )
    res = conn.getresponse()
    data = res.read()
    if res.status < 200 or res.status >= 300:
        raise RuntimeError(f"login failed HTTP {res.status} {res.reason}: {data[:300]!r}")
    cookie = res.getheader("Set-Cookie") or ""
    if cookie:
        _AUTH_COOKIE = cookie.split(";", 1)[0]
    reply = json.loads(data.decode("utf-8"))
    if not reply.get("ok"):
        raise RuntimeError(f"login response was not ok: {reply}")


def scene_items(base_url: str, scene_id: str) -> dict:
    q = urllib.parse.urlencode({"id": scene_id, "type": "all"})
    return http_json(base_url, f"/api/scene/items?{q}")


def alternate_candidates(text: str, slot: int | None) -> list[str]:
    """Small in-slot alternatives for B-team confirm dry-runs."""
    candidates: list[str] = []
    text = text or ""
    replacements = ["가", "나", "다", "라", "점", "수"]
    for i, ch in enumerate(text):
        if "가" <= ch <= "힣":
            for repl in replacements:
                if repl != ch:
                    candidates.append(text[:i] + repl + text[i + 1 :])
            break
    if text:
        last = "!" if not text.endswith("!") else "?"
        candidates.append(text[:-1] + last)
    max_syl = 3
    if isinstance(slot, int) and slot > 0:
        max_syl = max(1, min(3, slot // 2))
    for n in range(max_syl, 0, -1):
        candidates.append("가" * n)

    out = []
    seen = set()
    for cand in candidates:
        if not cand or cand == text or cand in seen:
            continue
        seen.add(cand)
        if not isinstance(slot, int) or slot <= 0 or TM.encoded_len(cand) <= slot:
            out.append(cand)
    return out


def direct_script_candidate(slot: int | None, build_slot: int | None) -> str | None:
    if not isinstance(slot, int) or not isinstance(build_slot, int):
        return None
    if slot <= build_slot or build_slot <= 0:
        return None
    syllables = min(slot // 2, build_slot // 2 + 2)
    if syllables <= build_slot // 2:
        return None
    return "가" * syllables


def dry_run_line(base_url: str, address: str, ko: str, confirm_bteam: bool = False) -> dict:
    payload = {"address": address, "ko": ko, "dry_run": True}
    if confirm_bteam:
        payload["confirm_bteam"] = True
    return http_json(base_url, "/api/dialogue/line", payload)


def real_save_line(base_url: str, address: str, ko: str, confirm_bteam: bool = False) -> dict:
    payload = {"address": address, "ko": ko}
    if confirm_bteam:
        payload["confirm_bteam"] = True
    return http_json(base_url, "/api/dialogue/line", payload)


def restore_backups(backups: dict[Path, dict]) -> None:
    for src, meta in backups.items():
        if meta["existed"]:
            shutil.copy2(meta["backup"], src)
        elif src.exists():
            src.unlink()


def backups_restored(backups: dict[Path, dict]) -> bool:
    for src, meta in backups.items():
        if meta["existed"]:
            if not src.exists() or sha256(src) != meta["sha256"]:
                return False
        elif src.exists():
            return False
    return True


def choose_actual_samples(records: list[dict]) -> tuple[dict | None, dict | None, dict | None]:
    normal = next((r for r in records if not r["bteam"] and r.get("alternate")), None)
    bteam = next((r for r in records if r["bteam"] and r.get("alternate_confirm_ok")), None)
    scripts = [
        r for r in records
        if str(r.get("kind") or "").startswith("script:") and not r["bteam"] and r.get("alternate")
    ]
    script = next((r for r in scripts if r.get("direct_span_expanded")), None)
    if script is None:
        script = next(iter(scripts), None)
    return normal, bteam, script


def expected_direct_script_bytes(text: str, slot: int, addr: int) -> bytes:
    raw_map = json.loads((ROOT / "data" / "syllable_to_code_2350.json").read_text(encoding="utf-8"))
    syl_to_code = {
        ch: int(code, 16) if isinstance(code, str) else int(code)
        for ch, code in raw_map.items()
    }
    enc, _level = B.encode_fit(text, slot, syl_to_code, collections.Counter(), addr)
    if enc is None:
        raw_len = len(B.encode_text(text, syl_to_code, collections.Counter()))
        raise AssertionError(f"direct script expected bytes overflow: {raw_len} > {slot}")
    return bytes(enc) + bytes([B.FILL_BYTE]) * (slot - len(enc))


def build_direct_script_sample(sample: dict) -> dict:
    cmd = [
        sys.executable,
        "tools/build_korean_full.py",
        "--out",
        str(BUILD_SAMPLE_ROM.relative_to(ROOT)),
        "--report",
        str(BUILD_SAMPLE_REPORT.relative_to(ROOT)),
        "--no-sync-outputs",
    ]
    integrity_existed = INTEGRITY_MAP.exists()
    integrity_bytes = INTEGRITY_MAP.read_bytes() if integrity_existed else None
    try:
        try:
            run = subprocess.run(
                cmd,
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=360,
            )
        except subprocess.TimeoutExpired as exc:
            return {
                "ok": False,
                "error": "build timed out",
                "timeout_sec": exc.timeout,
                "output_tail": ((exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else ""),
            }
    finally:
        if integrity_existed:
            INTEGRITY_MAP.write_bytes(integrity_bytes or b"")
        elif INTEGRITY_MAP.exists():
            INTEGRITY_MAP.unlink()
    if run.returncode != 0:
        return {
            "ok": False,
            "error": "build failed",
            "returncode": run.returncode,
            "output_tail": run.stdout[-4000:],
        }
    addr = int(sample["address"], 16)
    slot = int(sample["slot"])
    expected = expected_direct_script_bytes(sample["alternate"], slot, addr)
    actual = BUILD_SAMPLE_ROM.read_bytes()[addr:addr + slot]
    return {
        "ok": actual == expected,
        "rom": str(BUILD_SAMPLE_ROM.relative_to(ROOT)),
        "address": sample["address"],
        "slot": slot,
        "expected_hex": expected.hex(),
        "actual_hex": actual.hex(),
        "build_output_tail": run.stdout[-1200:],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="http://127.0.0.1:8782")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT,
                    help="report path; relative paths are resolved from the project root")
    ap.add_argument("--no-actual-sample", action="store_true")
    ap.add_argument("--no-build-sample", action="store_true")
    ap.add_argument("--password", default=default_editor_password(),
                    help="scene editor password; defaults to SCENE_EDITOR_PASSWORD/AW_EDITOR_PASSWORD/temp/editor_password.txt")
    args = ap.parse_args()

    started = time.time()
    preflight_failures: list[dict] = []
    if args.password:
        login(args.server, args.password)
    auth_status = http_json(args.server, "/api/auth/status")
    if args.password and not auth_status.get("auth_required"):
        preflight_failures.append({
            "error": "password was provided but the scene editor reports auth_required=false",
            "auth_status": auth_status,
        })
    if args.password and not auth_status.get("authenticated"):
        preflight_failures.append({
            "error": "password login did not leave the scene editor authenticated",
            "auth_status": auth_status,
        })
    scenes_payload = http_json(args.server, "/api/scenes")
    scenes = scenes_payload.get("scenes") or []
    records: list[dict] = []
    failures: list[dict] = list(preflight_failures)
    bteam_confirm_failures: list[dict] = []
    bteam_skips: list[dict] = []
    unlabelled_blank_members: list[dict] = []
    unprotected_all_blank_groups: list[dict] = []

    scene_count = 0
    dialogue_group_count = 0
    sprite_count = 0
    editable_count = 0
    bteam_count = 0
    build_slots = B.load_slots()

    for scene in scenes:
        sid = scene.get("id")
        if not sid:
            continue
        items = scene_items(args.server, sid)
        scene_count += 1
        dialogue = items.get("dialogue") or []
        sprites = items.get("sprites") or []
        dialogue_group_count += len(dialogue)
        sprite_count += len(sprites)
        for gi, group in enumerate(dialogue):
            group_members = group.get("members") or []
            if (
                (scene.get("scene_role") or "screen") == "screen"
                and group_members
                and all(not (m.get("ko") or "").strip() for m in group_members)
            ):
                statuses = [(m.get("blank_status") or {}).get("kind") for m in group_members]
                has_protected = any((m.get("budget") or {}).get("protected_address_text") for m in group_members)
                all_classified_blank = all(status in CLASSIFIED_BLANK_STATUSES for status in statuses)
                if not has_protected and not all_classified_blank:
                    unprotected_all_blank_groups.append({
                        "scene_id": sid,
                        "group_index": gi,
                        "group_id": group.get("group_id"),
                        "assembled_ja": group.get("assembled_ja"),
                        "statuses": statuses,
                        "addresses": [m.get("address") for m in group_members],
                        "kinds": [m.get("kind") for m in group_members],
                    })
            for mi, member in enumerate(group.get("members") or []):
                budget = member.get("budget") or {}
                if (
                    (scene.get("scene_role") or "screen") == "screen"
                    and not (member.get("ko") or "").strip()
                    and not member.get("blank_status")
                ):
                    unlabelled_blank_members.append({
                        "scene_id": sid,
                        "group_index": gi,
                        "member_index": mi,
                        "address": member.get("address"),
                        "ja": member.get("ja"),
                        "kind": member.get("kind"),
                        "editable": bool(budget.get("editable")),
                        "reason": budget.get("reason"),
                    })
                if not budget.get("editable"):
                    continue
                editable_count += 1
                address = member.get("address")
                ko = member.get("ko") or ""
                bteam = bool(budget.get("bteam"))
                if bteam:
                    bteam_count += 1
                row = {
                    "scene_id": sid,
                    "group_index": gi,
                    "member_index": mi,
                    "address": address,
                    "kind": member.get("kind"),
                    "bteam": bteam,
                    "slot": budget.get("slot"),
                    "build_slot": build_slots.get(int(address, 16)) if address else None,
                }
                current = dry_run_line(args.server, address, ko)
                if not current.get("ok"):
                    if current.get("bteam_confirm_required"):
                        current = dry_run_line(args.server, address, ko, confirm_bteam=True)
                    if not current.get("ok"):
                        failures.append({**row, "error": current})
                row["current_dry_run_ok"] = bool(current.get("ok"))

                alt_ok = None
                for alt in alternate_candidates(ko, budget.get("slot")):
                    confirmed = dry_run_line(args.server, address, alt, confirm_bteam=True)
                    if confirmed.get("ok"):
                        alt_ok = alt
                        break
                row["alternate"] = alt_ok
                if str(row.get("kind") or "").startswith("script:"):
                    direct_alt = direct_script_candidate(row.get("slot"), row.get("build_slot"))
                    if direct_alt:
                        direct_ok = dry_run_line(args.server, address, direct_alt, confirm_bteam=True)
                        if direct_ok.get("ok"):
                            row["alternate"] = direct_alt
                            row["direct_span_expanded"] = True

                if bteam:
                    if not alt_ok:
                        bteam_skips.append({**row, "reason": "no fitting alternate accepted by dry_run"})
                    else:
                        unconfirmed = dry_run_line(args.server, address, alt_ok)
                        confirmed = dry_run_line(args.server, address, alt_ok, confirm_bteam=True)
                        confirm_ok = (
                            bool(unconfirmed.get("bteam_confirm_required"))
                            and bool(confirmed.get("ok"))
                        )
                        row["alternate_confirm_ok"] = confirm_ok
                        if not confirm_ok:
                            bteam_confirm_failures.append({
                                **row,
                                "unconfirmed": unconfirmed,
                                "confirmed": confirmed,
                            })
                records.append(row)

    actual_samples = []
    build_sample = None
    current_dry_run_failure_count = len(failures)
    restored_after_samples = True
    if not args.no_actual_sample:
        normal, bteam, script = choose_actual_samples(records)
        (ROOT / "temp").mkdir(parents=True, exist_ok=True)
        backup_targets = [OVERRIDES, DIALOGUE_MAP]
        for optional in [SPRITE_BUILD_LAYOUTS, OBJLABEL_SPRITES]:
            if optional.exists():
                backup_targets.append(optional)
        backups = {}
        for src in backup_targets:
            existed = src.exists()
            dst = ROOT / "temp" / f"{src.name}.roundtrip_verify"
            backups[src] = {
                "backup": dst,
                "existed": existed,
                "sha256": sha256(src) if existed else None,
            }
            if existed:
                shutil.copy2(src, dst)
        try:
            for sample in [normal, bteam]:
                if not sample:
                    continue
                addr = sample["address"]
                alt = sample["alternate"]
                # Fetch the original value from the already collected live record.
                scene = scene_items(args.server, sample["scene_id"])
                member = (
                    scene["dialogue"][sample["group_index"]]["members"][sample["member_index"]]
                )
                original = member.get("ko") or ""
                save_alt = real_save_line(args.server, addr, alt, confirm_bteam=sample["bteam"])
                save_orig = real_save_line(args.server, addr, original, confirm_bteam=sample["bteam"])
                actual_samples.append({
                    "address": addr,
                    "scene_id": sample["scene_id"],
                    "bteam": sample["bteam"],
                    "save_alt_ok": bool(save_alt.get("ok")),
                    "restore_ok": bool(save_orig.get("ok")),
                    "alt": alt,
                    "original": original,
                })
                if not (save_alt.get("ok") and save_orig.get("ok")):
                    failures.append({
                        **sample,
                        "error": {"save_alt": save_alt, "restore": save_orig},
                    })
            if script and not args.no_build_sample:
                if not script.get("direct_span_expanded"):
                    build_sample = {"ok": False, "error": "selected direct script sample is not an expanded span"}
                else:
                    scene = scene_items(args.server, script["scene_id"])
                    member = (
                        scene["dialogue"][script["group_index"]]["members"][script["member_index"]]
                    )
                    original = member.get("ko") or ""
                    save_alt = real_save_line(args.server, script["address"], script["alternate"])
                    if save_alt.get("ok"):
                        build_sample = build_direct_script_sample(script)
                    else:
                        build_sample = {"ok": False, "error": "direct script sample save failed", "save": save_alt}
                    save_orig = real_save_line(args.server, script["address"], original)
                    build_sample = {
                        "address": script["address"],
                        "scene_id": script["scene_id"],
                        "kind": script.get("kind"),
                        "build_slot": script.get("build_slot"),
                        "direct_span_expanded": bool(script.get("direct_span_expanded")),
                        "alt": script["alternate"],
                        "original": original,
                        "save_alt_ok": bool(save_alt.get("ok")),
                        "restore_ok": bool(save_orig.get("ok")),
                        "build_verify": build_sample,
                    }
                if not build_sample.get("build_verify", build_sample).get("ok"):
                    failures.append({**script, "error": {"direct_script_build_sample": build_sample}})
            elif not args.no_build_sample:
                build_sample = {"ok": False, "error": "no expanded direct script sample found"}
                failures.append({"error": {"direct_script_build_sample": build_sample}})
        finally:
            restore_backups(backups)
            restored_after_samples = backups_restored(backups)

    if not restored_after_samples:
        failures.append({"error": "sample backup restore did not return files to pre-run hashes"})
    if unlabelled_blank_members:
        failures.append({
            "error": "screen scene has untranslated blank KO without blank_status; translate it or classify it explicitly",
            "count": len(unlabelled_blank_members),
            "sample": unlabelled_blank_members[:20],
        })
    if unprotected_all_blank_groups:
        failures.append({
            "error": "screen scene has an all-blank dialogue group without protected/symbol-table evidence",
            "count": len(unprotected_all_blank_groups),
            "sample": unprotected_all_blank_groups[:20],
        })

    summary = {
        "generated_on": date.today().isoformat(),
        "server": args.server,
        "auth_status": auth_status,
        "rom_sha256": sha256(OUTPUT_ROM) if OUTPUT_ROM.exists() else None,
        "scene_count": scene_count,
        "dialogue_group_count": dialogue_group_count,
        "sprite_count": sprite_count,
        "editable_member_count": editable_count,
        "bteam_editable_member_count": bteam_count,
        "current_dry_run_failures": current_dry_run_failure_count,
        "bteam_confirm_failures": len(bteam_confirm_failures),
        "bteam_confirm_skips": len(bteam_skips),
        "unlabelled_blank_members": len(unlabelled_blank_members),
        "unprotected_all_blank_groups": len(unprotected_all_blank_groups),
        "actual_sample_count": len(actual_samples),
        "actual_samples": actual_samples,
        "direct_script_build_sample": build_sample,
        "dialogue_files_clean_after": restored_after_samples,
        "elapsed_sec": round(time.time() - started, 2),
    }
    report = {
        "summary": summary,
        "failures": failures[:50],
        "bteam_confirm_failures": bteam_confirm_failures[:50],
        "bteam_confirm_skips": bteam_skips[:50],
        "unlabelled_blank_members": unlabelled_blank_members[:50],
        "unprotected_all_blank_groups": unprotected_all_blank_groups[:50],
    }
    out_path = args.out if args.out.is_absolute() else ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        display_out = out_path.relative_to(ROOT)
    except ValueError:
        display_out = out_path

    print(json.dumps(summary, ensure_ascii=False))
    print(f"wrote {display_out}")
    return 1 if failures or bteam_confirm_failures else 0


if __name__ == "__main__":
    sys.exit(main())
