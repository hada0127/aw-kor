#!/usr/bin/env python3
"""Verify every scene and sprite editor path through the live scene editor.

This is intentionally a CDP/browser test, not a data-only audit:
- opens every scene row by scene id
- checks its screenshot provenance state as exposed by the editor API
- selects every sprite in the scene
- verifies the editor renders original/current panes as canvas or image
- writes a JSON report plus screenshots for representative sprite/editor states
"""
from __future__ import annotations

import asyncio
import argparse
import base64
import json
import math
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import websockets


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "temp" / "browser_verify"
REPORT_PATH = OUT / "all_scene_editor_verify.json"
CDP_LIST = os.environ.get("SCENE_EDITOR_CDP_LIST", "http://127.0.0.1:9224/json/list")
BASE_URL = os.environ.get("SCENE_EDITOR_URL", "http://127.0.0.1:8782").rstrip("/")
URL = "%s/?verify=all-scene-editor-%d" % (BASE_URL, int(time.time()))
TARGET_NETLOC = urllib.parse.urlparse(BASE_URL).netloc

CAPTURE_SCENES = {
    "00_coldboot_nintendo",
    "02_select_part1",
    "03_select_part2",
    "10_part1_title",
    "16_part1_info_screen",
    "21a_part2_prologue_story",
    "24a_part2_operation_select",
    "24b_part2_strategic_map_mode4",
    "24_part2_campaign_map",
    "26a_part2_battle_start_overlays",
    "26_part2_battle_labels",
    "29_part2_result_summary",
    "19b2_part1_hoip_landing_setup_story",
    "19e1_part1_unit_info_detail_help",
    "19e7_part1_hoip_co_weather_help",
    "30g1_part2_green_earth_volcano_sortie_story",
}


class CDP:
    def __init__(self, ws):
        self.ws = ws
        self.seq = 0

    async def call(self, method, params=None):
        self.seq += 1
        msg_id = self.seq
        await self.ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(await self.ws.recv())
            if msg.get("id") == msg_id:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})


def first_page_ws() -> str:
    targets = json.load(urllib.request.urlopen(CDP_LIST, timeout=5))
    for t in targets:
        if t.get("type") == "page" and TARGET_NETLOC in (t.get("url") or ""):
            return t["webSocketDebuggerUrl"]
    for t in targets:
        if t.get("type") == "page":
            return t["webSocketDebuggerUrl"]
    raise SystemExit("no Chrome page target on %s" % CDP_LIST)


async def eval_expr(cdp: CDP, expression: str, await_promise: bool = True, timeout_s: int = 30):
    res = await asyncio.wait_for(
        cdp.call(
            "Runtime.evaluate",
            {
                "expression": expression,
                "awaitPromise": await_promise,
                "returnByValue": True,
            },
        ),
        timeout=timeout_s,
    )
    if "exceptionDetails" in res:
        raise RuntimeError(json.dumps(res["exceptionDetails"], ensure_ascii=False))
    return res.get("result", {}).get("value")


async def wait_ready(cdp: CDP):
    for _ in range(120):
        ok = await eval_expr(
            cdp,
            "document.readyState !== 'loading' && !!document.querySelector('#scenelist') && typeof loadScenes === 'function'",
            False,
        )
        if ok:
            return
        await asyncio.sleep(0.1)
    raise TimeoutError("scene editor did not become ready")


async def wait_document(cdp: CDP):
    for _ in range(120):
        ok = await eval_expr(cdp, "document.readyState !== 'loading'", False)
        if ok:
            return
        await asyncio.sleep(0.1)
    raise TimeoutError("document did not finish loading")


async def login_if_needed(cdp: CDP, password: str):
    if not password:
        return
    await wait_document(cdp)
    ok = await eval_expr(
        cdp,
        """
        (async (password) => {
          const res = await fetch('/api/login', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({password})
          });
          if (!res.ok) return {ok:false, status:res.status, text:(await res.text()).slice(0,200)};
          const data = await res.json();
          return {ok: !!data.ok, status: res.status};
        })(%s)
        """ % json.dumps(password),
    )
    if not ok or not ok.get("ok"):
        raise RuntimeError("scene editor login failed: %r" % (ok,))
    await cdp.call("Page.navigate", {"url": URL})


