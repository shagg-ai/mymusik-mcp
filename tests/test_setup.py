"""First-run behavior for clipboard pairing and generated MCP launch settings."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from mymusik_mcp import mcp_stdio as bridge, setup


class SetupTest(unittest.TestCase):
    def test_agent_prompt_redeems_only_the_invitation(self):
        url = "http://localhost:7790/ui/auth#grant=example&return=%2Fui"
        prompt = "\r\n".join(["Connection details", "MCP endpoint: http://localhost:7790/mcp",
                              url, "Pair once", "Origin: http://localhost:7790"])
        with patch.object(bridge, "pair", return_value=({"version": 1}, {"serverInfo": {}})) as pair:
            with patch.object(bridge, "save_profile") as save:
                self.assertEqual(setup.connect(prompt, Path("profile")), {"serverInfo": {}})
                pair.assert_called_once_with(url)
                save.assert_called_once_with(Path("profile"), {"version": 1})
        self.assertEqual(setup.invitation_url(url), url)

    def test_unusable_clipboard_fails_before_redemption(self):
        one = "https://localhost/ui/auth#grant=example"
        for text in ("", "some other text", one + "\n" + one.replace("example", "another")):
            with self.subTest(text=text), patch.object(bridge, "pair") as redeem:
                with self.assertRaises(bridge.BridgeError) as error:
                    setup.connect(text, Path("unused"))
                self.assertNotIn("example", str(error.exception))
                redeem.assert_not_called()

    def test_config_starts_unpaired_with_a_profile_containing_spaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "not paired yet"
            cli = Path(setup.__file__).with_name("cli.py")
            config = subprocess.check_output(
                [sys.executable, str(cli), "config", "--profile", str(profile)], text=True)
            server = json.loads(config)["mcpServers"]["mymusik"]
            with subprocess.Popen([server["command"], *server["args"]], cwd=tmp, stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, text=True) as proc:
                try:
                    proc.stdin.write('{"jsonrpc":"2.0","id":1,"method":"tools/list"}\n')
                    proc.stdin.flush()
                    tools = json.loads(proc.stdout.readline())["result"]["tools"]
                    self.assertIn("mymusik_playback", [tool["name"] for tool in tools])
                finally:
                    proc.stdin.close()
                    proc.wait(timeout=5)
