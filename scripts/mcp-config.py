"""Print an MCP client configuration with the correct absolute project paths."""

import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
print(
    json.dumps(
        {
            "mcpServers": {
                "so101": {
                    "command": str(root / ".venv/bin/python"),
                    "args": ["-m", "backend.mcp_server"],
                    "cwd": str(root),
                    "env": {"SO101_API_URL": "http://127.0.0.1:8765"},
                }
            }
        },
        indent=2,
    )
)
