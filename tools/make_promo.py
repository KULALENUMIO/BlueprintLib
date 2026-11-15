"""Builds the Steam Workshop gallery images and the description banners from demo-manager screenshots
(fictional data, see tools/demo/). Same look as tools/make_preview.py.

    python tools/demo/voxel_icons.py ICONS
    python tools/demo/demo_server.py ICONS              (keep running)
    capture SHOTS/<name>.png at 1920x1080, --force-device-scale-factor=2 (see docs/PUBLISHING.md)
    python tools/make_promo.py SHOTS docs/images

Writes <out>/workshop/*.jpg (gallery, 1920x1080) and <out>/workshop/banner_*.jpg (description headers).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_preview import MUTED, WHITE, YELLOW, H, W, blueprint_background, font, framed, save_jpeg  # noqa: E402

WORKSHOP_ID = "3840235435"  # the mod's Steam Workshop item (folder name under workshop/content/387990)
DSF = 2  # screenshots are taken at device scale factor 2; crop boxes below are in CSS pixels
PANEL_TOP, PANEL_BOTTOM, MARGIN = 330, 1040, 80
CAPTION_H = 54


def en(size, weight="SemiBold"):
    return font("bahnschrift.ttf", size, weight)


def jp(size, bold=False):
    return font("YuGothB.ttc" if bold else "YuGothM.ttc", size)


def caption_font(text: str, size: int):
    if any("가" <= c <= "힣" for c in text):
        return font("malgunbd.ttf", size)
    if text in ("中文", "简体中文"):  # simplified Chinese glyphs (Yu Gothic would draw Japanese forms)
        return font("msyhbd.ttc", size)
    if any(ord(c) > 0x2e80 for c in text):
        return jp(size, True)
    return en(size)


def crop(shots: Path, name: str, box) -> Image.Image:
    img = Image.open(shots / f"{name}.png").convert("RGB")
    return img.crop(tuple(v * DSF for v in box))


def mixed_title(d: ImageDraw.ImageDraw, x: int, baseline: int, title: str):
    """Big title; runs of CJK / Hangul get a font that has those glyphs."""
    def kind(c):
        return "ko" if "가" <= c <= "힣" else "cj" if ord(c) > 0x2e80 else "en"

    runs = []  # [text, kind]; spaces and punctuation stay with the run before them
    for c in title:
        k = kind(c)
        if runs and (runs[-1][1] == k or k == "en" and not c.isalnum()):
            runs[-1][0] += c
        else:
            runs.append([c, k])
    for r, k in runs:
        f = (en(84, "Bold Condensed") if k == "en" else font("malgunbd.ttf", 70) if k == "ko"
             else font("msyhbd.ttc", 70) if r.strip() == "中文" else jp(70, True))
        d.text((x, baseline), r, font=f, fill=WHITE, anchor="ls")
        x += d.textlength(r, font=f)


def header(img: Image.Image, label: str, title: str, title_jp: str, bullets: list[tuple[str, str]]):
    d = ImageDraw.Draw(img)
    x, y = MARGIN + 10, 70
    d.text((x, y), label, font=en(28), fill=YELLOW)
    mixed_title(d, x - 3, y + 112, title)
    d.text((x, y + 150), title_jp, font=jp(36, True), fill=MUTED)
    bx, by = 1130, 84
    for e, j in bullets:
        d.rectangle([bx, by + 12, bx + 12, by + 24], fill=YELLOW)
        d.text((bx + 28, by), e, font=en(29), fill=WHITE)
        d.text((bx + 28, by + 37), j, font=jp(21), fill=MUTED)
        by += 78


def place_row(img: Image.Image, panels: list[Image.Image], top: int, bottom: int, captions=None, gap=36):
    """Scale the panels to one common height so the row fits between MARGIN and the bottom, centred."""
    room_h = bottom - top - (CAPTION_H if captions else 0) - 40  # 40: frame padding
    room_w = W - 2 * MARGIN - gap * (len(panels) - 1) - 80 * len(panels)
    ratio = sum(p.width / p.height for p in panels)
    h = int(min(room_h, room_w / ratio))
    cards = [framed(p, round(p.width * h / p.height)) for p in panels]
    total = sum(c.width for c in cards) + gap * (len(cards) - 1)
    x = (W - total) // 2
    y = top + (bottom - top - (cards[0].height + (CAPTION_H if captions else 0))) // 2
    d = ImageDraw.Draw(img)
    for i, c in enumerate(cards):
        img.alpha_composite(c, (x, y))
        if captions:
            f = caption_font(captions[i], 30)
            d.text((x + c.width // 2, y + c.height - 6), captions[i], font=f, fill=WHITE, anchor="mt")
        x += c.width + gap


def feature_organize(shots):
    img = blueprint_background()
    header(img, "ORGANIZE", "Folders, tags & favorites", "階層フォルダ・タグ・お気に入りで整理",
           [("Nested folders, #tag search, 3 views", "サブフォルダ・#タグ検索・3種類の表示"),
            ("Select many, then move / tag / hide at once", "まとめて移動・タグ付け・非表示"),
            ("Original blueprint files are never touched", "元のファイルには手を加えません")])
    place_row(img, [crop(shots, "folders_en", (0, 48, 1302, 440)), crop(shots, "folders_en", (1604, 360, 1916, 712))],
              PANEL_TOP, PANEL_BOTTOM)
    return img


def feature_missing(shots):
    img = blueprint_background()
    header(img, "MISSING-MOD CHECK", "No more half-spawned creations", "MOD が足りないものは事前に分かる",
           [("Blueprints needing disabled mods are flagged", "有効でない MOD を使うものに ⚠ マーク"),
            ("Placing them is blocked; sequences skip them", "設置できず、順に設置では飛ばします"),
            ("See which mods are needed, with Steam links", "必要な MOD を Steam のリンク付きで表示")])
    place_row(img, [crop(shots, "missing_en", (0, 48, 720, 380)), crop(shots, "missing_en", (1604, 360, 1916, 810))],
              PANEL_TOP, PANEL_BOTTOM)
    return img


def feature_views(shots):
    img = blueprint_background()
    header(img, "VIEWS", "Three ways to browse", "表示は3種類から選べます",
           [("Large icons, small icons or a detailed list", "大きいアイコン・アイコン・一覧"),
            ("In game and in the browser manager", "ゲーム内でもマネージャーでも"),
            ("Double-click to place right away", "ダブルクリックですぐ設置")])
    box = (262, 96, 1010, 440)
    place_row(img, [crop(shots, n, box) for n in ("viewL_en", "viewG_en", "viewR_en")], PANEL_TOP, PANEL_BOTTOM,
              captions=["Large  /  大", "Icons  /  中", "List  /  一覧"], gap=28)
    return img


def feature_languages(shots):
    img = blueprint_background()
    header(img, "LANGUAGES", "English · 日本語 · 한국어 · 中文", "4言語に対応",
           [("In game: follows the game's language", "ゲーム内：ゲームの言語設定に合わせます"),
            ("Manager: follows your browser", "マネージャー：ブラウザの言語に合わせます"),
            ("Or pick one at the top right", "右上の欄でも切り替えできます")])
    box = (0, 0, 1010, 300)
    mid = (PANEL_TOP + PANEL_BOTTOM) // 2 + 8
    place_row(img, [crop(shots, "lang_en", box), crop(shots, "lang_ja", box)], PANEL_TOP, mid,
              captions=["English", "日本語"])
    place_row(img, [crop(shots, "lang_ko", box), crop(shots, "lang_zh", box)], mid - 8, PANEL_BOTTOM + 10,
              captions=["한국어", "中文"])
    return img


def getting_started(_shots):
    img = blueprint_background()
    d = ImageDraw.Draw(img)
    x = MARGIN + 10
    d.text((x, 70), "GETTING STARTED", font=en(28), fill=YELLOW)
    d.text((x - 3, 110), "First: run the included Manager", font=en(84, "Bold Condensed"), fill=WHITE)
    d.text((x, 220), "最初に、同梱のマネージャーを起動します（Python 3.10 以上が必要）", font=jp(36, True), fill=MUTED)
    steps = [
        ("Open this mod's folder", "この MOD のフォルダを開く",
         "<Steam library>\\steamapps\\workshop\\content\\387990\\" + WORKSHOP_ID + "\\"),
        ("Double-click  Blueprint Lib Manager.bat", "Blueprint Lib Manager.bat をダブルクリック",
         "The manager opens in your browser / ブラウザで管理画面が開きます"),
        ("Press  Rescan", "「再スキャン」を押す",
         "Your blueprints are listed (files are only read) / 一覧を作ります（読み取るだけ）"),
        ("In a Creative world: take the tool, right-click", "MOD を有効にしたクリエイティブのワールドで、ツールを持って右クリック",
         "Enable the mod in the world first / ワールドで MOD を有効に"),
    ]
    y = 320
    for i, (e, j, sub) in enumerate(steps, 1):
        d.rounded_rectangle([x, y, x + 96, y + 96], 14, fill=YELLOW)
        d.text((x + 48, y + 50), str(i), font=en(64, "Bold"), fill=(14, 40, 74), anchor="mm")
        d.text((x + 130, y - 2), e, font=en(44), fill=WHITE)
        d.text((x + 130, y + 54), j, font=jp(28, True), fill=MUTED)
        if i == 1:
            f = font("consola.ttf", 32)
            sub = sub.strip()
            w = d.textlength(sub, font=f)
            d.rounded_rectangle([x + 130, y + 108, x + 130 + w + 44, y + 170], 10, fill=(6, 20, 40), outline=(90, 130, 180))
            d.text((x + 152, y + 139), sub, font=f, fill=(210, 230, 255), anchor="lm")
            y += 80
        y += 150
    d.text((x, H - 66), "Can't find the Steam library?   Steam:  right-click Scrap Mechanic  >  Manage  >  "
           "Browse local files, then go up two folders to steamapps.", font=en(24, "SemiLight"), fill=MUTED)
    return img


BANNERS = {
    "first": ("FIRST STEP", "最初に"),
    "features": ("FEATURES", "特徴"),
    "controls": ("CONTROLS", "操作"),
    "notes": ("NOTES", "注意"),
}


def banner(en_text: str, jp_text: str) -> Image.Image:
    """A 1280x150 section header for the Workshop description."""
    bw, bh = 1280, 150
    img = blueprint_background().crop((0, 300, bw, 300 + bh))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 14, bh], fill=YELLOW)
    f = en(92, "Bold Condensed")
    d.text((56, bh // 2 + 4), en_text, font=f, fill=WHITE, anchor="lm")
    w = d.textlength(en_text, font=f)
    d.text((56 + w + 34, bh // 2 + 10), jp_text, font=jp(46, True), fill=YELLOW, anchor="lm")
    return img


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("shots", type=Path)
    ap.add_argument("out", type=Path)
    a = ap.parse_args()
    out = a.out / "workshop"
    out.mkdir(parents=True, exist_ok=True)
    for name, fn in [("1_getting_started", getting_started), ("2_organize", feature_organize),
                     ("3_missing_mods", feature_missing), ("4_languages", feature_languages)]:
        save_jpeg(fn(a.shots).convert("RGB"), out / f"{name}.jpg")
    for key, (e, j) in BANNERS.items():
        save_jpeg(banner(e, j).convert("RGB"), out / f"banner_{key}.jpg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
