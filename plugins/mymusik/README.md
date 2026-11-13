# MyMusik MCP

Use an MCP client to search the music you own in a running MyMusik app. The connector runs on your computer and connects to the app on localhost or your private network. You choose the permissions and session duration in MyMusik.

## Pair and find your first albums

**Guided setup with this source or bundle:** From the extracted plugin directory, run `python mymusik_mcp/cli.py setup` on a desktop with Python 3.10+ and Tk. The window offers **Open MyMusik** and **Download MyMusik**.

1. Open the **profile menu → Insights**. On the **Connect a device** card, select the shield at the right end of the header, above the QR code.
2. In **QR code access**, choose a permission preset and session duration. Select **Apply**, then **Copy agent prompt** below the QR code (**AI agent** in the compact view).
3. Back in setup, choose **Paste invitation and pair**. Reconnect the client and ask it to list three albums. If your MCP client uses JSON configuration, **Copy client configuration** provides this installation's exact launch paths.

**Terminal pairing with the released wheel**

1. Install Python 3.10 or newer. Install the release wheel with `python -m pip install https://github.com/shagg-ai/mymusik-mcp/releases/download/v0.2.0/mymusik_mcp-0.2.0-py3-none-any.whl`. Once version 0.2.0 is published on PyPI, you can use `python -m pip install mymusik-mcp==0.2.0`. Activate the environment you installed into before running its commands.
2. Follow the **profile menu → Insights** steps above to copy a fresh prompt with **Read only** access. Keep MyMusik running.
3. Run `mymusik-mcp pair`. At the hidden input, paste just the invitation URL containing `#grant=` from the copied prompt and press Enter. Each invitation can be used once.
4. Add the local connector to your MCP client. Set the executable to `mymusik-mcp` (or its absolute installed path) and the argument to `stdio`. Clients that start the executable with no arguments also use stdio. The Claude and Codex plugins supply their own launch configuration.
5. Ask **“List three albums from my MyMusik library.”** Compare the names with **Albums** in MyMusik.

If the session expires, copy a fresh invitation and run `mymusik-mcp pair` again. Restart or reconnect the MCP server in your client so it loads the renewed session. To pair another instance, supply the same `--profile PATH` to both `pair` and `stdio`. [MyMusik pairing guide](https://mymusik.app/en/music-mcp-server/)

## Claude and Codex

Claude launches its bundled connector using `python`. With Python 3.10 or newer on PATH, you can pair from this plugin folder with `python mymusik_mcp/cli.py pair`. Codex launches the installed `mymusik-mcp` command from its PATH. If you install the wheel in a virtual environment, start Codex from that activated environment. Pair under the same operating-system account that runs your client.

For Claude Code, start a local session with `claude --plugin-dir ./plugins/mymusik` from the repository root. For Codex, run `codex plugin marketplace add .`, then `codex plugin add mymusik@mymusik-plugins` and start a new local chat. After the GitHub release, users can replace the first command with `codex plugin marketplace add shagg-ai/mymusik-mcp`.

## Permissions and stored data

The connector stores the paired session under `%LOCALAPPDATA%/mymusik-mcp/connection.profile` on Windows, protected with Windows user-scoped DPAPI. On other systems it uses a private file with mode 0600 under `$XDG_CONFIG_HOME/mymusik-mcp` or `~/.config/mymusik-mcp`. Deleting the profile removes the connector's saved session. Keep invitations and profiles private. Tool results go to the MCP client you choose. Library edits and playback depend on the permissions granted in MyMusik.

With playback access, ask your client to pause, resume, skip or go back a track. The bundled mymusik_playback tool acts on the current queue.
