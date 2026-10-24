# Verification and delivery — 2026-10-24

Implemented from an empty dedicated directory, on local branch `feat/scene-editor`. No remote or public deployment was configured. The user explicitly delegated design and implementation decisions; no existing working code was replaced.

## Acceptance evidence

- Python tests: **17 passed**, covering the fixed six-joint robot, collision-free startup, physical settling for cup/plate/spoon, mesh packet consistency, scale/mass, collision participation, schema validation, atomic load failures, WebSocket controls, session isolation, and safe workspace-boundary handling.
- Frontend coordinate/file-validation tests: **6 passed**.
- Real Chrome interaction suite: **9 scenarios passed**, covering initial empty table, editing, native library drag, translation and rotation gizmos, physics controls, camera independence, scene save/load, invalid imports, reconnect success/failure, transient asset recovery, focused-draft saving, and rejected inspector edits.
- TypeScript type check and Vite production build: passed. Unused code checks enabled. Python F-class static checks: passed.
- npm dependency audit: zero reported vulnerabilities at verification time.
- Launcher lifecycle: started both servers, verified health through the editor proxy, terminated both owned processes, and preserved an unrelated IPv6 listener on the same numeric frontend port.
- Screenshots visually inspected at 1600 × 1000. Startup screenshot: `docs/screenshots/startup.png`.

## Independent review and fixes

A fresh-context read-only reviewer inspected the complete branch and reproduced four issues. Each received a failing regression test followed by a passing fix:

1. **Save could export stale field values.** Save now blurs/commits the focused draft and waits for the server acknowledgement before serializing. Tested both immediate button click and Cmd/Ctrl+S.
2. **Failed reconnect restoration could silently replace retained work.** Restoring no longer overwrites retained live state. Failure gates simulation and keeps Save, Open and Reset available. A server-rejected restore is injected in a real WebSocket test; saved retained objects survive.
3. **Frame/reset signals replayed on camera remount.** Each CameraRig consumes only changes after initialization, so switching views or loading camera settings does not replay historical actions.
4. **Rejected numeric drafts remained displayed as applied.** Fields revert to acknowledged values until a new value is accepted. The server-rejected X=8 regression now shows the original X=0.08.

The related runtime/schema mismatch was also fixed: if a simulation batch would move an object center beyond ±5 m, MuJoCo integration state is restored to the last valid state and physics pauses with an explanatory message. The paused snapshot remains loadable, including after collision-disabled falling. Both physics and WebSocket tests verify this behavior.

No optional review findings were deferred. The reviewer intentionally left undo/autosave, autonomy/IK/hardware, exact product models, public hosting, and cross-hardware stress benchmarks outside this local editor's agreed scope.

## Decisions and limits

- Work stayed in the empty project directory on a new local feature branch; there was no prior checkout to protect or merge target.
- The supplied attachment is exactly 10,000 bytes and ends midway through section 7. All complete requirements were implemented, with standard tabletop drag/drop behavior. Unseen requirements could require future additions.
- The real SO-101 model is vendored from a pinned Apache-2.0 Menagerie commit. The runtime uses its actual kinematics, limits, inertias and actuators. Robot collision proxies follow upstream approximations.
- Cups, plates and spoons use documented procedural approximations with shared render/collision primitives. They are not verified commercial product meshes.
- Camera configurations persist locally; scenes persist via explicit JSON export/import. A page refresh begins a new empty scene, as documented in the UI help and README.
- Simulation is local and per connection. Position-control targets are supported; autonomous manipulation and hardware control are not included.
- Known non-failing build/tool notices: the Three.js application bundle is about 1.2 MB before compression; FastAPI's test adapter emits an httpx deprecation notice. These did not affect the passing checks.
