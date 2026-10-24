# Path Preview and KALAS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement task-by-task.

**Goal:** Preview placement and verified gripper paths, improve selection, and provide researched KALAS assets with ten proven tasks.
**Architecture:** Procedural asset profiles → generic pick/place controller → isolated rehearsal planner/session lifecycle → React interaction/trajectory UI.
**Tech Stack:** Python/MuJoCo/SciPy, React/Three.js, existing official MCP bridge.
**Spec:** docs/superpowers/specs/2026-10-24-path-preview-kalas-design.md

## Global Constraints
- Meters, Z up, WXYZ. Old assets/scenes remain readable.
- Never move live physics during calculation. Never run stale/unverified plans.
- No object teleportation; disclosed grasp assistance and measured release success.
- Separate official IKEA measurements from estimates; use only licensed/original geometry.
- Bound planning resources; edits invalidate, camera-only changes preserve plans.

## Review Focus
- Drag cancellation/edges and ghost/drop alignment: task 3 browser tests.
- Held arrow keys while commands pending and text field focus: task 3 browser tests.
- Edits/deletion/physics during in-flight calculation cannot resurrect a stale plan: task 2 tests.
- Non-default spoon orientation, robot base pose and clutter: tasks 2/4 physics tests.
- Ten examples must execute, not just satisfy IK: task 4 measured physics matrix.

### Task 1: Researched KALAS profiles and geometry
**Files:** backend/catalog.py, schema.py, simulation.py; backend/tests/test_catalog.py; docs/KALAS-SOURCES.md.
**Interfaces:** asset_profile(asset) gives family/dimensions/grasp/bowl/support parameters; ASSETS includes four kalas_* IDs plus legacy assets. add_object consumes profiles for hollow compound geometry.
- [x] Write tests for official outer dimensions, open cavities and legacy compilation; run RED.
- [x] Implement researched geometry/metadata, preserving original assets and collision semantics.
- [x] Run catalog/import/simulation tests, GREEN; commit.

### Task 2: Verified path calculation and arbitrary scene controller
**Files:** backend/planning.py, policy.py, simulation.py, sessions.py, main.py, mcp_server.py; backend/tests/test_planning.py.
**Interfaces:** command type plan; packet.plan {status:idle|calculating|ready|failed, points:Vec3[], duration:number, message:string, verified:boolean}; run requires ready or resumes paused task. GET /api/examples lists {id,name,description}; command example accepts exampleId (optional).
- [x] Write non-mutating planning, reachable custom placement, failed/unreachable, stale-plan and pause/resume tests; run RED.
- [x] Implement generic profile-based grasp/delivery and candidate rehearsal using full cloned state; asynchronous bounded session integration and API/MCP contracts.
- [x] Run policy/planning/session/MCP tests, GREEN; commit.

### Task 3: Interactive placement, selection and path workbench
**Files:** frontend/src/App.tsx, Viewport.tsx, Inspector.tsx, Library.tsx, TaskPanel.tsx, types.ts, styles.css; new focused interaction helpers/components; frontend/e2e/workbench.spec.ts.
**Interfaces:** packet.plan and example endpoint from task 2; local dragging asset metadata; selection pulse id+token shared across views; same dropPosition for ghost/drop.
- [x] Write failing browser/unit tests for drag ghost, arrow nudges/input isolation, Inspector list selection and pulse, calculate→path→run and invalidation.
- [x] Implement translucent 3D ghost/footprint, coalesced world-axis keyboard nudges, timed selection halo, empty Inspector list, rainbow measured path, asynchronous plan feedback and example picker.
- [x] Run frontend unit/build and focused browser tests, GREEN; commit.

### Task 4: Ten examples, integration and final review
**Files:** backend/examples.py, backend/tests/test_examples.py, frontend/e2e tests, examples/, docs/API.md, docs/VERIFICATION.md, README.md.
**Interfaces:** ten named scenes through example_scene(exampleId), example_catalog().
- [x] Create ten distinct reachable task arrangements and execute each plan and run; record actual success/lift/release/time. Refine controller from failures without weakening verification.
- [x] Test unreachable/blocked user scenes and changed positions/orientations, update legacy tests for explicit planning.
- [x] Full backend/frontend/browser/build checks and visual screenshots. Independent whole-branch review, resolve important findings RED→GREEN.
- [x] Document dimensions/limits/results; commit, fast-forward main and push authorized repository.
