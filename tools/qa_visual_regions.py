#!/usr/bin/env python3
"""Targeted visual QA for Korean title/menu sprite regions.

This checks the high-risk Korean graphics that are easy to miss with text-only
QA: cold-boot Nintendo Presents, 1/2 select lower marker, Part 1 mode option
sprite sizes, and Part 1 submenu top-left logo visibility/safe zones.
Part 1 menu screen checks use a cold-boot route by default; cross-ROM
savestates can carry stale VRAM/text cache and must not be the main gate.
"""
from __future__ import annotations

import argparse
import os
import struct
import subprocess
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_title_hangul as th


ROOT = Path(__file__).resolve().parents[1]
KEYS = {
    "A": 1,
    "B": 2,
    "SELECT": 4,
    "START": 8,
    "RIGHT": 16,
    "LEFT": 32,
    "UP": 64,
    "DOWN": 128,
    "R": 256,
    "L": 512,
}

PART1_MENU_PRENAV = [
    "A",
    "START",
    "A",
    "START",
    "A",
    "A",
    "A",
    "A",
    "A",
    "A",
    "START",
]
PART1_MENU_ADVANCE_A_PRESSES = 17


def layer_bbox(layer: Image.Image) -> tuple[int, int, int, int]:
    bbox = layer.getbbox()
    if bbox is None:
        raise AssertionError("empty layer")
    return bbox


def assert_bbox(
    label: str,
    bbox: tuple[int, int, int, int],
    *,
    min_w: int = 1,
    min_h: int = 1,
    max_w: int | None = None,
    max_h: int | None = None,
    x0_min: int = 0,
    y0_min: int = 0,
    x1_max: int = 999,
    y1_max: int = 999,
) -> None:
    x0, y0, x1, y1 = bbox
    w = x1 - x0
    h = y1 - y0
    errors = []
    if w < min_w:
        errors.append(f"width {w} < {min_w}")
    if h < min_h:
        errors.append(f"height {h} < {min_h}")
    if max_w is not None and w > max_w:
        errors.append(f"width {w} > {max_w}")
    if max_h is not None and h > max_h:
        errors.append(f"height {h} > {max_h}")
    if x0 < x0_min:
        errors.append(f"x0 {x0} < {x0_min}")
    if y0 < y0_min:
        errors.append(f"y0 {y0} < {y0_min}")
    if x1 > x1_max:
        errors.append(f"x1 {x1} > {x1_max}")
    if y1 > y1_max:
        errors.append(f"y1 {y1} > {y1_max}")
    if errors:
        raise AssertionError(f"{label}: bbox={bbox}: " + ", ".join(errors))


def assert_layer_not_blank(label: str, layer: Image.Image) -> tuple[int, int, int, int]:
    bbox = layer.getbbox()
    if bbox is None:
        raise AssertionError(f"{label}: expected visible Korean label, got blank layer")
    return bbox


def assert_title_style_palette(label: str, layer: Image.Image) -> str:
    counts: dict[int, int] = {}
    for value in layer.getdata():
        if value:
            counts[int(value)] = counts.get(int(value), 0) + 1
    values = set(counts)
    required = {9, 10, 14, 15}
    missing = sorted(required - values)
    if missing:
        raise AssertionError(f"{label}: missing title-style shadow/outline indices {missing}, values={sorted(values)}")
    if len(values) < 7:
        raise AssertionError(f"{label}: palette too simple for title font style, values={sorted(values)}")
    style_pixels = sum(counts.get(idx, 0) for idx in (1, 5, 6, 9, 10, 14))
    if style_pixels < 80:
        raise AssertionError(f"{label}: title-style highlight/shadow pixels too few ({style_pixels} < 80)")
    if counts.get(10, 0) < 60 or counts.get(14, 0) < 60:
        raise AssertionError(f"{label}: title-style body/outline too weak, counts={counts}")
    return f"values={sorted(values)}:style_pixels={style_pixels}"


