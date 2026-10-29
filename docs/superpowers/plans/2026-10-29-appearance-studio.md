# Appearance Studio Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add portable, reproducible visual domain randomization for future robotics datasets.
**Architecture:** Scene appearance is authoritative. Shared generated texture pixels and compiled geometry feed MuJoCo and Three. Dedicated appearance commands preserve physics state.
**Tech Stack:** Existing Python/Pydantic/MuJoCo/Pillow and React/Three/Vite.
**Spec:** docs/superpowers/specs/2026-10-29-appearance-studio-design.md

## Global Constraints
No new dependencies. Preserve old scene loading and existing physical behavior. Use current checkout so the running user project receives the feature; isolate history on codex/appearance-studio. User delegates design and implementation choices; execute inline.

## Review Focus
- Appearance-only edits retain integration state and prepared plans.
- Environment geometry never affects collision or controller safety.
- Invalid seeds/material/light values fail atomically.
- Repeated seed/scopes/strength are reproducible; locked categories stay unchanged.
- Browser rendering and native observations both receive textures and environments.

### Task 1: Authoritative appearance and native rendering
- [x] Add failing backend tests for defaults, bounds, randomization scopes and state preservation.
- [x] Implement backend/appearance.py schema, presets, randomization, texture assets and XML decorations; integrate schema.py, simulation.py, sessions.py, planning.py, main.py.
- [x] Verify backend appearance tests and legacy table/render/session behavior.

### Task 2: Browser studio
- [x] Add browser workflow regression before implementing UI.
- [x] Extend types.ts and Viewport.tsx for materials, UVs and environment lights.
- [x] Add AppearanceStudio.tsx, accessible header entry, scoped randomization and recipe export; style responsive drawer.
- [x] Verify TypeScript, unit tests and browser editing/export workflow.

### Task 3: Integration and delivery
- [x] Verify native render changes, examples/reset persistence and full checks.
- [x] Review final diff, address defects, document API/limitations and restart/open live app.

## Verification record
- Full project check: 149 backend tests, 14 frontend unit tests, production build passed.
- After native material precedence fix: 10 focused appearance/table/render tests passed, including effective MjvScene colors and preserved physical model/state/plan.
- Browser: appearance workflow, camera snapshot draft retention, narrow screen/keyboard apply and repeated preset regression passed. Four existing camera/reset/workspace browser tests also passed.
- Independent review caught native geom RGBA precedence and draft synchronization issues; both fixed with regressions, including the same-preset edge case.
- Build retains the existing large-bundle advisory. Renderers share inputs and texture pixels but use different shading/projection models.
