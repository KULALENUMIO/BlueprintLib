"""Generates Mod/Gui/Layouts/BlueprintLib.layout (MyGUI).

Widget names here are the contract with Scripts/BlueprintLib.lua (VIEWS / FOLDER_ROWS / CHIP_COUNT).
Visible captions are overwritten from Lua (Japanese / English), so the ones here are fallbacks.

Views (only one container is visible at a time):
  L = large icons  4x3   LItem{i} / LIcon{i} / LName{i} / LCheck{i}
  G = icons        6x4   GItem{i} / GIcon{i} / GName{i} / GCheck{i}
  R = list rows    10    RItem{i} / RIcon{i} / RName{i} / RCheck{i} / RInfo{i}
"""
from pathlib import Path
from xml.sax.saxutils import quoteattr

FOLDER_ROWS = 12
CHIP_COUNT = 8
VIEWS = {"L": (4, 3), "G": (6, 4)}
LIST_ROWS = 10

OUT = Path(__file__).resolve().parent.parent / "Mod" / "Gui" / "Layouts" / "BlueprintLib.layout"


def f(v):
    return f"{v:.5f}".rstrip("0").rstrip(".")


class W:
    def __init__(self, type_, skin, name, x, y, w, h, **props):
        self.type, self.skin, self.name = type_, skin, name
        self.rect = (x, y, w, h)
        self.props = props
        self.children = []

    def add(self, *ws):
        self.children.extend(ws)
        return self

    def xml(self, ind=1):
        pad = "\t" * ind
        x, y, w, h = self.rect
        s = f'{pad}<Widget type="{self.type}" skin="{self.skin}" name="{self.name}" position_real="{f(x)} {f(y)} {f(w)} {f(h)}">\n'
        for k, v in self.props.items():
            s += f'{pad}\t<Property key="{k}" value={quoteattr(str(v))} />\n'
        for c in self.children:
            s += c.xml(ind + 1)
        return s + f"{pad}</Widget>\n"


def text(name, x, y, w, h, caption="", font="SM_TextTiny", align="Left VCenter", **kw):
    return W("TextBox", "TextBox", name, x, y, w, h, Caption=caption, FontName=font, TextAlign=align,
             NeedMouse="false", NeedKey="false", **kw)


def button(name, x, y, w, h, caption, skin="SettingsButton", font="SM_ButtonSmall"):
    return W("Button", skin, name, x, y, w, h, Caption=caption, FontName=font, TextAlign="Center")


def toggle(name, x, y, w, h, caption):
    return button(name, x, y, w, h, caption, skin="ToggleButton")


def edit(name, x, y, w, h):
    bg = W("Widget", "SearchBarBackground", name + "Bg", x, y, w, h)
    bg.add(W("EditBox", "EditBoxEmpty", name, 0.03, 0, 0.94, 1,
             FontName="SM_SearchText", TextAlign="Left VCenter", ReadOnly="false", Static="false"))
    return bg


def image(name, x, y, w, h, texture=None):
    props = dict(NeedMouse="false", NeedKey="false")
    if texture:
        props["ImageTexture"] = texture
    return W("ImageBox", "ImageBox", name, x, y, w, h, **props)


def container(name, x, y, w, h):
    return W("Widget", "PanelEmpty", name, x, y, w, h)


# $CONTENT_DATA is NOT expanded inside layout files (game log: "Unable to replace key"),
# so images referenced here need the mod's explicit content id. Lua sets them again at runtime.
MOD_ID = "cbd434bf-4b67-4bc1-b367-f35c1618b74a"
CHECK = f"$CONTENT_{MOD_ID}/Gui/check.png"
WARN = f"$CONTENT_{MOD_ID}/Gui/warn.png"

root = W("Widget", "BackgroundLiftImport", "BackPanel", 0, 0, 0.854688, 0.741667)
root.add(text("Title", 0.03, 0.045, 0.94, 0.06, "BLUEPRINT LIB", font="SM_HeaderLarge_Wide", align="Center"))

# ---- left: folders / tags -----------------------------------------------------------
left = W("Widget", "BackgroundPanel", "LeftPanel", 0.025, 0.13, 0.18, 0.83)
left.add(toggle("TabFolders", 0.05, 0.015, 0.44, 0.05, "Folders"))
left.add(toggle("TabTags", 0.51, 0.015, 0.44, 0.05, "Tags"))
left.add(text("DropHint", 0.05, 0.07, 0.9, 0.035, "", align="Center", TextColour="#F4C846"))
fy, fstep, fh = 0.11, 0.056, 0.05
for i in range(FOLDER_ROWS):
    fb = toggle(f"Folder{i}", 0.05, fy + i * fstep, 0.9, fh, f"Folder {i}")
    fb.props["TextAlign"] = "Left VCenter"  # tree indentation needs left alignment
    left.add(fb)
py = fy + FOLDER_ROWS * fstep + 0.006
left.add(W("Button", "DressbotArrowLeft", "FolderPrev", 0.05, py, 0.14, 0.045, NeedMouse="true"))
left.add(text("FolderPage", 0.2, py, 0.6, 0.045, "1/1", align="Center"))
left.add(W("Button", "DressbotArrowRight", "FolderNext", 0.81, py, 0.14, 0.045, NeedMouse="true"))
left.add(edit("FolderInput", 0.05, 0.85, 0.9, 0.05))
left.add(button("CreateFolder", 0.05, 0.91, 0.29, 0.05, "Create"))
left.add(button("RenameFolder", 0.355, 0.91, 0.29, 0.05, "Rename"))
left.add(button("DeleteFolder", 0.66, 0.91, 0.29, 0.05, "Delete"))
root.add(left)