def assert_compact_option_palette(label: str, layer: Image.Image) -> str:
    counts: dict[int, int] = {}
    for value in layer.getdata():
        if value:
            counts[int(value)] = counts.get(int(value), 0) + 1
    values = set(counts)
    missing = sorted({2} - values)
    if missing:
        raise AssertionError(f"{label}: missing compact fill index {missing}, values={sorted(values)}")
    extra = sorted(values - {2})
    if extra:
        raise AssertionError(f"{label}: unexpected high-profile option palette indices {extra}, values={sorted(values)}")
    pixels = sum(counts.values())
    if pixels < 35:
        raise AssertionError(f"{label}: too few compact label pixels ({pixels} < 35)")
    if counts.get(15, 0) > 0:
        raise AssertionError(f"{label}: outline pixels remain in compact option label, counts={counts}")
    return f"values={sorted(values)}:pixels={pixels}:edge={counts.get(15, 0)}"


def assert_select_logo_style(
    label: str,
    layer: Image.Image,
    crop_box: tuple[int, int, int, int],
    *,
    body_indices: set[int],
    outer_idx: int,
    inner_idx: int,
    center_min: float = 112,
    center_max: float = 121,
    x1_max: int = 214,
    min_w: int = 182,
    min_h: int = 23,
    min_body_pixels: int = 900,
) -> str:
    crop = layer.crop(crop_box)
    bbox = crop.getbbox()
    if bbox is None:
        raise AssertionError(f"{label}: missing")
    x0, y0, x1, y1 = bbox
    gx0, gy0, gx1, gy1 = x0 + crop_box[0], y0 + crop_box[1], x1 + crop_box[0], y1 + crop_box[1]
    w = gx1 - gx0
    h = gy1 - gy0
    cx = (gx0 + gx1) / 2
    if gx0 < 18:
        raise AssertionError(f"{label}: x0 {gx0} < 18")
    if gx1 > x1_max:
        raise AssertionError(f"{label}: x1 {gx1} > {x1_max}")
    if w < min_w:
        raise AssertionError(f"{label}: width {w} < {min_w}")
    if h < min_h:
        raise AssertionError(f"{label}: height {h} < {min_h}")
    if not (center_min <= cx <= center_max):
        raise AssertionError(f"{label}: center x {cx:.1f} outside {center_min}..{center_max}")
    counts: dict[int, int] = {}
    for value in crop.getdata():
        if value:
            counts[int(value)] = counts.get(int(value), 0) + 1
    body_pixels = sum(counts.get(idx, 0) for idx in body_indices)
    if counts.get(outer_idx, 0) < 650:
        raise AssertionError(f"{label}: dark outer outline too weak, counts={counts}")
    if counts.get(inner_idx, 0) < 500:
        raise AssertionError(f"{label}: white inner outline too weak, counts={counts}")
    if body_pixels < min_body_pixels:
        raise AssertionError(f"{label}: orange/yellow body too weak ({body_pixels} < {min_body_pixels})")
    return f"bbox={(gx0, gy0, gx1, gy1)}:body={body_pixels}:counts={counts}"


def assert_tm_pattern(label: str, layer: Image.Image, crop_box: tuple[int, int, int, int]) -> str:
    crop = layer.crop(crop_box)
    bbox = crop.getbbox()
    if bbox is None:
        raise AssertionError(f"{label}: missing TM pixels")
    x0, y0, x1, y1 = bbox
    gx0, gy0, gx1, gy1 = x0 + crop_box[0], y0 + crop_box[1], x1 + crop_box[0], y1 + crop_box[1]
    counts: dict[int, int] = {}
    for value in crop.getdata():
        if value:
            counts[int(value)] = counts.get(int(value), 0) + 1
    if (gx1 - gx0) < 12 or (gy1 - gy0) < 8:
        raise AssertionError(f"{label}: TM bbox too small {(gx0, gy0, gx1, gy1)}")
    if counts.get(1, 0) < 20 or counts.get(2, 0) < 50:
        raise AssertionError(f"{label}: TM outline/fill too weak, counts={counts}")
    return f"bbox={(gx0, gy0, gx1, gy1)}:counts={counts}"


