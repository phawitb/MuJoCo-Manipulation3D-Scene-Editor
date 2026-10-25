# Physical calibration and realtime sync — 2026-10-25

## Scope and result

The connected SO-101 completed bounded outward and return movements on all six joints using Gym targets and independent serial encoder feedback. Real-to-Gym, Gym-to-real, explicit Stop, and controller lease expiry were exercised. These tests validate this connected arm with an empty configured scene; they do not validate every workspace pose, a physical pick-and-place policy, or absolute optical calibration.

## Mapping and fixes

The five rotary-joint zeros now use the midpoints of the existing verified LeRobot calibration ranges, matching the upstream SO101 `new_calib` model convention. The gripper maps its physically calibrated closed encoder limit to zero hinge angle. LeRobot's 0–100 gripper percentage is not interpreted as radians. Encoder resolution is 2π/4096 radians. Half-tick midpoint zeros are preserved by the schema and settings UI. Calibration remains device-specific in local settings, not a default for other arms.

The existing EEPROM offsets and limits were read and cross-checked with the saved calibration, not rewritten. Motor identity, all six IDs, temperature, supply voltage, torque state, and encoder readings were verified. An initial elbow position near its mechanical stop was moved slowly toward a valid model pose before enabling guarded sync; model joint ranges and collision checks were not widened.

The streamed command now accumulates from its previous command instead of restarting at every measured reading. The former behavior could repeatedly send increments smaller than servo deadband. The updated controller retains the 0.3 rad/s command limit and refuses command lead over 0.15 radians before writing it. Tracking, joint bounds, scene collision, ownership, and heartbeat guards remain enabled. Switching synchronization initializes the ramp from current measurement. The worker waits 50 ms between cycles; this is not a hard realtime guarantee.

`POST /api/connection/align`, MCP `align_gym_to_robot`, and the **Match Gym to real arm** button copy a validated measured pose into Gym without motor commands. They reject active motion/synchronization and unsafe model poses.

## Recorded hardware results

- Real-to-Gym: three-second sampled mirror; zero discrepancy in the final run. An earlier run had at most one encoder tick (0.0879°) between separately sampled API reads.
- Gym-to-real: 12 phases, 1.8 seconds each, one joint at a time. Target offsets were +0.08, −0.06, −0.10, −0.06, +0.08, +0.12 rad respectively, followed by return to baseline. Every outward motion had the correct encoder direction and exceeded 0.015 rad from its immediately preceding measured position.
- Maximum sampled feedback age in the complete movement run: 63.2 ms. This measures age of the most recent completed read, not camera latency or guaranteed command-to-motion latency.
- Maximum final joint error: 3.36° at the loaded elbow. Other commanded-joint final errors were 0.88–1.50°. Existing servo deadband, gravity loading and gains remain relevant; no automatic gain tuning or hidden angle compensation was applied.
- Lease expiry with no heartbeat: streaming disabled at 3.09 seconds; motor torque remained on. Explicit Stop was also tested.
- UI verified connected/calibrated state, alignment button, real-to-Gym selection, continued lease while navigating back to Gym, and global Stop.

| Joint | Outward final error | Return final error |
| --- | ---: | ---: |
| Shoulder pan | 1.16° | 1.05° |
| Shoulder lift | 1.33° | 1.05° |
| Elbow | 3.36° | 1.14° |
| Wrist flex | 1.50° | 0.88° |
| Wrist roll | 1.24° | 1.23° |
| Gripper | 1.25° | 1.14° |

Full sampled targets, measured angles, encoder readings, timing, and lease trace: [physical-sync-trace.json](2026-10-25-physical-sync-trace.json).

## Verification and limits

- Backend: 34 focused connection, module, and MCP tests passed.
- Frontend: 21 unit tests passed; production build passed (existing large-bundle advisory remains).
- Fatal Python syntax/name checks passed. The broader style lint still reports existing import ordering, dictionary style, and related findings in the connection module; it is not a clean full-lint result.
- Added regressions cover fractional calibration zeros, accumulation through deadband, stalled motors, pre-write command lead, and measured alignment ownership/collision/active-mode rejection.
- All 14 existing scene sessions were preserved during backend replacement. Only the explicitly used hardware scene was aligned to measurement. Calibration survives restart; active connection and movement never resume automatically.
- Camera 0 provided an overhead image, but did not show the complete arm well enough to independently measure every link angle. Encoder-to-model agreement therefore must not be described as optical or millimeter-level verification.
- Hardware was left connected, streaming off, with existing torque preserved and Gym aligned to measured pose.

## Provenance

[Upstream SO101 simulation conventions](https://github.com/TheRobotStudio/SO-ARM100/blob/main/Simulation/SO101/README.md), [new calibration model](https://github.com/TheRobotStudio/SO-ARM100/blob/main/Simulation/SO101/so101_new_calib.xml), and [LeRobot SO-101 documentation](https://huggingface.co/docs/lerobot/en/so101). The installed LeRobot normalizer and the user's VLA-Benchmark connection implementation were also inspected locally.