async def browser_auth_status(cdp: CDP) -> dict:
    return await eval_expr(
        cdp,
        """
        (async () => {
          const res = await fetch('/api/auth/status', {credentials: 'same-origin'});
          if (!res.ok) return {ok:false, status:res.status, text:(await res.text()).slice(0,200)};
          return await res.json();
        })()
        """,
    )


def safe_name(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text)[:120]


async def screenshot(cdp: CDP, name: str):
    res = await cdp.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
    (OUT / f"{safe_name(name)}.png").write_bytes(base64.b64decode(res["data"]))


def write_report(report: dict):
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def app_scene_ids(cdp: CDP):
    return await eval_expr(
        cdp,
        """
        (async () => {
          S.scope = 'all';
          const q = document.querySelector('#q');
          if (q) q.value = '';
          await loadScenes();
          await new Promise(r => setTimeout(r, 150));
          for (let i = 0; i < 120; i++) {{
            const imgs = [...document.querySelectorAll('#editor img')];
            if (!imgs.length || imgs.every(img => img.complete && img.naturalWidth > 0 && img.naturalHeight > 0)) break;
            await new Promise(r => setTimeout(r, 100));
          }}
          return S.scenes.map(s => ({
            id: s.id,
            title: s.title,
            scope: s.scope,
            scene_role: s.scene_role || 'screen',
            counts: s.counts || {}
          }));
        })()
        """,
    )


async def open_scene(cdp: CDP, scene_id: str):
    return await eval_expr(
        cdp,
        f"""
        (async () => {{
          const sceneId = {json.dumps(scene_id)};
          if (!S.scenes || !S.scenes.length) await loadScenes();
          const scene = S.scenes.find(s => s.id === sceneId);
          if (!scene) throw new Error('scene not found: ' + sceneId);
          let row = document.querySelector(`#scenelist .scene-row[data-scene-id="${{sceneId}}"]`);
          if (!row) {{
            const idx = S.scenes.findIndex(s => s.id === sceneId);
            row = [...document.querySelectorAll('#scenelist .scene-row')][idx];
          }}
          if (!row) throw new Error('scene row not found: ' + sceneId);
          if (S.scene !== sceneId) {{
            await toggleScene(scene, row);
          }}
          for (let i = 0; i < 80; i++) {{
            if (S.scene === sceneId && S.items && S.items.id === sceneId) break;
            await new Promise(r => setTimeout(r, 100));
          }}
          if (S.scene !== sceneId || !S.items || S.items.id !== sceneId) {{
            throw new Error('scene open race: wanted ' + sceneId + ' got ' + S.scene);
          }}
          return {{
            id: sceneId,
            title: S.items.title,
            rowSceneId: row.dataset.sceneId || null,
            dialogue: S.items.dialogue.length,
            sprites: S.items.sprites.map(sp => ({{
              id: sp.id,
              desc: sp.desc,
              type: sp.type,
              has_onscreen: !!sp.has_onscreen,
            }})),
            screenshot: S.items.screenshot || {{}},
            extraScreenshots: S.items.extra_screenshots || [],
            editorText: (document.querySelector('#editor')?.innerText || '').slice(0, 600),
          }};
        }})()
        """,
    )


