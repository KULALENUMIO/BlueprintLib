"""Blueprint Lib - index sync

Scans the user's Scrap Mechanic blueprint folders (read only) and writes
Mod/Data/index.json, which the in-game tool uses to list blueprints.
The Lua sandbox cannot list directories, so this step has to run outside the game.

For every blueprint the index also lists the non-vanilla shape uuids it uses, grouped by the mod
they come from, so the game can tell (with sm.shape.uuidExists) whether it can be spawned in the
current world and which mods are missing.

Usage:
    python sync_index.py            # writes <mod>/Data/index.json (the mod this script ships in)
    python sync_index.py --out PATH # custom output path
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

SM_APP_ID = "387990"
DEFAULT_STEAM = Path(r"C:\Program Files (x86)\Steam")
SHAPE_LIST_KEYS = ("blockList", "partList", "wedgeList", "jointList")


def read_json(path: Path):
    # Blueprint json files are UTF-8; some older ones carry a BOM.
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def user_root() -> Path | None:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    return Path(appdata) / "Axolot Games" / "Scrap Mechanic" / "User"


def user_blueprint_dirs() -> list[Path]:
    root = user_root()
    if not root:
        return []
    return sorted(p / "Blueprints" for p in root.glob("User_*") if (p / "Blueprints").is_dir())


def user_mod_dirs() -> list[Path]:
    root = user_root()
    if not root:
        return []
    return sorted(p / "Mods" for p in root.glob("User_*") if (p / "Mods").is_dir())


def steam_libraries() -> list[Path]:
    libs = [DEFAULT_STEAM]
    vdf = DEFAULT_STEAM / "steamapps" / "libraryfolders.vdf"
    if vdf.is_file():
        text = vdf.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r'"path"\s+"([^"]+)"', text):
            p = Path(m.group(1).replace("\\\\", "\\"))
            if p not in libs:
                libs.append(p)
    return libs


def workshop_dirs() -> list[Path]:
    out = []
    for lib in steam_libraries():
        d = lib / "steamapps" / "workshop" / "content" / SM_APP_ID
        if d.is_dir():
            out.append(d)
    return out


def game_dir() -> Path | None:
    for lib in steam_libraries():
        d = lib / "steamapps" / "common" / "Scrap Mechanic"
        if (d / "Data").is_dir():
            return d
    return None


def shape_uuids_in(files) -> set[str]:
    out = set()
    for f in files:
        try:
            d = read_json(f)
        except (OSError, ValueError):
            continue
        if not isinstance(d, dict):
            continue
        for key in SHAPE_LIST_KEYS:
            for e in d.get(key) or []:
                if isinstance(e, dict) and isinstance(e.get("uuid"), str):
                    out.add(e["uuid"].lower())
    return out


def vanilla_shapes() -> set[str]:
    g = game_dir()
    if not g:
        print("  warning: game folder not found, every shape is treated as modded", file=sys.stderr)
        return set()
    files = [f for f in g.rglob("*.shapeset") if "ExampleMods" not in f.parts]
    return shape_uuids_in(files)


def installed_mod_shapes() -> dict[str, dict]:
    """uuid -> {"name", "fileId"} for every installed (workshop or local) part mod."""
    owners: dict[str, dict] = {}
    roots = [(d, "workshop") for d in workshop_dirs()] + [(d, "local") for d in user_mod_dirs()]
    for root, _ in roots:
        for mod in root.iterdir():
            desc_path = mod / "description.json"
            shapes_dir = mod / "Objects" / "Database" / "ShapeSets"
            if not desc_path.is_file() or not shapes_dir.is_dir():
                continue
            try:
                desc = read_json(desc_path)
            except (OSError, ValueError):
                continue
            info = {"name": str(desc.get("name") or mod.name)}
            if desc.get("fileId"):
                info["fileId"] = str(desc["fileId"])
            files = list(shapes_dir.glob("*.json")) + list(shapes_dir.glob("*.shapeset"))
            for u in shape_uuids_in(files):
                owners.setdefault(u, info)
    return owners


UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def blueprint_id(desc: dict, folder: Path) -> str | None:
    """The blueprint's localId (lower-case uuid), falling back to the folder name. Anything that is
    not a uuid is rejected: ids end up in file paths, HTML attributes and game content paths."""
    for cand in (desc.get("localId"), folder.name):
        if isinstance(cand, str) and UUID_RE.match(cand.lower()):
            return cand.lower()
    return None


def _dicts(v) -> list[dict]:
    return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []


def required_mods(bp: dict, vanilla: set[str], owners: dict[str, dict]) -> list[dict]:
    """Group the blueprint's non-vanilla shape uuids by the mod that provides them."""
    if not isinstance(bp, dict):
        raise ValueError("blueprint.json is not an object")
    used = set()
    for body in _dicts(bp.get("bodies")):
        for child in _dicts(body.get("childs")):
            if isinstance(child.get("shapeId"), str):
                used.add(child["shapeId"].lower())
    for joint in _dicts(bp.get("joints")):
        if isinstance(joint.get("shapeId"), str):
            used.add(joint["shapeId"].lower())
    modded = used - vanilla
    if not modded:
        return []

    groups: dict[str, dict] = {}
    remaining = set(modded)
    for dep in _dicts(bp.get("dependencies")):
        shape_ids = dep.get("shapeIds") if isinstance(dep.get("shapeIds"), list) else []
        ids = {s.lower() for s in shape_ids if isinstance(s, str)} & remaining
        if not ids:
            continue
        key = str(dep.get("contentId") or dep.get("name"))
        g = groups.setdefault(key, {"name": str(dep.get("name") or "?"), "shapes": []})
        if dep.get("steamFileId"):
            g["fileId"] = str(dep["steamFileId"])
        g["shapes"].extend(sorted(ids))
        remaining -= ids
    for u in sorted(remaining):  # not declared in dependencies: look it up in installed mods
        owner = owners.get(u)
        key = "owner:" + owner["name"] if owner else "unknown"
        g = groups.setdefault(key, {"name": owner["name"] if owner else "?", "shapes": []})
        if owner and owner.get("fileId"):
            g["fileId"] = owner["fileId"]
        g["shapes"].append(u)
    return list(groups.values())


