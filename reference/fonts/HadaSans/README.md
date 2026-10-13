# Hada Sans (Part 2 LARGE mode plates)

Used only for the seven Part 2 LARGE mode-menu plates (user decision 2026-10-13):
`HadaSans-Bold.otf` draws the letters and `HadaSans-Black.otf` is the weight guide
(see `tools/hangul_pixel_fit.py`, `data/part2_mode_plate_geometry.json`).
The font binaries are not committed here; only the licence (`LICENSE.txt`, SIL OFL 1.1).

## Pinned files

| File | Version (name table) | SHA-256 |
|---|---|---|
| `HadaSans-Bold.otf`  | Version 1.000 (`1.000;HADA;HadaSans-Bold`)  | `213aaecf921e19d71f43b8a7f0c4076d3efa0552c2ecc9ed2d021c6873bdebba` |
| `HadaSans-Black.otf` | Version 1.000 (`1.000;HADA;HadaSans-Black`) | `6e80fc2410876192323434584523b9d8e3dfba1a79f8a3d42cd7520631f6b048` |

`tools/aw_fonts.py` checks both hashes and fails closed (`hadasans_path()`,
`hadasans_black_path()`).

## Source

- Repository: https://github.com/hada0127/font (Hada Type Foundry), branch `main`
- Commit that last changed both files: `1e2b4c27e87594ca0d651a3c883d99b71505dff5` (2026-09-04)
- Path: `fonts/hada-sans/otf/HadaSans-Bold.otf`, `fonts/hada-sans/otf/HadaSans-Black.otf`
  (also packaged as `fonts/packages/HadaSans-OTF.zip` in that repository)

## Install

```bash
git clone https://github.com/hada0127/font.git /tmp/hada-font   # or any scratch dir
git -C /tmp/hada-font checkout 1e2b4c27e87594ca0d651a3c883d99b71505dff5
mkdir -p ~/.local/share/fonts/HadaSans
cp /tmp/hada-font/fonts/hada-sans/otf/HadaSans-{Bold,Black}.otf ~/.local/share/fonts/HadaSans/
sha256sum ~/.local/share/fonts/HadaSans/HadaSans-{Bold,Black}.otf   # must match the table above
```

Default lookup: `~/.local/share/fonts/HadaSans/`. Override with `AW_HADASANS_FONT`
(Bold) and `AW_HADASANS_BLACK_FONT` (Black). `AW_FONT_DIR` (OkDanDan) does not cover
these files.
