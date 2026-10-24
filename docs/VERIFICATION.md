# Verification — manipulation workbench

Environment: macOS Apple Silicon, Python 3.12, MuJoCo 3.17.0, official MCP SDK 2.3.0, React 19 / Three.js / Vite 7. Dependencies are pinned in requirements.lock.txt and frontend/package-lock.json.

## Evidence

- Python: 37 tests passed after camera rendering and MCP integration (including genuine stdio initialize/list/call and image content).
- Frontend unit tests: 10 passed; strict TypeScript and production build passed.
- Browser: 16/16 scenarios passed in the final complete run after all review fixes (1.1 minutes). Earlier testing exposed a direct-scene selection race: OrbitControls sent a no-op camera update before selection. Skipping unchanged camera saves fixed it. The direct-click test now also waits for the expanded canvas layout before calculating its click coordinates.
- The example physically lifts the spoon, changes arm joints, enables a proximity-gated soft grasp, releases it, and leaves its bowl inside the cup with low velocity and no active grasp. Default simulated duration ≈15.7 s. Three source placements (-5 mm / nominal / +5 mm X) all succeed.
- Negative tests cover missing task, out-of-reach source without movement, stop while grasped, nonexistent source/target, revision conflict, untrusted origin and oversized step count.
- Real STL/OBJ/GLB files are converted, compiled, exported, reloaded and dropped onto the table. Invalid, unsupported, oversized and flat inputs fail without replacing the scene.
- Browser tests cover import/edit/save/reload; direct scene clicks and collection clicks; editable front camera; actual wrist-pose motion; API updates visible in browser; pause/stop; all four views; narrow-window controls; existing precise edits/gizmos/native drag/drop; failed restore retaining recoverable work.
- Native MuJoCo wrist rendering produces a nonempty 640×480 PNG; MCP returns it as image content. Rendering is isolated in a subprocess and bounded to two simultaneous requests.

Screenshots: [task success](screenshots/pick-place-success.png), [narrow window](screenshots/narrow-workbench.png).

## Design decisions and limits

- User delegated decisions and opted out of approval questions. Work remains in the existing dedicated checkout on a feature branch so the local app stays accessible at its usual path.
- Grasp assist is explicitly disclosed. A contact-only grasp is not claimed; no source-object qpos animation is used. Delivery is replanned using measured grasp geometry because the thin spoon can rotate during closure.
- This is a bounded IK task controller, not general collision-free planning or hardware control. The verified arrangement and small perturbations succeed; arbitrary rearrangements may fail with a visible status.
- Imported meshes use convex hull collision and a single editable color. Hollow imported containers are not suitable insertion targets; use the procedural cup.
- MCP uses the installed official v2 SDK MCPServer API (FastMCP was renamed). Stdio avoids maintaining a custom MCP protocol. The server and bridge are local only.
- Session IDs unify HTTP/WebSocket/MCP. Each session is independent; idle unviewed browser-only sessions may be reclaimed at capacity, with client-side recovery on reconnect. Explicit sessions are retained until deletion/idle expiry.
- Camera PNGs use native MuJoCo lighting and a fixed 640×480 output. Their appearance differs from Three.js. OpenGL absence returns an explicit error rather than an empty image.
- Physics state stops at ±5 m object-center bounds. Portable files do not contain velocities or controller checkpoints: loading/editing recompiles paused, while reconnecting to a live session retains its ongoing controller.
- Vite reports a large 3D bundle warning. It is a local application with heavy model/renderer dependencies; this does not affect build success.

## Independent review and resolutions

One independent whole-branch review found no critical issues and three important issues. All three were reproduced and fixed:

1. **Cumulative imports could create an unopenable save.** A regression using real 10,242-vertex sphere imports reproduced an 8.57 MB formatted save. Scene validation now budgets the entire formatted portable document before any model swap, including JavaScript numeric-width differences, camera/command overhead and worst-case moving poses. Rejected additions retain the prior scene/revision. Every accepted import in the regression is saved, parsed and reloaded.
2. **Backpressure discarded structural snapshots.** Subscriber queues now coalesce frames while retaining the newest full snapshot plus newest state. The frontend tracks structural freshness independently from pose freshness, retains a late required snapshot, and waits for matching geometry before displaying poses from a new revision. A server overflow regression and frontend out-of-order regressions failed before the fixes and pass afterward.
3. **Stale packets regressed command revisions.** Revision tracking is monotonic within a session and resets only when joining a new session. Stale-state and new-session regressions now pass.

No minor review findings remain. The existing large-bundle build warning is documented above. No second review was requested; verification covers the fixes and the complete integrated application.

Final verification commands: `bash scripts/check.sh` (37 Python + 10 frontend unit tests, strict TypeScript and production build); `cd frontend && npm run test:e2e` (16/16); `uvx ruff check backend --select F`; `git diff --check`. All succeeded on 2026-10-24. The local app was restarted with the final backend, and the visible browser was left on the paused spoon → cup example ready to run.
