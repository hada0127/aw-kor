#!/usr/bin/env python3
"""Prove compact-display target liveness by one-address mutation screenshots.

For each target, this tool:
* copies the current output ROM to temp,
* overwrites only the requested target slot with a short Korean mutation,
* captures the same screen checkpoint for base and mutation,
* writes a pixel diff, contact sheet, and JSON evidence.

The evidence proves source provenance for that single target/address on that
route. It does not prove full visual-layout quality for the whole table.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_comparison_sheet import capture  # noqa: E402

ROM = ROOT / "output" / "game_wars_korean_full.gba"
CHECKPOINTS = ROOT / "data" / "screen_checkpoints.json"
DIALOGUE_MAP = ROOT / "data" / "dialogue_map.json"
OUT_DIR = ROOT / "temp" / "compact_display_mutation_proofs"
DOC_CONTACT_DIR = ROOT / "docs" / "screenshots" / "e12_compact_display_matrix_2026-06-27"
HARNESS = Path("/tmp/mgbah")

GBA_W = 240
GBA_H = 160


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def parse_addr(value: str) -> int:
    return int(value, 0)


def safe_tag(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣_.-]+", "_", value).strip("_")


def load_build_module():
    spec = importlib.util.spec_from_file_location("build_korean_full", ROOT / "tools" / "build_korean_full.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def encode_mutation(text: str) -> bytes:
    build = load_build_module()
    syl_to_code = {k: int(v, 16) for k, v in load_json(Path(build.SYLCODE)).items()}
    unmapped = Counter()
    encoded = build.encode_text(text, syl_to_code, unmapped)
    if unmapped:
        raise SystemExit(f"unmapped mutation chars for {text!r}: {dict(unmapped)}")
    return encoded


def dialogue_rows_by_addr() -> dict[int, dict]:
    doc = load_json(DIALOGUE_MAP)
    rows = {}
    for row in doc.get("lines", []):
        try:
            rows[int(row.get("address", ""), 16)] = row
        except (TypeError, ValueError):
            continue
    return rows


def checkpoint_by_name(name: str) -> dict:
    doc = load_json(CHECKPOINTS)
    for row in doc.get("checkpoints", []):
        if row.get("name") == name:
            return row
    raise SystemExit(f"screen checkpoint not found: {name}")


def validate_plain_text_slot(old: bytes, addr: int) -> None:
    """Reject command/control-looking slots; this proof tool is text-only."""
    seen_zero_padding = False
    i = 0
    while i < len(old):
        b = old[i]
        if b == 0x00:
            seen_zero_padding = True
            i += 1
            continue
        if b == 0x20:
            i += 1
            continue
        if seen_zero_padding:
            raise SystemExit(f"non-padding byte after 0x00 padding in slot 0x{addr:08X}")
        if b < 0x20:
            raise SystemExit(f"control byte 0x{b:02X} in slot 0x{addr:08X}; refusing mutation proof")
        if 0x81 <= b <= 0xE2:
            if i + 1 >= len(old):
                raise SystemExit(f"dangling SJIS/Hangul lead byte in slot 0x{addr:08X}")
            if old[i + 1] == 0x00:
                raise SystemExit(f"SJIS/Hangul lead followed by 0x00 in slot 0x{addr:08X}")
            i += 2
            continue
        if 0x21 <= b <= 0x7E:
            i += 1
            continue
        raise SystemExit(f"unsupported byte 0x{b:02X} in slot 0x{addr:08X}; refusing mutation proof")


def infer_fill_byte(old_tail: bytes, addr: int, mutation_len: int, slot: int) -> int:
    if not old_tail and mutation_len < slot:
        raise SystemExit(f"slot 0x{addr:08X} has no padding tail; refusing shorter mutation")
    tail_values = set(old_tail)
    if not tail_values:
        return 0x20
    if tail_values == {0x00}:
        return 0x00
    if tail_values == {0x20}:
        return 0x20
    raise SystemExit(f"slot 0x{addr:08X} has mixed/non-padding tail: {old_tail.hex()}")


def write_mutation_rom(base_rom: Path, out_rom: Path, addr: int, slot: int,
                       encoded: bytes, expected_old_prefix: bytes) -> dict:
    if len(encoded) > slot:
        raise SystemExit(f"encoded mutation does not fit 0x{addr:08X}: {len(encoded)} > slot {slot}")
    data = bytearray(base_rom.read_bytes())
    old = bytes(data[addr:addr + slot])
    validate_plain_text_slot(old, addr)
    if not old.startswith(expected_old_prefix):
        raise SystemExit(
            f"current ROM slot 0x{addr:08X} does not start with expected base text: "
            f"expected={expected_old_prefix.hex()} old={old.hex()}"
        )
    old_tail = old[len(expected_old_prefix):]
    fill_byte = infer_fill_byte(old_tail, addr, len(encoded), slot)
    data[addr:addr + slot] = encoded + (bytes([fill_byte]) * (slot - len(encoded)))
    out_rom.write_bytes(data)
    return {
        "old_hex": old.hex(),
        "new_hex": bytes(data[addr:addr + slot]).hex(),
        "fill_byte": fill_byte,
        "base_encoded_hex": expected_old_prefix.hex(),
        "old_tail_hex": old_tail.hex(),
    }


def diff_images(base: Image.Image, mutated: Image.Image, diff_mask_path: Path) -> dict:
    diff = ImageChops.difference(base.convert("RGB"), mutated.convert("RGB"))
    bbox = diff.getbbox()
    if bbox:
        mask = Image.new("RGB", diff.size, (0, 0, 0))
        src = diff.load()
        dst = mask.load()
        count = 0
        for y in range(diff.height):
            for x in range(diff.width):
                if src[x, y] != (0, 0, 0):
                    dst[x, y] = (255, 64, 64)
                    count += 1
        mask.save(diff_mask_path)
    else:
        count = 0
        Image.new("RGB", diff.size, (0, 0, 0)).save(diff_mask_path)
    return {"pixel_diff_count": count, "diff_bbox": list(bbox) if bbox else None}


def parse_box(value: str) -> list[int]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("--expected-diff-box must be x0,y0,x1,y1")
    try:
        box = [int(part, 0) for part in parts]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--expected-diff-box values must be integers") from exc
    x0, y0, x1, y1 = box
    if not (0 <= x0 <= x1 <= GBA_W and 0 <= y0 <= y1 <= GBA_H):
        raise argparse.ArgumentTypeError(
            f"--expected-diff-box out of GBA bounds: {box}"
        )
    return box


def bbox_within(inner: list[int] | None, outer: list[int] | None) -> bool | None:
    if outer is None:
        return None
    if inner is None:
        return False
    return outer[0] <= inner[0] and inner[2] <= outer[2] and outer[1] <= inner[1] and inner[3] <= outer[3]


def font(size: int):
    for path in ["/Library/Fonts/NanumGothic.ttf", "/System/Library/Fonts/Supplemental/AppleGothic.ttf"]:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def panel(img: Image.Image, title: str, scale: int = 4) -> Image.Image:
    body = img.convert("RGB").resize((img.width * scale, img.height * scale), Image.NEAREST)
    header = 28
    out = Image.new("RGB", (body.width, body.height + header), (24, 24, 26))
    out.paste(body, (0, header))
    d = ImageDraw.Draw(out)
    d.text((8, 6), title, fill=(238, 238, 238), font=font(15))
    return out


def write_contact(base_path: Path, mut_path: Path, diff_path: Path, out_path: Path, title: str) -> None:
    panels = [
        panel(Image.open(base_path), "base"),
        panel(Image.open(mut_path), "mutation"),
        panel(Image.open(diff_path), "diff"),
    ]
    pad = 10
    header = 34
    w = sum(p.width for p in panels) + pad * (len(panels) + 1)
    h = max(p.height for p in panels) + header + pad * 2
    sheet = Image.new("RGB", (w, h), (14, 14, 16))
    d = ImageDraw.Draw(sheet)
    d.text((pad, 8), title, fill=(245, 245, 245), font=font(18))
    x = pad
    for p in panels:
        sheet.paste(p, (x, header + pad))
        x += p.width + pad
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)


def parse_target(value: str) -> tuple[int, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("--target must be 0xADDR=TEXT")
    addr_s, text = value.split("=", 1)
    text = text.strip()
    if not text:
        raise argparse.ArgumentTypeError("mutation text is empty")
    return parse_addr(addr_s.strip()), text


def parse_nav_step(value: str) -> list:
    """Parse a small CLI nav step, e.g. press:DOWN:120 or frames:30."""
    parts = value.split(":")
    if not parts:
        raise argparse.ArgumentTypeError("empty nav step")
    op = parts[0].strip()
    if op == "frames":
        if len(parts) != 2:
            raise argparse.ArgumentTypeError("frames step must be frames:N")
        return ["frames", int(parts[1], 0)]
    if op == "press":
        if len(parts) not in (2, 3, 4):
            raise argparse.ArgumentTypeError("press step must be press:KEY[:AFTER[:HOLD]]")
        step = ["press", parts[1].strip()]
        if len(parts) >= 3:
            step.append(int(parts[2], 0))
        if len(parts) >= 4:
            step.append(int(parts[3], 0))
        return step
    raise argparse.ArgumentTypeError(f"unsupported nav op: {op!r}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=str(ROM))
    ap.add_argument("--checkpoint", default="41_part1_operation_room")
    ap.add_argument("--out", default=str(OUT_DIR))
    ap.add_argument("--contact-dir", default=str(DOC_CONTACT_DIR))
    ap.add_argument("--harness", default=str(HARNESS))
    ap.add_argument("--scene-id", default="15_part1_operation_logos")
    ap.add_argument("--group", default="b8_compact_display_table_all")
    ap.add_argument("--expected-diff-box", type=parse_box,
                    help="optional screen bbox x0,y0,x1,y1 that mutation diff must stay inside")
    ap.add_argument("--skip-null-control", action="store_true",
                    help="skip same-ROM repeated base capture deterministic null control")
    ap.add_argument("--append-nav-step", action="append", type=parse_nav_step, default=[],
                    help="append a fresh checkpoint nav step, e.g. press:DOWN:120 or frames:30; repeatable")
    ap.add_argument("--target", action="append", type=parse_target, required=True,
                    help="single-address mutation as 0xADDR=TEXT; repeatable")
    args = ap.parse_args()

    rom = Path(args.rom)
    if not rom.exists():
        raise SystemExit(f"ROM missing: {rom}")
    harness = Path(args.harness)
    if not harness.exists():
        raise SystemExit(f"mGBA harness missing: {harness}")
    out_dir = Path(args.out)
    contact_dir = Path(args.contact_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    contact_dir.mkdir(parents=True, exist_ok=True)

    checkpoint = dict(checkpoint_by_name(args.checkpoint))
    if args.append_nav_step:
        if checkpoint.get("mode") != "fresh":
            raise SystemExit("--append-nav-step only supports fresh checkpoints")
        nav_suffix = "_".join(safe_tag("_".join(map(str, step))) for step in args.append_nav_step)
        checkpoint_name = checkpoint["name"] + "_plus_" + nav_suffix
        if len(checkpoint_name) > 140:
            digest = hashlib.sha1(
                json.dumps(args.append_nav_step, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            ).hexdigest()[:10]
            checkpoint_name = f"{checkpoint['name']}_plus_{len(args.append_nav_step)}steps_{digest}"
        checkpoint["name"] = checkpoint_name
        checkpoint["nav"] = list(checkpoint.get("nav", [])) + args.append_nav_step
        checkpoint["note"] = (checkpoint.get("note") or "") + f" + appended nav {args.append_nav_step!r}"
    rows = dialogue_rows_by_addr()
    rom_sha = sha256(rom)

    checkpoint_name = checkpoint["name"]
    base_capture_root = out_dir / "base_capture"
    base_img = capture(rom, checkpoint, base_capture_root, harness, "patched")
    base_frame = base_capture_root / f"{checkpoint_name}_patched" / "frame.png"
    if not base_frame.exists():
        raise SystemExit("base capture missing: " + str(base_frame))
    null_control = {
        "enabled": not args.skip_null_control,
    }
    if not args.skip_null_control:
        null_root = out_dir / "base_repeat_capture"
        repeat_img = capture(rom, checkpoint, null_root, harness, "patched")
        repeat_frame = null_root / f"{checkpoint_name}_patched" / "frame.png"
        null_diff_mask = out_dir / "base_repeat_diff_mask.png"
        null_diff = diff_images(base_img, repeat_img, null_diff_mask)
        null_control.update({
            "base_repeat_frame": rel(repeat_frame),
            "diff_mask": rel(null_diff_mask),
            "pixel_diff_count": null_diff["pixel_diff_count"],
            "diff_bbox": null_diff["diff_bbox"],
            "deterministic": null_diff["pixel_diff_count"] == 0,
        })

    proofs = []
    for addr, mutation_text in args.target:
        row = rows.get(addr)
        if not row:
            raise SystemExit(f"dialogue_map row missing for 0x{addr:08X}")
        slot = int(row.get("slot") or 0)
        if slot <= 0:
            raise SystemExit(f"invalid slot for 0x{addr:08X}: {slot}")
        base_text = row.get("ship_ko") or row.get("ko") or ""
        base_encoded = encode_mutation(base_text)
        encoded = encode_mutation(mutation_text)
        tag = f"0x{addr:08X}_{safe_tag(mutation_text)}"
        work = out_dir / tag
        work.mkdir(parents=True, exist_ok=True)
        mut_rom = work / "mutation.gba"
        hexes = write_mutation_rom(rom, mut_rom, addr, slot, encoded, base_encoded)
        capture(mut_rom, checkpoint, work, harness, "patched")
        mut_frame = work / f"{checkpoint_name}_patched" / "frame.png"
        diff_mask = work / "diff_mask.png"
        diff = diff_images(base_img, Image.open(mut_frame), diff_mask)
        doc_diff_mask = contact_dir / f"{safe_tag(args.group)}_{addr:08X}_diff_mask.png"
        shutil.copyfile(diff_mask, doc_diff_mask)
        contact = contact_dir / f"{safe_tag(args.group)}_{addr:08X}_mutation_contact.png"
        write_contact(
            base_frame,
            mut_frame,
            diff_mask,
            contact,
            f"0x{addr:08X}: {base_text} -> {mutation_text}",
        )
        proof = {
            "address": f"0x{addr:08X}",
            "group": args.group,
            "type": "single_address_mutation_pixel_diff",
            "rom_sha256": rom_sha,
            "base_text": base_text,
            "mutation_text": mutation_text,
            "slot": slot,
            "encoded_hex": encoded.hex(),
            "base_encoded_hex": hexes["base_encoded_hex"],
            "old_hex": hexes["old_hex"],
            "new_hex": hexes["new_hex"],
            "fill_byte": hexes["fill_byte"],
            "old_tail_hex": hexes["old_tail_hex"],
            "checkpoint": checkpoint_name,
            "scene_id": args.scene_id,
            "base_frame": rel(base_frame),
            "mutated_frame": rel(mut_frame),
            "diff_mask": rel(doc_diff_mask),
            "contact_sheet": rel(contact),
            "contact_sheet_sha256": sha256(contact),
            "diff_mask_sha256": sha256(doc_diff_mask),
            "pixel_diff_count": diff["pixel_diff_count"],
            "diff_bbox": diff["diff_bbox"],
            "expected_diff_box": args.expected_diff_box,
            "diff_bbox_within_expected_box": bbox_within(diff["diff_bbox"], args.expected_diff_box),
            "null_control": null_control,
            "note": (
                f"Single-address mutation at 0x{addr:08X} produced a localized "
                f"pixel diff on checkpoint {checkpoint_name}. This proves this "
                f"{args.group} address is a live screen source on that route, not a dead copy."
                if diff["pixel_diff_count"] > 0 else
                f"Single-address mutation at 0x{addr:08X} produced no pixel diff on "
                f"checkpoint {checkpoint_name}; this route is not target-level evidence "
                f"for {args.group}."
            ),
        }
        (work / "evidence.json").write_text(
            json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        proofs.append(proof)

    summary = {
        "tool": "tools/prove_compact_display_mutation.py",
        "rom": rel(rom),
        "rom_sha256": rom_sha,
        "checkpoint": checkpoint_name,
        "base_frame": rel(base_frame),
        "null_control": null_control,
        "proofs": proofs,
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
