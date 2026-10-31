# Local mode: no Cloudflare Worker

Everything runs on your own Wi-Fi. Claude talks to the board through a small
MCP server on your computer, and the Unicorn Remote runs as a local web page.
You don't need Cloudflare, Node.js or a custom connector, only Python 3.8+
(standard library, nothing to install).

```
Claude Desktop / Claude Code ──stdio──> unicorn_mcp.py ──Wi-Fi──> board (port 80)
Browser ──> serve.py (localhost:8765) ──────────────────Wi-Fi──> board (port 80)
```

| | Cloud mode (`cloud/`) | Local mode (`local/`) |
|---|---|---|
| Works from | anywhere, incl. phone and claude.ai web | a computer on the same Wi-Fi as the board |
| Claude apps | any with custom connectors | Claude Desktop, Claude Code |
| Remote app | artifact in claude.ai | `http://localhost:8765` |
| Needs | Cloudflare account, Node.js | Python 3 |
| Tools | the 9 board tools | the same 9 board tools |

## 1. Set up the board without the cloud

Follow the board step of the main [Setup](../README.md#setup), but **skip
`_cloud.json`**: save `main.py`, `boot.py`, `_wd.py`, `secrets.py` and any
programs from `board/programs/`. Without `_cloud.json` the launcher simply
doesn't check in anywhere; its local web API is always on.

Already running in cloud mode? Both can run at once. Delete `_cloud.json` from
the board only if you want to turn the cloud off.

## 2. Find the board's address

The board scrolls its IP address when it starts (and when no program is
running). Check it by opening `http://<that-ip>/` in a browser: you should see
the board's own page.

The address can change when your router restarts. To keep it fixed, set a
**DHCP reservation** for the board in your router's settings. Some networks
also resolve `unicorn.local`; that's the default if you don't set an address.

## 3. Add the MCP server to Claude

**Claude Desktop:** Settings → Developer → Edit Config, and add to
`claude_desktop_config.json` (use the full path to this folder):

```json
{
  "mcpServers": {
    "stellar-unicorn": {
      "command": "python3",
      "args": ["/full/path/to/stellar-unicorn-x-claude/local/unicorn_mcp.py"],
      "env": { "UNICORN_HOST": "192.168.0.154" }
    }
  }
}
```

On Windows use `"command": "python"` and a path like
`"C:\\Users\\you\\stellar-unicorn-x-claude\\local\\unicorn_mcp.py"`.
Restart Claude Desktop.

**Claude Code:**

```bash
claude mcp add stellar-unicorn -e UNICORN_HOST=192.168.0.154 -- python3 /full/path/to/local/unicorn_mcp.py
```

Then ask: "What's on my Unicorn right now?"

Check the server by hand (it should print the board's status):

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_board_status","arguments":{}}}' \
  | UNICORN_HOST=192.168.0.154 python3 unicorn_mcp.py
```

## 4. Run the Unicorn Remote locally

```bash
python3 local/serve.py --host 192.168.0.154
```

Open <http://localhost:8765>. It's the same app as the artifact (tiles,
brightness, power-on default, rotation builder with drag-and-drop), with
calls going through `serve.py` to the board. Stop it with Ctrl-C.

`serve.py` only listens on your own computer (127.0.0.1). The board also has a
simpler page of its own at `http://<board-ip>/`, which works from a phone on
the same Wi-Fi.

## Settings

| Variable | Default | Used by |
|---|---|---|
| `UNICORN_HOST` | `unicorn.local` | both; the board's IP or host name |
| `UNICORN_TIMEOUT` | `15` | `unicorn_mcp.py`; seconds per request |
| `PORT` / `--port` | `8765` | `serve.py` |

## Security

The board's local API has **no password**: anyone on your Wi-Fi can change what
it shows, upload programs, or delete them. That's fine on a home network you
trust; don't put the board on a guest or public network, and don't forward
port 80 to it from your router.

## Troubleshooting

- **"Can't reach the board"**: check the IP (it scrolls at startup), that your
  computer is on the same network (not a guest network or VPN), and that
  `http://<board-ip>/api/status` opens in a browser.
- **Claude Desktop doesn't show the tools**: check the path in the config is
  absolute, that `python3` runs from a terminal, and see the MCP logs
  (Settings → Developer).
- **Remote shows "Can't reach the board"**: restart `serve.py` with the right
  `--host`.
