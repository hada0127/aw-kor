#!/usr/bin/env python3
"""Verify scene editor apply-needed and output SHA state.

The check is intentionally small and non-content-mutating:
1. The live :8782 server must report the canonical output ROM as current.
2. A clean tree should report apply_needed=false.
3. Temporarily moving an override file mtime past output ROM must make
   apply_needed=true, then restoring mtime must return to clean.
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROM = ROOT / "output" / "game_wars_korean_full.gba"
OVERRIDES = ROOT / "data" / "dialogue_overrides.json"

_HTTP_CLIENTS: dict[str, tuple[urllib.parse.ParseResult, http.client.HTTPConnection]] = {}
_AUTH_COOKIE = ""


def _http_connection(base_url: str) -> tuple[urllib.parse.ParseResult, http.client.HTTPConnection]:
    key = base_url.rstrip("/")
    rec = _HTTP_CLIENTS.get(key)
    if rec is not None:
        return rec
    parsed = urllib.parse.urlparse(key)
    if parsed.scheme != "http" or not parsed.hostname:
        raise ValueError("only http://host[:port] scene editor URLs are supported")
    conn = http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=10)
    rec = (parsed, conn)
    _HTTP_CLIENTS[key] = rec
    return rec


def _close_http_connection(base_url: str) -> None:
    rec = _HTTP_CLIENTS.pop(base_url.rstrip("/"), None)
    if rec is not None:
        rec[1].close()


def api_json(base_url: str, path: str) -> dict:
    last_exc = None
    for attempt in range(2):
        _parsed, conn = _http_connection(base_url)
        try:
            headers = {"Accept": "application/json", "Connection": "keep-alive"}
            if _AUTH_COOKIE:
                headers["Cookie"] = _AUTH_COOKIE
            conn.request("GET", path, headers=headers)
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
    raise AssertionError(f"unreachable api_json failure: {last_exc!r}")


def login(base_url: str, password: str) -> None:
    global _AUTH_COOKIE
    body = json.dumps({"password": password}, ensure_ascii=False).encode("utf-8")
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
    payload = json.loads(data.decode("utf-8"))
    require(bool(payload.get("ok")), "login response was not ok")


def wait_state(base_url: str, expected_apply_needed: bool, timeout_s: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout_s
    last = None
    while time.monotonic() < deadline:
        last = api_json(base_url, "/api/state")
        if bool(last.get("apply_needed")) == expected_apply_needed:
            return last
        time.sleep(0.1)
    raise AssertionError(
        "apply_needed did not become %s; last state=%s" %
        (expected_apply_needed, json.dumps(last, ensure_ascii=False))
    )


def stat_ns(path: Path) -> tuple[int, int]:
    st = path.stat()
    return st.st_atime_ns, st.st_mtime_ns


def require(cond: bool, message: str) -> None:
    if not cond:
        raise AssertionError(message)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="http://127.0.0.1:8782")
    ap.add_argument("--password", default=os.environ.get("SCENE_EDITOR_PASSWORD"),
                    help="scene editor password; defaults to SCENE_EDITOR_PASSWORD")
    args = ap.parse_args()

    if args.password:
        login(args.server, args.password)

    require(OUTPUT_ROM.exists(), f"missing output ROM: {OUTPUT_ROM}")
    require(OVERRIDES.exists(), f"missing overrides: {OVERRIDES}")

    old_times = stat_ns(OVERRIDES)
    future_ns = None
    restored_by_script = False
    try:
        clean = wait_state(args.server, False)
        require(clean.get("output_sync", {}).get("ok"), "output SHA sync is not OK")
        require(not clean.get("apply_needed"), "initial state unexpectedly requires apply")

        future_ns = max(time.time_ns(), OUTPUT_ROM.stat().st_mtime_ns) + 5_000_000_000
        os.utime(OVERRIDES, ns=(old_times[0], future_ns))
        dirty = wait_state(args.server, True)
        require(dirty.get("apply_needed"), "override mtime newer than ROM did not require apply")
        require(dirty.get("dirty", {}).get("apply_needed"), "dirty.apply_needed was not set")

    finally:
        if future_ns is not None:
            current_times = stat_ns(OVERRIDES)
            if current_times[1] == future_ns:
                os.utime(OVERRIDES, ns=old_times)
                restored_by_script = True

    require(restored_by_script, "override mtime changed during verification; not restoring over concurrent edit")
    restored = wait_state(args.server, False)
    require(restored.get("output_sync", {}).get("ok"), "output SHA sync failed after restore")
    require(not restored.get("apply_needed"), "apply_needed did not clear after mtime restore")

    print(json.dumps({
        "ok": True,
        "rom_sha256": restored.get("rom", {}).get("full_sha256"),
        "output_sha256": restored.get("output_sync", {}).get("full_sha256"),
        "apply_needed_probe": "passed",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
