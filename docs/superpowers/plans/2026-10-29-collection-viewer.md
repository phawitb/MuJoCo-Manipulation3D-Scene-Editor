# Collection Viewer Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline and request a final independent review.

**Goal:** Select capture cameras and inspect recorded episodes within a full-page Collect workspace.
**Architecture:** Config drives all capture stages. A validated cached metadata index maps v3 offsets/video files to read-only API endpoints. React viewer synchronizes sampled signals and video views with a frame clock.
**Stack:** Existing React/TypeScript/SVG, FastAPI, NumPy, isolated LeRobot/PyArrow runtime.
**Spec:** docs/superpowers/specs/2026-10-29-collection-viewer-design.md

## Constraints / review focus
Nonempty unique valid camera subset; all-five legacy default. Correct episode video offsets; no arbitrary files or unverified output. Episode changes stop playback and discard stale requests. Frame stepping and chart cursor match sampled trace. Fullscreen page remains usable at narrow widths; editor state survives return.

- [x] Add failing camera subset and viewer API/index regressions.
- [x] Implement selectable capture, subset readback and cached index/video/signal endpoints.
- [x] Implement full-page Collect, camera selectors and synchronized episode viewer.
- [x] Test real subset export/readback, browser playback/seek/episode switch/return, responsive layout and build.
- [x] Independent review, docs and screenshot verification.

Verification: 24 relevant backend tests, 4 browser scenarios and 14 frontend unit tests passed; TypeScript/build and correctness lint passed. Real subset export/readback, legacy shared-video offsets and screenshots verified. Independent review identified hidden editor shortcuts; reproduced with a failing regression, then fixed with explicit shortcut isolation and focus restoration. Evidence: docs/VERIFICATION.md.
