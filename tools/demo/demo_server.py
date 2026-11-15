"""Serves the manager UI with a fictional library (voxel icons from voxel_icons.py) - for promo
screenshots. Reads none of your real blueprints or library.

    python tools/demo/voxel_icons.py tools/demo/icons
    python tools/demo/demo_server.py tools/demo/icons [--port 47990]
    msedge --headless=new --window-size=1920,1080 --virtual-time-budget=9000 --screenshot=shot.png ^
        "http://127.0.0.1:47990/#view=L&scope=Vehicles&select=demo-buggy,demo-truck,demo-tank"
"""
from __future__ import annotations

import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "Mod" / "Manager" / "web"
TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".png": "image/png", ".ico": "image/x-icon"}

# (id suffix, icon, name, folder, tags, extra)
ITEMS = [
    ("buggy", "buggy", "Dune Buggy", "Vehicles/Cars", ["fast"], {"fav": True}),
    ("truck", "truck", "Cargo Hauler", "Vehicles/Trucks", ["cargo"], {"fav": True}),
    ("tank", "tank", "Tracked Tank T-2", "Vehicles/Tanks", ["armor"], {"fav": True}),
    ("buggy2", "buggy_blue", "Rally Buggy", "Vehicles/Cars", ["fast"], {}),
    ("truck2", "truck_red", "Fire Truck", "Vehicles/Trucks", ["service"], {}),
    ("tank2", "tank_grey", "Siege Tank", "Vehicles/Tanks", ["armor"], {"mods": ["Cannons Pack"]}),
    ("bus", "bus", "City Bus", "Vehicles/Trucks", ["transport"], {}),
    ("train", "train", "Locomotive 01", "Vehicles", ["rail"], {}),
    ("hover", "hover", "Hover Car", "Vehicles/Cars", ["fast", "prototype"], {}),
    ("hover2", "hover_lime", "Hover Car Mk2", "Vehicles/Cars", ["fast", "prototype"], {}),
    ("forklift", "forklift", "Forklift", "Vehicles", ["service"], {}),
    ("excavator", "excavator", "Excavator", "Vehicles", ["construction"], {}),
    ("mech", "mech", "Walker MK-II", "Robots", ["mech"], {"fav": True}),
    ("mech2", "mech_blue", "Walker MK-III", "Robots", ["mech"], {}),
    ("mech3", "mech_red", "Walker Assault", "Robots", ["mech"], {"mods": ["Cannons Pack"]}),
    ("dog", "robodog", "Robo Dog", "Robots", ["mech"], {}),
    ("dog2", "robodog_orange", "Robo Dog Scout", "Robots", ["mech", "fast"], {}),
    ("plane", "plane", "Sky Hopper", "Aircraft", ["fast"], {}),
    ("heli", "heli", "Rescue Copter", "Aircraft", ["service"], {}),
    ("drone", "drone", "Quad Drone", "Aircraft", ["prototype"], {}),
    ("drone2", "drone_orange", "Camera Drone", "Aircraft", [], {}),
    ("rocket", "rocket", "Rocket R-1", "Aircraft", ["prototype"], {}),
    ("house", "house", "Cottage", "Buildings", [], {}),
    ("house2", "house_blue", "Beach House", "Buildings", [], {}),
    ("tower", "tower", "Lighthouse", "Buildings", [], {}),
    ("crane", "crane", "Tower Crane", "Buildings", ["construction"], {}),
    ("boat", "boat", "Fishing Boat", "Vehicles", [], {}),
    ("turret", "turret", "Defense Turret", "Buildings", ["armor"], {}),
]


def demo_state() -> dict:
    now = int(time.time())
    blueprints, items = [], {}
    for i, (sid, icon, name, folder, tags, extra) in enumerate(ITEMS):
        bid = "demo-" + sid
        bp = {"id": bid, "name": name, "source": "local", "mtime": now - i * 86400, "hasIcon": True, "_icon": icon}
        if extra.get("mods"):
            bp["mods"] = [{"name": m, "shapes": []} for m in extra["mods"]]
        blueprints.append(bp)
        meta = {"folder": folder, "tags": tags}
        if extra.get("fav"):
            meta["fav"] = True
        items[bid] = meta
    folders = ["Aircraft", "Buildings", "Robots", "Vehicles", "Vehicles/Cars", "Vehicles/Tanks", "Vehicles/Trucks"]
    return {"index": {"blueprints": blueprints}, "library": {"folders": folders, "items": items, "rev": 1},
            "installedMods": [{"name": "Some Installed Mod"}]}


class Handler(BaseHTTPRequestHandler):
    icons: Path
    state = demo_state()

    def log_message(self, *a):
        pass

    def send(self, code, body: bytes, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            return self.send(200, (WEB / "index.html").read_text(encoding="utf-8").replace("__BR_TOKEN__", "demo").encode(), TYPES[".html"])
        if path == "/api/state":
            return self.send(200, json.dumps(self.state).encode())
        if path == "/api/rev":
            return self.send(200, b'{"rev": 1}')
        if path.startswith("/icon/"):
            bp = next((b for b in self.state["index"]["blueprints"] if b["id"] == path[6:]), None)
            f = self.icons / f"{bp['_icon']}.png" if bp else None
            return self.send(200, f.read_bytes(), "image/png") if f and f.is_file() else self.send(404, b"")
        f = (WEB / path.lstrip("/")).resolve()
        if WEB in f.parents and f.is_file() and f.suffix in TYPES:
            return self.send(200, f.read_bytes(), TYPES[f.suffix])
        return self.send(404, b"")

    def do_POST(self):
        return self.send(200, b'{"ok": true}')

    def do_PUT(self):
        return self.send(200, b'{"rev": 1}')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("icons", type=Path)
    ap.add_argument("--port", type=int, default=47990)
    a = ap.parse_args()
    Handler.icons = a.icons.resolve()
    print(f"demo manager on http://127.0.0.1:{a.port}/")
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
