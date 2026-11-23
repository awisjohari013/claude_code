#!/usr/bin/env python3
"""Kawalan aircond Samsung (SmartThings) melalui website.

Jalankan:   python3 server.py          ->  buka http://localhost:8080
Simulasi:   ST_FAKE=1 python3 server.py   (tanpa akaun Samsung)

Hanya guna pustaka standard Python 3.8+, tiada pip install diperlukan.
Token SmartThings disimpan di server sahaja dan tidak pernah dihantar ke browser.
"""
import base64
import hmac
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
API = "https://api.smartthings.com/v1"
OAUTH_AUTHORIZE = "https://api.smartthings.com/oauth/authorize"
OAUTH_TOKEN = "https://api.smartthings.com/oauth/token"
SCOPES = "r:devices:* x:devices:*"


# ----------------------------------------------------------------------
#  Konfigurasi (.env atau pemboleh ubah persekitaran)
# ----------------------------------------------------------------------
def load_env(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


load_env(os.path.join(ROOT, ".env"))
env = os.environ.get

HOST = env("HOST", "0.0.0.0")
PORT = int(env("PORT", "8080"))
WEB_USER = env("WEB_USER", "admin")
WEB_PASSWORD = env("WEB_PASSWORD", "")
PAT = env("SMARTTHINGS_TOKEN", "")
CLIENT_ID = env("SMARTTHINGS_CLIENT_ID", "")
CLIENT_SECRET = env("SMARTTHINGS_CLIENT_SECRET", "")
REDIRECT_URI = env("SMARTTHINGS_REDIRECT_URI", "https://httpbin.org/get")
FIXED_DEVICE = env("SMARTTHINGS_DEVICE_ID", "")
FAKE = env("ST_FAKE", "") == "1"
DATA_FILE = env("DATA_FILE", os.path.join(ROOT, "data.json"))


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


# ----------------------------------------------------------------------
#  Simpanan kecil (token OAuth, peranti dipilih, pemasa)
# ----------------------------------------------------------------------
class Store:
    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        try:
            with open(path, encoding="utf-8") as f:
                self.data = json.load(f)
        except (OSError, ValueError):
            self.data = {}

    def get(self, key, default=None):
        with self.lock:
            return self.data.get(key, default)

    def set(self, **kv):
        with self.lock:
            self.data.update(kv)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
            os.replace(tmp, self.path)
            try:
                os.chmod(self.path, 0o600)  # fail ini mengandungi token
            except OSError:
                pass


store = Store(DATA_FILE)


# ----------------------------------------------------------------------
#  Token: OAuth (jangka panjang, auto-refresh) atau PAT (sah 24 jam)
# ----------------------------------------------------------------------
class Tokens:
    lock = threading.Lock()

    @staticmethod
    def oauth_ready():
        return bool(CLIENT_ID and CLIENT_SECRET)

    def mode(self):
        if FAKE:
            return "fake"
        if store.get("oauth"):
            return "oauth"
        if PAT:
            return "pat"
        return "none"

    def authorize_url(self):
        return OAUTH_AUTHORIZE + "?" + urllib.parse.urlencode({
            "client_id": CLIENT_ID, "response_type": "code",
            "redirect_uri": REDIRECT_URI, "scope": SCOPES})

    def _token_request(self, form):
        basic = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
        req = urllib.request.Request(
            OAUTH_TOKEN, data=urllib.parse.urlencode(form).encode(), method="POST",
            headers={"Authorization": "Basic " + basic,
                     "Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                tok = json.load(r)
        except urllib.error.HTTPError as e:
            raise ApiError(e.code, "Token ditolak oleh Samsung: " + e.read().decode(errors="replace")[:300])
        except urllib.error.URLError as e:
            raise ApiError(502, f"Tidak dapat hubungi Samsung: {e.reason}")
        old = store.get("oauth") or {}
        store.set(oauth={
            "access_token": tok["access_token"],
            "refresh_token": tok.get("refresh_token", old.get("refresh_token")),
            "expires_at": time.time() + int(tok.get("expires_in", 86400)),
        })

    def exchange_code(self, code):
        self._token_request({"grant_type": "authorization_code", "code": code,
                             "client_id": CLIENT_ID, "redirect_uri": REDIRECT_URI})

    def refresh(self):
        with self.lock:
            oauth = store.get("oauth")
            if not oauth or not oauth.get("refresh_token"):
                raise ApiError(401, "Tiada refresh token. Log masuk Samsung semula.")
            self._token_request({"grant_type": "refresh_token", "client_id": CLIENT_ID,
                                 "refresh_token": oauth["refresh_token"]})

    def access_token(self):
        mode = self.mode()
        if mode == "oauth":
            if store.get("oauth")["expires_at"] - 300 < time.time():
                self.refresh()
            return store.get("oauth")["access_token"]
        if mode == "pat":
            return PAT
        raise ApiError(401, "SmartThings belum disambung.")


tokens = Tokens()


# ----------------------------------------------------------------------
#  Klien SmartThings API
# ----------------------------------------------------------------------
class SmartThings:
    def request(self, method, path, body=None, retry=True):
        url = path if path.startswith("http") else API + path
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": "Bearer " + tokens.access_token(),
            "Content-Type": "application/json", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                raw = r.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            if e.code == 401 and retry and tokens.mode() == "oauth":
                tokens.refresh()
                return self.request(method, path, body, retry=False)
            detail = e.read().decode(errors="replace")[:300]
            if e.code == 401:
                msg = "Token SmartThings tamat tempoh atau tidak sah."
            elif e.code == 403:
                msg = "Token tiada kebenaran untuk peranti ini."
            else:
                msg = f"Ralat SmartThings {e.code}: {detail}"
            raise ApiError(e.code, msg)
        except urllib.error.URLError as e:
            raise ApiError(502, f"Tidak dapat hubungi SmartThings: {e.reason}")

    def devices(self):
        items, url = [], "/devices"
        while url:
            page = self.request("GET", url)
            items += page.get("items", [])
            url = (page.get("_links") or {}).get("next", {}) or {}
            url = url.get("href") if isinstance(url, dict) else None
        return items

    def status(self, device_id):
        return self.request("GET", f"/devices/{device_id}/status")

    def commands(self, device_id, cmds):
        return self.request("POST", f"/devices/{device_id}/commands", {"commands": cmds})


class FakeSmartThings:
    """Peranti Samsung palsu, untuk mencuba website tanpa akaun."""

    def __init__(self):
        self.s = {"switch": "off", "mode": "cool", "temp": 24, "fan": "auto",
                  "osc": "fixed", "opt": "off", "room": 29.5, "hum": 68}

    def devices(self):
        return [{"deviceId": "fake-ac-1", "label": "Aircond Bilik (simulasi)",
                 "components": [{"id": "main", "capabilities": [{"id": "airConditionerMode"}]}]}]

    def status(self, device_id):
        s = self.s
        if s["switch"] == "on" and s["mode"] == "cool":  # bilik makin sejuk
            s["room"] = round(max(s["temp"], s["room"] - 0.3), 1)
        v = lambda x, **k: {"value": x, **k}
        return {"components": {"main": {
            "switch": {"switch": v(s["switch"])},
            "airConditionerMode": {"airConditionerMode": v(s["mode"]),
                                   "supportedAcModes": v(["auto", "cool", "dry", "wind", "heat"])},
            "thermostatCoolingSetpoint": {"coolingSetpoint": v(s["temp"], unit="C")},
            "airConditionerFanMode": {"fanMode": v(s["fan"]),
                                      "supportedAcFanModes": v(["auto", "low", "medium", "high", "turbo"])},
            "fanOscillationMode": {"fanOscillationMode": v(s["osc"]),
                                   "supportedFanOscillationModes": v(["fixed", "all", "vertical", "horizontal"])},
            "custom.airConditionerOptionalMode": {"acOptionalMode": v(s["opt"]),
                                                  "supportedAcOptionalMode": v(["off", "sleep", "quiet", "speed", "windFree"])},
            "temperatureMeasurement": {"temperature": v(s["room"], unit="C")},
            "relativeHumidityMeasurement": {"humidity": v(s["hum"], unit="%")},
        }}}

    def commands(self, device_id, cmds):
        keys = {"switch": "switch", "setAirConditionerMode": "mode", "setCoolingSetpoint": "temp",
                "setFanMode": "fan", "setFanOscillationMode": "osc", "setAcOptionalMode": "opt"}
        for c in cmds:
            print("[SmartThings]", c["capability"], c["command"], c.get("arguments", []))
            if c["capability"] == "switch":
                self.s["switch"] = c["command"]
            else:
                self.s[keys[c["command"]]] = c["arguments"][0]
        return {}


st = FakeSmartThings() if FAKE else SmartThings()


# ----------------------------------------------------------------------
#  Terjemah status SmartThings <-> format ringkas untuk website
# ----------------------------------------------------------------------
def is_aircon(dev):
    return any(cap.get("id") == "airConditionerMode"
               for comp in dev.get("components", []) for cap in comp.get("capabilities", []))


def list_aircons():
    return [{"id": d["deviceId"], "label": d.get("label") or d.get("name") or d["deviceId"]}
            for d in st.devices() if is_aircon(d)]


def current_device():
    dev = FIXED_DEVICE or store.get("device_id")
    if dev:
        return dev
    acs = list_aircons()
    if not acs:
        raise ApiError(404, "Tiada aircond dijumpai dalam akaun SmartThings ini.")
    store.set(device_id=acs[0]["id"], device_label=acs[0]["label"])
    return acs[0]["id"]


def normalize(status):
    main = status.get("components", {}).get("main", {})

    def attr(cap, name, default=None):
        val = (main.get(cap, {}).get(name) or {}).get("value")
        return default if val is None else val

    rng = attr("thermostatCoolingSetpoint", "coolingSetpointRange") or {}
    timer_at = store.get("timer_at") or 0
    return {
        "power": attr("switch", "switch") == "on",
        "mode": attr("airConditionerMode", "airConditionerMode"),
        "modes": attr("airConditionerMode", "supportedAcModes", ["cool", "dry", "wind", "auto", "heat"]),
        "temp": attr("thermostatCoolingSetpoint", "coolingSetpoint"),
        "unit": (main.get("thermostatCoolingSetpoint", {}).get("coolingSetpoint") or {}).get("unit", "C"),
        "min": rng.get("minimum", 16), "max": rng.get("maximum", 30),
        "roomTemp": attr("temperatureMeasurement", "temperature"),
        "humidity": attr("relativeHumidityMeasurement", "humidity"),
        "fan": attr("airConditionerFanMode", "fanMode"),
        "fans": attr("airConditionerFanMode", "supportedAcFanModes", ["auto", "low", "medium", "high"]),
        "swing": attr("fanOscillationMode", "fanOscillationMode"),
        "swings": attr("fanOscillationMode", "supportedFanOscillationModes",
                       ["fixed", "all"] if "fanOscillationMode" in main else []),
        "option": attr("custom.airConditionerOptionalMode", "acOptionalMode"),
        "options": attr("custom.airConditionerOptionalMode", "supportedAcOptionalMode", []),
        "timer": max(1, int((timer_at - time.time()) // 60) + 1) if timer_at else 0,
    }


WORD = re.compile(r"^[A-Za-z0-9_]{1,40}$")
COMMANDS = {  # medan website -> (capability, command)
    "mode": ("airConditionerMode", "setAirConditionerMode"),
    "fan": ("airConditionerFanMode", "setFanMode"),
    "swing": ("fanOscillationMode", "setFanOscillationMode"),
    "option": ("custom.airConditionerOptionalMode", "setAcOptionalMode"),
}


def build_commands(patch):
    cmd = lambda cap, name, args=(): {"component": "main", "capability": cap,
                                      "command": name, "arguments": list(args)}
    cmds = []
    if patch.get("power") is True:
        cmds.append(cmd("switch", "on"))
    for key, (cap, name) in COMMANDS.items():
        val = patch.get(key)
        if isinstance(val, str) and WORD.match(val):
            cmds.append(cmd(cap, name, [val]))
    temp = patch.get("temp")
    if isinstance(temp, (int, float)) and not isinstance(temp, bool) and 10 <= temp <= 35:
        cmds.append(cmd("thermostatCoolingSetpoint", "setCoolingSetpoint", [temp]))
    if patch.get("power") is False:
        cmds.append(cmd("switch", "off"))
    return cmds


def apply_patch(patch):
    dev = current_device()
    if isinstance(patch.get("timer"), int) and not isinstance(patch.get("timer"), bool):
        minutes = max(0, min(24 * 60, patch["timer"]))
        store.set(timer_at=time.time() + minutes * 60 if minutes else 0)
    if patch.get("power") is False:
        store.set(timer_at=0)
    cmds = build_commands(patch)
    if cmds:
        st.commands(dev, cmds)
        time.sleep(0.8)  # beri masa awan Samsung kemas kini status
    state = normalize(st.status(dev))
    # Status awan kadang-kadang lambat; tunjuk nilai yang baru dihantar.
    for key in ("power", "mode", "fan", "swing", "option", "temp"):
        if key in patch and patch[key] is not None and key != "timer":
            state[key] = patch[key]
    return state


# ----------------------------------------------------------------------
#  Kerja latar: pemasa tutup + refresh token sebelum tamat
# ----------------------------------------------------------------------
def background():
    while True:
        try:
            timer_at = store.get("timer_at") or 0
            if timer_at and time.time() >= timer_at:
                store.set(timer_at=0)
                st.commands(current_device(), build_commands({"power": False}))
                print("Pemasa tamat: aircond dimatikan")
            oauth = store.get("oauth")
            if tokens.mode() == "oauth" and oauth["expires_at"] - 3600 < time.time():
                tokens.refresh()
                print("Token OAuth diperbaharui")
        except Exception as e:  # jangan biar thread mati
            print("Latar:", e, file=sys.stderr)
        time.sleep(20)


# ----------------------------------------------------------------------
#  Pelayan web
# ----------------------------------------------------------------------
def extract_code(text):
    text = (text or "").strip()
    if "code=" in text:
        q = urllib.parse.urlparse(text).query or text.split("?", 1)[-1]
        return (urllib.parse.parse_qs(q).get("code") or [""])[0]
    return text


class Handler(BaseHTTPRequestHandler):
    server_version = "AircondWeb"

    def _send(self, code, body, ctype="application/json", headers=None):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self):
        if not WEB_PASSWORD:
            return True
        expected = "Basic " + base64.b64encode(f"{WEB_USER}:{WEB_PASSWORD}".encode()).decode()
        if hmac.compare_digest(self.headers.get("Authorization", ""), expected):
            return True
        self._send(401, {"error": "Perlu log masuk"},
                   headers={"WWW-Authenticate": 'Basic realm="Aircond", charset="UTF-8"'})
        return False

    def _body(self):
        try:
            length = min(int(self.headers.get("Content-Length", 0)), 10000)
            return json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            raise ApiError(400, "JSON tidak sah")

    def _run(self, fn):
        try:
            fn()
        except ApiError as e:
            self._send(e.status if 400 <= e.status < 600 else 502, {"error": str(e)})
        except Exception as e:
            print("Ralat:", repr(e), file=sys.stderr)
            self._send(500, {"error": "Ralat dalaman server"})

    def do_GET(self):
        if not self._authorized():
            return
        path, _, query = self.path.partition("?")
        if path == "/":
            with open(os.path.join(ROOT, "web", "index.html"), "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if path == "/api/state":
            return self._run(self.get_state)
        if path == "/api/devices":
            return self._run(lambda: self._send(200, {"devices": list_aircons(),
                                                     "current": FIXED_DEVICE or store.get("device_id")}))
        if path == "/auth/start":
            if not tokens.oauth_ready():
                return self._send(400, {"error": "SMARTTHINGS_CLIENT_ID/SECRET belum diisi dalam .env"})
            return self._send(302, b"", headers={"Location": tokens.authorize_url()})
        if path == "/auth/callback":
            code = (urllib.parse.parse_qs(query).get("code") or [""])[0]
            return self._run(lambda: self.finish_login(code, redirect=True))
        self._send(404, {"error": "Tidak dijumpai"})

    def do_POST(self):
        if not self._authorized():
            return
        if self.path == "/api/state":
            return self._run(lambda: self._send(200, apply_patch(self._body())))
        if self.path == "/api/device":
            def choose():
                dev = self._body().get("id", "")
                match = [d for d in list_aircons() if d["id"] == dev]
                if not match:
                    raise ApiError(404, "Peranti tidak dijumpai")
                store.set(device_id=dev, device_label=match[0]["label"], timer_at=0)
                self._send(200, {"ok": True})
            return self._run(choose)
        if self.path == "/auth/code":
            return self._run(lambda: self.finish_login(extract_code(self._body().get("code"))))
        self._send(404, {"error": "Tidak dijumpai"})

    def finish_login(self, code, redirect=False):
        if not code:
            raise ApiError(400, "Kod kebenaran kosong")
        tokens.exchange_code(code)
        store.set(device_id=None)
        if redirect:
            self._send(302, b"", headers={"Location": "/"})
        else:
            self._send(200, {"ok": True})

    def get_state(self):
        mode = tokens.mode()
        setup = {"authMode": mode, "oauthReady": tokens.oauth_ready(), "redirectUri": REDIRECT_URI}
        if mode == "none":
            return self._send(200, {"configured": False, **setup})
        dev = current_device()
        state = normalize(st.status(dev))
        label = store.get("device_label") if store.get("device_id") == dev else None
        self._send(200, {"configured": True, **setup, "device": {"id": dev, "label": label or "Aircond"},
                         **state})

    def log_message(self, fmt, *args):
        pass


def main():
    print(f"Mod token: {tokens.mode()}")
    if tokens.mode() == "none":
        print("  -> Isi SMARTTHINGS_TOKEN atau CLIENT_ID/SECRET dalam .env (lihat README.md)")
    if tokens.mode() == "pat":
        print("  -> Amaran: PAT SmartThings baharu hanya sah 24 jam. Guna OAuth untuk jangka panjang.")
    if not WEB_PASSWORD:
        print("  -> Amaran: WEB_PASSWORD kosong, sesiapa dalam rangkaian boleh kawal aircond!")
    threading.Thread(target=background, daemon=True).start()
    print(f"Website: http://localhost:{PORT}  (Ctrl+C untuk berhenti)")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
