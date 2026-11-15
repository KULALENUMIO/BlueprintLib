"""Blueprint Lib - web manager server (Python standard library only).

Serves web/ on http://127.0.0.1:<port>/ and a tiny JSON API around the mod's data files:

  GET  /api/state      index + library + installed mods
  GET  /api/rev        current library revision (cheap poll to notice in-game edits)
  PUT  /api/library    {library, baseRev} -> 409 + current state if someone else saved first
  POST /api/sync       rescan blueprint folders (same as sync_index.bat)
  POST /api/place      {id} -> Data/request.json, picked up by the tool while it is held in game
  POST /api/heartbeat  keeps the server alive; it exits a while after the last browser tab closes
  GET  /icon/<id>      the blueprint's icon.png (read only)

Usage:  pythonw manager_server.py --open      (no console window; opens the browser)
        python  manager_server.py --open      (with console log)
If a manager is already running on the port it just opens the browser and exits.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import br_paths  # noqa: E402  (same folder)
import sync_index  # noqa: E402

WEB = ROOT / "web"
_MOD = br_paths.find_mod_dir()
DATA = (_MOD / "Data") if _MOD else None  # None = mod not installed; the page explains what to do
INDEX = DATA / "index.json" if DATA else None
LIBRARY = DATA / "library.json" if DATA else None
REQUEST = DATA / "request.json" if DATA else None
LOG_FILE = br_paths.backup_dir() / "manager_server.log"  # outside the repo / mod folder

DEFAULT_PORT = 47851
IDLE_EXIT_SECONDS = 150     # after the last heartbeat (hidden tabs throttle timers to ~1/min)
BYE_EXIT_SECONDS = 10       # after a tab says goodbye (pagehide), unless another tab is still beating
STARTUP_GRACE_SECONDS = 90  # time for the first tab to show up
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
STATIC_TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                ".js": "text/javascript; charset=utf-8", ".png": "image/png", ".ico": "image/x-icon",
                ".svg": "image/svg+xml"}


def log(*parts):
    line = time.strftime("%H:%M:%S ") + " ".join(str(p) for p in parts)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass
    if sys.stdout:
        try:
            print(line, flush=True)
        except Exception:
            pass


def read_json(path: Path, default=None):
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def backup_quietly():
    try:
        br_paths.backup_library(DATA)
    except Exception as e:  # a failed backup must never break saving
        log("backup failed:", repr(e))


class Unavailable(Exception):
    """The data file is busy or unreadable right now - answer 503, never guess."""


def read_library() -> dict:
    """library.json as a dict. A missing file is an empty library; a file that exists but can't be
    parsed (the game may be mid-write, or it is locked) is retried and then reported as Unavailable,
    so an unreadable file is never mistaken for "empty, rev 0" and overwritten."""
    last = None
    for _ in range(8):
        try:
            with open(LIBRARY, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
            last = ValueError("library.json is not a JSON object")
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as e:
            last = e
        time.sleep(0.12)
    raise Unavailable(f"library.json unreadable: {last}")


def write_json_atomic(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent="\t")
    # On Windows os.replace fails with "access denied" while anyone (e.g. the game) has the target
    # open, even just for reading. Retry briefly instead of dropping the save.
    last = None
    for _ in range(15):
        try:
            os.replace(tmp, path)
            return
        except PermissionError as e:
            last = e
            time.sleep(0.1)
    try:
        tmp.unlink()  # don't leave half-done saves lying around
    except OSError:
        pass
    raise Unavailable(f"{path.name} is locked: {last}")


def rev_of(lib) -> int:
    try:
        return int(float((lib or {}).get("rev") or 0))
    except (TypeError, ValueError):
        return 0


class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.token = secrets.token_hex(16)
        self.paths: dict[str, Path] = {}
        self.installed: list[dict] = []
        self.last_beat = time.time() + STARTUP_GRACE_SECONDS - IDLE_EXIT_SECONDS
        self.port = DEFAULT_PORT
        self.backed_up_rev = None

    def refresh_paths(self, rescan: bool) -> dict:
        """Map blueprint ids to folders (for icons). rescan=True also rewrites index.json."""
        if rescan or not INDEX.is_file():
            payload, paths = sync_index.build_index(INDEX, log=log)
        else:
            # cheap pass: only folder locations, no blueprint parsing
            paths = {}
            for d in sync_index.user_blueprint_dirs() + sync_index.workshop_dirs():
                for entry in d.iterdir():
                    if (entry / "description.json").is_file():
                        desc = read_json(entry / "description.json", {})
                        lid = sync_index.blueprint_id(desc if isinstance(desc, dict) else {}, entry)
                        if lid:
                            paths.setdefault(lid, entry)
            payload = read_json(INDEX, {})
        self.paths = paths
        self.installed = sync_index.installed_mods()
        return payload


STATE = State()


class Handler(BaseHTTPRequestHandler):
    server_version = "BlueprintLibManager/1"

    def log_message(self, fmt, *args):  # route through our logger, quietly
        if "/api/heartbeat" in self.path or "/api/rev" in self.path or "/icon/" in self.path:
            return
        log(self.address_string(), fmt % args)

    # --- helpers -------------------------------------------------------------------------
    def _send(self, status, body: bytes, ctype="application/json; charset=utf-8", extra=None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status, obj):
        self._send(status, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def _host_ok(self) -> bool:
        # blocks DNS-rebinding: only accept requests addressed to localhost
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost")

    def _token_ok(self) -> bool:
        # blocks other web pages from driving the API (they can't read the token)
        return self.headers.get("X-BR-Token") == STATE.token

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None
        if n <= 0 or n > 20_000_000:
            return None
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except ValueError:
            return None

    # --- routes --------------------------------------------------------------------------
    def _guard(self, route):
        """Busy data files -> 503, anything unexpected -> 500. Never a silently dropped connection."""
        try:
            route()
        except Unavailable as e:
            log("503", e)
            self._json(503, {"error": "busy", "detail": str(e)})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            log("500", repr(e))
            try:
                self._json(500, {"error": "internal", "detail": repr(e)})
            except Exception:
                pass

    def do_GET(self):
        self._guard(self._get)

    def do_PUT(self):
        self._guard(self._put)

    def do_POST(self):
        self._guard(self._post)

    def _get(self):
        if not self._host_ok():
            return self._send(HTTPStatus.FORBIDDEN, b"{}")
        path = self.path.split("?")[0]
        if path == "/api/ping":
            return self._json(200, {"app": "BlueprintLib"})
        if path in ("/", "/index.html"):
            html = (WEB / "index.html").read_text(encoding="utf-8").replace("__BR_TOKEN__", STATE.token)
            return self._send(200, html.encode("utf-8"), STATIC_TYPES[".html"])
        if path.startswith("/icon/"):
            bid = path[len("/icon/"):].lower()
            folder = STATE.paths.get(bid) if UUID_RE.match(bid) else None
            icon = folder / "icon.png" if folder else None
            if icon and icon.is_file():
                return self._send(200, icon.read_bytes(), "image/png", {"Cache-Control": "max-age=300"})
            return self._send(404, b"")
        if path.startswith("/api/"):
            if not self._token_ok():
                return self._json(403, {"error": "token"})
            if path == "/api/state":
                with STATE.lock:
                    return self._json(200, self._state())
            if DATA is None:
                return self._json(503, {"error": "nomod", "detail": "Blueprint Lib mod not found (the page shows how to fix it)"})
            if path == "/api/rev":
                with STATE.lock:
                    rev = rev_of(read_library())
                    if rev != STATE.backed_up_rev:  # the game saved: keep the backup current too
                        backup_quietly()
                        STATE.backed_up_rev = rev
                    return self._json(200, {"rev": rev})
            return self._json(404, {"error": "unknown"})
        # static files from web/
        rel = path.lstrip("/")
        target = (WEB / rel).resolve()
        if WEB.resolve() in target.parents and target.is_file() and target.suffix in STATIC_TYPES:
            return self._send(200, target.read_bytes(), STATIC_TYPES[target.suffix])
        return self._send(404, b"not found", "text/plain")

    def _put(self):
        if not (self._host_ok() and self._token_ok()):
            return self._json(403, {"error": "forbidden"})
        if DATA is None:
            return self._json(503, {"error": "nomod"})
        if self.path != "/api/library":
            return self._json(404, {"error": "unknown"})
        body = self._body()
        if not isinstance(body, dict) or not isinstance(body.get("library"), dict):
            return self._json(400, {"error": "bad body"})
        with STATE.lock:
            current = read_library()  # raises Unavailable rather than pretending the file is empty
            base = rev_of({"rev": body.get("baseRev")})  # tolerant: bad values count as 0, never raise
            if rev_of(current) != base:
                return self._json(409, {"error": "conflict", "library": current, "rev": rev_of(current)})
            lib = body["library"]
            lib["rev"] = rev_of(current) + 1
            lib["version"] = 3
            write_json_atomic(LIBRARY, lib)
            backup_quietly()
        return self._json(200, {"rev": lib["rev"]})

    def _post(self):
        if self.path.split("?")[0] == "/api/bye":
            # sent with navigator.sendBeacon on pagehide; beacons can't carry headers -> token in query
            if self._host_ok() and ("t=" + STATE.token) in self.path:
                STATE.last_beat = min(STATE.last_beat, time.time() - IDLE_EXIT_SECONDS + BYE_EXIT_SECONDS)
            return self._json(200, {"ok": True})
        if not (self._host_ok() and self._token_ok()):
            return self._json(403, {"error": "forbidden"})
        if DATA is None and self.path != "/api/heartbeat":
            return self._json(503, {"error": "nomod"})
        if self.path == "/api/heartbeat":
            STATE.last_beat = time.time()
            return self._json(200, {"ok": True})
        if self.path == "/api/sync":
            with STATE.lock:
                STATE.refresh_paths(rescan=True)
            return self._json(200, self._state())
        if self.path == "/api/place":
            body = self._body() or {}
            bid = str(body.get("id") or "").lower()
            if not UUID_RE.match(bid):
                return self._json(400, {"error": "bad id"})
            with STATE.lock:
                write_json_atomic(REQUEST, {"id": bid, "nonce": secrets.token_hex(8)})
            return self._json(200, {"ok": True})
        return self._json(404, {"error": "unknown"})

    def _state(self):
        return {
            "index": read_json(INDEX, {"blueprints": []}),
            "library": read_library(),
            "installedMods": STATE.installed,
        }


def already_running(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1.5) as r:
            return json.loads(r.read().decode()).get("app") == "BlueprintLib"
    except Exception:
        return False


class Server(ThreadingHTTPServer):
    # The stdlib default (SO_REUSEADDR) lets two managers bind the same port on Windows; then the
    # tokens differ and requests randomly fail. Insist on exclusive use instead.
    allow_reuse_address = False
    daemon_threads = True

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def watchdog(server: ThreadingHTTPServer):
    while True:
        time.sleep(5)
        if time.time() - STATE.last_beat > IDLE_EXIT_SECONDS:
            log("no browser tab for a while - shutting down")
            server.shutdown()
            return


def main() -> int:
    ap = argparse.ArgumentParser(description="Blueprint Lib web manager")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--open", action="store_true", help="open the browser")
    ap.add_argument("--keep-alive", action="store_true", help="don't exit when the browser closes")
    ap.add_argument("--data", type=Path, help="use another data folder (testing)")
    args = ap.parse_args()
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if args.data:
        global DATA, INDEX, LIBRARY, REQUEST
        DATA = args.data.resolve()
        INDEX, LIBRARY, REQUEST = DATA / "index.json", DATA / "library.json", DATA / "request.json"
    url = f"http://127.0.0.1:{args.port}/"

    if already_running(args.port):
        log("manager already running, opening browser")
        if args.open:
            webbrowser.open(url)
        return 0

    try:  # keep the log small
        if LOG_FILE.stat().st_size > 512_000:
            LOG_FILE.unlink()
    except OSError:
        pass
    STATE.port = args.port
    if DATA is not None:
        restored = br_paths.restore_library(DATA)
        if restored:
            log(restored)
        backup_quietly()
        STATE.refresh_paths(rescan=not INDEX.is_file())
    else:
        log("mod not found - serving the page with instructions only")
    try:
        server = Server(("127.0.0.1", args.port), Handler)
    except OSError as e:  # lost a start-up race against another launch, or the port is taken
        log("port in use:", e)
        if args.open and already_running(args.port):
            webbrowser.open(url)
        return 0
    log(f"serving {url}  (data: {DATA})")
    if not args.keep_alive:
        threading.Thread(target=watchdog, args=(server,), daemon=True).start()
    if args.open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
