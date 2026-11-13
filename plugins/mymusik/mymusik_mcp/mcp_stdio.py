#!/usr/bin/env python3
"""Generic, dependency-free stdio connector for Framework's invitation-authenticated MCP.

Pair once using an invitation read from stdin (never a command-line secret), then
configure an MCP client to run this file with `stdio --profile <path>`.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import ctypes
import getpass
import http.client
from http.cookies import SimpleCookie
import ipaddress
import json
import math
import os
from pathlib import Path
import socket
import ssl
import stat
import sys
import tempfile
import threading
from urllib.parse import parse_qs, urlsplit

MAX_MESSAGE = 1024 * 1024
MAX_RESPONSE = 512 * 1024
VERSION = "2025-11-25"
DEFAULT_TIMEOUT = 180
SUPPORTED_VERSIONS = ("2025-03-26", "2025-06-18", "2025-11-25", "2026-07-28")


def request_timeout(value):
    try:
        seconds = int(value)
    except (ValueError, TypeError):
        raise BridgeError("Request timeout must be an integer from 1 to 3600 seconds.") from None
    if isinstance(value, bool) or str(seconds) != str(value) or not 1 <= seconds <= 3600:
        raise BridgeError("Request timeout must be an integer from 1 to 3600 seconds.")
    return seconds


class BridgeError(Exception):
    """Only fixed, credential-free messages are exposed to the caller."""


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def valid_id(value):
    if isinstance(value, int) and not isinstance(value, bool):
        return abs(value) <= 9007199254740991
    if isinstance(value, str):
        try:
            return len(value.encode("utf-8")) <= 128
        except UnicodeError:
            return False
    return False


def decode(data):
    def reject_constant(_):
        raise ValueError("Non-finite JSON number")
    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("JSON number exceeds finite range")
        return number
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON object member")
            result[key] = value
        return result
    return json.loads(data, parse_constant=reject_constant, parse_float=finite_float, object_pairs_hook=unique_object)


def parse_origin(value):
    if not isinstance(value, str) or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise BridgeError("Invalid endpoint origin.")
    try:
        url = urlsplit(value)
    except ValueError:
        raise BridgeError("Invalid endpoint origin.") from None
    if (url.scheme not in ("http", "https") or not url.hostname or url.username or url.password
            or url.query or url.fragment or url.path not in ("", "/")):
        raise BridgeError("Expected an HTTP(S) origin without credentials, path, query or fragment.")
    try:
        port = url.port or (443 if url.scheme == "https" else 80)
    except ValueError:
        raise BridgeError("Invalid endpoint port.") from None
    if url.scheme == "http":
        try:
            address = ipaddress.ip_address(url.hostname)
            local = address.is_loopback or address.is_private or address.is_link_local
        except ValueError:
            local = url.hostname.lower() == "localhost"
        if not local:
            raise BridgeError("Use HTTPS for a public endpoint; HTTP is limited to localhost/private LAN addresses.")
    return url, port


def json_object(data):
    try:
        value = decode(data)
    except (ValueError, UnicodeError, RecursionError):
        raise BridgeError("Expected a valid JSON object from the app or profile.") from None
    if not isinstance(value, dict):
        raise BridgeError("Expected a JSON object from the app or profile.")
    return value


class RequestCancellation:
    """Cancel one transport wait; never claim to roll back an application operation."""
    def __init__(self):
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._socket = None

    def is_set(self):
        return self._event.is_set()

    @staticmethod
    def _interrupt(active_socket):
        if active_socket is not None:
            try:
                # close() alone may leave a buffered HTTPResponse read blocked.
                # The worker owns close(); interrupt TCP without mutating an
                # SSLSocket's TLS state from this other thread.
                socket.socket.shutdown(active_socket, socket.SHUT_RDWR)
            except OSError:
                pass

    def set(self):
        with self._lock:
            self._event.set()
            active_socket = self._socket
        self._interrupt(active_socket)

    def attach(self, active_socket):
        with self._lock:
            self._socket = active_socket
            cancelled = self._event.is_set()
        if cancelled:
            self._interrupt(active_socket)
        return not cancelled

    def detach(self):
        with self._lock:
            self._socket = None


class Transport:
    def __init__(self, endpoint, origin, cookie="", timeout=DEFAULT_TIMEOUT):
        self.url, self.port = parse_origin(endpoint)
        parse_origin(origin)
        self.origin = origin.rstrip("/")
        self.cookie = cookie
        self.timeout = request_timeout(timeout)
        self.protocol_version = VERSION
        self.protocol_lock = threading.Lock()

    def request(self, method, path, body=None, extra=None, cancellation=None):
        # http.client neither follows redirects nor automatically retries requests.
        cls = http.client.HTTPSConnection if self.url.scheme == "https" else http.client.HTTPConnection
        connection = cls(self.url.hostname, self.port, timeout=self.timeout)
        headers = {"Accept": "application/json, text/event-stream", "Origin": self.origin}
        if self.cookie:
            headers["Cookie"] = self.cookie
        if body is not None:
            headers["Content-Type"] = "application/json"
        headers.update(extra or {})
        response = None
        try:
            if cancellation is not None:
                if cancellation.is_set():
                    raise BridgeError("Request cancelled. A dispatched operation may already have completed.")
                # Connect explicitly so cancellation owns a stable socket even
                # when getresponse() detaches it for a Connection: close reply.
                connection.connect()
                if not cancellation.attach(connection.sock):
                    raise BridgeError("Request cancelled. A dispatched operation may already have completed.")
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            data = response.read(MAX_RESPONSE + 1)
            if len(data) > MAX_RESPONSE:
                raise BridgeError("Server response exceeds connector limit. Do not automatically repeat a write.")
            if 300 <= response.status < 400:
                raise BridgeError("Redirect refused. Confirm the app endpoint and pair again.")
            if response.status in (401, 403):
                raise BridgeError("Session expired or access denied. Check the selected grants or pair with a fresh AI prompt.")
            return response.status, response.getheaders(), data
        except (OSError, http.client.HTTPException, ssl.SSLError):
            raise BridgeError("Connection failed or timed out. Outcome may be unknown; do not automatically repeat a write.") from None
        finally:
            if cancellation is not None:
                cancellation.detach()
            if response is not None:
                response.close()
            connection.close()

    def rpc(self, message, cancellation=None):
        if (not isinstance(message, dict) or message.get("jsonrpc") != "2.0"
                or not isinstance(message.get("method"), str)
                or ("id" in message and not valid_id(message["id"]))):
            raise BridgeError("Invalid MCP request envelope or ID.")
        body = encode(message)
        if len(body) > MAX_MESSAGE:
            raise BridgeError("MCP request exceeds 1 MiB.")
        params = message.get("params", {})
        if not isinstance(params, dict) or not isinstance(params.get("_meta", {}), dict):
            raise BridgeError("Invalid MCP request metadata.")
        meta = params.get("_meta", {})
        with self.protocol_lock:
            version = meta.get("io.modelcontextprotocol/protocolVersion", self.protocol_version)
        if message["method"] == "initialize":
            preferred = params.get("protocolVersion")
            version = preferred if preferred in SUPPORTED_VERSIONS[:3] else VERSION
        if version not in SUPPORTED_VERSIONS:
            raise BridgeError("Unsupported MCP protocol version.")
        headers = {"MCP-Protocol-Version": version}
        if version == "2026-07-28":
            headers["Mcp-Method"] = message.get("method", "")
            if message.get("method") == "tools/call":
                name = params.get("name", "")
                if not isinstance(name, str):
                    raise BridgeError("Invalid tool name.")
                # The generic names are ASCII. Encode arbitrary names per MCP.
                if not name.isascii() or name != name.strip() or any(ord(c) < 32 for c in name) or name.startswith("=?base64?"):
                    import base64
                    name = "=?base64?" + base64.b64encode(name.encode()).decode() + "?="
                headers["Mcp-Name"] = name
        if cancellation is None:
            status, _, data = self.request("POST", "/mcp", body, headers)
        else:
            status, _, data = self.request("POST", "/mcp", body, headers, cancellation=cancellation)
        if "id" not in message and status == 202:
            return None
        # Parser/rate-limit/readiness failures happen outside JSON-RPC. Preserve
        # their actionable meaning without echoing untrusted proxy HTML or secrets.
        if status == 413:
            raise BridgeError("HTTP 413: App request limit exceeded. Reduce input size; do not blindly repeat writes.")
        if status == 429:
            raise BridgeError("HTTP 429: App rate limit reached. Wait before new requests; check outcomes before retrying writes.")
        if status == 503:
            raise BridgeError("HTTP 503: App is unavailable or not ready. Recheck app.status when reachable; do not blindly repeat writes.")
        try:
            result = json_object(data)
        except BridgeError:
            raise BridgeError("App returned invalid JSON. Outcome may be unknown; do not automatically repeat a write.") from None
        if (result.get("jsonrpc") != "2.0" or "id" not in result
                or not valid_id(result["id"]) or result["id"] != message.get("id")):
            raise BridgeError("App returned a mismatched MCP response. Outcome may be unknown; do not automatically repeat a write.")
        if ("result" in result) == ("error" in result):
            raise BridgeError("App returned an invalid MCP response envelope; do not automatically repeat a write.")
        if "result" in result and not isinstance(result["result"], dict):
            raise BridgeError("App returned an invalid MCP result.")
        if "result" in result and status != 200:
            raise BridgeError("App returned an HTTP failure with a success envelope. Outcome may be unknown; do not repeat a write.")
        if "error" in result:
            failure = result["error"]
            if (not isinstance(failure, dict) or not isinstance(failure.get("code"), int)
                    or isinstance(failure["code"], bool) or not isinstance(failure.get("message"), str)):
                raise BridgeError("App returned an invalid MCP error.")
        if message["method"] == "initialize" and "result" in result:
            negotiated = result["result"].get("protocolVersion")
            if negotiated not in SUPPORTED_VERSIONS[:3]:
                raise BridgeError("App returned an invalid negotiated MCP version.")
            with self.protocol_lock:
                self.protocol_version = negotiated
        return result


def protect(data, decrypt=False):
    if os.name != "nt":
        return data
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    memory = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    incoming, outgoing = Blob(len(data), memory), Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if not function(ctypes.byref(incoming), None, None, None, None, 1, ctypes.byref(outgoing)):
        raise BridgeError("Unable to access the profile's Windows user-protected credentials.")
    try:
        return ctypes.string_at(outgoing.data, outgoing.size)
    finally:
        kernel.LocalFree(outgoing.data)


def save_profile(path, value):
    path = Path(path).absolute()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink():
        raise BridgeError("Profile must not be a symbolic link.")
    data = (b"DPAPI\n" + protect(encode(value))) if os.name == "nt" else b"JSON\n" + encode(value)
    fd, temporary = tempfile.mkstemp(prefix=".mcp-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_profile(path):
    path = Path(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > 64 * 1024:
        raise BridgeError("Invalid profile file.")
    if os.name != "nt" and (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077):
        raise BridgeError("Profile must belong to this user and have mode 0600.")
    data = path.read_bytes()
    prefix = b"DPAPI\n" if os.name == "nt" else b"JSON\n"
    if not data.startswith(prefix):
        raise BridgeError("Profile belongs to a different platform; pair again.")
    value = json_object(protect(data[len(prefix):], decrypt=True))
    if value.get("version") != 1 or not isinstance(value.get("cookie"), str) or not value["cookie"]:
        raise BridgeError("Invalid profile; pair again.")
    parse_origin(value.get("endpoint"))
    parse_origin(value.get("origin"))
    if any(ord(c) < 32 or ord(c) >= 127 for c in value["cookie"]):
        raise BridgeError("Invalid profile cookie; pair again.")
    return value


def pair(invitation, endpoint=None):
    invite = urlsplit(invitation.strip())
    origin = f"{invite.scheme}://{invite.netloc}"
    parse_origin(origin)
    grants = parse_qs(invite.fragment).get("grant", [])
    if len(grants) != 1 or not grants[0] or len(grants[0]) > 16384:
        raise BridgeError("Invitation has no valid one-use grant.")
    transport = Transport(endpoint or origin, origin, timeout=10)
    status, _, body = transport.request("GET", "/ui/auth/status")
    if status != 200 or json_object(body).get("tokenValid") is not False:
        raise BridgeError("Endpoint did not pass the unpaired Framework app probe.")
    status, headers, _ = transport.request("POST", "/ui/auth/session", b"", {"X-Local-Session-Grant": grants[0]})
    if status != 200:
        raise BridgeError("Invitation redemption failed. Copy a fresh AI prompt.")
    cookies = SimpleCookie()
    for key, value in headers:
        if key.lower() == "set-cookie":
            cookies.load(value)
    cookie_name = f"local_ui_session_p{invite.port or (443 if invite.scheme == 'https' else 80)}"
    if cookie_name not in cookies:
        raise BridgeError("App did not issue the expected session cookie.")
    transport.cookie = f"{cookie_name}={cookies[cookie_name].value}"
    status, _, body = transport.request("GET", "/ui/auth/status")
    if status != 200 or json_object(body).get("tokenValid") is not True:
        raise BridgeError("App did not verify the paired session.")
    hello = transport.rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                           "params": {"protocolVersion": VERSION, "capabilities": {},
                                      "clientInfo": {"name": "framework-connector", "version": "1"}}})
    result = hello.get("result")
    if "error" in hello or not isinstance(result, dict) or not isinstance(result.get("serverInfo"), dict):
        raise BridgeError("App session is valid but MCP initialization failed.")
    return {"version": 1, "endpoint": endpoint or origin, "origin": origin, "cookie": transport.cookie}, hello["result"]


def serve(profile, source=None, output=None, timeout=DEFAULT_TIMEOUT, *, transport_factory=Transport):
    transport = transport_factory(profile["endpoint"], profile["origin"], profile["cookie"], timeout=timeout)
    serve_transport(transport, source, output)


def serve_transport(transport, source=None, output=None):
    source, output = source or sys.stdin.buffer, output or sys.stdout.buffer
    output_lock, pending_lock = threading.Lock(), threading.Lock()
    pending = {}
    slots = threading.Semaphore(16)
    stopping = threading.Event()

    def stop():
        stopping.set()
        with pending_lock:
            cancellations = list(pending.values())
        for cancellation in cancellations:
            cancellation.set()

    def write(value):
        with output_lock:
            if stopping.is_set():
                return
            try:
                output.write(encode(value) + b"\n")
                output.flush()
            except (BrokenPipeError, OSError):
                stop()

    def error(identifier, message):
        write({"jsonrpc": "2.0", "id": identifier, "error": {"code": -32000, "message": message}})

    def execute(message, key, cancelled):
        try:
            if stopping.is_set() or cancelled.is_set():
                return
            result = transport.rpc(message, cancellation=cancelled)
            if result is not None and not cancelled.is_set():
                write(result)
        except BridgeError as failure:
            if "id" in message and not cancelled.is_set():
                error(message["id"], str(failure))
        except (ValueError, TypeError, AttributeError, RecursionError):
            if "id" in message and not cancelled.is_set():
                error(message["id"], "Invalid MCP message.")
        finally:
            with pending_lock:
                pending.pop(key, None)
            slots.release()

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as workers:
        while not stopping.is_set():
            try:
                line = source.readline(MAX_MESSAGE + 2)
            except (OSError, KeyboardInterrupt):
                stop()
                break
            if not line:
                stop()
                break
            if len(line) > MAX_MESSAGE or not line.endswith(b"\n"):
                error(None, "MCP input line exceeds 1 MiB or is incomplete.")
                stop()
                break
            try:
                message = decode(line)
                if (not isinstance(message, dict) or message.get("jsonrpc") != "2.0"
                        or not isinstance(message.get("method"), str)
                        or ("params" in message and not isinstance(message["params"], dict))
                        or ("id" in message and not valid_id(message["id"]))):
                    raise ValueError()
                if message["method"] == "notifications/cancelled":
                    # Stop the active HTTP wait and prevent queued work from starting.
                    # A running HTTP mutation may already have completed; no rollback is claimed.
                    identifier = (message.get("params") or {}).get("requestId")
                    with pending_lock:
                        cancellation = pending.get(encode(identifier))
                    if cancellation:
                        cancellation.set()
                    continue
                key = encode(message.get("id")) if "id" in message else object()
                cancelled = RequestCancellation()
                with pending_lock:
                    duplicate = key in pending
                    if not duplicate and slots.acquire(blocking=False):
                        pending[key] = cancelled
                    else:
                        raise BridgeError("Duplicate in-flight ID or connector concurrency limit reached; check outstanding calls.")
                workers.submit(execute, message, key, cancelled)
            except (ValueError, UnicodeError, RecursionError):
                error(None, "Invalid JSON-RPC input.")
            except BridgeError as failure:
                error(message.get("id"), str(failure))


def client_config(profile_path, timeout=DEFAULT_TIMEOUT):
    """Configuration contains only executable/profile paths, never credentials."""
    return {"mcpServers": {"framework-app": {"command": sys.executable,
        "args": [str(Path(__file__).resolve()), "stdio", "--profile", str(Path(profile_path).absolute()),
                 "--request-timeout", str(request_timeout(timeout))]}}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("pair", "stdio", "config"))
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--endpoint", help="Explicit HTTPS tunnel origin for pairing; preserves invitation Host/Origin")
    parser.add_argument("--request-timeout", default=str(DEFAULT_TIMEOUT), help="HTTP wait in seconds (1–3600; default 180). Never retries a write.")
    args = parser.parse_args()
    try:
        if args.command == "pair":
            invitation = getpass.getpass("Invitation URL (hidden): ") if sys.stdin.isatty() else sys.stdin.readline(MAX_MESSAGE)
            profile, hello = pair(invitation, args.endpoint)
            save_profile(args.profile, profile)
            print(json.dumps({"connected": True, "serverInfo": hello["serverInfo"], "profile": str(args.profile.absolute())}))
        elif args.command == "config":
            load_profile(args.profile)
            print(json.dumps(client_config(args.profile, args.request_timeout), indent=2))
        else:
            serve(load_profile(args.profile), timeout=request_timeout(args.request_timeout))
        return 0
    except (BridgeError, OSError, ValueError, KeyError, TypeError):
        print("Framework MCP connection failed. Check the app, selected access and profile; pair with a fresh prompt if needed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
