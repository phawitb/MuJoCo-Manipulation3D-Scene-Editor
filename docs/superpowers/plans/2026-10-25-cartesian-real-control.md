# Cartesian real-arm control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Control real SO101 motion by tool-center goals with independent joint solutions, full-arm collision checks and honest feedback provenance.
**Architecture:** Shared MuJoCo kinematics/collision model; measured real-arm Cartesian executor independent of Gym's clock; one serial owner. Endpoint reports replace joint-matching success; motor diagnostics and boundary recovery remain separate.
**Tech Stack:** Python, MuJoCo, SciPy, FastAPI, React, Three.js.
**Spec:** docs/superpowers/specs/2026-10-25-cartesian-real-control-design.md

## Global Constraints
Preserve collision/raw limits and stop/lease/ownership. No EEPROM writes. Preserve scenes; main development authorized; v1 unchanged. Encoder FK must be visibly labeled estimated. Simulated grasp success is not physical grasp evidence.

## Review Focus
- Stale/expired command after Stop never resumes a prior target (task 1/2 cancellation tests).
- Endpoint close with differing joints must not fail only for Sim mismatch (task 2 pose tests).
- Endpoint correct but wrong orientation/jaw must not qualify arrival (task 2 tests).
- Cartesian IK or intermediate path collides / unreachable (task 2 rejection tests).
- No external measurements: never label physical grasp verified (task 3 report tests).

### Task 1: Diagnose and repair motor response
**Files:** backend/modules/connection/driver.py, controls.py, limit_recovery.py; backend/tests/test_connection_driver.py, test_limit_recovery.py; docs/verification/.
**Interfaces:** SerialDriver read/write position and speed, read-only deadband diagnostics, service owner/lease.
- [x] Reproduce motor nonresponse with existing bounded recovery, inspect feedback and primary control-table documentation.
- [ ] Write regression for identified driver/control defect; observe failure; implement targeted RAM-only correction.
- [ ] Run driver/recovery/manual tests and physically verify movement then measured hold.
- [ ] Commit motor correction and existing uncommitted recovery work with truthful test evidence.

### Task 2: Cartesian targets and independent execution
**Files:** create backend/modules/connection/cartesian.py and test_cartesian.py; modify schemas.py, service.py, routes.py, mcp.py, execution.py, bridge.py.
**Interfaces:** pose(q)->position/rotation; solve(goal,measured)->bounded joints; CartesianMotion.tick(measured), status(), halt. ToolGoal uses world position, optional orientation, opening and control_epoch.
- [x] Tests: FK agrees with MuJoCo; IK solves reachable position from measured seed; unreachable and colliding path reject before writes; orientation/jaw affect arrival; no dependency on Sim joint equality.
- [x] Implement bounded pose solver, whole-arm swept validation and measured-feedback executor with speed/acceleration limits, stall detection, epoch/lease cancellation and encoder_fk status.
- [x] Real task execution uses task-space waypoints and measured start, separate from running Gym physics. Preserve simulation prerequisite and distinguish trajectory completion from object verification.
- [x] Run new and existing execution/guard tests; commit.

### Task 3: UI, reports and physical verification
**Files:** frontend/src/modules/connection/api.ts, GymRobot.tsx, new CartesianControls.tsx; backend/modules/connection/episode_report.py; docs/CONNECTION.md and verification report.
**Interfaces:** endpoint goals/status/results shared by HTTP and MCP; measurement source and object_verification explicit.
- [x] Add endpoint coordinates, measured/target position, error in mm and orientation error; keep joint controls as diagnostics. Connect no longer initiates pose matching.
- [x] Add API/MCP contract tests and UI build/unit checks, including unverified physical object state.
- [ ] Restart preserving scenes; test browser endpoint motion on real hardware, inspect telemetry and collision results; record achievable accuracy, not 100% claims.
- [x] Final independent review, fix important findings with regression tests, run relevant suite, commit/push main.

## Physical acceptance remains incomplete
Bounded hardware probes produced at most one encoder tick; the starting elbow/gripper range violations persist. No physical Cartesian episode or absolute TCP accuracy was verified. See `docs/verification/2026-10-25-cartesian-real-control.md`. The software work and simulated-bus verification do not close the hardware acceptance items above.