async def select_sprite(cdp: CDP, scene_id: str, sprite_id: str):
    return await eval_expr(
        cdp,
        f"""
        (async () => {{
          const sceneId = {json.dumps(scene_id)};
          const spriteId = {json.dumps(sprite_id)};
          if (S.scene !== sceneId || !S.items || S.items.id !== sceneId) {{
            throw new Error('scene not open before sprite select: ' + sceneId);
          }}
          let row = document.querySelector(`#scenelist .scene-row[data-scene-id="${{sceneId}}"]`);
          if (!row) throw new Error('scene row missing while selecting sprite: ' + sceneId);
          let idx = S.items.sprites.findIndex(sp => sp.id === spriteId);
          if (idx < 0) throw new Error('sprite not in open scene: ' + spriteId);
          let itemRow = row.querySelector(`.scene-items .row[data-kind="s"][data-i="${{idx}}"]`);
          if (!itemRow) {{
            S._limit = Math.max(S._limit || 0, S.items.sprites.length + S.items.dialogue.length + 10);
            renderSceneItems(row.querySelector('.scene-items'));
            itemRow = row.querySelector(`.scene-items .row[data-kind="s"][data-i="${{idx}}"]`);
          }}
          if (!itemRow) throw new Error('sprite row not rendered: ' + spriteId);
          await selectSprite(idx, itemRow);
          for (let i = 0; i < 120; i++) {{
            if (SP.id === spriteId && document.querySelector('#editor')) break;
            await new Promise(r => setTimeout(r, 100));
          }}
          if (SP.id !== spriteId) throw new Error('sprite select race: wanted ' + spriteId + ' got ' + SP.id);
          for (let i = 0; i < 120; i++) {{
            const imgs = [...document.querySelectorAll('#editor img')];
            if (!imgs.length || imgs.every(img => img.complete && img.naturalWidth > 0 && img.naturalHeight > 0)) break;
            await new Promise(r => setTimeout(r, 100));
          }}
          await new Promise(r => setTimeout(r, 150));

          function canvasStats(sel) {{
            const c = document.querySelector(sel);
            if (!c || !c.width || !c.height) return null;
            const ctx = c.getContext('2d', {{ willReadFrequently: true }});
            const data = ctx.getImageData(0, 0, c.width, c.height).data;
            const bg = [data[0], data[1], data[2], data[3]].join(',');
            let diff = 0, alpha = 0;
            const unique = new Set();
            for (let p = 0; p < data.length; p += 4) {{
              const key = data[p] + ',' + data[p + 1] + ',' + data[p + 2] + ',' + data[p + 3];
              if (key !== bg) diff++;
              if (data[p + 3]) alpha++;
              if (unique.size < 96) unique.add(key);
            }}
            return {{id: c.id, w: c.width, h: c.height, bg, diffFromTopLeft: diff, alphaPixels: alpha, uniqueColorsCapped: unique.size}};
          }}
          const images = [...document.querySelectorAll('#editor img')].map(img => ({{
            src: img.getAttribute('src') || '',
            complete: img.complete,
            naturalWidth: img.naturalWidth,
            naturalHeight: img.naturalHeight,
          }}));
          const canvases = [canvasStats('#sporigcv'), canvasStats('#spcv')].filter(Boolean);
          const osView = (SP.mode === 'onscreen' && SP.os) ? onscreenViewBox() : null;
          const zoom = SP.mode === 'onscreen' ? SP.osZoom : SP.zoom;
          const dims = document.querySelector('#spDims')?.textContent || '';
          const hint = document.querySelector('#sphint')?.textContent || '';
          const editorText = document.querySelector('#editor')?.innerText || '';
          return {{
            id: spriteId,
            scene: S.scene,
            mode: SP.mode,
            hasOnscreen: !!SP.hasOnscreen,
            readonly: !document.querySelector('#spcv') && images.length >= 2,
            os: SP.os ? {{w: SP.os.w, h: SP.os.h, x0: SP.os.x0, y0: SP.os.y0, cells: SP.os.cells.length, build: !!SP.os.build, screen: !!SP.os.screen}} : null,
            osView,
            zoom,
            dims,
            hint,
            canvases,
            images,
            editorText: editorText.slice(0, 600),
          }};
        }})()
        """,
    )


