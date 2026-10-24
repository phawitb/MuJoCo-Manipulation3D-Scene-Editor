# Manipulation Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement task-by-task.

**Goal:** A usable camera-equipped SO-101 pick/place workbench with import and complete external control.
**Architecture:** Validated portable scenes; MuJoCo IK/task controller; locked shared session service; REST and official MCP bridge; React workbench.
**Tech Stack:** Python, MuJoCo, NumPy/SciPy, trimesh, MCP Python SDK, FastAPI, React/Three.js.
**Spec:** docs/superpowers/specs/2026-10-24-manipulation-design.md

## Global Constraints
- SI units, Z up, WXYZ. Preserve old scene files.
- Run moves the arm; physics only remains explicit.
- No object teleportation. Label grasp assist, measure release success.
- Local-only bounded APIs; explicit session IDs; atomic scene updates.

## Review Focus
- Thin spoon grasp and post-release success: physical trajectory test (task 1).
- Invalid/reversed/unreachable tasks and cancel while held: task 1 tests.
- Import malformed/oversized/flat geometry and portable reload: task 2 tests.
- Stale concurrent edits and external control reflected in browser: task 3 tests.
- Camera edits/remounts, lost connection, click task and duplicate object IDs: task 4 tests.

### Task 1: IK policy and camera/task contract
**Files:** backend/schema.py, simulation.py, new policy.py, examples.py, tests/test_policy.py.
**Interfaces:** Scene.task {source,target}; Simulation.start_policy(), stop_policy(), state().task, state().cameras; example_scene().
- [x] Write/run failing tests for task validation, actual lifted/released spoon success, pause/cancel, wrist movement.
- [x] Implement bounded IK, phase controller, proximity-gated grasp constraint, physical success evaluator; scene camera/task defaults.
- [x] Run policy tests, verify repeated example success and negative cases. Commit.

### Task 2: Portable object import
**Files:** backend/importer.py, schema.py, simulation.py, tests/test_import.py.
**Interfaces:** import_object(data:bytes, filename:str, size:float)->SceneObject; optional mesh vertices/faces embedded in objects; snapshot.meshes for imported compiled geometry.
- [x] Write/run tests for real STL/OBJ/GLB conversion, malformed/flat/oversize input and save/load.
- [x] Implement bounded file conversion, schema mesh validation, MuJoCo rendering/collision.
- [x] Run importer tests and existing simulation tests. Commit.

### Task 3: Shared REST/WebSocket/MCP control
**Files:** backend/sessions.py, main.py, mcp_server.py, tests/test_api.py, tests/test_mcp.py.
**Interfaces:** /api/sessions, /api/sessions/{id}, /api/sessions/{id}/command, /api/import, /ws?session=id. Commands load/reset/example/run/pause/stop/physics/step/snapshot/task/object_add/object_update/object_remove/robot/camera.
- [x] Write/run tests for external control on same browser session, revision conflicts, malformed input and MCP tools.
- [x] Implement locked session lifecycle/ticking, one command dispatcher, official SDK bridge and connection example.
- [x] Run API and real MCP integration tests. Commit.

### Task 4: Workbench UI and end-to-end verification
**Files:** frontend/src/{App,Viewport,Library,useSimulation,types,math,styles}, new TaskPanel/CameraEditor/ImportDialog, e2e tests, README, docs/API, docs/VERIFICATION.
**Interfaces:** existing editor plus task/camera/import contract from tasks 1–3.
- [x] Write/run browser tests for four views, numeric front camera, example run, source/target clicks, import and reload.
- [x] Implement ergonomic task panel, observation views, editable cameras, import dialog and API session panel.
- [x] Run all Python, frontend unit, TypeScript/build and browser suites; inspect screenshots and actual task execution.
- [x] Independent whole-branch review; resolve important findings with regression tests. Document evidence and limitations; commit.
