"""Expose common queue controls alongside the app's discovery and library tools."""

if __package__:
    from . import mcp_stdio as bridge
else:
    import mcp_stdio as bridge


OPERATIONS = {
    "resume": "Service::Player::startPlaying",
    "pause": "Service::Player::stopPlaying",
    "next": "Service::Player::nextTrack",
    "previous": "Service::Player::prevTrack",
}
TOOL = {
    "name": "mymusik_playback",
    "description": (
        "Control the current MyMusik queue. Resume or pause playback, skip to the next "
        "track, or go back one track. Requires playback access. To play a particular "
        "song, album or playlist by name, use the app's search and API tools."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {"action": {"type": "string", "enum": list(OPERATIONS)}},
        "required": ["action"],
        "additionalProperties": False,
    },
}


class UnpairedMyMusik:
    """Offer connector-owned discovery until the user pairs and restarts the client."""

    def rpc(self, message, cancellation=None):
        if "id" not in message:
            return None
        reply = {"jsonrpc": "2.0", "id": message["id"]}
        method = message["method"]
        instruction = ("On the computer running your MCP client, open MyMusik Setup with mymusik-mcp setup. "
                       "Choose Open pairing settings. For older players, open the MyMusik profile menu and select Insights. In the Connect a device card header, "
                       "select the shield above the QR code. Choose permissions and a session duration in QR code access, "
                       "select Apply, then Copy agent prompt below the QR code. In setup, choose Paste invitation and pair. "
                       "For terminal pairing, use mymusik-mcp pair. Reconnect the client after pairing.")
        if method == "initialize":
            version = message.get("params", {}).get("protocolVersion")
            result = {
                "protocolVersion": version if version in bridge.SUPPORTED_VERSIONS[:3] else bridge.VERSION,
                "serverInfo": {"name": "MyMusik", "version": "0.2.0"},
                "capabilities": {"tools": {}},
                "instructions": instruction,
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": [TOOL]}
        elif method == "tools/call":
            result = {"isError": True, "content": [{"type": "text", "text": instruction}]}
        else:
            return {**reply, "error": {"code": -32601, "message": "Method not found."}}
        return {**reply, "result": result}


class MyMusikTransport(bridge.Transport):
    def rpc(self, message, cancellation=None):
        method = message.get("method")
        params = message.get("params", {})
        if method == "tools/call" and params.get("name") == TOOL["name"]:
            args = params.get("arguments")
            if (not isinstance(args, dict) or args.keys() != {"action"}
                    or not isinstance(args["action"], str) or args["action"] not in OPERATIONS):
                raise bridge.BridgeError("Choose one playback action: resume, pause, next or previous.")
            message = {**message, "params": {
                **params, "name": "api.call", "arguments": {"operationId": OPERATIONS[args["action"]]},
            }}

        reply = super().rpc(message, cancellation=cancellation)
        if method == "tools/list" and not params.get("cursor") and reply is not None:
            tools = reply.get("result", {}).get("tools")
            if isinstance(tools, list):
                names = {tool.get("name") for tool in tools if isinstance(tool, dict)}
                if "api.call" in names and TOOL["name"] not in names:
                    tools.append(TOOL)
        return reply
