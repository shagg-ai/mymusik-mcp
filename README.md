# MyMusik MCP

Use an MCP client to search the music you own in a running MyMusik app. The connector runs on your computer and connects to the app on localhost or your private network. You choose the permissions and session duration in MyMusik.

<!-- mcp-name: io.github.shagg-ai/mymusik-mcp -->

Clients that support local MCP bundles can install the release from the [official MCP Registry](https://registry.modelcontextprotocol.io/v0.1/servers/io.github.shagg-ai%2Fmymusik-mcp/versions/latest) or [download the MCPB](https://github.com/shagg-ai/mymusik-mcp/releases/download/v0.1.0/mymusik-mcp.mcpb). Pair with MyMusik before your first library query.

## Pair and find your first albums

1. Install Python 3.10 or newer. Install the published wheel with `python -m pip install https://github.com/shagg-ai/mymusik-mcp/releases/download/v0.1.0/mymusik_mcp-0.1.0-py3-none-any.whl`. Activate the environment you installed into before running its commands.
2. Open MyMusik and go to **Insights → Connect a device**. Open the shield, choose **Read only** and a duration, select **Apply**, and copy the agent prompt. Keep MyMusik running.
3. Run `mymusik-mcp pair`. At the hidden input, paste just the invitation URL containing `#grant=` from the copied prompt and press Enter. Each invitation can be used once.
4. Add the local connector to your MCP client. Set the executable to `mymusik-mcp` (or its absolute installed path) and the argument to `stdio`. Clients that start the executable with no arguments also use stdio. The Claude and Codex plugins supply their own launch configuration.
5. Ask **“List three albums from my MyMusik library.”** Compare the names with **Albums** in MyMusik.

If the session expires, copy a fresh invitation and run `mymusik-mcp pair` again. Restart or reconnect the MCP server in your client so it loads the renewed session. To pair another instance, supply the same `--profile PATH` to both `pair` and `stdio`. [MyMusik pairing guide](https://mymusik.app/en/music-mcp-server/)

## Claude and Codex

Claude launches its bundled connector using `python`. Codex launches the installed `mymusik-mcp` command from its PATH. With a virtual environment, start Codex from the activated environment. For a desktop launcher, install the wheel with `pipx install mymusik_mcp-0.1.0-py3-none-any.whl` and make the pipx applications directory available on PATH, then restart Codex. Pair under the same operating-system account that runs your client. You can also pair directly from this checkout with `python plugins/mymusik/mymusik_mcp/cli.py pair`.

For Claude Code, start a local session with `claude --plugin-dir ./plugins/mymusik` from the repository root. For Codex, run `codex plugin marketplace add shagg-ai/mymusik-mcp`, then `codex plugin add mymusik@mymusik-plugins` and start a new local chat.

## Permissions and stored data

The connector stores the paired session under `%LOCALAPPDATA%/mymusik-mcp/connection.profile` on Windows, protected with Windows user-scoped DPAPI. On other systems it uses a private file with mode 0600 under `$XDG_CONFIG_HOME/mymusik-mcp` or `~/.config/mymusik-mcp`. Deleting the profile removes the connector's saved session. Keep invitations and profiles private. Tool results go to the MCP client you choose. Library edits and playback depend on the permissions granted in MyMusik.
