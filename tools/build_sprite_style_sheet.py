#!/usr/bin/env python3
"""Compare final-ROM Part 1 sprite pixels and fresh-boot menu screenshots."""
import argparse
import hashlib
import html
import json
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import build_title_hangul as th
from export_sprites import tiles_to_indices
from sprite_relocations import RELOCATIONS, resolve_sprite_offset
from capture_sprite_style import observed_sprites

ROOT = Path(__file__).resolve().parents[1]


def font(size=18):
    return ImageFont.truetype('/System/Library/Fonts/AppleSDGothicNeo.ttc', size)


def decode(rom, offset, width):
    result = th.lz77_decompress(rom, resolve_sprite_offset(rom, offset))
    if result is None:
        raise ValueError(f"invalid compressed sprite at {offset:#x}")
    data, consumed = result
    if len(data) != width * 32 // 2:
        raise ValueError(f"unexpected decoded size at {offset:#x}: {len(data)}")
    layer = Image.new('L', (width, 32))
    for tile in range(len(data) // 32):
        if tile < 32:
            x, y = (tile % 8) * 8, (tile // 8) * 8
        else:
            cols = (width - 64) // 8
            x, y = 64 + ((tile - 32) % cols) * 8, ((tile - 32) // cols) * 8
        grid, _, _ = tiles_to_indices(data[tile * 32:(tile + 1) * 32], 1)
        for yy in range(8):
            for xx in range(8):
                layer.putpixel((x + xx, y + yy), grid[yy][xx])
    encoded = th.option_layer_to_tiles(layer) if width == 128 else th.part1_logo_layer_to_tiles(layer)
    if encoded != data:
        raise AssertionError(f"tile round trip differs at {offset:#x}")
    return layer, consumed


def colorize(layer, palette):
    image = layer.convert('P')
    image.putpalette([channel for color in palette for channel in color] + [0] * 720)
    image.info['transparency'] = 0
    return image.convert('RGBA')


def write_pages(rows, out, stem, per_page):
    paths = []
    for start in range(0, len(rows), per_page):
        group = rows[start:start + per_page]
        sheet = Image.new('RGB', (group[0].width, 36 + sum(row.height for row in group)), 'white')
        draw = ImageDraw.Draw(sheet)
        for col, title in enumerate(('원본', '수정 전', '수정 후')):
            draw.text((col * (sheet.width // 3) + 8, 6), title, font=font(), fill='black')
        y = 36
        for row in group:
            sheet.paste(row, (0, y))
            y += row.height
        path = out / f'{stem}_{start // per_page + 1:02}.png'
        sheet.save(path)
        paths.append(path.name)
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--after', type=Path, required=True)
    parser.add_argument('--captures', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--offset', type=lambda value: int(value, 0), action='append',
                        help='Limit comparison and allowed ROM writes to these source offsets')
    parser.add_argument('--state', action='append', help='Show only these captured states')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    paths = [ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba', args.before, args.after]
    roms = [path.read_bytes() for path in paths]
    captures = [args.captures / variant for variant in ('original', 'before', 'after')]
    manifests = [json.loads((path / 'capture.json').read_text()) for path in captures]
    for rom, manifest in zip(roms, manifests):
        if manifest['rom_sha256'] != hashlib.sha256(rom).hexdigest():
            raise AssertionError('capture ROM hash mismatch')
    routes = [[(s['name'], s['route']) for s in manifest['states']] for manifest in manifests]
    if not all(route == routes[0] for route in routes):
        raise AssertionError('capture navigation differs')
    for rom, directory, manifest in zip(roms, captures, manifests):
        for state in manifest['states']:
            for suffix, expected in state['artifacts_sha256'].items():
                if hashlib.sha256((directory / f'{state["name"]}.{suffix}').read_bytes()).hexdigest() != expected:
                    raise AssertionError('capture artifact hash mismatch')
            name = state['name']
            state['observed_sprites'] = observed_sprites(
                rom, (directory / f'{name}.oam').read_bytes(),
                (directory / f'{name}.obj').read_bytes(),
                int.from_bytes((directory / f'{name}.dispcnt').read_bytes(), 'little'))
    if args.state:
        for manifest in manifests:
            available = {state['name'] for state in manifest['states']}
            if not set(args.state) <= available:
                raise ValueError('requested capture state is missing')
            manifest['states'] = [state for state in manifest['states'] if state['name'] in args.state]

    palettes = (captures[0] / 'main_0.pal').read_bytes()
    labels = [(text, offset) for _, offset, text, _ in th.PART1_MAIN_HEADER_BLOCKS]
    specs = [(text, off, 128) for _, off, text, _ in th.PART1_MODE_OPTION_BLOCKS]
    specs += [(text, off, 80) for text, off in labels]
    specs += [(text, off, 80) for _, off, text, _ in th.PART1_SUBMENU_LOGO_BLOCKS]
    if args.offset:
        if not set(args.offset) <= {off for _, off, _ in specs}:
            raise ValueError('requested sprite offset is unknown')
        specs = [spec for spec in specs if spec[1] in args.offset]
    report, asset_rows, variant_rows, allowed = [], [], [], []
    for text, offset, width in specs:
        decoded = [decode(rom, offset, width) for rom in roms]
        layers = [item[0] for item in decoded]
        original_size = decoded[0][1]
        capacities = [RELOCATIONS[offset]['capacity'] if resolve_sprite_offset(rom, offset) != offset
                      else original_size for rom in roms]
        capacity = capacities[2]
        if any(item[1] > limit for item, limit in zip(decoded, capacities)):
            raise AssertionError(f'compressed slot overrun: {offset:#x}')
        allowed.append((offset, offset + original_size))
        if offset in RELOCATIONS:
            spec = RELOCATIONS[offset]
            allowed.extend([(spec['pointer'], spec['pointer'] + 4),
                            (spec['destination'], spec['destination'] + spec['capacity'])])
        before, after = layers[1].tobytes(), layers[2].tobytes()
        changed = sum(a != b for a, b in zip(before, after))
        rec = {'text': text, 'offset': hex(offset), 'width': width, 'changed_pixels': changed,
               'compressed_bytes': [item[1] for item in decoded], 'original_capacity': original_size,
               'final_capacity': capacity, 'final_offset': hex(resolve_sprite_offset(roms[2], offset)),
               'index_counts_after': {str(i): after.count(i) for i in sorted(set(after))},
               'layer_sha256': [hashlib.sha256(layer.tobytes()).hexdigest() for layer in layers],
               'bounds': [layer.getbbox() for layer in layers]}
        permitted = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14}
        if not set(after) <= permitted:
            raise AssertionError(f'indices not used by original sprite: {offset:#x}')
        report.append(rec)
        rec['runtime_observations'] = [
            {'capture': state['name'], **observed} for state in manifests[2]['states']
            for observed in state['observed_sprites'] if observed['source'] == hex(offset)
        ]
        for bank in ((9, 8, 10) if width == 128 else (4,)):
            pal = [th.bgr555_to_rgb(v) for v in struct.unpack_from('<16H', palettes, 512 + bank * 32)]
            row = Image.new('RGB', (1230, 160), (231, 234, 237))
            draw = ImageDraw.Draw(row)
            draw.text((8, 4), f'{text} / {offset:#010x} / OBJ {bank} / 변경 {changed}px', font=font(), fill='black')
            for col, layer in enumerate(layers):
                image = colorize(layer, pal)
                row.paste(image, (col * 410 + 8, 28), image)
                zoom = image.resize((width * 3, 96), Image.Resampling.NEAREST)
                row.paste(zoom, (col * 410 + 8, 62), zoom)
            (asset_rows if bank in (9, 4) else variant_rows).append(row)
    if len(roms[1]) != len(roms[2]):
        raise AssertionError('ROM size changed')
    unexpected = [i for i, (a, b) in enumerate(zip(roms[1], roms[2]))
                  if a != b and not any(lo <= i < hi for lo, hi in allowed)]
    if unexpected:
        raise AssertionError(f'changes outside sprite containers: {unexpected[:10]}')
    sheets = write_pages(asset_rows, args.out, 'sprites', 8)
    sheets += write_pages(variant_rows, args.out, 'palette_variants', 8)
    screen_rows = []
    for state in manifests[0]['states']:
        row = Image.new('RGB', (1440, 352), (231, 234, 237))
        ImageDraw.Draw(row).text((8, 5), state['name'], font=font(), fill='black')
        for col, capture in enumerate(captures):
            image = Image.open(capture / (state['name'] + '.png')).convert('RGB')
            if image.size != (240, 160):
                raise AssertionError('invalid screenshot dimensions')
            row.paste(image.resize((480, 320), Image.Resampling.NEAREST), (col * 480, 32))
        screen_rows.append(row)
    sheets += write_pages(screen_rows, args.out, 'ingame', 4)
    result = {'inputs': [{'path': str(path), 'sha256': hashlib.sha256(rom).hexdigest()}
                         for path, rom in zip(paths, roms)],
              'containers': report, 'changed_containers': sum(r['changed_pixels'] > 0 for r in report),
              'palette_capture_sha256': hashlib.sha256(palettes).hexdigest(),
              'outside_declared_sprite_writes': 0, 'runtime_capture_count': len(screen_rows),
              'runtime_observed_containers': sum(bool(r['runtime_observations']) for r in report),
              'runtime_unobserved_containers': [r['offset'] for r in report if not r['runtime_observations']],
              'active_relocations': [hex(off) for off in RELOCATIONS
                                     if resolve_sprite_offset(roms[2], off) != off],
              'menu_font_sha256': hashlib.sha256(th.MENU_FONT_PATH.read_bytes()).hexdigest(),
              'sheets': sheets}
    (args.out / 'report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    markup = '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
    markup += '<title>스프라이트 원본 비교</title><style>body{font:16px sans-serif;margin:24px;background:#f3f4f5;color:#161719}img{display:block;max-width:100%;height:auto;margin:16px 0}a{color:#155a8d}</style>'
    markup += '<h1>스프라이트 원본 비교</h1><p>왼쪽: 원본 · 가운데: 수정 전 · 오른쪽: 수정 후</p>'
    markup += (f'<p>검토 중인 부분 작업: {len(report)}개 컨테이너 중 '
               f'{result["changed_containers"]}개 변경. '
               f'{result["runtime_capture_count"]}개 캡처에서 '
               f'{result["runtime_observed_containers"]}개 자산의 OAM/VRAM 사용을 관측했습니다. '
               '전체 한글화 스프라이트 수정 완료나 전체 화면 검증을 뜻하지 않습니다.</p>')
    markup += '<p>미관측 자산: ' + html.escape(', '.join(result['runtime_unobserved_containers'])) + '</p>'
    if result['active_relocations']:
        markup += '<p>재배치 자산의 포인터 소비와 실제 표시는 아직 미검증입니다.</p>'
    markup += '<p>이 비교본은 배포 승인본이 아닙니다. 작은 제목의 영어는 원본에서 복원했습니다.</p>'
    markup += '<p>자산 시트의 색상 변형은 원본에서 캡처한 팔레트로 재조립한 비교이며, 아래 인게임 시트는 각 ROM의 새 부팅 캡처입니다.</p>'
    markup += ''.join(f'<p>{html.escape(name)}</p><a href="{name}"><img src="{name}" alt="{name}"></a>' for name in sheets)
    (args.out / 'index.html').write_text(markup + '</html>', encoding='utf-8')
    print(json.dumps({'containers': len(report), 'changed': result['changed_containers'], 'sheets': len(sheets)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
