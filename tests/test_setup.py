"""First-run behavior for clipboard pairing and generated MCP launch settings."""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch

from mymusik_mcp import mcp_stdio as bridge, setup


class SetupTest(unittest.TestCase):
    def test_saved_session_is_checked_without_redeeming_an_invitation(self):
        requests = []

        class Player(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def respond(self, body):
                self.send_response(self.server.status)
                self.end_headers()
                self.wfile.write(json.dumps(body).encode())

            def do_GET(self):
                requests.append((self.path, self.headers.get("Cookie")))
                self.respond({"tokenValid": self.server.valid})

            def do_POST(self):
                message = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append((self.path, message["method"]))
                self.respond({"id": 1, "jsonrpc": "2.0", "result": {
                    "protocolVersion": bridge.VERSION, "serverInfo": {"name": "MyMusik"}}})

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "connection.profile"
            self.assertEqual(setup.saved_connection(path), "new")
            path.write_bytes(b"invalid")
            self.assertEqual(setup.saved_connection(path), "invalid")
            with HTTPServer(("127.0.0.1", 0), Player) as server:
                origin = "http://127.0.0.1:" + str(server.server_port)
                bridge.save_profile(path, {"version": 1, "origin": origin, "endpoint": origin, "cookie": "test=local"})
                before = path.read_bytes()
                server.status, server.valid = 200, True
                thread = Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    self.assertEqual(setup.saved_connection(path), "connected")
                    self.assertEqual(requests, [("/ui/auth/status", "test=local"), ("/mcp", "initialize")])
                    server.valid = False
                    self.assertEqual(setup.saved_connection(path), "renew")
                    server.status = 403
                    self.assertEqual(setup.saved_connection(path), "renew")
                    server.status = 503
                    self.assertEqual(setup.saved_connection(path), "unavailable")
                finally:
                    server.shutdown()
                    thread.join()
            self.assertEqual(setup.saved_connection(path), "unavailable")
            self.assertEqual(path.read_bytes(), before)

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
