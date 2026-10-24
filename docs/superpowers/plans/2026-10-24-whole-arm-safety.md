# Whole-arm collision safety implementation plan

> Execute inline with executing-plans; user explicitly authorized decisions, fixes, testing and existing GitHub delivery without further approval.

**Goal:** Safe physically supported pick/place trajectories including retreat, and consecutive cup→plate→cup tasks from actual measured state.

**Architecture:** One collision classifier for model contact pairs is shared by IK candidate checking, per-physics-step execution, and rehearsal. Preserve MuJoCo contact geometry/force limits; select reachable collision-free configurations rather than masking contacts. Serialize measured joint positions, and preserve live physical state for instruction-only edits.

**Tech stack:** Python/MuJoCo/SciPy backend; React/Three.js browser; pytest and Playwright.

**Constraints:** No welds, object teleporting during execution, disabled collision masks, or weaker success criteria. Model calibration remains a simulation approximation, not hardware certification. Reject unreachable/blocked scenes explicitly. Valid finger/source contact is permitted only at the contact surface; unrelated contacts are not permitted. Existing scene setup editing remains paused editing, not physical robot jogging.

## Tasks
- [x] Reproduce full-trajectory self/table/object collisions and commanded-vs-measured reload using the reported final state and all eleven examples.
- [x] Add failing regressions for measured export and instruction changes without moving bodies. Fix backend task updates and browser snapshots/current-scene export to retain measured angles.
- [x] Add shared collision classification for robot self-contact, static environment, other objects, intentional fingertip grasp, and held-object obstacles. Add per-1-ms runtime and rehearsal checking, explicit failure with gravity still active, and joint/tracking constraints. Check terminal states too.
- [x] Reject colliding IK endpoints and swept joint segments, try alternate reachable solutions/clearance candidates, constrain delivery/withdrawal consistently. Ensure Example 11 has a safe final pose and can plan and run the return task. Test unreachable, blocked, unsafe initial, intermediate-only collision, and injected runtime obstruction.
- [x] Run every example with all existing batch sizes; full backend/unit/browser suites; independent full-duration 1-ms contact audit. Review once with fresh context, fix material findings, preserve open sessions, update live app, commit/push.

## Review focus
- Instruction changes and save/open after a physically constrained target must never snap to actuator commands.
- Self-collision during retreat or verification must prevent success.
- Between-waypoint and between-batch collisions must be detected.
- Genuine grasp/support contacts and passive gravity after failure must remain physical.
- Arbitrary user placements/rotations and unreachable targets must fail clearly instead of driving through obstacles.

## Evidence / decisions
- Reported old final state commands place shoulder/wrist camera 6.8 mm inside each other.
- Baseline controller ignores robot–robot contact in path validation and exports actuator commands as scene joints; these are separate defects.

- Measured baseline all11: Example11 self-contact during Place, final arm command discrepancy 0.0744 rad. First10 had no self-contact.
- Regression sequence: measured export/task edit/roundtrip tests failed before fixes; intermediate self-collision and terminal overruns were reproduced with actual contact geometry.
- Final fresh review found two P2 issues, both fixed: frontend raw limit overshoot made saved scenes unloadable (RED→GREEN persistedJoints test); leftover terminal batch substeps could introduce unchecked contact (RED→GREEN terminal_batch test).
- Independent 1 ms audit: all11 successful, zero self-penetration; maximum other-arm penetration 0.052 mm; final arm tracking error below 0.0005 rad.

- Final verification: pytest 115/115 (371.12 s), Playwright 32/32 (3.6 min), Vitest 14/14; production build and focused E/F lint pass. Existing bundle-size warning remains unchanged.
- Live update: backed up/restored all15 paused sessions. The reported already-interpenetrating scene was recovered in Edit mode by restoring only its saved robot reset pose; objects/cameras remained identical. Its actual old spoon-on-plate arrangement rehearsed and independently executed successfully back into source_cup, and live session is left Path ready. Backup: ignored scene-backups/before-whole-arm-update-2026-10-24.json.
