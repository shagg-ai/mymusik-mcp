from pathlib import Path
import sys

root = Path(SPECPATH).parent
plugin = root / "plugins" / "mymusik"
analysis = Analysis([str(root / "windows" / "launcher.py")], pathex=[str(plugin)],
                    datas=[(str(plugin / "mymusik_mcp" / "setup-icon.png"), "mymusik_mcp"),
                           (str(root / "LICENSE"), "licenses/MyMusik"),
                           (str(Path(sys.base_prefix) / "LICENSE.txt"), "licenses/Python")])
archive = PYZ(analysis.pure)

def executable(name, console):
    return EXE(archive, analysis.scripts, [], exclude_binaries=True, name=name,
               console=console, upx=False, icon=str(root / "windows" / "mymusik.ico"))

COLLECT(executable("MyMusik Setup", False), executable("mymusik-mcp", True),
        analysis.binaries, analysis.datas, upx=False, name="MyMusik MCP")
