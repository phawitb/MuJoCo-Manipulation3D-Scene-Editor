# MuJoCo Package Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox syntax for tracking.

**Goal:** Import a rigid MuJoCo object from a folder or ZIP with portable visuals and physics.
**Architecture:** Validate package-local XML/assets, compile an isolated rigid object, normalize compiled geometry/inertia into a bounded scene model, and reconstruct it alongside existing objects. The UI previews the validated object before insertion.
**Tech Stack:** Python, MuJoCo, Pydantic, FastAPI, React/TypeScript, existing Playwright.
**Spec:** docs/superpowers/specs/2026-10-30-mujoco-package-import-design.md

## Global Constraints
- Preserve SI dimensions, per-part colors, compound collision, COM and inertia.
- One rigid object; reject unsupported physics and external resources without modifying the live scene.
- Existing imports and 8 MB portable scene budget remain supported.
- No new services; preserve user scenes during restart.

## Review Focus
- Nested ZIP/folder paths and path traversal must not escape package data (task 1).
- Compiled mesh frame transforms must not rotate or recenter parts incorrectly (task 2).
- Source per-part contact/color data must survive edits and collection (tasks 2/3).
- Duplicate names and save/reopen must preserve independent objects (task 2).
- Failed preview or importing during simulation must leave existing scene intact (task 3).

### Task 1: Validated portable package reader
**Files:** backend/package_schema.py, backend/package_importer.py, backend/schema.py, backend/tests/test_package_import.py
**Interfaces:** import_package(files: dict[str, bytes]) -> SceneObject; import_package_zip(data: bytes) -> SceneObject. SceneObject.package holds typed normalized data; asset='mujoco'.
- [x] Write tests for primitive and mesh fixture physics/colors, ZIP equivalence, unsupported joints/unsafe paths/missing files/budgets.
- [x] Run tests RED, implement bounded parser and typed normalized representation, run GREEN.

### Task 2: Simulation, editing and collection integration
**Files:** backend/package_geometry.py, backend/simulation.py, backend/catalog.py, backend/appearance.py, backend/collection_randomization.py, frontend/src/types.ts, frontend/src/interaction.ts
**Interfaces:** add_package(root, obj) creates namespaced object with source inertia/contacts; profile returns centered dimensions and family='mesh'. Overrides are explicit optional flags on SceneObject.
- [x] Write reconstruction tests for mass/COM/tensor, transformed meshes, duplicate import, scaling, colors/friction overrides, save/reopen and native camera rendering.
- [x] Run RED, implement reconstruction and appearance/placement integration, run GREEN.

### Task 3: Import API and UI
**Files:** backend/main.py, frontend/src/ImportDialog.tsx, frontend/src/Inspector.tsx, frontend/src/App.tsx, frontend/e2e/package-import.spec.ts
**Interfaces:** POST /api/import/package accepts JSON files [{path,data:base64}] for folders, or application/zip for archives; returns validated SceneObject preview. Import and place uses existing object_add command.
- [x] Write API/browser tests for folder+ZIP preview, insert, original colors, editing, save/reopen and rejected import.
- [x] Run RED, implement UI and API, run GREEN; inspect real supplied package in browser and native camera.

### Task 4: Verification and release locally
**Files:** README.md, docs/VERIFICATION.md, design/plan status
- [x] Run focused backend tests, frontend unit/build and browser integration; inspect original sample physics and render.
- [x] Fresh reviewer reads final changes; fix material findings with regression tests.
- [x] Preserve active scenes, restart backend with restoration, leave application running; document result and commit.

## Execution ledger
- User approved design and explicitly requested continuing without repeat questions.
- Ruling: use existing clean feature checkout codex/lerobot-collection and running frontend, avoiding a second checkout/server and preserving active user environment. Native execution chosen; fresh final reviewer per executing-plans skill.

- Tasks 1–3: implemented and verified (26 package tests; folder/ZIP browser integration passed). Ruling: JSON base64 upload for folder files avoids new dependencies; ZIP uses a binary request. Ruling: source material scalars are preserved natively; Three shading remains the existing approximate rendering model. API and Inspector color/friction overrides use explicit flags so source per-part values remain recoverable.
- Review fixes: retain inherited childclass while extracting a rigid body; accept both complete object.xml and include fragments; match unnamed scene bodies structurally; send pkg_ meshes in browser snapshots.
- Actual example compared against native source with 8.2e-10 m maximum mesh error. Preview, browser rendering and native image visually inspected. Final verification: full backend regression suite 214 passed; final affected-code run 45 passed including 26 package cases; frontend 14 unit tests, build, folder/ZIP browser test and No random collection browser test passed. Fresh final reviewer confirmed no blocking findings. Ruling: keep work on the existing local feature branch without merge/push; user requested no further questions.
