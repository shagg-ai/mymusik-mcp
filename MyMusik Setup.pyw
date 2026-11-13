"""Double-click after extracting the MyMusik connector source on Windows."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "plugins" / "mymusik"))
from mymusik_mcp.cli import desktop_setup

if __name__ == "__main__":
    desktop_setup()