def run_asset_checks() -> list[str]:
    checked: list[str] = []
    failures: list[str] = []
    try:
        select_layer = th.make_select_index_layer()
        top = assert_select_logo_style(
            "select top Korean logo",
            select_layer,
            (0, 0, 204, 64),
            body_indices={2, 4, 6, 8, 10},
            outer_idx=15,
            inner_idx=1,
            center_min=110,
            center_max=118,
            x1_max=204,
            min_w=176,
            min_h=22,
            min_body_pixels=860,
        )
        bottom = assert_select_logo_style(
            "select bottom Korean logo",
            select_layer,
            (0, 88, 220, 132),
            body_indices={4, 5, 6, 7, 8},
            outer_idx=1,
            inner_idx=15,
            center_min=117,
            center_max=126,
            x1_max=219,
        )
        top_tm = assert_tm_pattern("select top TM", th.make_select_top_tm_overlay_layer(), (201, 26, 219, 38))
        part1_tm = assert_tm_pattern("part1 title TM", th.make_part1_tm_overlay_layer(), (210, 33, 229, 45))
        part2_title = assert_select_logo_style(
            "part2 title Korean logo",
            th.make_part2_index_layer(),
            (0, 16, 220, 64),
            body_indices={4, 5, 6, 7, 8},
            outer_idx=1,
            inner_idx=15,
            center_min=112,
            center_max=121,
            x1_max=208,
            min_w=176,
            min_h=22,
            min_body_pixels=860,
        )
        checked.append(f"asset:select_top_logo:{top}")
        checked.append(f"asset:select_bottom_logo:{bottom}")
        checked.append(f"asset:select_top_tm:{top_tm}")
        checked.append(f"asset:part1_title_tm:{part1_tm}")
        checked.append(f"asset:part2_title_logo:{part2_title}")
    except AssertionError as exc:
        failures.append(str(exc))

    # Part1 option labels scroll behind the translucent help box. Check every
    # option block, including long communication labels, so the replacement
    # cannot regress back to oversized/shadow-heavy graphics.
    for name, _off, text, max_size in th.PART1_MODE_OPTION_BLOCKS:
        try:
            layer = th.make_part1_option_block(text, max_size)
            bbox = layer_bbox(layer)
            assert_bbox(
                f"part1 option {name}",
                bbox,
                min_w=18,
                min_h=8,
                max_w=96,
                max_h=16,
                x0_min=10,
                y0_min=4,
                x1_max=118,
                y1_max=24,
            )
            style = assert_compact_option_palette(f"part1 option {name}", layer)
            display_text = th.part1_option_display_text(text)
            checked.append(f"asset:part1_option:{name}:{display_text}:{bbox}:{style}")
        except AssertionError as exc:
            failures.append(str(exc))

    submenu_targets = {"single_battle", "connect", "single_card", "multi_card", "cable_battle"}
    for name, _off, text, max_size in th.PART1_SUBMENU_LOGO_BLOCKS:
        if name not in submenu_targets:
            continue
        layer = th.make_part1_submenu_label_block(text, max_size)
        try:
            bbox = assert_layer_not_blank(f"part1 submenu {name}", layer)
            assert_bbox(
                f"part1 submenu {name}",
                bbox,
                min_w={"single_battle": 68, "connect": 44}.get(name, 18),
                min_h=8,
                x0_min=4,
                y0_min=4,
                x1_max=78,
                y1_max=30,
            )
            nonzero = sum(1 for value in layer.getdata() if value)
            if nonzero < 45:
                raise AssertionError(f"part1 submenu {name}: too few label pixels ({nonzero} < 45)")
            style = ""
            if name in {"single_battle", "connect"}:
                style = ":" + assert_title_style_palette(f"part1 submenu {name}", layer)
            checked.append(f"asset:part1_submenu:{name}:{bbox}:pixels={nonzero}{style}")
        except AssertionError as exc:
            failures.append(str(exc))
    if failures:
        raise AssertionError("asset visual failures:\n" + "\n".join(f"- {failure}" for failure in failures))
    return checked


def raw_to_png(raw_path: Path, png_path: Path) -> Image.Image:
    data = raw_path.read_bytes()
    w, h = struct.unpack("<HH", data[:4])
    color_size = data[4]
    pixels = data[5:]
    image = Image.new("RGB", (w, h))
    out = image.load()
    for y in range(h):
        for x in range(w):
            idx = (y * w + x) * color_size
            out[x, y] = (pixels[idx], pixels[idx + 1], pixels[idx + 2])
    image.save(png_path)
    return image


