# Scene Studio API

Local FastAPI backend at `127.0.0.1:8765`, proxied through Vite at `127.0.0.1:5173`. No external service or API key. Browser WebSocket origins are restricted to localhost/loopback; bind only to loopback. This is not an authenticated public service.

## Coordinates

All positions, lengths and dimensions are **meters**, world **Z up**. Quaternions are **[w, x, y, z]**, normalized on input; Three.js converts to [x, y, z, w]. Robot joint positions are radians, in model order. UI Euler fields use intrinsic Three.js XYZ angles in degrees; conversion to quaternion happens on commit. Euler representations may wrap by 360° without changing orientation.

Geometry `size` follows compiled MuJoCo conventions: box half-extents, cylinder radius/half-length, capsule radius/half-length excluding endcaps, sphere radius, ellipsoid radii. Cylinder/capsule local axis is Z. Compiled `mesh_vert` is rendered using the compiled world geom pose; applying the source mesh's extra offsets again would be incorrect. The frontend does not parse URDF or perform its own robot kinematics.

## HTTP

- `GET /api/health`: `{status, engine, version}`.
- `GET /api/default-scene`: validated default `Scene`.
- `GET /api/assets`: procedural asset metadata (`id, name, category, dimensions, mass, color, description`).
- `GET /api/meshes`: immutable compiled robot meshes by index (`vertices` flattened XYZ, `faces` flattened triangle indices). Cached one hour. These match mesh IDs in every snapshot.
- `/docs`: FastAPI API explorer (WebSocket protocol documented here).

## WebSocket `/ws`

Each connection creates independent `MjModel` and `MjData`. Initial message is a paused `snapshot`. Receive and physics stepping are serialized for that session; CPU compilation/stepping happens in a thread so other sessions remain responsive.

Command example:

```json
{"type":"load","requestId":"4","revision":2,"scene":{"version":1,"name":"Example","table":{"width":0.8,"depth":0.6,"height":0.75},"robot":{"model":"so101","position":[-0.3,0,0.754],"quaternion":[1,0,0,0],"joints":[0,-0.7,0.7,0.3,0,0.6]},"objects":[]}}
```

Commands:

| Type | Action | Reply |
|---|---|---|
| `load` | Validate and atomically compile a full scene; allowed only while paused. Optional `revision` must match. | `snapshot` |
| `run` | Start stepping, preserving current state. | `state`, then streamed states |
| `pause` | Pause and retain current object poses. | `snapshot` |
| `step` | Advance 10 steps × 0.002 s while paused. | `state` |
| `reset` | Restore default empty scene and pause. | `snapshot` |
| `snapshot` | Read current scene/model and state. | `snapshot` |

Replies echo `requestId`; unsolicited streaming packets have none. Errors are `{type:"error",message,revision,requestId}` and do not replace the current scene. Physics rolls back the last integration batch and pauses before an object center leaves ±5 m; streaming sends a paused snapshot followed by an error. This keeps every exported physics state loadable. Scene revision increments only after successful compilation. The client permits one in-flight command, disables editing during compilation/running, and updates the display on acknowledgement. A command times out after 15 seconds and initiates reconnect with the last acknowledged scene. Edits always start from current simulated object poses. Changing physical properties recompiles/reset velocities and simulation time; run/pause/step do not.

`state` contains `{type, revision, running, time, contacts, poses, joints, objects}`. `poses` are `{id,position,quaternion}` for visible geom IDs; `objects` are body-center poses by object ID. `joints` are measured positions. `snapshot` adds `scene`, `geometry`, and `jointInfo`. `geometry` contains `{id,name,owner,kind,size,color,mesh}`; robot collision proxies (upstream groups 3/4) are hidden from visual rendering but retained in physics. Robot visual materials and mesh geometry come directly from the model. `jointInfo` provides actual named limits.

## JSON scene files

```json
{"version":1,"scene":{},"cameras":{"main":{"position":[1.05,-1.25,1.55],"target":[0,0,0.77],"zoom":1},"top":{"position":[0,0,2.6],"target":[0,0,0.75],"zoom":320}}}
```

Replace `scene` with the full server schema/example file. `cameras` is optional and frontend-owned. A scene without cameras preserves existing views; a file with cameras intentionally restores them only after server acceptance. Reset scene never alters cameras.

Object schema: `id` (unique non-reserved ASCII identifier), `name`, `asset` (`cup|plate|spoon|cube`), `position`, `quaternion`, uniform `scale` (0.25–3), `mass` (0.001–10 kg), `friction` ([sliding,torsional,rolling], each 0–5), `collision`, hex `color`. Max 64 objects, 150 KB command/file limit. Extra fields, non-finite values, duplicate IDs, invalid quaternions, out-of-range joints and unknown assets are rejected. Full defaults and bounds live in `backend/schema.py`.

There is no server filesystem write or shared session persistence. On disconnect, its physics loop stops and model state is released. A failed restoration preserves the retained client scene and blocks run/pause/step; Save, Open and Reset remain available for recovery. Save commits the focused draft and awaits in-flight edits before serializing. A reconnect starts a new session and the client restores its last acknowledged scene in paused mode; velocities/time are intentionally reset.
