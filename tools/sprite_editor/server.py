#!/usr/bin/env python3
"""스프라이트 픽셀아트 에디터 — 경량 웹도구 (stdlib http.server + PIL).

GBA 저해상도(8×8 4bpp 타일)에 맞춘 픽셀 단위 편집기. muramasa ui_editor의
서버 스캐폴드를 따르되 프론트엔드는 확대 캔버스 + 팔레트 스와치 픽셀 페인트.

실행:
  python3 tools/sprite_editor/server.py            # http://127.0.0.1:8781

데이터:
  data/sprites_index.json   {sprites:[{id,offset,type,width,height,palette_guess,png,source,...}]}
  temp/sprites_png/<id>.png  원본 렌더(인덱스 생성 시 export_sprites.py가 생성)
  data/sprite_edits/<id>.png 편집본(저장 시)
  data/sprites_overrides.json {id:{offset,type,width,height,edited_png}}  빌드 역기록용 기록

API
  GET  /api/sprites?type=&source=&q=&curated=     인덱스(필터)
  GET  /api/png?id=<id>                           원본(or 편집본) PNG
  GET  /api/png?id=<id>&orig=1                     항상 원본 PNG
  POST /api/save  {id, png_b64}                    편집 PNG 저장 + overrides 기록
  POST /api/revert {id}                            편집 되돌리기(편집본 삭제)
"""
import argparse
import base64
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).resolve().parent / "static"
INDEX_PATH = ROOT / "data" / "sprites_index.json"
ORIG_PNG_DIR = ROOT / "temp" / "sprites_png"
EDIT_DIR = ROOT / "data" / "sprite_edits"
OVERRIDES_PATH = ROOT / "data" / "sprites_overrides.json"

_LOCK = threading.Lock()
MIME = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8", ".png": "image/png", ".json": "application/json; charset=utf-8"}


def load_json(path, default=None):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def save_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sprite_list():
    d = load_json(INDEX_PATH, {"sprites": []})
    return d.get("sprites", []) if isinstance(d, dict) else d


def png_for(sid, orig=False):
    """편집본 우선(없거나 orig=True면 원본). (data, found)."""
    if not orig:
        ep = EDIT_DIR / f"{sid}.png"
        if ep.exists():
            return ep.read_bytes(), True
    # index의 png 경로 우선, 없으면 temp/sprites_png/<id>.png
    sp = next((s for s in sprite_list() if s.get("id") == sid), None)
    if sp and sp.get("png"):
        p = ROOT / sp["png"]
        if p.exists():
            return p.read_bytes(), True
    p = ORIG_PNG_DIR / f"{sid}.png"
    if p.exists():
        return p.read_bytes(), True
    return b"", False


# --- 인덱스(4bpp) 기반 편집: ROM 바이트 → 팔레트 인덱스 그리드 ---
import sys as _sys
import struct as _struct
if str(ROOT / "tools") not in _sys.path:
    _sys.path.insert(0, str(ROOT / "tools"))
import export_sprites as ES  # noqa: E402  lz77_decompress, tiles_to_indices, GRAYSCALE, read_palette, guess_cols, TILE_BYTES

ROM_PATH = ROOT / "original" / "Game Boy Wars Advance 1+2 (Japan).gba"
_ROM = None


def rom_bytes():
    global _ROM
    if _ROM is None:
        _ROM = ROM_PATH.read_bytes() if ROM_PATH.exists() else b""
    return _ROM


def sprite_by_id(sid):
    return next((s for s in sprite_list() if s.get("id") == sid), None)


def decode_indices(sp):
    """sprite 레코드 → (grid[h][w] 0..15, w, h, tile_cols). 실패 시 None."""
    rom = rom_bytes()
    off = sp.get("offset_int")
    if off is None:
        off = int(sp.get("offset", "0x0"), 16)
    typ = sp.get("type")
    if typ == "lz77":
        res = ES.lz77_decompress(rom, off)
        if not res:
            return None
        tile_data = res[0]
    else:
        tile_data = rom[off: off + (sp.get("size") or 0)]
    n = len(tile_data) // ES.TILE_BYTES
    if n == 0:
        return None
    cols = sp.get("tile_cols") or ES.guess_cols(n)
    grid, w, h = ES.tiles_to_indices(tile_data, cols)
    return grid, w, h, cols


def encode_indices(grid, w, h):
    """index grid(h×w, 0..15) → 4bpp 타일 바이트(8×8 타일, cols=w//8)."""
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