class MGBADriver:
    def __init__(self, rom: Path, out_dir: Path, harness: Path, savegame: Path | None = None) -> None:
        env = os.environ.copy()
        env["DYLD_LIBRARY_PATH"] = "/opt/homebrew/lib"
        self.out_dir = out_dir
        argv = [str(harness), str(rom), str(out_dir / "mgbah.stderr.log")]
        if savegame is not None:
            argv.append(str(savegame))
        self.proc = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

    def cmd(self, command: str) -> str:
        assert self.proc.stdin is not None and self.proc.stdout is not None
        self.proc.stdin.write(command + "\n")
        self.proc.stdin.flush()
        return self.proc.stdout.readline().strip()

    def frames(self, count: int) -> None:
        self.cmd(f"frames {count}")

    def press(self, key: str, hold: int = 6, after: int = 120) -> None:
        self.cmd(f"keys {KEYS[key]}")
        self.frames(hold)
        self.cmd("keys 0")
        self.frames(after)

    def shot(self, name: str) -> Image.Image:
        raw = self.out_dir / f"{name}.raw"
        png = self.out_dir / f"{name}.png"
        self.cmd(f"shot {raw}")
        return raw_to_png(raw, png)

    def loadstate(self, state: Path) -> None:
        response = self.cmd(f"loadstate {state}")
        if not response.endswith("ok=1"):
            raise AssertionError(response)

    def close(self) -> None:
        if self.proc.poll() is None:
            self.cmd("quit")
        self.proc.wait(timeout=5)


def drive_part1_menu_from_coldboot(driver: MGBADriver) -> None:
    """Reach the Part 1 post-name mode menu without loading a savestate."""
    driver.frames(480)
    for key in PART1_MENU_PRENAV:
        driver.press(key, after=120)
    for _ in range(PART1_MENU_ADVANCE_A_PRESSES):
        driver.press("A", after=160)
    driver.frames(10)


def foreground_bbox(
    image: Image.Image,
    box: tuple[int, int, int, int],
    bg_color: tuple[int, int, int],
    threshold: int,
) -> tuple[int, int, int, int] | None:
    crop = image.crop(box).convert("RGB")
    pixels = crop.load()
    points: list[tuple[int, int]] = []
    for y in range(crop.height):
        for x in range(crop.width):
            r, g, b = pixels[x, y]
            dist = (r - bg_color[0]) ** 2 + (g - bg_color[1]) ** 2 + (b - bg_color[2]) ** 2
            if dist >= threshold:
                points.append((x, y))
    if not points:
        return None
    return (
        min(x for x, _y in points),
        min(y for _x, y in points),
        max(x for x, _y in points) + 1,
        max(y for _x, y in points) + 1,
    )


def foreground_stats(
    image: Image.Image,
    box: tuple[int, int, int, int],
    bg_color: tuple[int, int, int],
    threshold: int,
) -> tuple[tuple[int, int, int, int] | None, int, float]:
    crop = image.crop(box).convert("RGB")
    points: list[tuple[int, int]] = []
    for y in range(crop.height):
        for x in range(crop.width):
            r, g, b = crop.getpixel((x, y))
            dist = (r - bg_color[0]) ** 2 + (g - bg_color[1]) ** 2 + (b - bg_color[2]) ** 2
            if dist >= threshold:
                points.append((x, y))
    if not points:
        return None, 0, 0.0
    bbox = (
        min(x for x, _y in points),
        min(y for _x, y in points),
        max(x for x, _y in points) + 1,
        max(y for _x, y in points) + 1,
    )
    area = max(1, (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))
    return bbox, len(points), len(points) / area


def count_dark_pixels(image: Image.Image, box: tuple[int, int, int, int]) -> int:
    crop = image.crop(box).convert("RGB")
    count = 0
    for r, g, b in crop.getdata():
        if max(r, g, b) < 120 and (max(r, g, b) - min(r, g, b) > 20):
            count += 1
    return count


def count_intrusive_help_pixels(image: Image.Image, box: tuple[int, int, int, int]) -> int:
    crop = image.crop(box).convert("RGB")
    count = 0
    for r, g, b in crop.getdata():
        if max(r, g, b) < 70 and (max(r, g, b) - min(r, g, b) > 15):
            count += 1
    return count


