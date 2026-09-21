"""Minimal MCP server for Zen Browser (Firefox-based) over WebDriver BiDi.

Setup
-----
    pip install "mcp[cli]" websockets

Fully quit Zen, then start it with remote debugging enabled:
    macOS:   /Applications/Zen.app/Contents/MacOS/zen --remote-debugging-port 9222
    Linux:   zen --remote-debugging-port 9222
    Windows: "C:\\Program Files\\Zen Browser\\zen.exe" --remote-debugging-port 9222

Run / register with an MCP client (stdio transport):
    python server.py

Claude Desktop config example:
    {"mcpServers": {"zen": {"command": "python", "args": ["/abs/path/server.py"]}}}

NOTE: with stdio transport never print() to stdout; it corrupts the protocol.
Use logging (stderr) instead.
"""
import asyncio
import itertools
import json
import logging
import os
from typing import Any

import websockets
from mcp.server.fastmcp import FastMCP, Image

logging.basicConfig(level=logging.INFO)  # goes to stderr
log = logging.getLogger("zen-mcp")

PORT = int(os.environ.get("ZEN_DEBUG_PORT", "9222"))
URL = f"ws://127.0.0.1:{PORT}/session"

mcp = FastMCP("zen-browser")


class BiDiError(RuntimeError):
    pass


class BiDi:
    """Tiny WebDriver BiDi client: JSON commands over one WebSocket."""

    def __init__(self) -> None:
        self.ws = None
        self.ids = itertools.count(1)
        self.pending: dict[int, asyncio.Future] = {}
        self.lock = asyncio.Lock()

    async def _read(self) -> None:
        try:
            async for raw in self.ws:
                msg = json.loads(raw)
                fut = self.pending.pop(msg.get("id"), None)
                if fut is None:
                    continue  # an event, not a command response
                if msg.get("type") == "error":
                    fut.set_exception(
                        BiDiError(f"{msg.get('error')}: {msg.get('message')}")
                    )
                else:
                    fut.set_result(msg.get("result", {}))
        finally:
            self.ws = None
            for fut in self.pending.values():
                if not fut.done():
                    fut.set_exception(BiDiError("Connection to Zen closed"))
            self.pending.clear()

    async def _send(self, method: str, params: dict[str, Any]) -> dict:
        cmd_id = next(self.ids)
        fut = asyncio.get_running_loop().create_future()
        self.pending[cmd_id] = fut
        await self.ws.send(json.dumps({"id": cmd_id, "method": method, "params": params}))
        return await fut

    async def call(self, method: str, params: dict[str, Any] | None = None) -> dict:
        async with self.lock:
            if self.ws is None:
                try:
                    self.ws = await websockets.connect(URL, max_size=None)
                except OSError as e:
                    raise BiDiError(
                        f"Can't reach Zen on port {PORT}. Start Zen with "
                        f"--remote-debugging-port {PORT} first."
                    ) from e
                asyncio.create_task(self._read())
                await self._send("session.new", {"capabilities": {}})
        return await self._send(method, params or {})


bidi = BiDi()


async def _ctx(tab_id: str | None) -> str:
    """Use the given tab, or fall back to the first top-level tab."""
    if tab_id:
        return tab_id
    tree = await bidi.call("browsingContext.getTree")
    if not tree["contexts"]:
        raise BiDiError("No open tabs")
    return tree["contexts"][0]["context"]


def _value(result: dict) -> Any:
    if result.get("type") == "exception":
        raise BiDiError(result["exceptionDetails"]["text"])
    return result["result"].get("value")


@mcp.tool()
async def list_tabs() -> list[dict]:
    """List open top-level tabs (id + current URL)."""
    tree = await bidi.call("browsingContext.getTree")
    return [{"id": c["context"], "url": c["url"]} for c in tree["contexts"]]


@mcp.tool()
async def new_tab(url: str = "about:blank") -> str:
    """Open a new tab and optionally navigate it. Returns the tab id."""
    res = await bidi.call("browsingContext.create", {"type": "tab"})
    tab = res["context"]
    if url != "about:blank":
        await bidi.call(
            "browsingContext.navigate", {"context": tab, "url": url, "wait": "complete"}
        )
    return tab


@mcp.tool()
async def close_tab(tab_id: str) -> str:
    """Close a tab by id."""
    await bidi.call("browsingContext.close", {"context": tab_id})
    return "closed"


@mcp.tool()
async def navigate(url: str, tab_id: str | None = None) -> str:
    """Navigate a tab (default: first tab) to a URL and wait for load."""
    res = await bidi.call(
        "browsingContext.navigate",
        {"context": await _ctx(tab_id), "url": url, "wait": "complete"},
    )
    return res.get("url", url)


@mcp.tool()
async def get_page_text(tab_id: str | None = None) -> str:
    """Return the visible text of the page."""
    res = await bidi.call(
        "script.evaluate",
        {
            "expression": "document.body.innerText",
            "target": {"context": await _ctx(tab_id)},
            "awaitPromise": False,
        },
    )
    return _value(res) or ""


@mcp.tool()
async def evaluate(expression: str, tab_id: str | None = None) -> Any:
    """Evaluate JavaScript in the page and return the (primitive) result."""
    res = await bidi.call(
        "script.evaluate",
        {
            "expression": expression,
            "target": {"context": await _ctx(tab_id)},
            "awaitPromise": True,
        },
    )
    return _value(res)


@mcp.tool()
async def screenshot(tab_id: str | None = None) -> Image:
    """Screenshot the viewport as a PNG."""
    import base64

    res = await bidi.call(
        "browsingContext.captureScreenshot", {"context": await _ctx(tab_id)}
    )
    return Image(data=base64.b64decode(res["data"]), format="png")


if __name__ == "__main__":
    mcp.run()  # stdio transport
