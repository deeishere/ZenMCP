Minimal MCP server for Zen Browser (Firefox-based) over WebDriver BiDi.

Setup
-----
    pip install "mcp[cli]" websockets

Fully quit Zen, then start it with remote debugging enabled:
    macOS:   /Applications/Zen.app/Contents/MacOS/zen --remote-debugging-port 9222
    Linux:   zen --remote-debugging-port 9222
    Windows: "C:\\Program Files\\Zen Browser\\zen.exe" --remote-debugging-port 9222


Claude Desktop config example:

    {"mcpServers": {"zen": {"command": "python", "args": ["/abs/path/server.py"]}}}

Quit claude and re open and test it with zen

# Zen Browser MCP Server

A small [Model Context Protocol](https://modelcontextprotocol.io) server that lets Claude control [Zen Browser](https://zen-browser.app). It is written in Python and talks to Zen over WebDriver BiDi, so it needs no browser extension, Selenium, or Playwright.

> **Status:** a minimal starting point with seven tools. Expect to adjust details for your setup.

## How it works

```
Claude Desktop / Claude Code
        │  (MCP over stdio)
        ▼
   server.py  ──(WebSocket, WebDriver BiDi)──▶  Zen Browser (port 9222)
```

Zen is built on Firefox, which supports WebDriver BiDi. That protocol is off by default. Starting Zen with `--remote-debugging-port` opens a local WebSocket that this server uses to list tabs, navigate, read pages, and take screenshots.

## Tools

| Tool | What it does |
|------|--------------|
| `list_tabs` | List open top-level tabs (id and URL) |
| `new_tab` | Open a new tab, optionally at a URL; returns its id |
| `close_tab` | Close a tab by id |
| `navigate` | Go to a URL and wait for the page to load |
| `get_page_text` | Return the visible text of the page |
| `evaluate` | Run JavaScript in the page and return the result |
| `screenshot` | Capture the viewport as a PNG |

Every tool that takes `tab_id` falls back to the **first tab in browser order** when it is omitted. That is not necessarily the tab you are looking at. Pass an explicit `tab_id` (from `list_tabs`) when it matters.

## Requirements

- Python 3.10 or newer
- Zen Browser
- Claude Desktop or Claude Code (the server runs on your own computer, so it does not work from claude.ai in the browser or the mobile app)

## Install

Use a virtual environment so the packages don't clash with others on your machine.

```bash
python3 -m venv zen-env
source zen-env/bin/activate          # Windows: zen-env\Scripts\activate
python3 -m pip install "mcp[cli]<2" websockets
```

> **Important:** pin `mcp<2`. Version 2.x renamed `FastMCP`, and this code uses the 1.x API. Without the pin, the server crashes on startup with `No module named 'mcp.server.fastmcp'`.

Check the install:

```bash
python3 -c "from mcp.server.fastmcp import FastMCP; print('ok')"
```

## Run Zen with remote debugging

Fully quit Zen first (Cmd+Q on macOS; closing the window is not enough), then relaunch it with the flag:

```bash
# macOS
/Applications/Zen.app/Contents/MacOS/zen --remote-debugging-port 9222

# Linux
zen --remote-debugging-port 9222

# Windows (PowerShell)
& "C:\Program Files\Zen Browser\zen.exe" --remote-debugging-port 9222
```

The flag only takes effect at launch, so an already-running Zen won't pick it up. Check that the port is open:

```bash
python3 -c "import socket; socket.create_connection(('127.0.0.1', 9222), 2); print('debug port open')"
```

To use a different port, set the `ZEN_DEBUG_PORT` environment variable for the server.

## Connect Claude

You need the full path to the venv's Python and to `server.py`:

```bash
python3 -c "import sys; print(sys.executable)"           # run with the venv active
python3 -c "import os; print(os.path.abspath('server.py'))"
```

### Claude Desktop

Edit `claude_desktop_config.json`:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "zen": {
      "command": "/full/path/to/zen-env/bin/python3",
      "args": ["/full/path/to/server.py"]
    }
  }
}
```

If the file already has other servers, add `"zen"` inside the existing `mcpServers` block. On Windows, use forward slashes in paths (`C:/Users/you/zen-env/Scripts/python.exe`) or double the backslashes.

Restart Claude Desktop completely (Cmd+Q, then reopen). The `zen` server should appear under Settings → Developer.

### Claude Code

```bash
claude mcp add zen -- /full/path/to/zen-env/bin/python3 /full/path/to/server.py
```

### Try it

Ask Claude: *"List my open tabs in Zen."*

## Troubleshooting

| Symptom | Cause and fix |
|---------|---------------|
| `Failed to spawn process: No such file or directory` in the Claude log | The config's `command` isn't a real path. Use the full path to the venv's Python, not plain `python`. |
| `No module named 'mcp'` | The package was installed into a different Python. Use `python3 -m pip install ...` inside the activated venv. |
| `No module named 'mcp.server.fastmcp'` | You have `mcp` 2.x. Run `python3 -m pip install "mcp<2"`. |
| pip warns about conflicts with `selenium` or `httpcore` | Those come from other packages in your global Python. Use a venv and the warnings go away. |
| `Connection refused` on port 9222, or "Can't reach Zen" | Zen isn't running with `--remote-debugging-port`. Quit it fully and relaunch with the flag. |
| Server shows as disconnected right after starting | Read the log: `~/Library/Logs/Claude/mcp-server-zen.log` on macOS. |

With the stdio transport, never `print()` to stdout in the server, because that corrupts the protocol. Log to stderr instead.

## Security

This gives an AI control of a browser that may be logged in to your accounts.

- Run it only when you want it, and quit Zen (or relaunch it without the flag) afterward.
- The debug port listens on `127.0.0.1` only, so other devices can't reach it by default. Don't expose it on a shared or untrusted network.
- Anything Claude reads from a web page is untrusted content. Be careful with pages that could contain instructions aimed at the AI.
- `evaluate` runs arbitrary JavaScript in the page. Consider removing it or adding a domain allowlist if you share this setup.

## Ideas for extending it

- Interaction tools: click, fill, and key presses, via `evaluate` or BiDi's `input.performActions`.
- Focus tracking, so "current tab" means the tab you are actually viewing.
- Zen-specific data, such as Spaces and pinned tabs, read from the Zen profile directory.
- Packaging for `uvx` or `pipx` so others can install it in one command.

## Existing alternatives

- [`sh6drack/zen-mcp`](https://github.com/sh6drack/zen-mcp) (JavaScript, WebDriver BiDi, run with `npx -y zen-mcp`)
- [`ZenLink-MCP`](https://github.com/JayQuan-McCleary/ZenLink-MCP) (Python, extension-based, `uvx zenlink-mcp`)