async def verify_collapse_clears_editor(cdp: CDP, scene_id: str, sprite_id: str):
    return await eval_expr(
        cdp,
        f"""
        (async () => {{
          const sceneId = {json.dumps(scene_id)};
          const spriteId = {json.dumps(sprite_id)};
          const scene = S.scenes.find(s => s.id === sceneId);
          if (!scene) throw new Error('collapse test scene not found: ' + sceneId);
          const row = document.querySelector(`#scenelist .scene-row[data-scene-id="${{sceneId}}"]`);
          if (!row) throw new Error('collapse test row not found: ' + sceneId);
          if (S.scene !== sceneId || !S.items || S.items.id !== sceneId) {{
            await toggleScene(scene, row);
          }}
          for (let i = 0; i < 80; i++) {{
            if (S.scene === sceneId && S.items && S.items.id === sceneId) break;
            await new Promise(r => setTimeout(r, 100));
          }}
          const idx = S.items.sprites.findIndex(sp => sp.id === spriteId);
          if (idx < 0) throw new Error('collapse test sprite not found: ' + spriteId);
          let itemRow = row.querySelector(`.scene-items .row[data-kind="s"][data-i="${{idx}}"]`);
          if (!itemRow) {{
            S._limit = Math.max(S._limit || 0, S.items.sprites.length + S.items.dialogue.length + 10);
            renderSceneItems(row.querySelector('.scene-items'));
            itemRow = row.querySelector(`.scene-items .row[data-kind="s"][data-i="${{idx}}"]`);
          }}
          await selectSprite(idx, itemRow);
          for (let i = 0; i < 120; i++) {{
            if (SP.id === spriteId) break;
            await new Promise(r => setTimeout(r, 100));
          }}
          await toggleScene(scene, row);
          await new Promise(r => setTimeout(r, 100));
          const editorText = document.querySelector('#editor')?.innerText || '';
          return {{
            scene: S.scene,
            hasItems: !!S.items,
            item: S.item,
            spId: SP.id,
            openHeads: document.querySelectorAll('#scenelist .scene-head.open').length,
            hasSpriteCanvas: !!document.querySelector('#spcv') || !!document.querySelector('#sporigcv'),
            hasSpritePanelText: /스프라이트 (편집|확인)/.test(editorText),
            editorText: editorText.slice(0, 400),
          }};
        }})()
        """,
    )


