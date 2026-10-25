# Direct Robot Control Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restore cross-project motor responsiveness and deliver live sliders, Home, torque controls and measured robot preview.
**Architecture:** Serialized existing hardware owner with a replaceable manual target, bounded trajectory updates and an owned servo-speed profile restored on handoff. Preview uses scratch MuJoCo state, not live scene mutations.
**Tech Stack:** Python/FastAPI/MuJoCo, React/TypeScript/Three.
**Spec:** docs/superpowers/specs/2026-10-25-direct-robot-control-design.md

## Global Constraints
- Stay on main; preserve v1 and external repository changes.
- No EEPROM writes or blind collision bypass; explicit Torque off is user-authorized.
- Only one serial owner, no movement on read-only API connect.

## Review Focus
- Partial bus-write failure must still release port and report failed profile restoration.
- Slider bursts replace targets rather than queue old motion.
- Torque off cancels every producer before release and never auto-enables.
- Scene changes/lease expiry/physical stalls stop manual motion.
- UI model and sliders use measured values, never fake achieved poses.

### Task 1 — Servo speed lifecycle and repair
- [x] Failing driver tests: save before override, measured hold before restore, exact original restoration, port closure on failure.
- [x] Implement RAM-only speed restoration and explicit legacy default repair; verify live readback while no other app owns serial.
### Task 2 — Manual commands and measured preview
- [x] Failing tests: latest target wins, bounds/collision checks, Home saved pose, torque off cancels, no automatic restart; preview leaves scene unchanged.
- [x] Add manual helper, typed API/MCP, status metadata and live update loop.
### Task 3 — Robot control UI
- [x] Live sliders + measured/target display + coalesced send; Home, Match Gym and explicit torque buttons. Display measured simplified SO-101 beside controls.
- [x] Build/test and fullscreen browser validation with bounded real movement. Record endpoint/response latency and speed profile restoration; do not claim unobserved mimic movement.
### Task 4 — Verification and delivery
- [x] Relevant regression suite and one fresh static review, fix important findings, document outcomes, push main.

Validation limitation: six-axis UI/nearby Home and profile handoff verified physically; full real episode and long Home return remain blocked by modeled table overlap. Torque release tested on fake bus only. Final findings and exact metrics: docs/verification/2026-10-25-direct-robot-control.md.
