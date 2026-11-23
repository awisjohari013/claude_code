#!/usr/bin/env python3
"""Pelayan simulasi: cuba website di komputer TANPA board ESP.

    python3 tools/mock_server.py      ->  buka http://localhost:8080

API yang sama seperti firmware sebenar, tetapi isyarat IR hanya dicetak ke terminal.
"""
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRANDS = ["COOLIX", "DAIKIN", "GREE", "HAIER_AC", "HITACHI_AC", "LG", "MIDEA",
          "MITSUBISHI_AC", "PANASONIC_AC", "SAMSUNG_AC", "SHARP_AC", "TCL112AC",
          "TOSHIBA_AC", "CARRIER_AC64"]
MODES = ["auto", "cool", "dry", "fan", "heat"]
FANS = ["auto", "low", "medium", "high"]

state = {"power": False, "mode": "cool", "temp": 24, "fan": "auto", "swing": False,
         "turbo": False, "econo": False, "brand": "DAIKIN", "model": 1}
off_at = 0.0


def snapshot(ir_ok=True):
    global off_at
    if off_at and time.time() >= off_at:
        off_at = 0
        state["power"] = False
        print("[IR] pemasa tamat -> power=False")
    timer = int((off_at - time.time()) // 60) + 1 if off_at else 0
    return {**state, "timer": timer, "irOk": ir_ok}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/":
            with open(os.path.join(ROOT, "web", "index.html"), "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")
        elif self.path == "/api/state":
            self._send(200, snapshot())
        elif self.path == "/api/brands":
            self._send(200, BRANDS)
        else:
            self._send(404, {"error": "Tidak dijumpai"})

    def do_POST(self):
        global off_at
        if self.path != "/api/state":
            return self._send(404, {"error": "Tidak dijumpai"})
        try:
            p = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, {"error": "JSON tidak sah"})
        for k in ("power", "swing", "turbo", "econo"):
            if isinstance(p.get(k), bool):
                state[k] = p[k]
        if isinstance(p.get("temp"), int):
            state["temp"] = max(16, min(30, p["temp"]))
        if p.get("mode") in MODES:
            state["mode"] = p["mode"]
        if p.get("fan") in FANS:
            state["fan"] = p["fan"]
        if p.get("brand") in BRANDS:
            state["brand"] = p["brand"]
        if isinstance(p.get("model"), int):
            state["model"] = p["model"]
        if isinstance(p.get("timer"), int):
            m = max(0, min(1440, p["timer"]))
            off_at = time.time() + m * 60 if m else 0
        if not state["power"]:
            off_at = 0
        if p.get("send", True):
            print("[IR]", {k: state[k] for k in ("brand", "power", "mode", "temp", "fan", "swing")})
        self._send(200, snapshot())

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print("Simulasi berjalan: http://localhost:8080  (Ctrl+C untuk berhenti)")
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
