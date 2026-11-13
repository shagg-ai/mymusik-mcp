"""Build Gemini CLI release assets from the same local connector as the wheel."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parent
FILES = (
    "gemini-extension.json", "README.md", "LICENSE",
    *(f"plugins/mymusik/mymusik_mcp/{module}.py"
      for module in ("__init__", "cli", "mcp_stdio", "playback", "setup")),
)


if __name__ == "__main__":
    dest = ROOT / "dist"
    dest.mkdir(exist_ok=True)
    # A mixed GitHub release needs a matching OS prefix for Gemini's asset selector.
    for platform in ("win32", "darwin", "linux"):
        with ZipFile(dest / f"{platform}.mymusik.zip", "w") as bundle:
            for path in FILES:
                entry = ZipInfo(path)
                entry.create_system = 3
                entry.external_attr = 0o100644 << 16
                bundle.writestr(entry, (ROOT / path).read_bytes().replace(b"\r\n", b"\n"),
                                compress_type=ZIP_DEFLATED)
