#!/usr/bin/env python3
"""통합 편집기 허브 — 대사/스프라이트 에디터를 하나의 UI에서 메뉴로 전환.

상단 메뉴(대사 편집기 / 스프라이트 에디터) + 섹션 탭(공통/1편/2편/전체)을 제공하고,
선택에 따라 각 에디터를 iframe으로 임베드(?embed=1&section=…)한다. 각 에디터는 section으로
공통/1편/2편 필터 + 인게임 출력 순서 정렬을 적용한다.

실행(에디터 2종이 8780/8781에 떠 있어야 함):
  python3 tools/dialogue_editor/server.py &   # 8780
  python3 tools/sprite_editor/server.py &     # 8781
  python3 tools/editor_hub.py                 # http://127.0.0.1:8782
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SHELL = """<!DOCTYPE html><html lang=ko><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>AW 한글화 편집기</title>
<style>
*{box-sizing:border-box} html,body{margin:0;height:100%;font-family:system-ui,AppleGothic,sans-serif}
body{display:flex;flex-direction:column;background:#15151a;color:#eee}
#bar{display:flex;align-items:center;gap:14px;padding:8px 14px;background:#1f1f27;border-bottom:1px solid #333;flex-wrap:wrap}
#bar .brand{font-weight:700;color:#fff}
#bar .grp{display:flex;gap:4px;align-items:center}
#bar .lbl{color:#89a;font-size:12px;margin-right:2px}
#bar button{background:#2a2a36;color:#ccd;border:1px solid #3a3a48;border-radius:6px;padding:5px 12px;cursor:pointer;font-size:13px}
#bar button.on{background:#3a6ea5;color:#fff;border-color:#4a8ec5}
#bar .sep{width:1px;height:22px;background:#3a3a48}
#bar a{color:#7af;font-size:12px;text-decoration:none;margin-left:auto}
iframe{flex:1;border:0;width:100%;background:#fff}
</style></head><body>
<div id=bar>
  <span class=brand>🎮 AW 한글화 편집기</span>
  <div class=grp><span class=lbl>도구</span>
    <button data-tool=dlg class=on>대사 편집기</button>
    <button data-tool=spr>스프라이트 에디터</button></div>
  <div class=sep></div>
  <div class=grp><span class=lbl>구분</span>
    <button data-sec=all class=on>전체</button>
    <button data-sec=common>공통</button>
    <button data-sec=part1>1편</button>
    <button data-sec=part2>2편</button></div>
  <a href="#" id=open target=_blank>새 탭에서 열기 ↗</a>
</div>
<iframe id=fr></iframe>
<script>
const PORTS={dlg:8780,spr:8781};
const S={tool:'dlg',sec:'all'};
function url(){const h=location.hostname||'127.0.0.1';return `http://${h}:${PORTS[S.tool]}/?embed=1&section=${S.sec}`;}
function load(){const u=url();document.getElementById('fr').src=u;document.getElementById('open').href=u;}
for(const b of document.querySelectorAll('[data-tool]'))b.onclick=()=>{S.tool=b.dataset.tool;
  document.querySelectorAll('[data-tool]').forEach(x=>x.classList.toggle('on',x===b));load();};
for(const b of document.querySelectorAll('[data-sec]'))b.onclick=()=>{S.sec=b.dataset.sec;
  document.querySelectorAll('[data-sec]').forEach(x=>x.classList.toggle('on',x===b));load();};
load();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        body = SHELL.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8782)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"통합 편집기 허브: http://{args.host}:{args.port}  (대사 8780 / 스프라이트 8781 필요)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