def count_bright_pixels(image: Image.Image, box: tuple[int, int, int, int]) -> int:
    crop = image.crop(box).convert("RGB")
    count = 0
    for r, g, b in crop.getdata():
        if min(r, g, b) > 220:
            count += 1
    return count


def count_light_pixels(image: Image.Image, box: tuple[int, int, int, int]) -> int:
    crop = image.crop(box).convert("RGB")
    count = 0
    for r, g, b in crop.getdata():
        if min(r, g, b) > 140:
            count += 1
    return count


def count_saturated_bright_pixels(image: Image.Image, box: tuple[int, int, int, int]) -> int:
    crop = image.crop(box).convert("RGB")
    count = 0
    for r, g, b in crop.getdata():
        if max(r, g, b) > 145 and max(r, g, b) - min(r, g, b) > 65:
            count += 1
    return count


def count_saturated_pixels_touching_edge(
    image: Image.Image,
    box: tuple[int, int, int, int],
    *,
    edge: str,
) -> int:
    crop = image.crop(box).convert("RGB")
    if edge == "right":
        points = ((crop.width - 1, y) for y in range(crop.height))
    elif edge == "bottom":
        points = ((x, crop.height - 1) for x in range(crop.width))
    else:
        raise ValueError(edge)
    count = 0
    for x, y in points:
        r, g, b = crop.getpixel((x, y))
        if max(r, g, b) > 145 and max(r, g, b) - min(r, g, b) > 65:
            count += 1
    return count


def count_clipped_logo_text_pixels(image: Image.Image, box: tuple[int, int, int, int]) -> int:
    """Count colored letter pixels in the risky top-left logo area.

    The submenu screens keep a purple decorative banner in this area. That is
    acceptable; clipped red/cyan/green logo letters at the screen edge are not.
    """
    crop = image.crop(box).convert("RGB")
    count = 0
    for r, g, b in crop.getdata():
        is_pink = r > 170 and b > 130 and g < 160
        is_cyan = g > 150 and b > 140 and r < 160
        is_green = g > 150 and r < 160 and b < 120
        is_red = r > 170 and g < 120 and b < 120
        if is_pink or is_cyan or is_green or is_red:
            count += 1
    return count


def count_top_left_label_edge_pixels(image: Image.Image) -> int:
    boxes = (
        (0, 0, 4, 36),
        (0, 0, 86, 4),
        (80, 0, 86, 36),
        (0, 31, 86, 36),
    )
    return sum(count_clipped_logo_text_pixels(image, box) for box in boxes)


