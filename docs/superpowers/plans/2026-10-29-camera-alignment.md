# Camera Alignment Implementation Plan

> **For agentic workers:** Execute inline using test-driven development; independent final review.

**Goal:** Recorded camera poses and vertical projection match the editor.
**Architecture:** Correct backend free-camera conversion and orthographic model settings; carry top canvas height through collection config; provenance identifies old projection.
**Tech stack:** Existing MuJoCo/Python/React/Three.js.
**Spec:** docs/superpowers/specs/2026-10-29-camera-alignment.md

- [x] Fail regression for Main/Front/Back position, orientation and zoom; Top true ortho/height/distance/up; Top→Wrist→Main state isolation.
- [x] Correct renderer, add reference-height capture and projection provenance with old-video explanation.
- [x] Validate numerical cameras, native render, real collected videos, browser top-height payload and existing collection controls. Inspect aligned frame.
- [x] Independent review, docs and local commit; leave existing video data intact.

Review focus: renderer state leak across five views, zoom parallax, output-resolution independence, hidden Top fallback, legacy cached viewer indexes. Defaults preserve old scene configs; new projection metadata only applies to future captures.

Verification: 13 camera cases RED→GREEN, 28 relevant backend tests, 3 browser scenarios and 14 frontend unit tests passed; build/lint/diff checks passed. Native/editor images and real encoded first frames inspected. Independent review: no actionable findings. Evidence: docs/VERIFICATION.md.
