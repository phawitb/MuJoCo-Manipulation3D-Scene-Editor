# SO-101 Scene Studio

A functional desktop 3D manipulation scene editor with a real **MuJoCo** physics backend and the **SO-101** robot from MuJoCo Menagerie. React/Three.js renders the compiled MuJoCo geometry; no second physics engine is used.

## Start

Requirements: **Node.js 22+**, **Python 3.12**, and either `uv` or `pip`. On macOS/Linux:

```sh
bash scripts/start.sh
```

The first run installs dependencies. Open **http://127.0.0.1:5173**. Stop both servers with Ctrl+C. Ports 5173 (editor) and 8765 (simulation) must be available; the launcher never kills unrelated applications. To install separately, run `bash scripts/setup.sh`.

The app opens in Edit Mode with a fixed SO-101 near the left table edge and an empty 0.8 × 0.6 m tabletop, 0.75 m high. The main and orthographic top cameras are available immediately.

## Use

- Drag a cup, plate, spoon or cube from the library onto the table in **either view**. The + button places an asset in a convenient table location.
- Click an object or its scene-tree entry. **Move (T)** and **Rotate (R)** display transform gizmos. The inspector accepts position in meters and XYZ Euler rotation in degrees. Press Enter or leave an input to apply it.
- **Snap** enables 1 cm translation and 15° rotation increments. **F** frames the selection in the active view. Delete removes it; the inspector also duplicates objects.
- Edit uniform scale, mass, sliding/torsional/rolling friction, collision participation and color. Uniform scale rebuilds visual and collision shapes together.
- Select **SO-101 arm** to edit its six joint targets within the actual model limits and adjust the fixed base pose. Select the table to configure dimensions. Changing table height moves the robot mount by the same amount; existing objects retain their world positions.
- **Run simulation / Space** starts MuJoCo. Pause to edit, or **Step** advances 20 ms. Editing is disabled while running. Pausing retains simulated object poses. Joint targets are held by the model's position actuators; measured angles may deflect slightly under load.
- Main view: left-drag orbits, right-drag pans, wheel zooms. Top view: drag pans, wheel zooms; the top-down direction is locked. Click a viewport to make it active. Each viewport has independent frame/reset controls.
- **Save scene / Cmd-Ctrl+S** downloads JSON containing the current object poses and both cameras. **Open** validates and restores it. Invalid files leave the working scene unchanged. [Example empty scene](examples/empty-scene.json).
- **Reset scene** restores the empty default scene and pauses physics, preserving cameras. Camera settings also survive page refresh in local storage. Scenes are saved explicitly with Save; refreshing without saving starts a new empty scene.
- A transient network disconnect reconnects with the last acknowledged scene and pauses physics. Each browser connection has an isolated simulation.

## Verification

```sh
bash scripts/check.sh
# Browser tests require the running app:
cd frontend
npx playwright install chromium
npm run test:e2e
```

The browser test configuration uses installed Google Chrome by default. Set `PLAYWRIGHT_CHROMIUM=1` to use Playwright's bundled Chromium. Tests exercise startup, numerical edits, physical settling, real gizmo dragging, drag/drop, camera state, saving/loading, invalid inputs and connection recovery. `test-results` contains verification screenshots/traces.

## Structure

- `backend/schema.py`: bounded/versioned scene schema and asset metadata.
- `backend/simulation.py`: MJCF composition, isolated models/data, authoritative state and geometry export.
- `backend/main.py`: FastAPI HTTP and WebSocket API.
- `frontend/src`: editor, viewport, inspector, library, connection state and coordinate utilities.
- `assets/so101`: original robot model and meshes, with Apache-2.0 license.
- `docs/API.md`: protocol, units, frames and synchronization rules.

## Scope and model fidelity

The robot uses its real kinematic structure, inertias, actuator configuration and model collision geometry. Its base has no free joint. Robot collision shapes follow the upstream model's approximations; they are not exact visual-mesh collisions. Household objects are explicitly **procedural approximations**, not IKEA product models: the cup is open, the plate has a shallow rim, and the spoon uses a rounded solid bowl and handle. Their render primitives are their physics primitives. Model source and exact commit: [assets/PROVENANCE.md](assets/PROVENANCE.md).

This is a local single-user editor with per-connection sessions, not a multi-user deployment or autonomous grasping system. There is no trajectory planner, IK, learning policy or hardware control. Maximum 64 objects per scene; physics advances at 500 Hz and publishes around 30 Hz, subject to machine load. Very large/high-contact scenes may run slower than real time. Arbitrary manual transforms may create overlaps; MuJoCo resolves contacts when simulation begins. No GPU is required for physics; browser WebGL is required for 3D rendering.

The supplied specification was truncated midway through section 7. The implemented scope covers all complete requirements in that attachment and functional drag/drop behavior.
