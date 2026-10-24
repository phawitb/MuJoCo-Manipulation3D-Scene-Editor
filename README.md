# SO-101 Scene Studio

A local 3D manipulation workbench with **real MuJoCo physics**, an **SO-101 arm**, four camera views, portable mesh import, researched **IKEA KALAS assets**, and **ten rehearsed pick/place examples**, and **MCP / HTTP control** of the scene you see in the browser.

![Successful spoon-to-cup task](docs/screenshots/pick-place-success.png)

## Start

Requires Node.js 22+ and Python 3.12, with `uv` or `pip`. On macOS/Linux:

```sh
bash scripts/setup.sh   # install or update pinned dependencies
bash scripts/start.sh
```

Open **http://127.0.0.1:5173**. First launch installs dependencies automatically if absent. After updating an existing installation, run setup again. Ctrl+C stops both servers. The launcher checks IPv4 ports 5173 / 8765 and never kills another app.

## Try the task

1. Choose a task from the **10-example menu** and click **Load example**.
2. Click **Calculate path**. The app rehearses the task in an isolated MuJoCo copy; your live scene stays still.
3. Inspect the **rainbow gripper path**, then click **Run simulation**. The arm approaches, closes, lifts, transfers, lowers, releases and retreats.
4. **Complete** appears after measured lift, release and settling. Examples take about 16 simulated seconds. Pause/Run resumes the active task; physical edits require a new calculation.

Calculation also works with user-arranged objects. Tests include moved destinations and spoon rotations of 0°, 45°, 90° and 270°. Unreachable or obstructed arrangements show a failure instead of enabling Run. This is a bounded rehearsal search, not a guarantee for every placement. Calculation can be cancelled; camera changes preserve a valid plan.

The controller uses numerical IK and **physical jaw contact/friction only**. There is no grasp weld, hidden attachment or object teleportation. Both jaws must sustain opposing forces before lifting; contact loss fails the task and lets gravity act. The UI shows measured left/right grip forces. Delivery is recalculated after lifting, and success requires release, actual destination support and settling. All ten examples were audited at every 1 ms step; see the [physics audit and example 06 video](docs/PHYSICS-AUDIT.md). This is not hardware-calibrated contact dynamics or a guarantee for arbitrary scenes.

## Build your own task

Click **Pick object**, then click the object directly in a viewport or the scene collection. Next click the destination. **Calculate path first, then Run simulation / Space moves the arm**; Pause freezes execution, Run resumes, Stop releases and cancels. Invalid or unreachable tasks show an actionable error. Cups, bowls, plates and solid supports can be destinations; the ten bundled arrangements cover cup insertion, bowl/plate placement and surrounding objects. Bring objects closer to the arm if IK cannot reach them. Imported hollow vessels use solid collision; use the procedural cup for insertion.

**Physics only** runs physics without a pick/place policy and opens the gripper. **Step** advances 20 ms while paused. While a task is paused, Step also advances its controller. Editing physical scene properties cancels the current task, recompiles and resets time/velocities.

## Cameras and editing

- **Main**, **Top**, **Front**, **Wrist** tabs expand a view. Multi-view shows all four; narrow windows show front/wrist previews and keep Top available as a tab.
- Front camera defaults to a front oblique/downward angle. Its settings button edits position, look-at target and field of view. Main/front support orbit/pan/zoom; top is orthographic with locked downward direction. Wrist follows the actual model-mounted `wrist_cam` pose and field of view.
- Drag asset cards into a view or use +. During dragging a translucent object and footprint show the exact clamped drop position before release. **Import object** accepts STL, OBJ and self-contained GLB from your computer, with explicit longest-side sizing. The mesh is centered and embedded in saved scenes, with editable color and **convex hull collision**. Limits: 10 MB upload, 20k vertices/40k triangles; textures and external sidecar files are not imported.
- Click empty tabletop/background to see the current object list in **Inspector**. Clicking a row selects the same object and axes as the viewport. Selection and task-source/destination buttons briefly highlight the object in every view.
- **Arrow keys** move the selected object on world X/Y by 1 cm; **Shift + arrows** uses 1 mm. Footprints stay within the tabletop; typing in fields is unaffected.
- Select an object for move/rotate gizmos, exact pose, scale, mass, friction, collision and color. **T/R**, **F**, **Delete**, **Cmd/Ctrl+S** shortcuts are available. Snap uses 1 cm / 15° increments.
- Select the arm for five arm joint targets plus gripper, or base pose. Select the table to resize it. All coordinates use meters, Z up, WXYZ quaternions; UI angles are degrees.
- **Save scene** downloads portable JSON including current poses, task and cameras. **Open** validates atomically; malformed files leave the current scene intact. Old version-1 files still load with new defaults. Max scene/message size 8 MB, 64 objects. A cumulative size budget rejects oversized additions before they can make your saved scene impossible to reopen.
- **Reset scene** empties the table while preserving cameras. Camera preferences also survive refresh in local storage. Refresh opens a new empty session; save your scene explicitly. A transient disconnect reconnects to the same session; its controller may continue while disconnected. If the server restarted, the browser restores its last acknowledged scene paused. Failed restoration leaves a downloadable recovery copy.
- At narrow widths, **Objects** and **Inspector** toggle side panels.

