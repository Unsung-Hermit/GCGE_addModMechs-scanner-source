"""Shared scanner for GCGE_addModMechs (plan 5d option A).

Modes:
  all  — scan every mod under the parent Mods folder; rewrite gui_config.ini
  one  — scan *.pak next to the calling bat; merge into adjacent gui_config.ini

Tool search (repak / UAssetGUI): bat folder → this Tools folder → PATH.
(MW5_TOOLS\\bin is an optional silent fallback for developers.)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

CONFIG_SECTION = "Glowing_Cockpit_Glass_Expanded_ModMechs"
DISPLAY_NAME = "Glowing Cockpit Glass Expanded — Mod Mechs"
MAIN_MOD_NAME = "Glowing_Cockpit_Glass_Expanded"
ADDON_MOD_NAME = "GCGE_addModMechs"

WEIGHTS = ("Light", "Medium", "Heavy", "Assault")
WEIGHT_CAT = {w: f"Per-Mech: Mod Chassis: {w}" for w in WEIGHTS}
OTHER_CAT = "Per-Mech: Mod Chassis: Other"
HERO_CAT = "Per-Mech: Mod Hero Variants"
CATEGORY_ORDER = [WEIGHT_CAT[w] for w in WEIGHTS] + [OTHER_CAT, HERO_CAT]

CHASSIS_REPLACE = ("-", "(", ")")
HERO_KEY_RESERVED = frozenset(
    ("On", "Color", "Intensity", "Enabled", "OverrideColor", "OverrideIntensity"))
KEY_RE = re.compile(r"^[A-Za-z0-9_]+$")
TAG_RE = re.compile(r'Tag="(Mech\.[^"]+)"')
MECH_TAG_VALUE_RE = re.compile(r"^Mech\.")

# Same amber as Glowing_Cockpit_Glass_Expanded (hue_table override_color_default)
GENERIC_COLOR = "(R=1,G=0.638946,B=0.464622,A=1)"
INT_LO, INT_HI = 0.0, 3.0

COLOR_TIP = (
    "Glow color (brightness from Glow brightness in Global; a darker color does not dim it, a lower alpha "
    "does, 0 = off). Used when this tier's Override color is on.")
INT_TIP = "Glow brightness multiplier (0 = off). Used when this tier's Override intensity is on."
HERO_VAR_TIP = "Override color for this hero variant (wins over Hero mechs bulk)."

# PyInstaller --onefile: snapshots / repak / UAssetGUI live next to the .exe, not in _MEIPASS.
if getattr(sys, "frozen", False):
    TOOLS_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
EXE_NAMES = {
    "repak": ("repak.exe", "repak"),
    "uassetgui": ("UAssetGUI.exe", "UAssetGUI", "uassetgui.exe", "uassetgui"),
}


def warn(msg: str) -> None:
    print(f"WARNING: {msg}", file=sys.stderr)


def chassis_key(name: str) -> str:
    for ch in CHASSIS_REPLACE:
        name = name.replace(ch, "_")
    return name


def chassis_of(tag: str):
    parts = [p for p in tag.split(".") if p]
    if len(parts) == 3:
        return parts[2]
    if len(parts) >= 4:
        return parts[-2]
    return None


def weight_of(tag: str) -> str:
    parts = [p for p in tag.split(".") if p]
    if len(parts) >= 2 and parts[1] in WEIGHTS:
        return parts[1]
    return "Other"


def variant_of(tag: str):
    parts = [p for p in tag.split(".") if p]
    if len(parts) >= 3:
        return parts[-1]
    return None


def load_key_set(path: str) -> set:
    if not os.path.isfile(path):
        raise SystemExit(f"missing snapshot: {path}")
    out = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s:
                out.add(s.lower())
    return out


def find_exe(kind: str, bat_dir: str) -> str:
    names = EXE_NAMES[kind]
    candidates = []
    for n in names:
        candidates.append(os.path.join(bat_dir, n))
        candidates.append(os.path.join(TOOLS_DIR, n))
    mw5 = os.environ.get("MW5_TOOLS")
    if mw5:
        for n in names:
            candidates.append(os.path.join(mw5, "bin", n))
            candidates.append(os.path.join(mw5, "bin", "repak", n))
    for c in candidates:
        if os.path.isfile(c):
            return c
    for n in names:
        found = shutil.which(n)
        if found:
            return found
    raise SystemExit(
        f"{names[0]} not found (searched bat folder, {TOOLS_DIR}, PATH). "
        f"Install it or place the exe next to the .bat / in Tools.")


def run(cmd, **kwargs):
    return subprocess.run(cmd, check=False, capture_output=True, text=True, **kwargs)


def repak_list(repak: str, pak: str) -> list[str] | None:
    r = run([repak, "list", pak])
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()
        if "encrypt" in err.lower() or "aes" in err.lower():
            warn(f"encrypted pak skipped: {pak}")
        else:
            warn(f"repak list failed ({pak}): {err or r.returncode}")
        return None
    return [ln.strip().replace("\\", "/") for ln in (r.stdout or "").splitlines() if ln.strip()]


def has_tags_or_mda(entries: list[str]) -> bool:
    for e in entries:
        low = e.lower()
        if "/config/tags/" in low and low.endswith(".ini"):
            return True
        if low.endswith("_mda.uasset") or low.endswith("_mda.uexp"):
            return True
    return False


def select_extract_paths(entries: list[str]) -> list[str]:
    picked = []
    for e in entries:
        low = e.lower()
        if "/config/tags/" in low and low.endswith(".ini"):
            picked.append(e)
        elif low.endswith("_mda.uasset") or low.endswith("_mda.uexp"):
            picked.append(e)
    return picked


def unpack_selected(repak: str, pak: str, out_dir: str, paths: list[str]) -> bool:
    if not paths:
        return True
    os.makedirs(out_dir, exist_ok=True)
    # chunk includes to avoid huge argv
    ok = True
    for i in range(0, len(paths), 120):
        chunk = paths[i:i + 120]
        cmd = [repak, "unpack", "-q", "-f", "-o", out_dir]
        for p in chunk:
            cmd.extend(["-i", p])
        cmd.append(pak)
        r = run(cmd)
        if r.returncode != 0:
            warn(f"repak unpack failed ({pak}): {(r.stderr or r.stdout or r.returncode)}")
            ok = False
    return ok


def walk_files(root: str, pred):
    for dp, _, fs in os.walk(root):
        for f in fs:
            if pred(f, dp):
                yield os.path.join(dp, f)


def parse_tag_inis(root: str) -> list[str]:
    tags = []
    for path in walk_files(root, lambda f, dp: f.lower().endswith(".ini") and os.path.basename(dp).lower() == "tags"):
        try:
            text = open(path, encoding="utf-8-sig", errors="replace").read()
        except OSError as e:
            warn(f"cannot read {path}: {e}")
            continue
        tags.extend(TAG_RE.findall(text))
    return tags


def find_bool_named(obj, name: str, hits=None):
    if hits is None:
        hits = []
    if isinstance(obj, dict):
        if obj.get("Name") == name or obj.get("PropertyName") == name:
            hits.append(obj.get("Value"))
        for v in obj.values():
            find_bool_named(v, name, hits)
    elif isinstance(obj, list):
        for v in obj:
            find_bool_named(v, name, hits)
    return hits


def collect_mech_tag_strings(obj, found=None):
    if found is None:
        found = []
    if isinstance(obj, dict):
        for v in obj.values():
            collect_mech_tag_strings(v, found)
    elif isinstance(obj, list):
        for v in obj:
            collect_mech_tag_strings(v, found)
    elif isinstance(obj, str) and MECH_TAG_VALUE_RE.match(obj):
        found.append(obj)
    return found


def tojson_mda(uassetgui: str, uasset: str, json_path: str) -> bool:
    r = run([uassetgui, "tojson", uasset, json_path, "VER_UE4_26"])
    if r.returncode != 0 or not os.path.isfile(json_path):
        warn(f"UAssetGUI tojson failed ({uasset}): {(r.stderr or r.stdout or r.returncode)}")
        return False
    return True


def is_hero_mda(data) -> bool:
    hits = find_bool_named(data, "bIsHeroMech")
    return any(v is True for v in hits)


def hero_type_from_mda(data, uasset_path: str) -> str | None:
    tags = collect_mech_tag_strings(data)
    for tag in tags:
        last = variant_of(tag)
        if last:
            return last
    base = os.path.basename(uasset_path)
    if base.lower().endswith("_mda.uasset"):
        return base[:-11]  # strip _MDA.uasset
    return None


def empty_gui() -> dict:
    return {
        "ConfigSection": CONFIG_SECTION,
        "DisplayName": DISPLAY_NAME,
        "UIElements": [
            {"Category": cat, "Collapsed": True, "Elements": []} for cat in CATEGORY_ORDER
        ],
    }


def ensure_categories(gui: dict) -> dict:
    by = {c["Category"]: c for c in gui.get("UIElements", [])}
    els = []
    for cat in CATEGORY_ORDER:
        if cat in by:
            c = by[cat]
            c.setdefault("Collapsed", True)
            c.setdefault("Elements", [])
            els.append(c)
        else:
            els.append({"Category": cat, "Collapsed": True, "Elements": []})
    gui["ConfigSection"] = CONFIG_SECTION
    gui["DisplayName"] = DISPLAY_NAME
    gui["UIElements"] = els
    return gui


def chassis_elements(display: str, key: str) -> list:
    tip = f"Apply this tier to every {display} variant."
    return [
        {"Var": f"Mech_{key}_On", "Type": "Toggle", "Name": display, "Tooltip": tip, "Default": False},
        {"Var": f"Mech_{key}_Color", "Type": "ColorWheel", "Name": f"{display} color",
         "Tooltip": COLOR_TIP, "Default": GENERIC_COLOR},
        {"Var": f"Mech_{key}_Intensity", "Type": "Slider", "Name": f"{display} intensity",
         "Tooltip": INT_TIP, "Default": 1.0, "Min": INT_LO, "Max": INT_HI},
    ]


def hero_elements(display: str, key: str) -> list:
    return [
        {"Var": f"MechHero_{key}_On", "Type": "Toggle", "Name": display, "Tooltip": HERO_VAR_TIP,
         "Default": False},
        {"Var": f"MechHero_{key}_Color", "Type": "ColorWheel", "Name": f"{display} color",
         "Tooltip": HERO_VAR_TIP, "Default": GENERIC_COLOR},
    ]


def existing_vars(gui: dict) -> set:
    return {el["Var"] for c in gui.get("UIElements", []) for el in c.get("Elements", [])}


def write_gui(path: str, gui: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    text = json.dumps(gui, indent=4, ensure_ascii=False) + "\n"
    with open(path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(text)


def load_gui(path: str) -> dict:
    if not os.path.isfile(path):
        return empty_gui()
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class Findings:
    def __init__(self):
        # weight -> {key_lower: (display, key)}
        self.chassis = {w: {} for w in WEIGHTS}
        self.chassis["Other"] = {}
        # key_lower -> (display, key)
        self.heroes = {}

    def add_chassis(self, display: str, weight: str, vanilla: set):
        key = chassis_key(display)
        if KEY_RE.fullmatch(key) is None:
            warn(f"drop chassis {display!r}: bad key {key!r}")
            return
        if key.lower() in vanilla:
            return
        bucket = self.chassis.get(weight, self.chassis["Other"])
        if key.lower() not in bucket:
            bucket[key.lower()] = (display, key)

    def add_hero(self, display: str, vanilla_heroes: set):
        key = chassis_key(display)
        if KEY_RE.fullmatch(key) is None or key in HERO_KEY_RESERVED:
            warn(f"drop hero variant {display!r}: bad/reserved key {key!r}")
            return
        if key.lower() in vanilla_heroes:
            return
        if key.lower() not in self.heroes:
            self.heroes[key.lower()] = (display, key)

    def extend_from_tags(self, tags: list[str], vanilla_chassis: set):
        for tag in tags:
            name = chassis_of(tag)
            if not name:
                continue
            self.add_chassis(name, weight_of(tag), vanilla_chassis)


def scan_extracted(root: str, uassetgui: str, findings: Findings,
                   vanilla_chassis: set, vanilla_heroes: set, tmp: str) -> None:
    tags = parse_tag_inis(root)
    findings.extend_from_tags(tags, vanilla_chassis)

    mdas = list(walk_files(root, lambda f, _dp: f.lower().endswith("_mda.uasset")))
    for uasset in mdas:
        jpath = os.path.join(tmp, os.path.basename(uasset) + ".json")
        if not tojson_mda(uassetgui, uasset, jpath):
            continue
        try:
            data = json.load(open(jpath, encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            warn(f"bad MDA json {jpath}: {e}")
            continue
        if not is_hero_mda(data):
            continue
        typ = hero_type_from_mda(data, uasset)
        if not typ:
            warn(f"hero MDA without type: {uasset}")
            continue
        findings.add_hero(typ, vanilla_heroes)


def scan_pak(repak: str, uassetgui: str, pak: str, findings: Findings,
             vanilla_chassis: set, vanilla_heroes: set) -> None:
    entries = repak_list(repak, pak)
    if entries is None:
        return
    if not has_tags_or_mda(entries):
        return
    paths = select_extract_paths(entries)
    with tempfile.TemporaryDirectory(prefix="gcge_scan_") as tmp:
        out = os.path.join(tmp, "extract")
        if not unpack_selected(repak, pak, out, paths):
            return
        jtmp = os.path.join(tmp, "json")
        os.makedirs(jtmp, exist_ok=True)
        scan_extracted(out, uassetgui, findings, vanilla_chassis, vanilla_heroes, jtmp)


def iter_mod_paks(mods_dir: str):
    skip = {MAIN_MOD_NAME.lower(), ADDON_MOD_NAME.lower()}
    for name in sorted(os.listdir(mods_dir), key=str.lower):
        mod_path = os.path.join(mods_dir, name)
        if not os.path.isdir(mod_path):
            continue
        if name.lower() in skip:
            continue
        paks_dir = os.path.join(mod_path, "Paks")
        if not os.path.isdir(paks_dir):
            continue
        for f in sorted(os.listdir(paks_dir), key=str.lower):
            if f.lower().endswith(".pak"):
                yield name, os.path.join(paks_dir, f)


def build_gui_full(findings: Findings) -> dict:
    gui = empty_gui()
    by = {c["Category"]: c for c in gui["UIElements"]}
    for w in list(WEIGHTS) + ["Other"]:
        cat = WEIGHT_CAT.get(w, OTHER_CAT)
        rows = sorted(findings.chassis[w].values(), key=lambda r: r[0].lower())
        els = []
        for display, key in rows:
            els.extend(chassis_elements(display, key))
        by[cat]["Elements"] = els
    hero_rows = sorted(findings.heroes.values(), key=lambda r: r[0].lower())
    hels = []
    for display, key in hero_rows:
        hels.extend(hero_elements(display, key))
    by[HERO_CAT]["Elements"] = hels
    return gui


def merge_gui(gui: dict, findings: Findings) -> tuple[dict, int]:
    gui = ensure_categories(gui)
    have = existing_vars(gui)
    by = {c["Category"]: c for c in gui["UIElements"]}
    added = 0
    for w in list(WEIGHTS) + ["Other"]:
        cat = WEIGHT_CAT.get(w, OTHER_CAT)
        rows = sorted(findings.chassis[w].values(), key=lambda r: r[0].lower())
        for display, key in rows:
            on = f"Mech_{key}_On"
            if on in have:
                continue
            by[cat]["Elements"].extend(chassis_elements(display, key))
            have.update(el["Var"] for el in chassis_elements(display, key))
            added += 1
    for display, key in sorted(findings.heroes.values(), key=lambda r: r[0].lower()):
        on = f"MechHero_{key}_On"
        if on in have:
            continue
        by[HERO_CAT]["Elements"].extend(hero_elements(display, key))
        have.update(el["Var"] for el in hero_elements(display, key))
        added += 1
    return gui, added


def count_summary(findings: Findings) -> str:
    n_ch = sum(len(v) for v in findings.chassis.values())
    return f"chassis={n_ch} heroes={len(findings.heroes)}"


def resolve_bat_dir(explicit: str | None) -> str:
    if explicit:
        return os.path.abspath(explicit)
    # cwd is set by the .bat to its own folder
    return os.path.abspath(os.getcwd())


def cmd_all(args) -> int:
    bat_dir = resolve_bat_dir(args.bat_dir)
    addon_root = bat_dir
    # if launched from Tools/, go up
    if os.path.basename(addon_root).lower() == "tools":
        addon_root = os.path.dirname(addon_root)
    mods_dir = args.mods_dir or os.path.dirname(addon_root)
    out_ini = args.out or os.path.join(addon_root, "Resources", "gui_config.ini")

    repak = find_exe("repak", bat_dir)
    uassetgui = find_exe("uassetgui", bat_dir)
    vanilla_chassis = load_key_set(os.path.join(TOOLS_DIR, "gcge_vanilla_chassis_keys.txt"))
    vanilla_heroes = load_key_set(os.path.join(TOOLS_DIR, "gcge_vanilla_hero_variant_keys.txt"))

    print(f"Mods: {mods_dir}")
    print(f"Output: {out_ini}")
    findings = Findings()
    n_paks = 0
    for mod_name, pak in iter_mod_paks(mods_dir):
        n_paks += 1
        print(f"  scan {mod_name}: {os.path.basename(pak)}")
        scan_pak(repak, uassetgui, pak, findings, vanilla_chassis, vanilla_heroes)
    gui = build_gui_full(findings)
    write_gui(out_ini, gui)
    print(f"Wrote full gui_config.ini ({count_summary(findings)}; paks seen={n_paks})")
    return 0


def cmd_one(args) -> int:
    bat_dir = resolve_bat_dir(args.bat_dir)
    ini_path = args.ini or os.path.join(bat_dir, "gui_config.ini")
    paks = sorted(
        (os.path.join(bat_dir, f) for f in os.listdir(bat_dir) if f.lower().endswith(".pak")),
        key=str.lower)

    repak = find_exe("repak", bat_dir)
    uassetgui = find_exe("uassetgui", bat_dir)
    # snapshots: Tools next to script, or next to bat
    snap_chassis = os.path.join(TOOLS_DIR, "gcge_vanilla_chassis_keys.txt")
    snap_heroes = os.path.join(TOOLS_DIR, "gcge_vanilla_hero_variant_keys.txt")
    if not os.path.isfile(snap_chassis):
        snap_chassis = os.path.join(bat_dir, "gcge_vanilla_chassis_keys.txt")
        snap_heroes = os.path.join(bat_dir, "gcge_vanilla_hero_variant_keys.txt")
    vanilla_chassis = load_key_set(snap_chassis)
    vanilla_heroes = load_key_set(snap_heroes)

    print(f"Paks dir: {bat_dir} ({len(paks)} pak(s))")
    print(f"Ini: {ini_path}")
    findings = Findings()
    for pak in paks:
        print(f"  scan {os.path.basename(pak)}")
        scan_pak(repak, uassetgui, pak, findings, vanilla_chassis, vanilla_heroes)

    gui = load_gui(ini_path)
    gui, added = merge_gui(gui, findings)
    write_gui(ini_path, gui)
    print(f"Merged gui_config.ini ({count_summary(findings)}; newly added entries={added})")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="GCGE_addModMechs scanner (option A)")
    ap.add_argument("--bat-dir", help="folder of the calling .bat (defaults to cwd)")
    sub = ap.add_subparsers(dest="mode", required=True)

    p_all = sub.add_parser("all", help="full regenerate from parent Mods")
    p_all.add_argument("--mods-dir", help="Mods folder (default: parent of add-on root)")
    p_all.add_argument("--out", help="output gui_config.ini path")
    p_all.set_defaults(func=cmd_all)

    p_one = sub.add_parser("one", help="merge from *.pak next to the bat")
    p_one.add_argument("--ini", help="gui_config.ini beside the bat (default)")
    p_one.set_defaults(func=cmd_one)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
