"""Run the verified example through HTTP. Usage: python examples/run_task.py [session-id]"""

import sys
import time
import httpx

with httpx.Client(
    base_url="http://127.0.0.1:8765", timeout=30, trust_env=False
) as client:

    def request(method, path, **kwargs):
        result = client.request(method, path, **kwargs)
        result.raise_for_status()
        return result.json()

    sid = (
        sys.argv[1]
        if len(sys.argv) > 1
        else request("POST", "/api/sessions")["sessionId"]
    )
    print(f"View this session: http://127.0.0.1:5173/?session={sid}", flush=True)
    url = f"/api/sessions/{sid}"
    request("POST", url + "/command", json={"type": "pause"})
    request("POST", url + "/command", json={"type": "example"})
    request("POST", url + "/command", json={"type": "run"})
    previous = None
    deadline = time.monotonic() + 60
    try:
        while time.monotonic() < deadline:
            state = request("GET", url)
            task = state["task"]
            if task["phase"] != previous:
                print(f"{state['time']:.2f}s: {task['phase']}", flush=True)
                previous = task["phase"]
            if task["status"] in ("succeeded", "failed"):
                print(task["message"])
                sys.exit(0 if task["success"] else 1)
            time.sleep(0.25)
        raise TimeoutError("Task did not finish within 60 seconds")
    finally:
        request("POST", url + "/command", json={"type": "pause"})