def run_emulator_checks(rom: Path, out_dir: Path, harness: Path, menu_state: Path | None) -> list[str]:
    checked: list[str] = []
    failures: list[str] = []
    if not harness.exists():
        raise AssertionError(f"missing mGBA harness: {harness}")

    cold = out_dir / "cold"
    cold.mkdir(parents=True, exist_ok=True)
    driver = MGBADriver(rom, cold, harness)
    try:
        driver.frames(60)
        nintendo = driver.shot("00_nintendo")
        bbox, nintendo_pixels, nintendo_density = foreground_stats(nintendo, (40, 58, 204, 92), (159, 159, 159), 2000)
        if bbox is None:
            failures.append("nintendo presents: no foreground pixels")
        else:
            try:
                assert_bbox("nintendo presents screen", bbox, min_w=55, min_h=9, y0_min=1, y1_max=30)
            except AssertionError as exc:
                failures.append(str(exc))
            if nintendo_density > 0.68:
                failures.append(
                    f"nintendo presents too dense/unreadable: density={nintendo_density:.3f}, "
                    f"pixels={nintendo_pixels}, bbox={bbox}"
                )
            checked.append(f"screen:nintendo:{bbox}:density={nintendo_density:.3f}")

        driver.frames(300)
        driver.press("A", after=180)
        driver.press("START", after=180)
        select_up = driver.shot("01_select_up")
        select_top_tm_dark = count_dark_pixels(select_up, (204, 28, 217, 36))
        select_top_tm_light = count_light_pixels(select_up, (204, 28, 217, 36))
        if select_top_tm_dark < 45 or select_top_tm_light < 18:
            failures.append(
                "select top TM missing/unreadable: "
                f"dark={select_top_tm_dark}, light={select_top_tm_light}"
            )
        checked.append(f"screen:select_top_tm:dark={select_top_tm_dark}:light={select_top_tm_light}")
        driver.press("DOWN", after=120)
        select_down = driver.shot("02_select_down")
        right_preserved = count_saturated_bright_pixels(select_down, (208, 80, 240, 144))
        right_edge_preserved = count_saturated_bright_pixels(select_down, (232, 80, 240, 144))
        bottom_logo_bright = count_bright_pixels(select_down, (192, 127, 240, 135))
        if right_preserved < 650:
            failures.append(
                "part2 select right-side graphic missing/cut: "
                f"saturated preserved pixels {right_preserved} < 650"
            )
        if right_edge_preserved < 140:
            failures.append(
                "part2 select right edge no longer matches full original graphic: "
                f"saturated edge pixels {right_edge_preserved} < 140"
            )
        checked.append(
            "screen:select_part2_lower_right:"
            f"preserved={right_preserved}:edge_preserved={right_edge_preserved}:"
            f"bottom_logo_bright={bottom_logo_bright}"
        )
    finally:
        driver.close()

    menu = out_dir / "part1_menu"
    menu.mkdir(parents=True, exist_ok=True)
    driver = MGBADriver(rom, menu, harness)
    try:
        if menu_state is not None:
            driver.frames(1)
            driver.loadstate(menu_state)
            driver.frames(10)
            driver.shot("00_loaded_external_state")
            checked.append(f"screen:part1_menu_entry=external_state:{menu_state}")
        else:
            drive_part1_menu_from_coldboot(driver)
            driver.shot("00_fresh_menu")
            driver.cmd(f"savestate {menu / 'fresh_menu.ss0'}")
            checked.append("screen:part1_menu_entry=fresh_coldboot")
        driver.press("A", after=160)
        driver.shot("01_operation")
        driver.press("B", after=180)
        menu_img = driver.shot("02_menu_after_operation_back")
        # These labels are asset-checked for exact size. The screen check makes
        # sure the refreshed ROM path is being exercised and visible.
        for label, box in {
            "mode_battle": (118, 0, 160, 30),
            "mode_link": (75, 26, 130, 62),
            "mode_operation": (42, 58, 128, 98),
        }.items():
            light = count_light_pixels(menu_img, box)
            if light < 80:
                failures.append(f"{label}: too few visible compact label pixels ({light})")
            checked.append(f"screen:{label}:light_pixels={light}")
        help_intrusive = count_intrusive_help_pixels(menu_img, (8, 108, 140, 154))
        if help_intrusive > 60:
            failures.append(f"mode help box has intrusive dark label pixels ({help_intrusive} > 60)")
        checked.append(f"screen:mode_help_intrusive_dark={help_intrusive}")

        driver.press("DOWN", after=120)
        driver.shot("03_menu_single_selected")
        driver.press("A", after=180)
        single = driver.shot("04_single_screen")
        single_edge = count_top_left_label_edge_pixels(single)
        single_visible = count_clipped_logo_text_pixels(single, (6, 4, 78, 30))
        if single_edge > 24:
            failures.append(f"single battle top-left clipped logo text: edge colored pixels {single_edge} > 24")
        if single_visible < 35:
            failures.append(f"single battle top-left label missing/unreadable: visible label pixels {single_visible} < 35")
        single_help_intrusive = count_intrusive_help_pixels(single, (8, 108, 150, 154))
        if single_help_intrusive > 60:
            failures.append(f"single battle help box has intrusive dark label pixels ({single_help_intrusive} > 60)")
        checked.append(f"screen:single_top_left:visible={single_visible}:edge={single_edge}")
        checked.append(f"screen:single_help_intrusive_dark={single_help_intrusive}")

        driver.press("B", after=180)
        driver.press("DOWN", after=120)
        driver.shot("05_menu_link_selected")
        driver.press("A", after=180)
        link = driver.shot("06_link_screen")
        link_edge = count_top_left_label_edge_pixels(link)
        link_visible = count_clipped_logo_text_pixels(link, (6, 4, 78, 30))
        if link_edge > 24:
            failures.append(f"connect top-left clipped logo text: edge colored pixels {link_edge} > 24")
        if link_visible < 35:
            failures.append(f"connect top-left label missing/unreadable: visible label pixels {link_visible} < 35")
        link_help_intrusive = count_intrusive_help_pixels(link, (8, 108, 150, 154))
        if link_help_intrusive > 60:
            failures.append(f"connect help box has intrusive dark label pixels ({link_help_intrusive} > 60)")
        checked.append(f"screen:connect_top_left:visible={link_visible}:edge={link_edge}")
        checked.append(f"screen:connect_help_intrusive_dark={link_help_intrusive}")
    finally:
        driver.close()

    if failures:
        raise AssertionError("visual region failures:\n" + "\n".join(f"- {failure}" for failure in failures))

    return checked


