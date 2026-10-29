# Scene Collection Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans, implement inline. Request final independent code review.

**Goal:** Scene-specific seeded datasets with broad defaults and exact requested retained episode count.
**Architecture:** Extend validated config/API; isolate scene selection/XY grouping helpers; replan per attempt and retain complete episodes to target with bounded retries; update existing Collect panel.
**Tech Stack:** React/TypeScript, FastAPI/Pydantic, MuJoCo, pinned official LeRobot.
**Spec:** docs/superpowers/specs/2026-10-29-scene-collection-design.md

## Constraints and review focus
- All default choices except orange/yellow robot body. Disabled scopes preserve values.
- One scene per job; no live editor mutation; explicit scene provenance/filter.
- Bounds, contained-object relationships and task identities survive placement variation.
- No reused paths after physical edits. Rehearsal failure is provenance, not a retained demonstration.
- Target saved episodes, bounded attempts, clear partial completion/cancellation, intact prior data.

## Steps
- [x] Add failing tests for defaults, scene selection and deterministic object positioning.
- [x] Implement schema/scene/position helpers and per-attempt rehearsal/counting tests.
- [x] Add All buttons, scene selector/filter, position settings and episode-target progress.
- [x] Verify official multi-episode collection with new positions and browser flow; run relevant regressions/build.
- [x] Review, document and show updated running app.

## Verification

Defaults/scene/position tests failed before implementation. Containment regression failed for lower-half cargo and spoon-end containment before sharing the existing controller geometry predicate; it now passes. Final relevant backend run: **44 passed in 172.73 s**, including all collection, planning, cup grasp and clearance tests. The actual official writer/reader test rejects seed 42 deliberately, then collects two successful physically randomized episodes with separate rehearsals. Budget exhaustion stops after 5 attempts for a one-episode target and reports 0/1 instead of completion.

Browser collection + appearance checks: **4 passed in 24.4 s**. Final collection rerun after resetting tab scroll: **1 passed in 17.9 s**. It verifies all defaults/All buttons, independent preset selection from an empty editor, both position controls, two retained episodes (20 frames), scene filtering, download, unchanged live editor, and mobile close control. Frontend **14 unit tests**, TypeScript/build and focused Python lint pass. Screenshots inspected. Independent reviewer reports no remaining actionable findings.