# ---- center: search + toolbar + views -----------------------------------------------------
center = W("Widget", "BackgroundPanel", "CenterPanel", 0.215, 0.13, 0.47, 0.83)
center.add(edit("Search", 0.03, 0.02, 0.94, 0.055))
ty, th = 0.085, 0.048
center.add(toggle("ViewL", 0.03, ty, 0.08, th, "L"))
center.add(toggle("ViewG", 0.115, ty, 0.08, th, "M"))
center.add(toggle("ViewR", 0.2, ty, 0.08, th, "List"))
center.add(button("Sort", 0.29, ty, 0.19, th, "Sort"))
center.add(toggle("SelectMode", 0.49, ty, 0.17, th, "Multi"))
center.add(button("SelectAll", 0.67, ty, 0.145, th, "All"))
center.add(button("SelectNone", 0.825, ty, 0.145, th, "None"))

VX, VY, VW, VH = 0.03, 0.145, 0.94, 0.74
for p, (cols, rows) in VIEWS.items():
    panel = container(f"View{p}Panel", VX, VY, VW, VH)
    cw, ch = 1 / cols, 1 / rows
    for r in range(rows):
        for c in range(cols):
            i = r * cols + c
            cell = W("Button", "ContainerItemBackground", f"{p}Item{i}",
                     c * cw + 0.004, r * ch + 0.005, cw - 0.008, ch - 0.01, NeedKey="false")
            cell.add(image(f"{p}Icon{i}", 0.1, 0.05, 0.8, 0.68))
            cell.add(text(f"{p}Name{i}", 0.03, 0.74, 0.94, 0.24, "", align="Center"))
            cell.add(image(f"{p}Check{i}", 0.04, 0.03, 0.24, 0.2, CHECK))
            cell.add(image(f"{p}Warn{i}", 0.72, 0.03, 0.24, 0.2, WARN))  # missing mods
            panel.add(cell)
    center.add(panel)

panel = container("ViewRPanel", VX, VY, VW, VH)
rh = 1 / LIST_ROWS
for i in range(LIST_ROWS):
    row = W("Button", "ContainerItemBackground", f"RItem{i}", 0, i * rh + 0.004, 1, rh - 0.008, NeedKey="false")
    row.add(image(f"RIcon{i}", 0.008, 0.08, 0.054, 0.84))
    row.add(image(f"RCheck{i}", 0.008, 0.08, 0.03, 0.45, CHECK))
    row.add(image(f"RWarn{i}", 0.035, 0.47, 0.03, 0.45, WARN))
    row.add(text(f"RName{i}", 0.075, 0, 0.42, 1, ""))
    row.add(text(f"RInfo{i}", 0.5, 0, 0.49, 1, "", TextColour="#8B999F"))
    panel.add(row)
center.add(panel)

center.add(text("Status", 0.03, 0.9, 0.32, 0.06, "0"))
center.add(W("Button", "DressbotArrowLeft", "GridPrev", 0.36, 0.905, 0.05, 0.05, NeedMouse="true"))
center.add(text("GridPage", 0.42, 0.9, 0.16, 0.06, "1/1", align="Center"))
center.add(W("Button", "DressbotArrowRight", "GridNext", 0.59, 0.905, 0.05, 0.05, NeedMouse="true"))
center.add(button("Reload", 0.72, 0.9, 0.25, 0.06, "Reload"))
root.add(center)

# ---- right: detail / bulk actions --------------------------------------------------------
right = W("Widget", "BackgroundPanel", "RightPanel", 0.695, 0.13, 0.28, 0.83)
right.add(image("DetailIcon", 0.282, 0.02, 0.436, 0.27))
right.add(text("DetailName", 0.04, 0.295, 0.92, 0.045, "-", font="SM_ItemTitle", align="Center"))
right.add(text("DetailInfo", 0.04, 0.34, 0.92, 0.035, "", align="Center"))
right.add(text("DetailFolder", 0.04, 0.375, 0.92, 0.035, ""))
right.add(text("TagHeader", 0.04, 0.41, 0.92, 0.035, "Tags", TextColour="#8B999F"))
for i in range(CHIP_COUNT):
    r, c = divmod(i, 2)
    right.add(button(f"Chip{i}", 0.04 + c * 0.47, 0.45 + r * 0.051, 0.45, 0.045, "tag"))
right.add(edit("TagInput", 0.04, 0.66, 0.62, 0.05))
right.add(button("AddTag", 0.68, 0.66, 0.28, 0.05, "Add"))
right.add(toggle("DropMode", 0.04, 0.72, 0.92, 0.05, "Put into..."))
right.add(button("Unfile", 0.04, 0.78, 0.29, 0.05, "Unfile"))
right.add(button("Favorite", 0.355, 0.78, 0.29, 0.05, "Fav"))
right.add(button("Hide", 0.67, 0.78, 0.29, 0.05, "Hide"))
right.add(text("DetailWarn", 0.04, 0.835, 0.92, 0.035, "", align="Center"))
right.add(button("Place", 0.1, 0.875, 0.8, 0.08, "PLACE", skin="StyledButtonLarge", font="SM_Button"))
disabled = button("PlaceDisabled", 0.1, 0.875, 0.8, 0.08, "MISSING MODS", skin="StyledButtonLarge", font="SM_Button")
disabled.props["Enabled"] = "false"  # same trick as the game's lift import button
disabled.props["Visible"] = "false"
right.add(disabled)
root.add(right)

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text('<?xml version="1.0" encoding="UTF-8" ?>\n<MyGUI type="Layout" version="3.2.0">\n'
               + root.xml() + "\t<CodeGeneratorSettings />\n</MyGUI>\n", encoding="utf-8")
print(f"wrote {OUT}")
