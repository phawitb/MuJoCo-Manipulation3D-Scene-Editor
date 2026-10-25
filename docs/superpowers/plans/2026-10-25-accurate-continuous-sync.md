# Accurate continuous SO-101 synchronization

> **For agentic workers:** Use superpowers:executing-plans for native implementation and an independent final review.

**Goal:** Reduce measured joint tracking error, especially the loaded elbow, and verify continuous multi-joint motion with recorded evidence.

**Architecture:** Keep device calibration fixed. Add a bounded feedback correction outside the existing motor position loop, with smooth bounded goal changes and explicit desired/commanded/measured telemetry. Do not rewrite motor EEPROM or move the displayed Gym pose to conceal error.

**Tech stack:** Python, MuJoCo, Feetech protocol 0, React.

**Design decision:** The user delegates decisions and authorizes physical trials. A bounded host feedback correction is preferred to changing servo EEPROM gains (harder to restore safely and hardware-specific) or changing calibration zeros (would mask load-dependent error). No claim of exact 100% geometric accuracy is possible from encoder data alone.

## Constraints and review focus

- Maintain raw/model bounds, whole-arm collision checks, 0.3 rad/s command speed, 0.15 rad tracking fault, ownership and 3-second lease.
- Bound correction and integration; no windup during saturated or stale updates. Stop on faults, do not auto-restart.
- Normal stop/start should retain learned gravity compensation without continuing a trajectory. Fault handling must not reuse unsafe compensation.
- Show actual error separately from requested Gym pose. Restart never resumes physical motion.
- Preserve main/v1 and all existing scenes; only one hardware owner.

## Steps

- [x] Record an unmodified continuous baseline after moving to a collision-safe pose with clearance. Validate the complete planned motion before running; retain failures as well as passes.
- [x] Add deterministic tests for load-offset rejection, deadband, smooth reversal, velocity/acceleration bounds, saturation, stalled motors, stop/restart bias and stale feedback. Run red before implementation.
- [x] Implement a small controller module and integrate it into the existing service; expose reference, compensation and tracking errors in status and UI. Keep motor driver changes separate unless measured timing requires them.
- [x] Verify tests, then commission static accuracy and multi-cycle continuous motion. Compare identical profiles before/after; record per-joint RMS/peak/settled errors and timing. Adjust bounded gains only from measured results.
- [x] Review changes, run focused checks, preserve state while deploying, verify UI, document achieved accuracy and limitations, commit and push main. Leave streaming stopped and torque preserved.

## Execution evidence and adjustments

- Completed baseline, matched final comparison, 117-second independent six-axis motion and 15-second stop/re-enable/stationary-sync test. See `docs/verification/2026-10-25-continuous-sync.md` and recorded CSVs.
- Physical measurements justified checked block-feedback reads and bounded confirmation for isolated temperature anomalies; the origin of those anomalies is not claimed fixed.
- Independent review fixes: clear compensation after unconfirmed Stop; reject stale compensated holds; check actual SDK packet lengths before decoding. Final review found no important regression.
- 61 focused backend tests, 21 frontend tests, TypeScript/build and fatal lint/whitespace checks passed. UI checked with physical connection; final streaming off and torque preserved.
- Work remains on main. v1 is the untouched backup. No calibration-zero or motor EEPROM change.
