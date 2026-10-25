# Connected Gym execution and horizontal camera views

User authorizes autonomous implementation and real-robot UI tests of three examples on the computer's fullscreen landscape display. Stay on main; preserve v1.

1. Change shared camera results to a responsive horizontal strip (side-by-side frames; scroll horizontally on narrow displays).
2. Add connected-session execution coordinator: Calculate uses a fresh measured starting pose; Run validates the verified plan and current physical pose, explicitly enables/synchronizes the owning device, then advances simulation with measured-feedback pacing instead of independent wall-clock stepping. Preserve simulation-only behavior when not connected. Pause/stop/fault/reload stop both; do not bypass calibration, collision, joint, thermal, speed or lease checks.
3. Test new command/clock/state transitions with fake drivers before hardware. Test through the browser on fullscreen landscape, select/calculate/run three examples, record physical angle feedback and simulator outcomes. Do not claim physical object transfers when only virtual objects are present. Stop/hold at end. Review independently once, fix important findings, verify tests/build and push main.

Review focus: lock order, ownership, stale planning state, failure stop of both systems, cancellation and resume, standalone Gym module, bounded simulation advancement, physical feedback lag, final target settling, no hidden automatic motion on connect/load/plan.


## Execution ledger

- Horizontal layout implemented and checked in fullscreen Chrome for Scan (0,1,2) and Verify (Back 0, Wrist 1).
- Connected execution and clock ownership implemented with fake-driver regressions (RED → GREEN).
- Ruling: compensate only within existing hard limits and map MuJoCo's already accepted 0.002 rad compliant residual onto hard-bounded targets. Do not relax physical measured-pose or collision guards. Added braking/rate/reversal tests (RED → GREEN).
- Ruling: failed policy settling and switching to passive physics must stop the real robot immediately. Fresh review identified both gaps; regression tests reproduced and fixed them.
- Live outcome: example01 moved then stopped at the table guard; example02 and05 could not start from the resulting measured pose. Three successful physical executions remain unfulfilled. No collision bypass or calibration change was used to manufacture a pass. Details in docs/verification/2026-10-25-linked-gym-run.md.
- Final validation: backend full suite 244 passed; after last status-reset fix, related subset 69 passed; frontend 21 passed and build passed. Current arm remains connected, streaming off, torque held. Real-world completion remains blocked by measured/model table overlap, documented explicitly.