def scan_folder(folder: Path, source: str, seen: dict, vanilla: set[str], owners: dict, stats: dict,
                paths: dict | None = None) -> int:
    count = 0
    for entry in folder.iterdir():
        if not entry.is_dir():
            continue
        desc_path = entry / "description.json"
        bp_path = entry / "blueprint.json"
        if not desc_path.is_file() or not bp_path.is_file():
            continue
        try:
            desc = read_json(desc_path)
        except (OSError, ValueError) as e:
            print(f"  skip (bad description.json): {entry.name}: {e}", file=sys.stderr)
            continue
        if not isinstance(desc, dict) or desc.get("type", "Blueprint") != "Blueprint":
            continue
        local_id = blueprint_id(desc, entry)
        if not local_id:
            print(f"  skip (localId is not a uuid): {entry.name}", file=sys.stderr)
            continue
        if local_id in seen:
            continue
        item = {
            "id": local_id,
            "name": str(desc.get("name") or entry.name),
            "source": source,
            "mtime": int(bp_path.stat().st_mtime),
            "hasIcon": (entry / "icon.png").is_file(),
        }
        if source == "workshop" and desc.get("fileId"):
            item["fileId"] = str(desc["fileId"])  # 64-bit ids break sm.json, keep as string
        try:
            mods = required_mods(read_json(bp_path), vanilla, owners)
        except Exception as e:  # one malformed blueprint must not abort the whole scan
            print(f"  warning: could not read blueprint.json of {entry.name}: {e}", file=sys.stderr)
            mods = None
        if mods:
            item["mods"] = mods
            stats["modded"] += 1
            if any(m["name"] == "?" for m in mods):
                stats["unknown"] += 1
        elif mods is None:
            item["modsUnknown"] = True
        seen[local_id] = item
        if paths is not None:
            paths[local_id] = entry
        count += 1
    return count


def build_index(out: Path, log=print) -> tuple[dict, dict[str, Path]]:
    """Scan everything and write index.json. Returns (payload, {blueprint id: folder})."""
    vanilla = vanilla_shapes()
    owners = installed_mod_shapes()
    log(f"vanilla shapes {len(vanilla)}, shapes from installed mods {len(owners)}")

    seen: dict[str, dict] = {}
    paths: dict[str, Path] = {}
    stats = {"modded": 0, "unknown": 0}
    for d in user_blueprint_dirs():
        n = scan_folder(d, "local", seen, vanilla, owners, stats, paths)
        log(f"local    {n:5d}  {d}")
    for d in workshop_dirs():
        n = scan_folder(d, "workshop", seen, vanilla, owners, stats, paths)
        log(f"workshop {n:5d}  {d}")

    items = sorted(seen.values(), key=lambda x: x["mtime"], reverse=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 2, "generated": int(time.time()), "count": len(items), "blueprints": items}
    tmp = out.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, out)
    log(f"wrote {len(items)} blueprints ({stats['modded']} use mod parts, "
        f"{stats['unknown']} with parts of unknown origin) -> {out}")
    return payload, paths


def installed_mods() -> list[dict]:
    """Installed part mods (workshop + local) as [{name, fileId?, localId}] for the web manager."""
    out = []
    for root in workshop_dirs() + user_mod_dirs():
        for mod in root.iterdir():
            desc_path = mod / "description.json"
            if not desc_path.is_file():
                continue
            try:
                desc = read_json(desc_path)
            except (OSError, ValueError):
                continue
            if desc.get("type") not in ("Blocks and Parts", "Custom Game"):
                continue
            item = {"name": str(desc.get("name") or mod.name), "localId": str(desc.get("localId") or "")}
            if desc.get("fileId"):
                item["fileId"] = str(desc["fileId"])
            out.append(item)
    return out


def main() -> int:
    import br_paths  # same folder

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, help="index.json to write (default: the installed mod's Data folder)")
    ap.add_argument("--mod-dir", type=Path, help="the mod folder, if it can't be found automatically")
    args = ap.parse_args()
    out = args.out
    if out is None:
        mod = br_paths.find_mod_dir(args.mod_dir)
        if not mod:
            print("Blueprint Lib mod not found. Subscribe to it on the Steam Workshop (or put it in "
                  "your Mods folder), start the game once, then run this again. "
                  "You can also pass --mod-dir <folder>.", file=sys.stderr)
            return 1
        out = mod / "Data" / "index.json"
        msg = br_paths.restore_library(out.parent)
        if msg:
            print(msg)
        br_paths.backup_library(out.parent)
    build_index(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
