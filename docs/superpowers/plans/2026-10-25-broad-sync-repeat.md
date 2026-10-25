# Broad physical synchronization repeat

> **For agentic workers:** Use superpowers:executing-plans for native execution and independent review of any controller change.

**Goal:** Measure and improve continuous joint tracking across a wider collision-checked pose set, with explicit measured coverage and limits.

**Architecture:** Keep the verified physical calibration and hardware limits unchanged. Use existing Gym HTTP commands and the sole connection-service owner for physical testing. Compare repeatable profiles before and after any evidence-backed controller change; never tune calibration to conceal load error.

**Tech stack:** Python, MuJoCo, Feetech serial feedback, existing HTTP service.

**Spec:** User requests repeat trials, broad angular coverage, smoother continuous synchronization and maximum achievable agreement, with autonomous execution.

## Constraints and review focus

- Work on main; preserve v1, 14 sessions and torque. One serial owner only.
- Offline preflight plus runtime collision/joint/telemetry/heartbeat guards stay active. Do not force mechanically inaccessible or unobserved joint-limit poses.
- Camera framing is incomplete. Encoder accuracy is not independent geometric accuracy; no 100% claim.
- Record motion failures, temperature anomalies, reversals, steady-state error, timing and angular coverage.
- A software change requires a failing regression, focused verification and independent review. No tuning without a measured error/timing hypothesis.

## Execution

- [x] Record current connection/pose and camera view. Back up existing scenes.
- [x] Build a repeatable preflighted multi-pose profile with simultaneous and single-axis movement, reversals and stationary holds. Save baseline trace and summarize per-axis coverage/RMS/peak/settled error.
- [x] Investigate remaining tracking error and control timing. Make only an evidence-supported change with regression tests, or retain the better existing controller.
- [x] Repeat matched physical motion, verify sustained multi-axis motion and Stop/re-enable. Retain actual evidence and failures.
- [x] Review any controller change, run focused tests, document measured limits, push main and leave streaming off with torque preserved.

## Design and execution ledger

- Initial connection healthy and stopped, torque on; all 14 scenes backed up. Camera 0 shows only part of the arm/workspace, so it cannot establish independent absolute-angle accuracy.
- Baseline profile: 11 collision-checked poses and a 48-second multi-axis wave section; 246.9 seconds total. Joint extremes are deliberately inside verified model/raw limits.
- Prior recorded same-path motion shows a velocity-correlated error equivalent to 197–388 ms delay (linear error/velocity fit, not a measured network delay). Steady error is already small.
- Ruling: test a filtered velocity feedforward term of 0.12 seconds, with a 0.10-second filter, inside existing total correction/speed/acceleration bounds — it targets reversal lag without changing feedback gains or calibration — reject it if matched hardware trials regress materially. Increasing loop frequency or motor EEPROM gains is deferred because it changes additional variables without evidence yet.
- New independent first-order loaded servo regression failed at 0.007886 rad RMS for 0.22-second lag; after bounded feedforward, both 0.10/0.22-second plants and existing tracking/connection/driver tests pass (59 tests). Running backend remains baseline until the current hardware trial ends.

- Baseline physical run passed: 3,656 samples / 246.9 seconds, 11 poses plus independent waves. Four temperature confirmations, no motion fault. All six final settled errors below 0.17°. Baseline moving-wave RMS [0.944, 0.638, 0.606, 0.540, 0.977, 0.541]°.
- Deployment preserved 14 scenes; calibration remains confirmed, connection resumed with motion disabled before explicit commissioning.
- Independent final review: no Critical/Important findings; tracking tests independently 10/10. Minor deferred: direct assertions for reference_velocity reset/stale state would improve future regression coverage; current reset code is correct and existing output-bound tests pass. Operational review exclusions are addressed by recorded hardware trials/session/torque/remote checks; absolute geometric accuracy remains explicitly unverified.

- Feedforward commissioning passed: 944 samples / 64 seconds. On the identical 48-second wave section, RMS improved on every axis to [0.599, 0.561, 0.491, 0.457, 0.549, 0.409]°; final stationary errors remain below 0.17°. Now repeating the complete 11-pose profile before accepting the tuning.

- Full physical repeat passed: 3,579 samples / 245 seconds. Wave RMS improved on all axes to [0.557, 0.577, 0.513, 0.458, 0.540, 0.417]°. Some pose-transition errors increased slightly (elbow RMS 0.160→0.208°, lift peak 1.768→2.005°); retained tuning for the broad continuous-motion benefit, documented rather than concealed.
- Extra 54-second worst-pose dwell test passed; with 12-second hold the high-right elbow settled within 0.130°. Stop/re-enable/static sync test also passed with no encoder drift observed. Total physical verification about 625 seconds; no motion faults in this repeat series.
- Final focused verification: 63 backend tests passed in 6.44 seconds; fatal lint and diff checks passed. No frontend change. Existing session count 14, torque preserved, stream off. Full traces, chart and limitations saved in docs/verification/2026-10-25-broad-sync-repeat.md.
