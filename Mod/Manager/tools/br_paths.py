"""Blueprint Lib - where things live, shared by sync_index.py, manager_server.py and release.py.

The manager ships inside the mod (<mod>/Manager/tools/this file), so normally the mod folder is
simply two levels up - wherever the mod is installed:
  - a Steam Workshop subscription: <steam library>/steamapps/workshop/content/387990/<file id>/
  - a local copy in %APPDATA%/Axolot Games/Scrap Mechanic/User/User_*/Mods/<any name>/
  - this repository's Mod/ folder (development, linked into the game's Mods folder)
If the manager was copied somewhere else, those places are searched. The mod is identified by the
localId in its description.json, never by folder name.

The in-game tool can only write inside its own mod folder, and Steam may replace that folder when
the Workshop item is updated. So the user's library.json is also backed up to
%APPDATA%/BlueprintLib/ and restored from there when the mod's copy is missing or older.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import time
from pathlib import Path

MOD_ID = "cbd434bf-4b67-4bc1-b367-f35c1618b74a"
OWN_MOD = Path(__file__).resolve().parents[2]  # <mod>/Manager/tools/br_paths.py -> <mod>
STEAM_DEFAULT = Path(r"C:\Program Files (x86)\Steam")
SM_APP_ID = "387990"
HISTORY_KEEP = 20


def _read_json(path: Path):
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def is_our_mod(folder: Path) -> bool:
    desc = _read_json(folder / "description.json")
    return isinstance(desc, dict) and str(desc.get("localId", "")).lower() == MOD_ID


def user_root() -> Path | None:
    appdata = os.environ.get("APPDATA")
    return Path(appdata) / "Axolot Games" / "Scrap Mechanic" / "User" if appdata else None


def steam_libraries() -> list[Path]:
    libs = [STEAM_DEFAULT]
    vdf = STEAM_DEFAULT / "steamapps" / "libraryfolders.vdf"
    if vdf.is_file():
        text = vdf.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r'"path"\s+"([^"]+)"', text):
            p = Path(m.group(1).replace("\\\\", "\\"))
            if p not in libs:
                libs.append(p)
    return libs


def find_mod_dir(explicit: Path | None = None) -> Path | None:
    """The installed mod folder (see module docstring for the search order)."""
    if explicit:
        return explicit if is_our_mod(explicit) else None
    if is_our_mod(OWN_MOD):  # the mod this manager came with
        return OWN_MOD
    root = user_root()
    if root and root.is_dir():
        for mods in sorted(root.glob("User_*/Mods")):
            for d in sorted(mods.iterdir()):
                if d.is_dir() and is_our_mod(d):
                    return d
    for lib in steam_libraries():
        ws = lib / "steamapps" / "workshop" / "content" / SM_APP_ID
        if ws.is_dir():
            for d in sorted(ws.iterdir()):
                if d.is_dir() and is_our_mod(d):
                    return d
    return None


def backup_dir() -> Path:
    base = Path(os.environ.get("APPDATA") or str(Path.home()))
    new = base / "BlueprintLib"
    old = base / "BlueprintRebuild"  # name used before the project was renamed
    if old.is_dir() and not new.exists():
        try:
            old.rename(new)
        except OSError:
            pass  # e.g. a file inside is open: keep using the new (empty) folder, nothing is lost
    return new


def _rev(lib) -> int:
    try:
        return int(float((lib or {}).get("rev") or 0))
    except (TypeError, ValueError, AttributeError):
        return 0


def backup_library(data_dir: Path) -> bool:
    """Copy data_dir/library.json to the backup folder when it is newer than the backup.
    Also keeps a short history of previous versions. Returns True when a copy was made."""
    src = data_dir / "library.json"
    lib = _read_json(src)
    if not isinstance(lib, dict):
        return False  # missing or unreadable right now: never back up garbage
    dst_dir = backup_dir()
    dst = dst_dir / "library.json"
    old = _read_json(dst)
    if isinstance(old, dict) and (old == lib or _rev(old) > _rev(lib)):
        return False  # unchanged, or the backup is newer (then restore_library is what's needed)
    dst_dir.mkdir(parents=True, exist_ok=True)
    if dst.is_file():
        hist = dst_dir / "history"
        hist.mkdir(exist_ok=True)
        shutil.copy2(dst, hist / f"library-{time.strftime('%Y%m%d-%H%M%S')}-rev{_rev(old)}.json")
        for stale in sorted(hist.glob("library-*.json"))[:-HISTORY_KEEP]:
            stale.unlink(missing_ok=True)
    tmp = dst.with_suffix(".tmp")
    shutil.copy2(src, tmp)
    os.replace(tmp, dst)
    return True


def restore_library(data_dir: Path) -> str | None:
    """If the mod's library.json is missing (e.g. wiped by a Workshop update) or older than the
    backup, put the backup back. Returns a short message when something was restored."""
    backup = backup_dir() / "library.json"
    saved = _read_json(backup)
    if not isinstance(saved, dict):
        return None
    target = data_dir / "library.json"
    current = _read_json(target)
    if target.exists() and not isinstance(current, dict):
        return None  # exists but unreadable (game mid-write?) - leave it alone
    if isinstance(current, dict) and _rev(current) >= _rev(saved):
        return None
    data_dir.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    shutil.copy2(backup, tmp)
    os.replace(tmp, target)
    return f"library.json restored from backup (rev {_rev(saved)})"
