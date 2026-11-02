# GCGE_addModMechs scanner — source and build steps

Source and rebuild instructions for `scan_modmechs.exe`, the ModOptions helper used by the **GCGE_addModMechs** add-on for *MechWarrior 5: Mercenaries* (requires GCGE_Main).

This repository / folder is **source and build metadata only**. It does not include compiled binaries.

## What the scanner does

`Tools/scan_modmechs.py` scans mod `.pak` files (via external CLI tools) and merges chassis / hero-variant entries into a ModOptions `gui_config.ini`.

`Scan_One_Mod.bat` (cmd.exe) behavior, matching the script in this folder:

1. If `scan_modmechs.exe` exists next to the `.bat`, run it with `one`.
2. Else if `Tools\scan_modmechs.exe` exists, run that with `one`.
3. Else look for `scan_modmechs.py` next to the `.bat`, then `Tools\scan_modmechs.py`, and run it with `py -3` or `python` (whichever is on `PATH`) and `one`.

## Runtime vs build dependencies

**To run the** `.py` **under Python 3:** standard library only. No `pip install` is required for the application itself.

Imports used by `scan_modmechs.py`:

`argparse`, `json`, `os`, `re`, `shutil`, `subprocess`, `sys`, `tempfile` (plus `__future__` annotations).

A search of `Tools/scan_modmechs.py` for `socket`, `urllib`, `requests`, `http`, `ftp`, `webhook`, `http://`, and `https://` found **no matches**. The source does not contain network/client code. This statement is about the **source file**, not about a compiled `.exe`.

**To build** `scan_modmechs.exe`**:** Python **3.11.9** and `PyInstaller==6.22.3` (see `requirements.txt`).

**External CLIs used at scan time** (not authored here, **not included in this source folder**):

| Tool | Upstream / license |
|------|-------------------|
| `repak` | https://github.com/trumank/repak — Apache-2.0 / MIT. The optional-file zip submitted to Nexus includes `Tools\LICENSE-APACHE` and `Tools\LICENSE-MIT` next to `repak.exe`. |
| `UAssetGUI` | https://github.com/atenfyr/UAssetGUI — MIT. Verified by opening upstream [LICENSE](https://github.com/atenfyr/UAssetGUI/blob/master/LICENSE) (MIT License, Copyright (c) 2020–2026 atenfyr) and [NOTICE.md](https://github.com/atenfyr/UAssetGUI/blob/master/NOTICE.md) (third-party notices). |

The **optional-file zip submitted to Nexus** for GCGE_addModMechs **includes** these executables next to `scan_modmechs.exe` under `Tools\`. Measured copies from that packaging tree:

| File | Version / note | Size (bytes) | SHA-256 |
|------|----------------|--------------|---------|
| `Tools\repak.exe` | `repak_cli 0.2.3` (`repak.exe --version`) | 4541952 | `fcd538e5994b9bb833622d425ae346f4e0692f02d4b0025114a559f9b6286022` |
| `Tools\UAssetGUI.exe` | as packaged (no `--version` used here) | 13163201 | `b7d75c0893f1a60e565853ae638bc21f2416cd12c2d9d854e297abb87ceb3263` |

## Build (relative paths)

Use **cmd.exe** (the `.venv\Scripts\activate` line below is a cmd batch activator, not PowerShell).

From this folder (the directory that contains `scan_modmechs.spec` and `Tools/`):

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm scan_modmechs.spec
```

The build leaves `dist\`, `build\`, and `.venv\` in the working directory. Do not commit those; copy `dist\scan_modmechs.exe` into `Tools\` only when packaging the add-on.

Equivalent one-liner (same flags as the recorded 2026-10-17 author build: `--onefile --console --name scan_modmechs`):

```bat
python -m PyInstaller --onefile --console --name scan_modmechs --distpath dist --workpath build --specpath . Tools\scan_modmechs.py
```

`scan_modmechs.spec` in this folder uses a **relative** entry `Tools/scan_modmechs.py`, with `console=True` and `upx=True`. Those two settings match the PyInstaller `.spec` kept from the 2026-10-17 build record; only the absolute local path from that record was replaced with the relative entry above.

**UPX:** the `.spec` sets `upx=True`, which only compresses if the `upx` tool is on `PATH`. On the author machine used for this write-up, `upx --version` is not recognized (UPX not installed / not on `PATH`). The 2026-10-17 build session log and leftover build warn file do **not** record an UPX version or an explicit “UPX applied / UPX unavailable” line, so whether that build actually ran UPX is **unverified**. Do not assume the submitted `.exe` is UPX-compressed.

## Source vs the optional-file exe

| Artifact | SHA-256 | Notes |
|----------|---------|--------|
| `Tools/scan_modmechs.py` (this folder) | `82cf8eb9064fc8d23c64fcac4b612f121e479808e4aaca7498cb1d892b53c6dc` | Published scanner source |
| `Tools\scan_modmechs.exe` in the optional-file zip submitted to Nexus | `93129823e3cf30ec654ee8056286feef019ce46eaa3d77f038a36d66fe2e4501` | Author build dated 2026-10-17 (PyInstaller onefile), per build record / file timestamp |

**What was checked:** using **Python 3.11.9** (the same major.minor.patch as the recorded build environment), the published `.py` was compiled, and that result was compared to the Python code object embedded inside the `.exe` from the optional-file zip. The comparison (instruction bytes, names, and constant values; nested code objects compared the same way, without treating filename metadata as part of the match) succeeded, including `sys.frozen` / `TOOLS_DIR`. Comments and insignificant whitespace in a `.py` do not appear in bytecode, so this is **not** a claim that the on-disk source file bytes are identical to whatever file was fed to PyInstaller on build day.

**What was not proven:** that rebuilding produces the same `.exe` file hash. A clean rebuild can differ (environment / timestamps). Do not read this section as “rebuild will match `93129823…`.”

## Layout

```
Scan_One_Mod.bat
mod.json
README.md
requirements.txt
scan_modmechs.spec
Resources/gui_config.ini
Resources/Icon128.png
Tools/scan_modmechs.py
Tools/gcge_vanilla_chassis_keys.txt
Tools/gcge_vanilla_hero_variant_keys.txt
```

No license is specified at this time.
