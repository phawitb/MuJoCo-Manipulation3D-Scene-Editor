# Contact Physics Correction Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans; implement inline, one fresh final review.

**Goal:** Replace invisible attachment with verified physical gripping across examples.
**Architecture:** Physical grasp diagnostics → geometry-aware actuator controller → isolated rehearsal/live execution → measured UI/API feedback.
**Tech Stack:** Existing MuJoCo/Python/React.
**Spec:** docs/superpowers/specs/2026-10-24-contact-physics-design.md

## Global Constraints
- No object teleportation, weld attachment or artificial holding force.
- Grasp validity must use opposing jaw forces, not proximity alone.
- Keep original examples for comparison; record honest failures.
- Bounded controller, solver and planning; retain scene/API compatibility.

## Review Focus
- Jaw contact from the table or another object must not count as source grasp.
- Opening/slipping in mid-air must let gravity act and invalidate successful execution.
- Partial/one-sided contact and excessive penetration must not count as secure grasp.
- Observation batch sizes must not materially change advertised success.
- Rehearsal must not move live state; all ten outcomes must be actually measured.

### Task1: Diagnose and replace artificial attachment
- [x] Record original ten-case contact audit; write RED tests for missed grasp, opening/drop and no noncontact holding.
- [x] Implement contact telemetry and physical jaw-aware grasp/closure/slip/release. Remove equality generation.
- [x] GREEN physical regression tests and ten-case probe; commit.

### Task2: Reliable physical task execution
- [x] Strengthen ten-example tests for actual supporting contact and multiple execution batch sizes; observe original failures.
- [x] Refine grasp/trajectory from measured failures, preserving contact semantics and actuator bounds.
- [x] Run backend suite, preserve live-state and cancellation tests; commit.

### Task3: Feedback, visual validation and integration
- [x] Show measured grip/contact-only status in UI/API and update docs, examples and tests.
- [x] Capture06 close-up plus other tasks and verify full backend/frontend/browser suites.
- [x] Fresh independent review; fix important findings RED→GREEN; push authorized main.
