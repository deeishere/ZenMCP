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


