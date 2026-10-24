# Scene Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A working SO-101 3D scene editor with real MuJoCo simulation.
**Architecture:** FastAPI owns independent WebSocket simulation sessions and compiles MJCF. React renders backend-provided geometry and poses in two independent camera views, with shared editing state.
**Tech Stack:** React, TypeScript, Vite, Three.js, R3F, Drei, Python, FastAPI, MuJoCo.
**Spec:** docs/superpowers/specs/2026-10-24-scene-editor-design.md

## Global Constraints
- MuJoCo is the only physics engine; meters, Z up, WXYZ quaternions.
- Startup has fixed SO-101 at table edge, empty tabletop, paused physics.
- Actual robot kinematics and licensed real model; matching visual/collision shapes.
- Independent main/top cameras; reset scene preserves camera states.
- User has delegated design decisions; continue without approval questions.

## Review Focus
- Invalid scene loads preserve working scene and show an actionable error.
- Fast edits and simulation toggles cannot lose edits or apply stale state.
- Camera persistence does not overwrite another view or break framing.
- Dropped objects settle on table; robot fixed base never moves.
- Disconnect/reconnect does not silently replace user work.

### Task 1: Simulation and API
Files: backend/schema.py, backend/simulation.py, backend/main.py, backend/tests/test_simulation.py, assets/so101/.
Interfaces: Scene schema and commands described in docs/API.md; geometry assets and poses from compiled model.
- [ ] Write tests for default empty scene/fixed base/no penetrations, object settling, mesh export alignment, invalid loads, robot limits and session isolation. Run and observe missing modules.
- [ ] Vendor verified model; implement schema, procedural geometry, atomic compilation, step/run/pause and geometry serialization.
- [ ] Implement FastAPI metadata/assets and WebSocket sessions with errors and state updates. Test real round trips.
- [ ] Run .venv/bin/python -m pytest backend/tests. Expected: all pass. Commit.

### Task 2: Interactive editor
Files: frontend/src/{App,Viewport,Inspector,Library}.tsx, types.ts, math.ts, styles.css and configs.
Interfaces: API of Task 1, shared scene state and geometry poses. Separate camera storage.
- [ ] Write tests for coordinate/drop math and persistence validation; run to see missing implementation.
- [ ] Build polished editor shell, real geometry rendering, selection/transforms and two cameras, bounded drag/drop.
- [ ] Implement inspector, object/robot edits, physics controls, JSON import/export and reset semantics.
- [ ] Run npm test and npm run build. Expected: all pass. Commit.

### Task 3: End-to-end verification and delivery
Files: frontend/e2e/editor.spec.ts, scripts/start.sh, README.md, docs/API.md.
Interfaces: Running frontend and backend through Vite proxy; browser and HTTP integration.
- [ ] Exercise startup, drag/drop, inspector, gizmos, camera switch/reset/frame, physics step/run/pause/reset, save/load, malformed input and reconnect in a real browser.
- [ ] Fix defects with targeted regression tests; inspect screenshot at desktop size.
- [ ] Add single-command setup/start, dependency locks and docs/provenance. Run complete suite and production build.
- [ ] Fresh-context whole-branch review, resolve important findings, launch app and deliver working link. Commit.