def run_title_entry_checks(rom: Path, out_dir: Path, harness: Path) -> list[str]:
    checked: list[str] = []
    failures: list[str] = []
    if not harness.exists():
        raise AssertionError(f"missing mGBA harness: {harness}")

    part1 = out_dir / "entry_part1"
    part1.mkdir(parents=True, exist_ok=True)
    driver = MGBADriver(rom, part1, harness)
    try:
        driver.frames(360)
        driver.press("A", after=180)
        driver.press("START", after=180)
        driver.shot("00_select_1")
        driver.press("A", after=240)
        driver.press("START", after=240)
        part1_title = driver.shot("01_part1_title")
        tm_bright = count_bright_pixels(part1_title, (210, 33, 229, 45))
        tm_dark = count_dark_pixels(part1_title, (210, 33, 229, 45))
        if tm_bright < 35 or tm_dark < 45:
            failures.append(f"part1 title TM missing/unreadable: bright={tm_bright}, dark={tm_dark}")
        checked.append(f"screen:part1_title_tm:bright={tm_bright}:dark={tm_dark}")
    finally:
        driver.close()

    part2 = out_dir / "entry_part2"
    part2.mkdir(parents=True, exist_ok=True)
    driver = MGBADriver(rom, part2, harness)
    try:
        driver.frames(360)
        driver.press("A", after=180)
        driver.press("START", after=180)
        driver.press("DOWN", after=120)
        driver.shot("00_select_2")
        driver.press("A", after=240)
        driver.press("START", after=240)
        part2_title = driver.shot("01_part2_title")
        logo_dark = count_dark_pixels(part2_title, (10, 20, 225, 80))
        logo_saturated = count_saturated_bright_pixels(part2_title, (10, 20, 225, 80))
        if logo_dark < 350 or logo_saturated < 4500:
            failures.append(
                "part2 title logo missing/unreadable: "
                f"dark={logo_dark}, saturated={logo_saturated}"
            )
        checked.append(f"screen:part2_title_logo:dark={logo_dark}:saturated={logo_saturated}")
    finally:
        driver.close()

    if failures:
        raise AssertionError("entry title visual failures:\n" + "\n".join(f"- {failure}" for failure in failures))
    return checked


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", default=str(ROOT / "output/game_wars_korean_final.gba"))
    parser.add_argument("--out", default=str(ROOT / "temp/qa_visual_regions_20260615"))
    parser.add_argument("--harness", default="/tmp/mgbah")
    parser.add_argument(
        "--menu-state",
        default="",
        help="Optional debug-only Part1 menu savestate. Default uses a coldboot fresh route.",
    )
    parser.add_argument("--asset-only", action="store_true")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    checked: list[str] = []
    failures: list[str] = []
    try:
        checked.extend(run_asset_checks())
    except AssertionError as exc:
        failures.append(str(exc))
    if not args.asset_only:
        try:
            menu_state = Path(args.menu_state) if args.menu_state else None
            checked.extend(run_emulator_checks(Path(args.rom), out_dir, Path(args.harness), menu_state))
        except AssertionError as exc:
            failures.append(str(exc))
        try:
            checked.extend(run_title_entry_checks(Path(args.rom), out_dir, Path(args.harness)))
        except AssertionError as exc:
            failures.append(str(exc))

    for item in checked:
        print(item)
    print(f"visual_region_checks={len(checked)}")
    if failures:
        raise AssertionError("visual region failures:\n" + "\n".join(failures))


if __name__ == "__main__":
    main()
