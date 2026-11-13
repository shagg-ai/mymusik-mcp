"""The two Windows executables share one embedded Python/Tk runtime."""

from pathlib import Path
import sys

from mymusik_mcp.cli import desktop_setup, main

if __name__ == "__main__":
    if Path(sys.executable).stem.casefold() == "mymusik setup":
        desktop_setup()
    else:
        raise SystemExit(main())
