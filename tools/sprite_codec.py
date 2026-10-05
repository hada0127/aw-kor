"""Strict 4bpp tile encoding shared by editors and the ROM builder."""

def encode_indices(grid, w, h):
    """index grid(h×w, 0..15) → 4bpp 타일 바이트(8×8 타일, cols=w//8)."""
    if type(w) is not int or type(h) is not int or w <= 0 or h <= 0 or w % 8 or h % 8:
        raise ValueError("픽셀 크기는 양수이며 8의 배수여야 합니다")
    if not isinstance(grid, list) or len(grid) != h or any(
        not isinstance(row, list) or len(row) != w for row in grid
    ):
        raise ValueError("픽셀 행 길이가 일치하지 않습니다")
    if any(type(pixel) is not int or not 0 <= pixel <= 15 for row in grid for pixel in row):
        raise ValueError("픽셀 인덱스는 0~15 정수여야 합니다")
    cols = w // 8
    rows = h // 8
    out = bytearray()
    for t in range(cols * rows):
        gx = (t % cols) * 8
        gy = (t // cols) * 8
        for row in range(8):
            for c2 in range(4):
                lo = grid[gy + row][gx + c2 * 2] & 0xF
                hi = grid[gy + row][gx + c2 * 2 + 1] & 0xF
                out.append(lo | (hi << 4))
    return bytes(out)

