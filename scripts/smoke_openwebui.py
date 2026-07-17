"""Verify Open WebUI can reach Data Platform MCP by service name on ai-platform.

This only exercises network reachability (HU-801). It never drives Open WebUI's
chat or admin UI, since that requires a real LLM provider configured by the
operator — see docs/openwebui-integration.md for the manual HU-802/HU-803 runbook.
"""

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request


def parse_args() -> argparse.Namespace:
    """Parse the Open WebUI container name and the MCP service URL to reach."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--openwebui-container", default="openwebui-open-webui-1")
    parser.add_argument("--mcp-health-url", default="http://data-platform-mcp:8000/health")
    parser.add_argument("--local-openwebui-url", default="http://127.0.0.1:3000")
    return parser.parse_args()


def check_local_openwebui(url: str) -> None:
    """Confirm Open WebUI itself answers on its published port."""
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            if response.status >= 500:
                raise RuntimeError(f"Open WebUI respondió {response.status} en {url}")
    except urllib.error.URLError as error:
        raise RuntimeError(f"Open WebUI no respondió en {url}: {error}") from error


def check_mcp_reachable_from_openwebui(container: str, mcp_health_url: str) -> dict[str, object]:
    """Confirm the MCP server is reachable by service name from inside the network."""
    probe = (
        "import json, urllib.request, sys; "
        f"r = urllib.request.urlopen('{mcp_health_url}', timeout=5); "
        "sys.stdout.write(r.read().decode())"
    )
    result = subprocess.run(
        ["docker", "exec", container, "python3", "-c", probe],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"data-platform-mcp no es alcanzable por nombre desde '{container}': "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    payload: dict[str, object] = json.loads(result.stdout)
    if payload.get("status") != "ok":
        raise RuntimeError(f"health_check inesperado desde Open WebUI: {payload}")
    return payload


def main() -> None:
    """Run the connectivity checks and print one reviewable JSON document."""
    args = parse_args()
    check_local_openwebui(args.local_openwebui_url)
    mcp_health = check_mcp_reachable_from_openwebui(
        args.openwebui_container,
        args.mcp_health_url,
    )
    print(
        json.dumps(
            {
                "open_webui_reachable": True,
                "mcp_reachable_from_open_webui": True,
                "mcp_health": mcp_health,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        print(f"FALLÓ: {error}", file=sys.stderr)
        sys.exit(1)
