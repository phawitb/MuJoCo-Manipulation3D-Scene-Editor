> Historical assisted-mode results. Superseded by [contact-only verification](VERIFICATION.md); these results did not validate realistic grasp support.

# Verification — path preview and KALAS workbench (v3)

2026-10-24 · macOS Apple Silicon · Python 3.12 · MuJoCo 3.17.0 · official MCP SDK 2.3.0 · React 19 / Three.js / Vite 7. Pinned dependency locks are committed.

## Results

- Backend: **63 tests passed**, including native physics, asynchronous planning/invalidation, real MCP stdio handshake/tool calls/images, imports and scene roundtrips.
- Frontend: **13 unit tests passed**, strict TypeScript and production build pass. Vite retains its large 3D bundle warning (~1.24 MB before gzip).
- Browser: **21 scenarios passed** on the final implementation, including a complete pick-and-place run through the UI. Total: **97 automated tests passed**.
- The standalone HTTP example also calculated a 160-point trajectory and physically completed the task at 15.73 simulated seconds.
- An earlier run correctly exposed outdated asset-count/name assertions after adding KALAS; those assertions now match the new library. The task-example selector uses an exact label to avoid also matching the Load button.
- New regressions cover ghost visibility/cancellation/exact drop coordinates; blank-table selection; Inspector row selection; repeated and fine arrow movement without stealing form input; task selection pulses; isolated path calculation and edit invalidation; ten-item example picker.

## Ten actual physics executions

Each case first runs an isolated rehearsal without modifying the live-state fingerprint, then starts a separate physical execution with the selected controller configuration. Execution uses 17-step batches to exercise a different observation cadence. Every result below required actual lift, active grasp then release, stable placement and no active weld at completion. No object qpos animation is used.

| Example | Destination / arrangement | Rehearsal attempts | Measured lift | Actual completion |
|---|---|---:|---:|---|
| 01 kalas-cup-front | KALAS cup, front | 1 | 0.217 m | PASS · 15.71 s |
| 02 kalas-cup-left | Cup left, source rotated 170° | 1 | 0.217 m | PASS · 15.71 s |
| 03 kalas-cup-right | Cup right, source rotated 190° | 1 | 0.217 m | PASS · 15.71 s |
| 04 kalas-cup-near | Near cup, source rotated 160° | 1 | 0.217 m | PASS · 15.71 s |
| 05 kalas-bowl-front | KALAS bowl | 2 | 0.114 m | PASS · 15.71 s |
| 06 kalas-bowl-left | Bowl left, angled source | 3 | 0.164 m | PASS · 15.71 s |
| 07 kalas-plate-front | KALAS plate | 1 | 0.148 m | PASS · 15.71 s |
| 08 kalas-plate-angle | Plate right, angled source | 1 | 0.148 m | PASS · 15.71 s |
| 09 kalas-cup-clutter | Cup with surrounding bowl/cup | 1 | 0.217 m | PASS · 15.71 s |
| 10 kalas-bowl-clutter | Bowl with surrounding bowl/cup | 3 | 0.164 m | PASS · 15.71 s |

Test: `backend/tests/test_examples.py` (16 cases: ten examples, four custom rotations, a moved/rotated robot base and a blocked scene). All pass. The custom scenes change the destination position and set spoon yaw to 0°, 45°, 90° and 270°; both plan and execution succeed. An obstructed source and an out-of-reach source produce explicit failed plans with unchanged live state. Legacy ±5 mm variation tests also pass.

Runnable scene files: [examples/tasks](../examples/tasks). HTTP runner: [examples/run_task.py](../examples/run_task.py).

## Design decisions, evidence and limits

- User delegated decisions. Work uses a dedicated feature branch in the existing checkout to keep the local app path usable. Implementation stays inline because physics/session/UI contracts are coupled; source research and final review use independent agents.
- Chosen approach is bounded rehearsal in a full model/data copy, rather than geometric-only preview. The displayed path records actual gripper motion. Planning takes additional time and is not a complete search over every possible manipulation trajectory.
- Grasp assistance is disclosed in the UI. A soft weld only activates after measured proximity and closure; release occurs before success evaluation. This is not pure-contact or hardware grasp validation.
- Planning is bounded to two workers/four jobs, five candidate configurations, 45 seconds wall budget and 30 simulated seconds per candidate. Edits/cancellation invalidate the result; camera-only updates preserve it. Fingerprints prevent starting a stale plan. Pause/resume preserves the active controller.
- Shallow-container placement allows spoon yaw to follow reachable kinematics while keeping the spoon level; cup insertion aims its head downward. A too-near initial example failed IK and was moved to a reachable arrangement, not relabelled successful.
- Official dimensions, secondary-source heights and inferred thicknesses/profiles are separated in [KALAS-SOURCES.md](KALAS-SOURCES.md). Original procedural meshes avoid uncertain redistribution rights. Real samples are needed for metrology-grade dimensions and physical properties.
- KALAS cups/bowls/plates have hollow compound collision shells. Imported STL/OBJ/GLB still use convex hull collision; imported hollow containers are unsuitable for insertion. Legacy asset IDs retain original dimensions.
- Old scene/import recovery, full-scene size budgeting, queued snapshot retention, monotonic revisions, camera persistence and native PNG observation remain covered by regression tests.
- Local-only service; no hardware control or public deployment. Save files preserve poses/task/cameras/assets, not velocities/controller checkpoints/plans. Arbitrary scene success is not guaranteed: failures keep user work intact and leave Run unavailable until a valid plan is calculated.

Screenshots: [path preview and Inspector](screenshots/path-preview.png), [drag placement preview](screenshots/placement-preview.png), [successful physical execution](screenshots/pick-place-success.png), [narrow window](screenshots/narrow-workbench.png).

A regression also caught visual-only mesh shells inadvertently reducing the requested body mass. Mass now distributes across collision pieces only; the actual compiled body mass matches the Inspector value. All ten tasks were rerun after this correction; the table above uses those results.

## Independent review and final decisions

A fresh-context, read-only whole-branch review covered afad159..c82cf07, the spec/plan and decision ledger. Verdict: **Ready to merge**; no Critical, Important or deferred Minor findings. The reviewer inspected code and tests; the execution results above were run by the implementer. The following boundaries were explicitly reviewed and retained:

- Bounded planning can reject physically possible arrangements. A valid rehearsal is required before Run; comprehensive planning is beyond this implementation. Cost: the user may need to move objects or simplify a scene.
- Grasp assistance remains disclosed, with measured closure/proximity and release checks. Cost: a successful simulation does not prove hardware or contact-only grasp reliability.
- Missing manufacturer measurements remain estimates with provenance. Cost: real-world replicas need physical calibration.
- Imported meshes retain their documented convex collision hull. Cost: an imported hollow vessel cannot be relied on for insertion; use the procedural hollow containers.
- The app remains a local workbench. Cost: public or multi-user hosting needs a separate authentication/isolation design.

The earlier implementation decisions remain: preserve the existing app checkout on a dedicated feature branch (cost: no second filesystem sandbox); implement coupled changes inline with independent research/review (cost: fewer implementation perspectives); rehearse full physics before showing a runnable path (cost: calculation time and bounded solvability); identify unreported dimensions as estimates (cost: calibration needed). No external third-party models were redistributed. Main is updated by fast-forward, without force push.