def palette_for(sp):
    """편집/표시용 16색 팔레트. overrides에 저장된 게 있으면 사용, 없으면 grayscale."""
    ov = load_json(OVERRIDES_PATH, {}) or {}
    rec = ov.get(sp.get("id"))
    if rec and rec.get("palette"):
        return rec["palette"]
    return [list(c) for c in ES.GRAYSCALE]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if u.path in ("/", "/index.html"):
            return self._static("index.html")
        if u.path.startswith("/static/"):
            return self._static(u.path[len("/static/"):])
        if u.path == "/api/sprites":
            return self._send(200, self._sprites(q))
        if u.path == "/api/png":
            sid = q.get("id", [""])[0]
            data, ok = png_for(sid, orig=q.get("orig", ["0"])[0] == "1")
            if not ok:
                return self._send(404, {"error": "no png for " + sid})
            return self._send(200, data, "image/png")
        if u.path == "/api/tile":
            return self._send(200, self._tile(q))
        return self._send(404, {"error": "not found"})

    def _static(self, rel):
        path = (STATIC / rel)
        if not path.exists():
            return self._send(404, {"error": "missing " + rel})
        self._send(200, path.read_bytes(), MIME.get(path.suffix, "application/octet-stream"))

    def _sprites(self, q):
        sprites = sprite_list()
        typ = (q.get("type", [""])[0] or "").strip()
        src = (q.get("source", [""])[0] or "").strip()
        qs = (q.get("q", [""])[0] or "").strip()
        cur = (q.get("curated", [""])[0] or "").strip()
        edited = {p.stem for p in EDIT_DIR.glob("*.png")} if EDIT_DIR.exists() else set()
        out = []
        for s in sprites:
            if typ and s.get("type") != typ:
                continue
            if cur == "1" and not s.get("curated"):
                continue
            if src and src not in (s.get("source") or ""):
                continue
            if qs and qs not in (s.get("id") or "") and qs not in (s.get("source") or "") and qs not in (s.get("offset") or ""):
                continue
            out.append({**s, "edited": s.get("id") in edited})
        types = sorted({s.get("type", "") for s in sprites})
        return {"count": len(out), "total": len(sprites), "types": types,
                "edited_count": len(edited), "sprites": out[:3000]}

    def _tile(self, q):
        sid = q.get("id", [""])[0]
        sp = sprite_by_id(sid)
        if sp is None:
            return {"ok": False, "error": "id 없음: %s" % sid}
        # 편집본(인덱스) 우선
        ov = load_json(OVERRIDES_PATH, {}) or {}
        rec = ov.get(sid)
        if rec and rec.get("indices"):
            grid = rec["indices"]
            h = len(grid); w = len(grid[0]) if grid else 0
            return {"ok": True, "id": sid, "width": w, "height": h,
                    "tile_cols": w // 8, "type": sp.get("type"),
                    "palette": palette_for(sp), "indices": grid, "edited": True,
                    "offset": sp.get("offset"), "source": sp.get("source")}
        dec = decode_indices(sp)
        if dec is None:
            return {"ok": False, "error": "디코드 실패(타입 %s)" % sp.get("type")}
        grid, w, h, cols = dec
        return {"ok": True, "id": sid, "width": w, "height": h, "tile_cols": cols,
                "type": sp.get("type"), "palette": palette_for(sp), "indices": grid,
                "edited": False, "offset": sp.get("offset"), "source": sp.get("source")}

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        try:
            body = self._body()
        except Exception as e:
            return self._send(400, {"error": "bad json: %r" % e})
        if u.path == "/api/save":
            return self._send(200, self._save(body))
        if u.path == "/api/revert":
            return self._send(200, self._revert(body))
        return self._send(404, {"error": "not found"})

    def _save(self, body):
        sid = body.get("id")
        indices = body.get("indices")
        palette = body.get("palette")
        sp = sprite_by_id(sid)
        if sp is None:
            return {"ok": False, "error": "id 없음: %s" % sid}
        if not indices or not isinstance(indices, list) or not indices[0]:
            return {"ok": False, "error": "indices(2D 0..15) 필요"}
        h = len(indices)
        w = len(indices[0])
        try:
            enc = encode_indices(indices, w, h)
        except Exception as e:
            return {"ok": False, "error": "encode: %r" % e}
        if sp.get("type") == "lz77":
            fits = (len(enc) == sp.get("size"))  # 타일수 동일해야 함(압축적합은 apply에서)
        else:
            fits = (len(enc) <= (sp.get("size") or len(enc)))
        with _LOCK:
            ov = load_json(OVERRIDES_PATH, {}) or {}
            ov[sid] = {"offset": sp.get("offset"), "type": sp.get("type"),
                       "width": w, "height": h, "indices": indices, "palette": palette,
                       "raw_len": len(enc), "orig_size": sp.get("size"),
                       "comp_size": sp.get("comp_size"), "fits_raw": fits}
            save_json(OVERRIDES_PATH, ov)
            try:
                EDIT_DIR.mkdir(parents=True, exist_ok=True)
                pal = [tuple(c) for c in (palette or [list(c) for c in ES.GRAYSCALE])]
                ES.render_png(indices, w, h, pal, str(EDIT_DIR / f"{sid}.png"), scale=2)
            except Exception:
                pass
        return {"ok": True, "id": sid, "raw_len": len(enc), "orig_size": sp.get("size"),
                "fits_raw": fits,
                "note": "편집 저장됨. ROM 역기록은 tools/apply_sprite_edits.py (타입 %s, lz77은 재압축 ≤comp_size 검증)." % sp.get("type")}

    def _revert(self, body):
        sid = body.get("id")
        with _LOCK:
            ep = EDIT_DIR / f"{sid}.png"
            if ep.exists():
                ep.unlink()
            ov = load_json(OVERRIDES_PATH, {})
            ov.pop(sid, None)
            save_json(OVERRIDES_PATH, ov)
        return {"ok": True, "id": sid}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8781)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"스프라이트 픽셀 에디터: http://{args.host}:{args.port}  (Ctrl+C 종료)")
    print(f"  index: {INDEX_PATH}  edits: {EDIT_DIR}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
