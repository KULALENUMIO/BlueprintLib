"""Blueprint Lib - release helper.

  python tools/release.py check            what would be uploaded to the Workshop, and what's wrong
  python tools/release.py prepare-upload   move your personal data out of Mod/ (to %APPDATA%), then check
  python tools/release.py restore          put the data moved by prepare-upload back
  python tools/release.py zip              build dist/BlueprintLib-<version>.zip for a GitHub release

The Scrap Mechanic Mod Tool uploads the whole mod folder - which also carries the manager
(Mod/Blueprint Lib Manager.bat + Mod/Manager/). Mod/Data/*.json (your blueprint list and library),
Mod/Cache/ and Python caches must not be in it at upload time. prepare-upload stashes them;
starting the manager (or `restore`) brings them back.
"""
from __future__ import annotations

import fnmatch
import json
import shutil
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MOD = ROOT / "Mod"
sys.path.insert(0, str(MOD / "Manager" / "tools"))  # br_paths ships with the manager inside the mod
import br_paths  # noqa: E402

VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip() if (ROOT / "VERSION").is_file() else "0.0.0"

# Only these files are part of the published mod (paths relative to Mod/, glob syntax).
MOD_ALLOW = [
    "description.json", "preview.jpg",
    "Data/README.txt",
    "Gui/*.png", "Gui/*.xml", "Gui/Layouts/*.layout", "Gui/Language/*/*.json",
    "Objects/Database/*.shapedb",
    "Scripts/*.lua",
    "Tools/Database/*.tooldb", "Tools/Database/ToolSets/*.toolset",
    # the browser manager ships inside the mod (Workshop subscribers get it too)
    "Blueprint Lib Manager.bat",
    "Manager/tools/*.py", "Manager/tools/*.bat",
    "Manager/web/*.html", "Manager/web/*.js", "Manager/web/*.css", "Manager/web/*.png",
]
PERSONAL = ["Data/index.json", "Data/library.json", "Data/request.json", "Data/*.tmp"]
GENERATED_DIRS = ["Cache"]
# Files of the GitHub release zip besides the mod folder (relative to the repository root).
TOOLS_ALLOW = ["README.md", "README.en.md", "LICENSE", "VERSION"]
ZIP_MOD_FOLDER = "Blueprint Lib"  # in the zip the mod is ready to be copied into the game's Mods folder
PREVIEW_MAX_BYTES = 1_000_000


def rel(p: Path, base: Path) -> str:
    return p.relative_to(base).as_posix()


def allowed(path: str) -> bool:
    return any(fnmatch.fnmatch(path, pat) for pat in MOD_ALLOW)


def generated(path: str) -> bool:
    parts = path.split("/")
    return parts[0] in GENERATED_DIRS or "__pycache__" in parts or path.endswith(".pyc")


def check() -> int:
    problems, files = [], []
    for p in sorted(MOD.rglob("*")):
        if p.is_dir():
            continue
        r = rel(p, MOD)
        if generated(r):
            problems.append(f"generated cache would be uploaded: {r}  (run prepare-upload)")
        elif any(fnmatch.fnmatch(r, pat) for pat in PERSONAL):
            problems.append(f"PERSONAL data would be uploaded: {r}  (run prepare-upload)")
        elif not allowed(r):
            problems.append(f"unexpected file: {r}")
        else:
            files.append((r, p.stat().st_size))
    preview = MOD / "preview.jpg"
    if not preview.is_file():
        problems.append("preview.jpg missing (Workshop image, 1920x1080 recommended)")
    elif preview.stat().st_size > PREVIEW_MAX_BYTES:
        problems.append(f"preview.jpg is {preview.stat().st_size // 1024} KB (keep it under ~1 MB)")
    desc = json.loads((MOD / "description.json").read_text(encoding="utf-8-sig"))
    if str(desc.get("localId", "")).lower() != br_paths.MOD_ID:
        problems.append("description.json localId changed - the tools would no longer find the mod")

    print(f"Blueprint Lib {VERSION} - files that would be uploaded ({len(files)}):")
    for r, size in files:
        print(f"  {r:60s} {size:>9,d} B")
    print("Workshop item:", f"fileId {desc['fileId']} (update)" if desc.get("fileId") else "not published yet (new item)")
    if problems:
        print("\nPROBLEMS:")
        for p in problems:
            print("  - " + p)
        return 1
    print("\nOK - ready to upload with the Scrap Mechanic Mod Tool.")
    return 0


def stash_root() -> Path:
    return br_paths.backup_dir() / "upload-stash"


def prepare_upload() -> int:
    data = MOD / "Data"
    br_paths.backup_library(data)
    stash = stash_root() / time.strftime("%Y%m%d-%H%M%S")
    moved = 0
    for p in sorted(MOD.rglob("*")):
        if p.is_dir():
            continue
        r = rel(p, MOD)
        if generated(r) or any(fnmatch.fnmatch(r, pat) for pat in PERSONAL):
            dst = stash / r
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), dst)
            moved += 1
    for d in GENERATED_DIRS:
        if (MOD / d).is_dir():
            shutil.rmtree(MOD / d, ignore_errors=True)
    for d in MOD.rglob("__pycache__"):
        shutil.rmtree(d, ignore_errors=True)
    print(f"moved {moved} personal/generated files to {stash}")
    print("Close the game before uploading. Afterwards run `release.py restore` (or just start the manager).\n")
    return check()


def restore() -> int:
    stashes = sorted(stash_root().glob("*")) if stash_root().is_dir() else []
    if not stashes:
        print("nothing to restore")
        return 0
    latest = stashes[-1]
    back = 0
    for p in sorted(latest.rglob("*")):
        if p.is_file():
            r = rel(p, latest)
            if generated(r):
                continue  # the game / Python rebuild their caches
            dst = MOD / r
            if not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, dst)
                back += 1
    print(f"restored {back} files from {latest}")
    msg = br_paths.restore_library(MOD / "Data")
    if msg:
        print(msg)
    return 0


def make_zip() -> int:
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    out = dist / f"BlueprintLib-{VERSION}.zip"
    top = f"BlueprintLib-{VERSION}"
    missing = [f for f in TOOLS_ALLOW if not (ROOT / f).is_file()]
    if missing:
        print("missing files:", ", ".join(missing))
        return 1
    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in TOOLS_ALLOW:
            z.write(ROOT / f, f"{top}/{f}")
            count += 1
        for p in sorted(MOD.rglob("*")):
            if p.is_file() and allowed(rel(p, MOD)):
                z.write(p, f"{top}/{ZIP_MOD_FOLDER}/{rel(p, MOD)}")
                count += 1
    print(f"wrote {out} ({count} files, {out.stat().st_size // 1024} KB) - personal data excluded")
    return 0


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    return {"check": check, "prepare-upload": prepare_upload, "restore": restore, "zip": make_zip}.get(
        cmd, lambda: (print(__doc__), 2)[1])()


if __name__ == "__main__":
    raise SystemExit(main())
