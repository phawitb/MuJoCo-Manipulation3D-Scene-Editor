# SO-101 manipulation scene editor

User authorized all implementation decisions and asked for complete working software. The supplied specification ends mid-sentence in section 7 (10,000 bytes). Implement all complete requirements and practical drag/drop, persistence, and simulation behavior.

Repository inspection: empty directory, no existing source, assets, or git history. Build in this dedicated project directory on feat/scene-editor.

Use React + TypeScript + Vite + React Three Fiber/Drei, Python FastAPI, MuJoCo. Vendor the real Apache-2.0 SO-101 model from MuJoCo Menagerie with its provenance and license. All coordinates are meters, Z up, quaternions WXYZ over API. Render geometry and poses from the compiled MuJoCo model so robot visuals match authoritative kinematics. For meshes, export compiled MuJoCo vertices/faces to JSON once at startup; this avoids independent URDF/MJCF parsers and mismatched mesh offsets. Procedural cup, plate and spoon collision primitives are also their rendered geometry.

A fixed robot near the edge of a 0.8 x 0.6 m table; empty tabletop; edit mode by default. A large main perspective canvas and smaller independent orthographic top canvas. Object library at left, inspector at right; geometry selection, translate/rotate controls, numeric pose/physical properties, robot joints, delete, frame, camera reset. Add objects with ray-plane drop placement bounded to tabletop. No frontend physics.

Each WebSocket owns an independent SimulationSession. Commands load scene, run, pause, step, reset. Edits compile atomically, only in paused mode; failures preserve previous scene/model. Server sends scene, geometry description and world poses after compilation; streams poses at 30 Hz while stepping at 500 Hz. Revisions/serialized commands prevent stale state. Disconnection stops that session. Local JSON save/load includes independently persisted camera states; reset scene preserves cameras. Bounded schema rejects invalid floats, dimensions, IDs, positions, and excessive objects.

Approximate household objects are explicitly marked procedural; no product accuracy or autonomous manipulation claim. No external deployment needed. Launch scripts, README/API docs, backend physics and WebSocket tests, frontend math tests and browser interaction tests are deliverables.
