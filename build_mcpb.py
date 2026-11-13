"""Build the local stdio bundle from the connector shared by both plugins."""

from hashlib import sha256
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parent
PLUGIN = ROOT / "plugins" / "mymusik"
FILES = (
    "manifest.json",
    "LICENSE",
    "README.md",
    "icon.png",
    "mymusik_mcp/__init__.py",
    "mymusik_mcp/cli.py",
    "mymusik_mcp/mcp_stdio.py",
)


if __name__ == "__main__":
    output = ROOT / "dist" / "mymusik-mcp.mcpb"
    output.parent.mkdir(exist_ok=True)
    with ZipFile(output, "w") as archive:
        for name in FILES:
            data = (PLUGIN / name).read_bytes()
            if name != "icon.png":
                data = data.replace(b"\r\n", b"\n")
            entry = ZipInfo(name, date_time=(2026, 11, 12, 0, 0, 0))
            entry.create_system = 0
            archive.writestr(entry, data, compress_type=ZIP_DEFLATED)
    print(f"{sha256(output.read_bytes()).hexdigest()}  {output.name}")
