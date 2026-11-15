"""Builds the Steam Workshop preview image (1920x1080 JPEG, < 1 MB) from a manager screenshot.

    python tools/make_preview.py OUT.jpg                     Workshop thumbnail (16:9, name only)
    python tools/make_preview.py OUT.jpg --style keyart --screenshot SHOT.png   promo image

The screenshot is a 1920x1080 capture of the manager, e.g. (Edge, headless):
    msedge --headless=new --window-size=1920,1080 --virtual-time-budget=9000 \
           --screenshot=shot.png "http://127.0.0.1:47851/#view=L&scope=Robots&select=<id>,<id>"
Requires Pillow (pip install pillow). Fonts: Windows' Bahnschrift / Yu Gothic.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1920, 1080
FONTS = Path(r"C:\Windows\Fonts")
YELLOW = (244, 200, 70)
WHITE = (240, 244, 248)
MUTED = (170, 196, 224)
BLUE_TOP, BLUE_BOTTOM = (18, 58, 104), (9, 30, 58)

FEATURES = [
    ("Nested folders, tags, favorites", "階層フォルダ・タグ・お気に入り"),
    ("Lift-like placement, multi-select", "リフト感覚の設置・まとめて操作"),
    ("Missing-mod check before spawning", "MOD不足を事前にチェック"),
    ("Browser manager with drag & drop", "ブラウザ管理画面でドラッグ＆ドロップ"),
]


def font(name: str, size: int, variation: str | None = None):
    f = ImageFont.truetype(str(FONTS / name), size)
    if variation:
        try:
            f.set_variation_by_name(variation)
        except Exception:
            pass
    return f


def blueprint_background() -> Image.Image:
    bg = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(bg)
    for y in range(H):
        t = y / (H - 1)
        d.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(BLUE_TOP, BLUE_BOTTOM)))
    grid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = ImageDraw.Draw(grid)
    for x in range(0, W, 24):
        g.line([(x, 0), (x, H)], fill=(160, 200, 255, 38 if x % 120 else 70), width=1)
    for y in range(0, H, 24):
        g.line([(0, y), (W, y)], fill=(160, 200, 255, 38 if y % 120 else 70), width=1)
    return Image.alpha_composite(bg.convert("RGBA"), grid)


def framed(shot: Image.Image, width: int) -> Image.Image:
    """Screenshot scaled to width, with a light frame and a soft drop shadow."""
    s = shot.resize((width, round(shot.height * width / shot.width)), Image.LANCZOS).convert("RGBA")
    pad = 40
    out = Image.new("RGBA", (s.width + pad * 2, s.height + pad * 2), (0, 0, 0, 0))
    shadow = Image.new("RGBA", out.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([pad + 6, pad + 14, pad + s.width + 6, pad + s.height + 14], 10, fill=(0, 0, 0, 170))
    out = Image.alpha_composite(out, shadow.filter(ImageFilter.GaussianBlur(16)))
    out.alpha_composite(s, (pad, pad))
    ImageDraw.Draw(out).rounded_rectangle([pad - 2, pad - 2, pad + s.width + 1, pad + s.height + 1], 6, outline=(220, 232, 245, 255), width=3)
    return out


def draw_title(d: ImageDraw.ImageDraw, x: int, y: int, scale: float = 1.0) -> int:
    d.text((x, y), "SCRAP MECHANIC  ·  CREATIVE MOD", font=font("bahnschrift.ttf", int(26 * scale), "SemiBold"), fill=YELLOW)
    y += int(46 * scale)
    big = font("bahnschrift.ttf", int(118 * scale), "Bold Condensed")
    d.text((x - 4, y), "BLUEPRINT", font=big, fill=WHITE)
    y += int(112 * scale)
    d.text((x - 4, y), "LIB", font=big, fill=YELLOW)
    y += int(134 * scale)
    d.text((x, y), "Organize & place your blueprints", font=font("bahnschrift.ttf", int(34 * scale), "SemiLight"), fill=WHITE)
    y += int(46 * scale)
    d.text((x, y), "ブループリントを整理して、リフトのように設置", font=font("YuGothB.ttc", int(28 * scale)), fill=MUTED)
    return y + int(46 * scale)


def keyart(shot: Image.Image) -> Image.Image:
    img = blueprint_background()
    d = ImageDraw.Draw(img)
    y = draw_title(d, 90, 150)
    y += 34
    en, jp = font("bahnschrift.ttf", 30, "SemiBold"), font("YuGothM.ttc", 22)
    for e, j in FEATURES:
        d.rectangle([92, y + 12, 106, y + 26], fill=YELLOW)
        d.text((126, y), e, font=en, fill=WHITE)
        d.text((126, y + 38), j, font=jp, fill=MUTED)
        y += 86
    card = framed(shot, 1120)
    img.alpha_composite(card, (W - card.width - 20, (H - card.height) // 2 + 10))
    d = ImageDraw.Draw(img)
    d.text((90, H - 58), "Free companion manager on GitHub  ·  Python 3.10+", font=font("bahnschrift.ttf", 22, "SemiLight"), fill=MUTED)
    return img.convert("RGB")


def hero(shot: Image.Image) -> Image.Image:
    img = shot.resize((W, H), Image.LANCZOS).convert("RGBA")
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for x in range(W):  # dark on the left, fading out so the UI stays visible on the right
        a = max(0, int(235 * (1 - x / 1150)))
        sd.line([(x, 0), (x, H)], fill=(8, 22, 44, a))
    img = Image.alpha_composite(img, shade)
    d = ImageDraw.Draw(img)
    y = draw_title(d, 90, 230, 1.1)
    en = font("bahnschrift.ttf", 30, "SemiBold")
    for e, _ in FEATURES:
        d.rectangle([92, y + 12, 106, y + 26], fill=YELLOW)
        d.text((126, y), e, font=en, fill=WHITE)
        y += 52
    return img.convert("RGB")


TITLE_MARGIN = 56  # px left/right: the name fills the width almost edge to edge


def title_card() -> Image.Image:
    """The Workshop thumbnail: 16:9, nothing but the name on a plain blueprint background, as large as
    fits, so it stays readable in the Workshop grid (about 260 px wide)."""
    img = blueprint_background()
    d = ImageDraw.Draw(img)

    def measure(size):
        f = font("bahnschrift.ttf", size, "Bold Condensed")
        gap = size * 0.2
        l1 = d.textbbox((0, 0), "BLUEPRINT", font=f, anchor="ls")
        l2 = d.textbbox((0, 0), "LIB", font=f, anchor="ls")
        return f, gap, l1, l2, (l1[2] - l1[0]) + gap + (l2[2] - l2[0])

    size = 300
    for _ in range(3):  # scale until the ink width matches the target (font metrics aren't linear)
        size = int(size * (W - 2 * TITLE_MARGIN) / measure(size)[4])
    while measure(size)[4] > W - 2 * TITLE_MARGIN:
        size -= 1
    f, gap, l1, l2, total = measure(size)
    x = (W - total) / 2 - l1[0]
    cap = -l1[1]  # cap height above the baseline
    base = (H + cap) / 2  # vertically centre the capitals
    d.text((x, base), "BLUEPRINT", font=f, fill=WHITE, anchor="ls")
    d.text((x + l1[2] + gap - l2[0], base), "LIB", font=f, fill=YELLOW, anchor="ls")
    return img.convert("RGB")


def save_jpeg(img: Image.Image, out: Path) -> None:
    for q in (90, 86, 82, 78, 72):
        img.save(out, "JPEG", quality=q, optimize=True, progressive=True)
        if out.stat().st_size < 950_000:
            break
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--style", choices=("title", "keyart", "hero"), default="title")
    ap.add_argument("--screenshot", type=Path, help="manager screenshot (keyart / hero styles)")
    a = ap.parse_args()
    if a.style == "title":
        save_jpeg(title_card(), a.out)
        return 0
    if not a.screenshot:
        ap.error("--screenshot is required for this style")
    shot = Image.open(a.screenshot).convert("RGB")
    save_jpeg(keyart(shot) if a.style == "keyart" else hero(shot), a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
