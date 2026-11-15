"""Generates generic, Scrap-Mechanic-looking blueprint icons (isometric voxel renders) for promo
screenshots, so the published images don't show anyone's real creations.

    python tools/demo/voxel_icons.py OUT_DIR      -> OUT_DIR/<model>.png (256x256, transparent)
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

C = {  # Scrap Mechanic-ish palette
    "orange": (223, 127, 0), "yellow": (236, 190, 44), "blue": (46, 112, 196), "red": (196, 52, 42),
    "olive": (104, 122, 62), "grey": (142, 148, 152), "dark": (58, 60, 66), "white": (222, 226, 230),
    "black": (34, 34, 38), "teal": (36, 150, 150), "purple": (126, 84, 170), "wood": (170, 120, 70),
    "glass": (150, 200, 230), "lime": (130, 190, 60),
}


class Model:
    def __init__(self):
        self.v: dict[tuple[int, int, int], tuple[int, int, int]] = {}

    def box(self, x0, x1, y0, y1, z0, z1, color):
        col = C[color] if isinstance(color, str) else color
        for x in range(x0, x1):
            for y in range(y0, y1):
                for z in range(z0, z1):
                    self.v[(x, y, z)] = col
        return self

    def wheel(self, x, y, z=0, r=2, w=1, color="black", axis="y"):
        for a in range(-r, r):
            for b in range(-r, r):
                if (a + 0.5) ** 2 + (b + 0.5) ** 2 <= r * r:
                    for t in range(w):
                        if axis == "y":
                            self.v[(x + a, y + t, z + r + b)] = C[color]
                        else:
                            self.v[(x + t, y + a, z + r + b)] = C[color]
        return self


def render(m: Model, size=256) -> Image.Image:
    s = 1.0
    cos30, sin30 = math.cos(math.pi / 6), 0.5
    pts = []
    for (x, y, z) in m.v:
        for dx in (0, 1):
            for dy in (0, 1):
                for dz in (0, 1):
                    X, Y, Z = x + dx, y + dy, z + dz
                    pts.append(((X - Y) * cos30, (X + Y) * sin30 - Z))
    minx, maxx = min(p[0] for p in pts), max(p[0] for p in pts)
    miny, maxy = min(p[1] for p in pts), max(p[1] for p in pts)
    big = size * 3
    scale = (big * 0.86) / max(maxx - minx, maxy - miny)
    ox = big / 2 - (minx + maxx) / 2 * scale
    oy = big / 2 - (miny + maxy) / 2 * scale

    def P(X, Y, Z):
        return (ox + (X - Y) * cos30 * scale, oy + ((X + Y) * sin30 - Z) * scale)

    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    shade = lambda c, f: tuple(max(0, min(255, int(v * f))) for v in c) + (255,)
    edge_w = max(1, int(scale * 0.06))
    for (x, y, z) in sorted(m.v, key=lambda k: (k[0] + k[1] + k[2], k[2])):
        c = m.v[(x, y, z)]
        faces = []
        if (x, y, z + 1) not in m.v:
            faces.append(([P(x, y, z + 1), P(x + 1, y, z + 1), P(x + 1, y + 1, z + 1), P(x, y + 1, z + 1)], 1.0))
        if (x + 1, y, z) not in m.v:
            faces.append(([P(x + 1, y, z), P(x + 1, y + 1, z), P(x + 1, y + 1, z + 1), P(x + 1, y, z + 1)], 0.78))
        if (x, y + 1, z) not in m.v:
            faces.append(([P(x, y + 1, z), P(x + 1, y + 1, z), P(x + 1, y + 1, z + 1), P(x, y + 1, z + 1)], 0.6))
        for poly, f in faces:
            d.polygon(poly, fill=shade(c, f), outline=shade(c, f * 0.72), width=edge_w)
    return img.resize((size, size), Image.LANCZOS)


# ---- models ----------------------------------------------------------------------------------
def buggy(body="orange"):
    m = Model().box(0, 10, 1, 6, 1, 3, body).box(3, 7, 2, 5, 3, 5, "dark").box(3, 4, 1, 6, 3, 6, "grey").box(6, 7, 1, 6, 3, 6, "grey")
    for x in (2, 8):
        m.wheel(x, -1, 0, 2, 2).wheel(x, 6, 0, 2, 2)
    return m


def truck(cab="blue"):
    m = Model().box(0, 16, 1, 7, 2, 3, "dark").box(11, 16, 1, 7, 3, 8, cab).box(15, 16, 2, 6, 5, 7, "glass")
    m.box(0, 11, 1, 7, 3, 7, "grey")
    for x in (3, 7, 13):
        m.wheel(x, 0, 0, 2, 1).wheel(x, 7, 0, 2, 1)
    return m


def tank(hull="olive"):
    m = Model().box(0, 16, 0, 2, 0, 3, "dark").box(0, 16, 8, 10, 0, 3, "dark").box(1, 15, 2, 8, 1, 4, hull)
    m.box(4, 11, 2, 8, 4, 7, hull).box(11, 20, 4, 6, 5, 6, "dark").box(5, 8, 3, 5, 7, 8, "grey")
    return m


def mech(main="orange"):
    m = Model()
    for y0 in (1, 6):
        m.box(3, 6, y0, y0 + 2, 0, 2, "dark").box(3, 5, y0, y0 + 2, 2, 7, "grey")
    m.box(2, 7, 0, 9, 7, 12, main).box(3, 6, 3, 6, 12, 14, "grey").box(5, 6, 3, 6, 12, 13, "glass")
    m.box(3, 5, -2, 0, 7, 11, "grey").box(3, 5, 9, 11, 7, 11, "grey").box(5, 10, 9, 11, 9, 10, "dark")
    return m


def plane(body="white"):
    m = Model().box(0, 18, 3, 6, 2, 5, body).box(14, 18, 3, 6, 5, 6, "glass").box(6, 11, -6, 15, 3, 4, body)
    m.box(0, 3, -2, 11, 4, 5, body).box(0, 3, 4, 5, 5, 9, "red").box(0, 18, 3, 6, 4, 5, "red")
    return m


def heli(body="yellow"):
    m = Model().box(4, 12, 2, 7, 1, 6, body).box(10, 12, 2, 7, 3, 6, "glass").box(0, 4, 4, 5, 4, 5, body)
    m.box(0, 1, 4, 5, 5, 8, body).box(-2, 18, 4, 5, 7, 8, "dark").box(7, 9, -4, 13, 7, 8, "dark").box(7, 9, 4, 5, 6, 7, "grey")
    m.box(4, 12, 1, 2, 0, 1, "dark").box(4, 12, 7, 8, 0, 1, "dark")
    return m


def house(wall="white", roof="red"):
    m = Model().box(0, 12, 0, 10, 0, 7, wall).box(5, 7, 9, 10, 0, 4, "wood").box(2, 4, 9, 10, 3, 5, "glass").box(8, 10, 9, 10, 3, 5, "glass")
    for i in range(4):
        m.box(-1 + i, 13 - i, -1, 11, 7 + i, 8 + i, roof)
    return m


def crane():
    m = Model().box(0, 8, 0, 8, 0, 2, "dark").box(3, 5, 3, 5, 2, 18, "yellow").box(-6, 14, 3, 5, 17, 19, "yellow")
    m.box(-6, -3, 2, 6, 15, 17, "grey").box(12, 13, 3, 5, 9, 17, "dark").box(11, 14, 2, 6, 7, 9, "orange")
    return m


def boat(hull="blue"):
    m = Model().box(0, 18, 0, 7, 0, 3, hull).box(18, 20, 1, 6, 1, 3, hull).box(4, 11, 1, 6, 3, 7, "white").box(9, 11, 1, 6, 5, 6, "glass")
    m.box(6, 7, 3, 4, 7, 12, "grey")
    return m


def rocket():
    m = Model().box(2, 6, 2, 6, 0, 18, "white").box(3, 5, 3, 5, 18, 21, "red").box(2, 6, 2, 6, 8, 9, "red")
    m.box(0, 2, 3, 5, 0, 4, "red").box(6, 8, 3, 5, 0, 4, "red").box(3, 5, 0, 2, 0, 4, "red").box(3, 5, 6, 8, 0, 4, "red")
    return m


def drone(color="teal"):
    m = Model().box(4, 9, 4, 9, 2, 4, color).box(6, 7, 6, 7, 1, 2, "glass")
    for a, b in ((0, 0), (0, 10), (10, 0), (10, 10)):
        m.box(a, a + 3, b, b + 3, 3, 4, "dark").box(a + 1, a + 2, b + 1, b + 2, 4, 5, "grey")
    m.box(2, 11, 6, 7, 3, 4, "grey").box(6, 7, 2, 11, 3, 4, "grey")
    return m


def forklift():
    m = Model().box(0, 9, 1, 7, 1, 4, "yellow").box(2, 6, 2, 6, 4, 8, "dark").box(2, 3, 1, 7, 4, 10, "grey").box(5, 6, 1, 7, 4, 10, "grey")
    m.box(9, 10, 1, 7, 1, 11, "dark").box(10, 15, 2, 3, 1, 2, "grey").box(10, 15, 5, 6, 1, 2, "grey")
    m.wheel(2, 0, 0, 1, 1).wheel(2, 7, 0, 1, 1).wheel(7, 0, 0, 1, 1).wheel(7, 7, 0, 1, 1)
    return m


def robodog(color="grey"):
    m = Model().box(2, 12, 2, 6, 4, 7, color).box(12, 15, 2, 6, 5, 9, color).box(14, 15, 3, 5, 6, 7, "red")
    for x in (3, 10):
        m.box(x, x + 2, 1, 2, 0, 5, "dark").box(x, x + 2, 6, 7, 0, 5, "dark")
    m.box(0, 2, 3, 5, 6, 7, color)
    return m


def train(color="red"):
    m = Model().box(0, 20, 1, 7, 2, 3, "dark").box(0, 12, 1, 7, 3, 8, color).box(12, 18, 1, 7, 3, 11, color)
    m.box(14, 17, 1, 7, 8, 10, "glass").box(3, 5, 3, 5, 8, 11, "dark").box(18, 20, 2, 6, 2, 4, "grey")
    for x in (2, 6, 10, 15):
        m.wheel(x, 0, 0, 2, 1).wheel(x, 7, 0, 2, 1)
    return m


def excavator():
    m = Model().box(0, 12, 0, 2, 0, 2, "dark").box(0, 12, 7, 9, 0, 2, "dark").box(1, 11, 2, 7, 1, 2, "dark")
    m.box(1, 9, 1, 8, 2, 6, "orange").box(6, 9, 1, 4, 6, 9, "glass").box(8, 16, 4, 6, 6, 8, "orange").box(15, 17, 4, 6, 1, 8, "orange")
    m.box(15, 19, 3, 7, 0, 2, "grey")
    return m


def turret():
    m = Model().box(0, 10, 0, 10, 0, 2, "grey").box(2, 8, 2, 8, 2, 6, "olive").box(8, 18, 3, 4, 4, 5, "dark").box(8, 18, 6, 7, 4, 5, "dark")
    m.box(3, 6, 3, 7, 6, 7, "dark")
    return m


def bus(color="yellow"):
    m = Model().box(0, 22, 1, 8, 1, 8, color).box(0, 22, 1, 8, 5, 7, "glass").box(0, 22, 1, 8, 4, 5, "dark")
    for x in (4, 17):
        m.wheel(x, 0, 0, 2, 1).wheel(x, 8, 0, 2, 1)
    return m


def tower():
    m = Model()
    for z in range(0, 22):
        c = "red" if (z // 4) % 2 == 0 else "white"
        w = 3 if z < 10 else 2
        m.box(4 - w, 4 + w, 4 - w, 4 + w, z, z + 1, c)
    m.box(1, 7, 1, 7, 22, 25, "glass").box(1, 7, 1, 7, 25, 26, "dark")
    return m


def hover(color="purple"):
    m = Model().box(0, 14, 1, 8, 2, 5, color).box(5, 11, 2, 7, 5, 7, "glass").box(0, 3, 0, 9, 1, 2, "dark").box(11, 14, 0, 9, 1, 2, "dark")
    m.box(-2, 0, 3, 6, 3, 4, "teal")
    return m


MODELS = {
    "buggy": buggy(), "buggy_blue": buggy("blue"), "truck": truck(), "truck_red": truck("red"),
    "tank": tank(), "tank_grey": tank("grey"), "mech": mech(), "mech_blue": mech("blue"), "mech_red": mech("red"),
    "plane": plane(), "heli": heli(), "house": house(), "house_blue": house("white", "blue"), "crane": crane(),
    "boat": boat(), "rocket": rocket(), "drone": drone(), "drone_orange": drone("orange"), "forklift": forklift(),
    "robodog": robodog(), "robodog_orange": robodog("orange"), "train": train(), "excavator": excavator(),
    "turret": turret(), "bus": bus(), "tower": tower(), "hover": hover(), "hover_lime": hover("lime"),
}


def main() -> int:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for name, m in MODELS.items():
        render(m).save(out / f"{name}.png")
    print(f"wrote {len(MODELS)} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