## IKEA KALAS assets

Defaults include bowl **603.786.69**, handleless cup **403.786.70**, spoon **204.406.54** and plate **203.786.71**. Official published dimensions are bowl Ø120 mm, spoon length 160 mm, plate Ø190 mm and cup capacity 230 mL. Heights, wall thicknesses, detailed profiles and physical properties are documented estimates. These are independently authored reconstructions, not manufacturer CAD. Open compound collision shells preserve container cavities; the visible spoon head is concave.

Existing model listings were researched, but no redistributable four-item set was verified. No paid/restricted meshes were bundled. See **[sources and dimensional confidence](docs/KALAS-SOURCES.md)**. Legacy plastic assets remain available so old files keep their original geometry.

## AI agents and external programs

Click **AI / API** or the session ID in the footer. Every browser scene has an explicit ID. An agent can list sessions, control that exact scene, read measured state, import meshes, change all object/robot/table/camera settings, execute tasks and obtain **native MuJoCo camera PNGs**. Independent headless sessions are also supported.

```sh
# Print ready-to-copy MCP client configuration, including absolute paths:
.venv/bin/python scripts/mcp-config.py
# MCP stdio entry point (editor service must already be running):
bash scripts/mcp.sh
# Run example in a new headless session; add an ID to use an existing scene:
.venv/bin/python examples/run_task.py
```

The bridge uses the official MCP Python SDK (v2), not a custom protocol. It connects only to the local service. Full endpoint/tool schemas, session lifecycle, concurrency and example commands: **[docs/API.md](docs/API.md)**. Interactive HTTP documentation: **http://127.0.0.1:8765/docs**.

## Verify

```sh
bash scripts/check.sh
# With the app running (uses installed Chrome by default):
cd frontend && npm run test:e2e
# Or: npx playwright install chromium && PLAYWRIGHT_CHROMIUM=1 npm run test:e2e
```

See **[docs/VERIFICATION.md](docs/VERIFICATION.md)** for current evidence and limits. Tests cover physical manipulation, repeated/perturbed placements, cancellation, camera poses/images, real STL/OBJ/GLB import, real MCP handshake/tools, shared API/browser control, direct scene clicks, four views, responsive layout and existing editing/recovery workflows.

## Model and system limits

Robot model: [MuJoCo Menagerie SO-101 provenance and Apache-2.0 license](assets/PROVENANCE.md). Household assets are procedural approximations. Physics runs at 1000 Hz and streams roughly 30 Hz, subject to machine load; highly detailed/high-contact scenes may run slower. WebGL is required for the editor. Agent PNG observations need native OpenGL; if unavailable, the API returns an explicit 503 while browser views remain usable. Native and browser lighting differ.

Local single-user service, no authentication or hardware connection. Bind only to loopback; HTTP and WebSocket origins/hosts are checked. Models are serialized per session. Up to 16 concurrent sessions; inactive browser-only sessions may be reclaimed to make room. Explicit API-created sessions remain until deletion or 30 minutes idle (reclaimed on creation). Exported scenes contain no server filesystem paths. Physics pauses before an object center escapes ±5 m.
