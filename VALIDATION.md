# MyMusik MCP 0.2.0 release checks

The published wheel was built from the source archive and installed into a fresh Windows Python 3.13 environment. All 19 shared bridge tests and the new playback integration test passed. The playback test launches the stdio command against a local HTTP test server and checks discovery, the four actions, session-cookie forwarding, invalid input and a permission denial without a retry.

The four operation IDs match MyMusik’s published API contract. The extracted MCPB passed the same playback test, the bundle hash matched the registry manifest, and Claude Code validated the plugin. Audio output on a running MyMusik app was not exercised in this release check.

## MyMusik MCP 0.1.0 release checks

Validated on Windows on 2026-11-12 with Python 3.13 and the local MyMusik 1.2.6 debug application.

| Check | Result |
|---|---|
| Python distributions | Built the source archive, then built the wheel from it. Both passed `twine check --strict`. Installed the final wheel in an isolated environment outside the repository. All 19 Framework connector tests passed against the installed module. |
| Local pairing and album search | Used the app's invitation API with the same GET/HEAD permissions as the Read only preset. Fed the single-use URL to the installed pairing command over stdin. Its default stdio server returned both albums present in the library. IDs and names matched the app's album API and both names were visible on the Albums screen. |
| Permissions and expiry | The read-only connection refused an erase request targeting a nonexistent album ID. A short-lived grant expired, the app rejected the existing session, and pairing with a fresh invitation restored the album query. |
| Claude | Claude Code 2.1.322 passed local plugin validation, and its MCP health check reported the bundled server connected. The bundled launch command returned the same albums. |
| Codex | Installed the marketplace and plugin into an isolated Codex home. With the wheel's command on PATH, the Codex app server discovered all seven MyMusik MCP tools. |
| Registry and archives | Validated the listing against its official 2025-12-11 schema. Checked distribution contents against explicit file lists, confirmed the PyPI ownership marker, verified the bridge is byte-identical to the Framework source, and checked for invitation, cookie and private-key material. |

The live check used automated stdin pairing. The interactive hidden-input prompt and other operating systems were outside this run. Public name ownership, portal review and public installation are checked during publication.

| Artifact | SHA-256 |
|---|---|
| `mymusik_mcp-0.1.0-py3-none-any.whl` | `9b3c828f96f6fe59a7502a627d55d0c9fc43c12513dcb9eb0f7651a8b98c8bdf` |
| `mymusik_mcp-0.1.0.tar.gz` | `70fe7e31bdb2932c5a39576cdf77da4ed32ce3a3a780a8421b496f8914f5e4b1` |
