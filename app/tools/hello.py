"""Bootstrap MCP tools."""


def hello_world(name: str = "world") -> dict[str, str]:
    """Return a deterministic greeting used to verify MCP connectivity."""
    recipient = name.strip() or "world"
    return {"message": f"Hello, {recipient}!"}
