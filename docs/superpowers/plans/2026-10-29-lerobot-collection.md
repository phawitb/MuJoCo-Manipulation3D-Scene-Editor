# LeRobot collection implementation plan

> **For agentic workers:** Use superpowers:executing-plans; implement inline and request one final independent review.

**Goal:** Capture synchronized multi-camera robot demonstrations with seeded palette constraints as an official LeRobot v3 dataset.
**Architecture:** Editor process owns job dispatch/status only. Isolated worker owns simulation, renderer and official LeRobot writer. Full recipe and dense trajectory accompany each retained episode.
**Tech Stack:** Existing React/FastAPI/MuJoCo, isolated lerobot[dataset] 0.6.1 runtime.
**Spec:** docs/superpowers/specs/2026-10-29-lerobot-collection-design.md

## Global constraints
Five cameras at one simulation state. SI radians/meters. Fixed 1000 Hz physics; 10/20/25/50 Hz datasets. Palette lists constrain sampled values, empty means locked. Never upload datasets automatically or overwrite another dataset. Run on current checkout in codex/lerobot-collection.

## Review focus
- Correct observation/action time alignment and no variable-rate mislabeled data.
- Cancel/error cannot publish a partial episode or corrupt earlier saved episodes.
- Rehearsal and collection never mutate the live editor session.
- Download paths/names bounded to generated dataset directories.
- LeRobot reads exported data and video frames without hub access.

### Task 1: Configuration, randomization and synchronized capture
- [x] Write failing tests for palettes/scopes/validation and before-step callback time/control.
- [x] Add collection schema/randomizer, recorder hook and reusable native camera renderer.
- [x] Verify deterministic recipes and unchanged physical behavior.

### Task 2: Official writer and worker
- [x] Add integration test using actual writer and reader.
- [x] Implement bounded worker, rehearsal, five-camera sampling, dense NPZ, metadata, stop/finalize and validation.
- [x] Verify a complete task and interrupted recording with readback.

### Task 3: Jobs, API and UI
- [x] Add API tests and failing browser workflow.
- [x] Add safe process manager, polling/status/download, palette-aware Collect panel.
- [x] Verify UI, API isolation, completed download and recoverable cancellation.

### Task 4: Delivery
- [x] Run full regression checks and independent review; fix findings.
- [x] Document setup, dataset contract and examples; restart and verify live app.

## Completion evidence

- Official writer/reader integration, cancellation, palette constraints, encoding rollback and repeated-finalization-error rollback: 8 collection tests passed. Regressions were observed failing before their fixes.
- Full backend run: 158 passed in 514.65 s; the additional finalization-failure regression plus a focused final 8-test run cover all 159 currently collected backend tests.
- Frontend: 14 unit tests, TypeScript and production build passed. Browser suite: 38 passed initially; an existing capacity test assumed all 16 slots were free despite the live editor. Updated it to fill available slots while preserving existing sessions. Focused collection/capacity rerun: 2 passed, covering all 39 browser scenarios. The collection test waits for its own newly created job and asserts 10 saved frames plus unchanged editor scene/time.
- Completed real example: seeds 42/43, 2 successful episodes at 640x480/20 FPS, 359 frames each (718 per camera), 17.907 s each. All five videos and state/action/time alignment read back successfully. ZIP verified (23 files). Native camera imagery and browser panel inspected.
- Independent review findings resolved: palette secondary colors, interrupted-attempt provenance, failed-write rollback and finalization-error recovery. Focused final review reports no actionable findings.
