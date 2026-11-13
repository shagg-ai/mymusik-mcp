"""Build the x64 per-user installer using PyInstaller and NSIS 3."""

import argparse
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parent


def build_extension(payload, output):
    plugin = ROOT / "plugins" / "mymusik"
    manifest = json.loads((plugin / "manifest.json").read_text(encoding="utf-8"))
    entry = "server/mymusik-mcp.exe"
    manifest["server"] = {"type": "binary", "entry_point": entry, "mcp_config": {
        "command": "${__dirname}/" + entry, "args": ["stdio"]}}
    manifest["compatibility"] = {"platforms": ["win32"]}
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
        archive.write(plugin / "icon.png", "icon.png")
        archive.write(ROOT / "LICENSE", "LICENSE")
        archive.write(payload / "mymusik-mcp.exe", entry)
        for path in sorted((payload / "_internal").rglob("*")):
            if path.is_file():
                archive.write(path, "server/" + path.relative_to(payload).as_posix())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--makensis", default="makensis", help="Path to the NSIS compiler")
    args = parser.parse_args()
    if sys.platform != "win32" or platform.machine().upper() != "AMD64" or sys.maxsize <= 2**32:
        parser.error("Build with 64-bit Python on x64 Windows.")
    build = ROOT / "build" / "windows"
    output = ROOT / "dist" / "MyMusik-MCP-Setup-x64.exe"
    output.parent.mkdir(exist_ok=True)
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--distpath", str(build / "dist"),
                    "--workpath", str(build / "work"), str(ROOT / "windows" / "connector.spec")], check=True)
    payload = build / "dist" / "MyMusik MCP"
    bundle = output.with_name("MyMusik-Windows-x64.mcpb")
    build_extension(payload, bundle)
    shutil.copyfile(bundle, payload / bundle.name)
    # Only remove the files delivered by this installer, even in a custom install folder.
    removal = build / "remove-files.nsh"
    paths = sorted(payload.rglob("*"), key=lambda p: len(p.parts), reverse=True)
    with removal.open("w", encoding="utf-8-sig") as stream:
        for path in paths:
            relative = str(path.relative_to(payload)).replace("$", "$$")
            command = "RMDir" if path.is_dir() else "Delete"
            print(f'{command} "$INSTDIR\\{relative}"', file=stream)
    version = re.search(r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(), re.MULTILINE)[1]
    subprocess.run([args.makensis, "/V2", f"/DPAYLOAD={payload}", f"/DOUTPUT={output}",
                    f"/DREMOVE_FILES={removal}", f"/DVERSION={version}",
                    str(ROOT / "windows" / "installer.nsi")], check=True)
    print(output)


if __name__ == "__main__":
    main()
