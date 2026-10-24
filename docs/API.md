# Scene Studio control API (v3)

Service: `http://127.0.0.1:8765`; editor/proxy: `http://127.0.0.1:5173`. No key, cloud or hardware access. Local hosts/origins only; do not expose it publicly. All positions/lengths **meters**, world **Z up**, quaternions **[w,x,y,z]**, joint angles **radians**. Joint order: shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper.

## Connect to the visible scene

Read the session ID in **AI / API**, or list sessions and select the intended ID explicitly. To open a known session in a browser, use `http://127.0.0.1:5173/?session=ID`. `POST /api/sessions` creates an independent session. `/ws` without an ID creates a browser session; `/ws?session=ID` joins it. Different sessions remain isolated.

Commands and physics stepping share a per-session lock. Scene revision guards prevent stale edits when a client supplies `revision`; state `sequence` orders packets. Changes appear in all connected viewers. Backpressure coalesces poses while retaining the newest structural snapshot; clients should track snapshot and pose sequence independently and only render matching revisions. CPU work runs off the HTTP event loop. A task continues when a viewer disconnects; reconnect resumes observing the same session. The frontend keeps a last-acknowledged recovery copy for backend restart. Deleting a session stops it and disconnects its viewers; the frontend preserves its copy for Save and requires reload to start again.

Limit 16 sessions. Idle browser-only sessions can be evicted at capacity. API-created sessions are retained until explicitly deleted or 30 minutes idle, with expiry checked at creation. Sessions are in memory; export your scene before restarting the service. A headless physics session can continue until stopped; delete it after use.

## HTTP endpoints

| Method / path | Result |
|---|---|
| GET `/api/health` | Engine/version/API version |
| GET `/api/assets` | KALAS and legacy library metadata, dimensions and approximation labels |
| GET `/api/examples` | Eleven named example IDs, names and descriptions |
| GET `/api/default-scene` | Full default scene |
| GET `/api/scene-schema` | Authoritative Scene JSON schema |
| GET `/api/command-schema` | Authoritative Command JSON schema |
| GET `/api/meshes` | Immutable compiled robot meshes, cached 1 hour |
| GET `/api/sessions` | ID, name, running, revision, viewer count |
| POST `/api/sessions` | New empty session snapshot |
| GET `/api/sessions/ID` | Snapshot with portable scene and measured state |
| POST `/api/sessions/ID/command` | Validated command, returns snapshot |
| DELETE `/api/sessions/ID` | Stop/release/delete session |
| POST `/api/import?filename=part.stl&size=0.1` | Raw octet-stream upload → portable SceneObject; size is longest side in meters |
| GET `/api/sessions/ID/image?view=wrist` | 640×480 PNG; `main`, `top`, `front`, `back`, `wrist`; headers X-Scene-Revision/X-Simulation-Time |
| GET `/docs` | Interactive OpenAPI explorer with command schema |

Errors: 404 unknown session, 409 revision conflict, 413 payload too large, 422 validation/task planning error, 503 native renderer unavailable. Errors are JSON `{detail: ...}`. Rejected scene edits preserve the current model. Import conversion returns an object but does not add it until `object_add` succeeds.

## Commands

All commands accept optional unique `requestId`; edits accept optional current `revision`. HTTP responses do not need correlation IDs; WebSocket acknowledgements echo them. Unknown command fields are rejected.

| type | Parameters / behavior |
|---|---|
| `snapshot` | Read current state |
| `load` | `scene`: full Scene; compile atomically while paused |
| `reset` | Empty default scene, preserve cameras, pause |
| `example` | Optional `exampleId` from /api/examples; load arrangement/instruction, preserve cameras, paused only. Omitted ID retains the legacy example. |
| `plan` | Rehearse asynchronously without moving live physics; poll plan.status, inspect points, require verified:true before run |
| `task` | `source`, `target`: object IDs or null; must exist and differ; paused only |
| `run` | Start an unchanged verified plan or resume a paused active task; **moves arm**; rejects missing/stale/failed plans |
| `pause` | Freeze physics/controller, retaining phase/actuator targets |
| `stop` | Cancel controller, queue jaw opening, and pause; Step/physics advances the physical opening |
| `physics` | Cancel/release task and run passive physics |
| `step` | `count`: 1–2500 integration steps (default 10; each step is 1 ms), paused only; advances active policy too |
| `object_add` | `object`: valid SceneObject |
| `object_update` | `id`, `patch`: partial object properties (ID immutable) |
| `object_remove` | `id`; clears task references to the removed object |
| `robot` | `joints`: six targets and/or `patch` for base position/quaternion/joints |
| `camera` | `camera`: main/top/front/back; `value`: position,target,zoom,fov; allowed during execution |

