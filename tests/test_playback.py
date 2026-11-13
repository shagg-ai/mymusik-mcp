"""Exercise the installed stdio command against a local MCP endpoint."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

from mymusik_mcp import mcp_stdio


class PlaybackTest(unittest.TestCase):
    def test_controls_use_the_paired_session_and_never_retry(self):
        requests = []
        deny = False

        class App(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                msg = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append((msg, self.headers["Cookie"]))
                if deny:
                    self.send_error(403)
                    return
                result = {"tools": [{"name": "api.call"}]} if msg["method"] == "tools/list" else {"content": []}
                data = json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": result}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        with ThreadingHTTPServer(("127.0.0.1", 0), App) as server, tempfile.TemporaryDirectory() as tmp:
            threading.Thread(target=server.serve_forever, daemon=True).start()
            self.addCleanup(server.shutdown)
            origin = f"http://127.0.0.1:{server.server_port}"
            profile = Path(tmp) / "profile"
            mcp_stdio.save_profile(profile, {"version": 1, "origin": origin, "endpoint": origin, "cookie": "test=only"})
            with subprocess.Popen([sys.executable, "-m", "mymusik_mcp.cli", "stdio", "--profile", str(profile)],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True) as proc:
                self.addCleanup(proc.kill)
                def call(method, params):
                    msg = {"jsonrpc": "2.0", "id": 17, "method": method, "params": params}
                    proc.stdin.write(json.dumps(msg) + "\n")
                    proc.stdin.flush()
                    reply = json.loads(proc.stdout.readline())
                    self.assertEqual(reply["id"], 17)
                    return reply

                def playback(action):
                    return call("tools/call", {"name": "mymusik_playback", "arguments": {"action": action}})

                try:
                    tools = call("tools/list", {})["result"]["tools"]
                    self.assertEqual([t["name"] for t in tools], ["api.call", "mymusik_playback"])
                    for action, operation in (("pause", "stopPlaying"), ("resume", "startPlaying"),
                                              ("next", "nextTrack"), ("previous", "prevTrack")):
                        self.assertIn("result", playback(action))
                        request, cookie = requests[-1]
                        self.assertEqual(cookie, "test=only")
                        self.assertEqual(request["params"], {"name": "api.call", "arguments": {
                            "operationId": "Service::Player::" + operation}})
                    self.assertIn("error", playback("shuffle"))
                    self.assertEqual(len(requests), 5)
                    deny = True
                    self.assertIn("denied", playback("next")["error"]["message"])
                    self.assertEqual(len(requests), 6)
                finally:
                    proc.stdin.close()
                    proc.wait(timeout=5)
                    server.shutdown()
