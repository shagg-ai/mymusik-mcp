"""Pair with MyMusik and serve the paired connection over standard input/output."""

import argparse
import getpass
import json
import os
from pathlib import Path
import sys

if __package__:
    from . import mcp_stdio as bridge
    from .playback import MyMusikTransport
else:  # Plugin hosts run this file with their own Python interpreter.
    import mcp_stdio as bridge
    from playback import MyMusikTransport


def default_profile():
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return root / "mymusik-mcp" / "connection.profile"


def main():
    parser = argparse.ArgumentParser(prog="mymusik-mcp", description=__doc__)
    parser.add_argument("command", nargs="?", choices=("pair", "stdio"), default="stdio")
    parser.add_argument("--profile", type=Path, default=default_profile(),
                        help="Profile to save or use (default: per-user MyMusik profile)")
    parser.add_argument("--request-timeout", type=bridge.request_timeout,
                        default=bridge.DEFAULT_TIMEOUT, help="HTTP timeout in seconds (1 to 3600)")
    try:
        args = parser.parse_args()
        if args.command == "pair":
            invitation = (getpass.getpass("MyMusik invitation URL (hidden): ")
                          if sys.stdin.isatty() else sys.stdin.readline(bridge.MAX_MESSAGE))
            profile, hello = bridge.pair(invitation)
            bridge.save_profile(args.profile, profile)
            print(json.dumps({"connected": True, "serverInfo": hello["serverInfo"]}))
        else:
            bridge.serve(bridge.load_profile(args.profile), timeout=args.request_timeout,
                         transport_factory=MyMusikTransport)
    except (bridge.BridgeError, OSError, ValueError, KeyError, TypeError):
        print("MyMusik connection failed. Check that MyMusik is running and pair with a fresh invitation using mymusik-mcp pair.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