async def main():
    global OUT, REPORT_PATH, CDP_LIST, BASE_URL, URL, TARGET_NETLOC
    parser = argparse.ArgumentParser(description="Verify scene editor scenes/sprites through Chrome CDP")
    parser.add_argument("--url", default=BASE_URL, help="scene editor URL, e.g. http://127.0.0.1:8793")
    parser.add_argument("--cdp-list", default=CDP_LIST, help="Chrome CDP /json/list URL")
    parser.add_argument("--password", default=os.environ.get("SCENE_EDITOR_PASSWORD", ""), help="scene editor password")
    parser.add_argument("--out-dir", default=str(OUT), help="output directory for report/screenshots")
    args = parser.parse_args()
    OUT = Path(args.out_dir)
    REPORT_PATH = OUT / "all_scene_editor_verify.json"
    CDP_LIST = args.cdp_list
    BASE_URL = args.url.rstrip("/")
    URL = "%s/?verify=all-scene-editor-%d" % (BASE_URL, int(time.time()))
    TARGET_NETLOC = urllib.parse.urlparse(BASE_URL).netloc

    OUT.mkdir(parents=True, exist_ok=True)
    async with websockets.connect(first_page_ws(), max_size=64 * 1024 * 1024) as ws:
        cdp = CDP(ws)
        await cdp.call("Page.enable")
        await cdp.call("Runtime.enable")
        await cdp.call(
            "Emulation.setDeviceMetricsOverride",
            {"width": 1520, "height": 980, "deviceScaleFactor": 1, "mobile": False},
        )
        await cdp.call("Network.setCacheDisabled", {"cacheDisabled": True})
        await cdp.call("Page.navigate", {"url": URL})
        await login_if_needed(cdp, args.password)
        await wait_document(cdp)
        auth_status = await browser_auth_status(cdp)
        if args.password and not auth_status.get("auth_required"):
            raise RuntimeError("password was provided but auth_required=false: %r" % (auth_status,))
        if auth_status.get("auth_required") and not auth_status.get("authenticated"):
            raise RuntimeError("scene editor is not authenticated: %r" % (auth_status,))
        await wait_ready(cdp)
        scenes = await app_scene_ids(cdp)
        game_scenes = [
            s for s in scenes
            if not str(s["id"]).startswith(("98_", "99_")) and s.get("scope") != "review"
            and s.get("scene_role") != "container"
        ]
        review_scenes = [s for s in scenes if s not in game_scenes]
        report = {
            "url": URL,
            "complete": False,
            "total_scene_count": len(scenes),
            "scene_count": len(game_scenes),
            "sprite_count": 0,
            "review_scenes": review_scenes,
            "scenes": [],
            "failures": [],
            "auth_status": auth_status,
        }
        state_dom = await eval_expr(
            cdp,
            """
            (async () => {
              await refreshState();
              return {
                state: document.querySelector('#state')?.innerText || '',
                applyNeed: document.querySelector('#apply')?.classList.contains('need') || false,
                downloadDisabled: document.querySelector('#download')?.disabled || false,
                downloadTitle: document.querySelector('#download')?.title || '',
              };
            })()
            """,
        )
        report["state_dom"] = state_dom
        state_text = state_dom.get("state") or ""
        if "ROM " not in state_text or "적용됨" not in state_text or "output SHA 검증" not in state_text:
            report["failures"].append({"kind": "state_dom_unexpected", "state": state_dom})
        if state_dom.get("applyNeed"):
            report["failures"].append({"kind": "apply_button_unexpected_need", "state": state_dom})
        if state_dom.get("downloadDisabled"):
            report["failures"].append({"kind": "download_unexpected_disabled", "state": state_dom})
        write_report(report)
        for pos, scene in enumerate(game_scenes, 1):
            sid = scene["id"]
            try:
                state = await open_scene(cdp, sid)
                print(f"[{pos:02d}/{len(game_scenes):02d}] {sid} d={state.get('dialogue')} s={len(state.get('sprites') or [])}", flush=True)
                shot = state.get("screenshot") or {}
                if not shot.get("exists"):
                    report["failures"].append({"scene": sid, "kind": "missing_screenshot", "checkpoint": shot.get("checkpoint")})
                if shot.get("stale") is True:
                    report["failures"].append({"scene": sid, "kind": "stale_screenshot", "checkpoint": shot.get("checkpoint")})
                if state.get("rowSceneId") not in (None, sid):
                    report["failures"].append({"scene": sid, "kind": "row_mismatch", "row": state.get("rowSceneId")})
                if not state.get("sprites") and any(token in (state.get("editorText") or "") for token in ("스프라이트 편집", "스프라이트 확인")):
                    report["failures"].append({"scene": sid, "kind": "stale_sprite_editor_panel", "editorText": state.get("editorText")})
                if sid in CAPTURE_SCENES:
                    await screenshot(cdp, f"scene_{sid}")

                sprite_states = []
                for sp in state.get("sprites", []):
                    report["sprite_count"] += 1
                    try:
                        sp_state = await select_sprite(cdp, sid, sp["id"])
                        sprite_states.append(sp_state)
                        if sp_state.get("readonly"):
                            bad_imgs = [img for img in sp_state.get("images", []) if not img.get("complete") or not img.get("naturalWidth")]
                            if bad_imgs:
                                report["failures"].append({"scene": sid, "sprite": sp["id"], "kind": "readonly_image_not_loaded", "images": bad_imgs})
                        else:
                            cvs = {c["id"]: c for c in sp_state.get("canvases", [])}
                            for cid in ("sporigcv", "spcv"):
                                c = cvs.get(cid)
                                if not c:
                                    report["failures"].append({"scene": sid, "sprite": sp["id"], "kind": "missing_canvas", "canvas": cid})
                                elif c["w"] <= 0 or c["h"] <= 0 or c["diffFromTopLeft"] <= 0:
                                    report["failures"].append({"scene": sid, "sprite": sp["id"], "kind": "blank_canvas", "canvas": cid, "stats": c})
                            if sp.get("has_onscreen") and sp_state.get("mode") != "onscreen":
                                report["failures"].append({"scene": sid, "sprite": sp["id"], "kind": "onscreen_not_default", "mode": sp_state.get("mode")})
                            if sp.get("has_onscreen") and sp_state.get("mode") == "onscreen" and not sp_state.get("readonly"):
                                os_data = sp_state.get("os") or {}
                                os_view = sp_state.get("osView") or {}
                                zoom = max(1, int(sp_state.get("zoom") or 1))
                                expected_w = max(1, math.ceil(float(os_data.get("w") or 1)))
                                expected_h = max(1, math.ceil(float(os_data.get("h") or 1)))
                                view_w = int(os_view.get("w") or 0)
                                view_h = int(os_view.get("h") or 0)
                                if view_w != expected_w or view_h != expected_h:
                                    report["failures"].append({
                                        "scene": sid,
                                        "sprite": sp["id"],
                                        "kind": "onscreen_viewbox_not_layout",
                                        "expected": {"w": expected_w, "h": expected_h},
                                        "actual": os_view,
                                    })
                                for cid in ("sporigcv", "spcv"):
                                    c = cvs.get(cid)
                                    if c and (c["w"] != expected_w * zoom or c["h"] != expected_h * zoom):
                                        report["failures"].append({
                                            "scene": sid,
                                            "sprite": sp["id"],
                                            "kind": "onscreen_canvas_size_mismatch",
                                            "canvas": cid,
                                            "expected": {"w": expected_w * zoom, "h": expected_h * zoom, "zoom": zoom},
                                            "actual": {"w": c["w"], "h": c["h"]},
                                            "os": os_data,
                                            "view": os_view,
                                        })
                        if sid in CAPTURE_SCENES:
                            await screenshot(cdp, f"sprite_{sid}_{sp['id']}")
                    except Exception as exc:
                        report["failures"].append({"scene": sid, "sprite": sp["id"], "kind": "sprite_exception", "error": str(exc)})
                state["sprite_states"] = sprite_states
                report["scenes"].append(state)
            except Exception as exc:
                report["failures"].append({"scene": sid, "kind": "scene_exception", "error": str(exc)})
            write_report(report)

        collapse_candidate = next(
            (
                (scene["id"], len(scene.get("sprites") or []))
                for scene in report["scenes"]
                if scene.get("sprites")
            ),
            None,
        )
        if collapse_candidate:
            sid = collapse_candidate[0]
            try:
                state = await open_scene(cdp, sid)
                sprite_id = state["sprites"][0]["id"]
                collapsed = await verify_collapse_clears_editor(cdp, sid, sprite_id)
                report["collapse_regression"] = {"scene": sid, "sprite": sprite_id, **collapsed}
                if collapsed.get("scene") is not None or collapsed.get("hasItems") or collapsed.get("item") is not None:
                    report["failures"].append({"scene": sid, "sprite": sprite_id, "kind": "collapse_state_not_cleared", "state": collapsed})
                if collapsed.get("spId") is not None or collapsed.get("openHeads") != 0:
                    report["failures"].append({"scene": sid, "sprite": sprite_id, "kind": "collapse_selection_not_cleared", "state": collapsed})
                if collapsed.get("hasSpriteCanvas") or collapsed.get("hasSpritePanelText"):
                    report["failures"].append({"scene": sid, "sprite": sprite_id, "kind": "collapse_stale_sprite_editor", "state": collapsed})
            except Exception as exc:
                report["failures"].append({"scene": sid, "kind": "collapse_regression_exception", "error": str(exc)})
        else:
            report["failures"].append({"kind": "collapse_regression_no_sprite_candidate"})

        report["complete"] = True
        write_report(report)
        print(json.dumps({
            "scene_count": report["scene_count"],
            "sprite_count": report["sprite_count"],
            "failure_count": len(report["failures"]),
            "report": str(REPORT_PATH),
            "first_failures": report["failures"][:20],
        }, ensure_ascii=False, indent=2))
        return 1 if report["failures"] else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