Table dimensions, scene name, entire imported geometry and any other schema field are editable via `load`. Physical edits require pause and recompile, resetting time/velocity and cancelling a paused policy. Camera-only edits do not reset simulation. Top camera must be directly above its target; wrist is model-mounted and not a free camera.

Example:

```python
import httpx, time
api = httpx.Client(base_url="http://127.0.0.1:8765", timeout=30)
sid = api.post("/api/sessions").json()["sessionId"]
path = f"/api/sessions/{sid}"
for cmd in ({"type":"example", "exampleId":"kalas-cup-front"}, {"type":"plan"}):
    result = api.post(path + "/command", json=cmd)
    result.raise_for_status()
deadline = time.monotonic() + 60
while True:
    state = api.get(path).json()
    if state["plan"]["status"] != "calculating":
        if not state["plan"]["verified"]:
            raise RuntimeError(state["plan"]["message"])
        break
    if time.monotonic() > deadline:
        api.post(path + "/command", json={"type":"stop"})
        raise TimeoutError("Calculation timed out")
    time.sleep(.1)
api.post(path + "/command", json={"type":"run"}).raise_for_status()
while True:
    state = api.get(path).json()
    if state["task"]["status"] in ("succeeded", "failed"):
        print(state["task"])  # inspect success; acceptance is not completion
        break
    time.sleep(.25)
image = api.get(path + "/image?view=wrist")
image.raise_for_status()
open("wrist.png", "wb").write(image.content)
api.delete(path)
```

The bounded runnable version is [examples/run_task.py](../examples/run_task.py).

## MCP

Official Python SDK v2 stdio server. Start the editor first. Generate a client configuration with `.venv/bin/python scripts/mcp-config.py`; it prints the correct absolute interpreter and project directory. Equivalent shape:

```json
{
  "mcpServers": {
    "so101": {
      "command": "/absolute/project/.venv/bin/python",
      "args": ["-m", "backend.mcp_server"],
      "cwd": "/absolute/project",
      "env": {"SO101_API_URL": "http://127.0.0.1:8765"}
    }
  }
}
```

Tools: `list_examples`, `list_sessions`, `create_session`, `get_scene`, `scene_command`, `import_mesh`, `delete_session`, `get_contract`, `camera_image`. `scene_command(session_id, command)` exposes the same typed command schema, so an agent can operate every editor domain. `import_mesh(filename,data_base64,longest_side_m)` returns portable geometry; follow with object_add. `camera_image` returns an MCP image content block. No arbitrary server path reading/execution. Missing sessions or validation errors become MCP tool errors. Native camera rendering runs in a bounded subprocess for macOS GL-context compatibility; it observes a consistent captured state, not a later simulation frame.

Typical agent sequence: list sessions → get_scene → scene_command example/task → plan → poll plan.status → inspect verified path → run → poll get_scene → inspect success → camera_image. For edits, include the revision from get_scene and handle conflict by rereading.

## State, geometry and portable files

`state`: type, sessionId, sequence, revision, running, mode, time, contacts, poses, joints, objects, task, cameras. `task` includes status (`idle|running|cancelled|succeeded|failed`), phase, progress, message, held, graspAssist:false, grip, success. `grip` contains leftForce/rightForce (newtons), opposing, secure, maxPenetration (metres). `held` means a confirmed physical grasp, not an attachment constraint. `timeStep` is 0.001 s. On a dropped grasp the task fails but physics continues for 1.5 s to let gravity act; workspace/numerical errors still pause immediately. While paused mid-task, status remains running but `running:false`; phase/grasp resume on Run. `cameras.wrist` is the measured position/WXYZ quaternion/fov. `snapshot` additionally contains scene, geometry, jointInfo and imported compiled `meshes`.

Geometry size uses MuJoCo conventions: box half-extents; cylinder/capsule radius and half-length; sphere radius; ellipsoid radii. Mesh vertices/faces come from the compiled model and use compiled geom world transforms. Combine immutable robot meshes with snapshot imported meshes by numeric key; source STL offsets must not be reapplied. Collision proxies (groups 3/4) stay hidden in visuals but remain active in physics. WebSocket unsolicited states have no requestId. A workspace-boundary failure returns a paused snapshot with `warning`, task failure and last valid physics state.

Save wrapper: `{version:1, scene: <Scene>, cameras: <optional legacy camera map>}`. Scene version remains 1 with additive defaults: old primitive-only scenes remain valid. Scene includes `task:{source,target}`, `cameras:{main,top,front,back}` and object mesh data. Legacy wrapper cameras override scene cameras when opened in the editor. Mesh objects include `asset:"mesh"`, `mesh:{vertices:[...],faces:[...],filename:"part.stl"}`. Bounds: 64 objects, 8 MB scene/message, object centers ±5 m, scale .25–3, mass .001–10 kg, friction 0–5; imported files 10 MB, 20k vertices/40k triangles, longest side .005–1 m. The complete formatted portable scene is budgeted before accepting edits, including cumulative imports and serialization headroom; an oversized addition leaves the previous scene intact. Imported collision is convex: no hollow cavity or texture fidelity is implied.

## Path lifecycle

`plan` contains `status: idle|calculating|ready|failed`, `verified`, `message`, `points` (world-space gripper positions in trajectory order), `duration` (simulated seconds), and a stable `id` on success. Rainbow rendering may color points by index. Ready means the isolated trial completed measured success; command acceptance alone is not a plan. Completed tasks retain the path for inspection but set verified:false; calculate again for another run.

Planning copies the full compiled model/integration state (including velocities, controls and warmstart). It tries up to five bounded IK configurations and checks actual lift/release/settling and unwanted table/distractor contacts. Limits: two workers, four jobs including queued work, 45-second budget, 30 simulated seconds per attempt. Cancel with `stop`. Physical edits, passive physics and stepping invalidate the plan; camera-only updates do not. Results from cancelled/deleted/edited sessions cannot revive a plan. Run checks the captured physics fingerprint before starting; paused execution can resume without recalculation. Planning is not serialized into saved files.

KALAS IDs: `kalas_bowl`, `kalas_cup`, `kalas_spoon`, `kalas_plate`. They compile from original procedural profiles, not imported convex hulls. Published dimensions and estimates: [KALAS-SOURCES.md](KALAS-SOURCES.md).

## Policy limits

All ten examples are rehearsed and independently executed with contact-only dynamics, including source rotations and legacy spoon variations. IK uses measured robot kinematics and bounded actuators. A grasp requires sustained opposing jaw contacts; no equality weld or object-pose animation is used. Delivery solves from the carried spoon pose after lift. Released placement must have actual destination support and no jaw support, correct containment, low linear/angular speed and measured lift. Unsupported or missed grasps fail explicitly. See [contact physics audit](PHYSICS-AUDIT.md) for the force thresholds, numerical settings, results and limitations.

`kalas-cup-to-plate` starts with spoon `spoon` supported by `source_cup` and uses `cup` (a KALAS plate) as the task destination. Upright utensils use position plus pinch-axis IK constraints, with remaining wrist tilt selected by the five-axis arm. The API retains legacy asset entries for existing scenes; the editor library displays only KALAS assets and cube.

Back camera defaults to position `[-0.30, 0, 1.65]`, look-at target `[0, 0, 0.80]` and 55° field of view: above the default robot base, looking obliquely down onto the table. Missing back-camera records in older scenes are filled automatically. `camera_image` accepts `view: "back"`; camera edits use `camera: "back"`.
