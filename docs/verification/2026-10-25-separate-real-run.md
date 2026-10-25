# Separate simulation and physical execution — 25 October 2026

## Result

The web application now separates **Run simulation** and **Run Realrobot**. Simulation does not enable physical following. A successful simulation saves its initial scene; a real attempt rehearses that scene from fresh encoder measurements, with the existing collision checks, before any motion enable. Edits invalidate approval and starting a physical attempt consumes it.

**Physical acceptance remains blocked.** Three simulation examples passed, but three successful real-arm examples have not been demonstrated. No claim of absolute geometric calibration or 100% real/sim agreement is made.

## Actual fullscreen web tests

Chrome fullscreen landscape, 1512 × 893 viewport, existing Gym session:

| Example | UI sequence | Result |
| --- | --- | --- |
| 01 · Spoon into cup | Load → Calculate path → Run simulation | Complete; object released and settled |
| 02 · Cup on the left | Load → Calculate path → Run simulation | Complete; object released and settled |
| 05 · Spoon into bowl | Load → Calculate path → Run simulation | Complete; object released and settled |
| 01, repeated | Successful simulation → Run Realrobot | Rejected before physical enable: table / gripper overlap 4.02 mm at measured pose |

Physical control remained disabled with sync off throughout these simulation-only runs. Example 01's servo goal registers were also compared before and after; they were unchanged. Real-run rejection did not bypass the collision gate.

## Bounded physical recovery attempt

A shallow table departure was checked offline for hard joint limits, all robot collision geometry and monotonic separation of existing jaw/table contacts. An empty scene is required. The runtime monitors measured progress, controller heartbeat and scene identity. It prefers elbow flexion and does not add more effort to an already lagging shoulder. Collision masks, table height, tolerances and calibration zeros were unchanged.

The shoulder attempt had stopped at tracking error. A subsequent elbow departure was clicked in the web UI; encoder position remained unchanged and its tracking limit stopped further streaming. The motors acknowledged updated target registers, but that is not evidence of movement.

Fresh read-only diagnostics after the attempts:

| Motor | Measured raw | Held target raw | Difference |
| --- | ---: | ---: | ---: |
| Shoulder lift | 2295 | 2243 | 52 ticks / 4.57° |
| Elbow flex | 1956 | 1929 | 27 ticks / 2.37° |

These are **command-following errors**, not measured calibration offsets. Servo status bytes were zero, measured speed zero, supply 12.2 V. Shoulder temperature rose from 39°C earlier in the investigation to 52°C at final verification. The cause of the non-following motion remains unresolved; software evidence cannot distinguish a physical obstruction, load problem or calibration geometry mismatch. No higher torque, wider collision tolerance or additional forced movement was used. The user requested proceeding without relying on camera imagery, so no new visual pose alignment claim is made.

[Post-retreat feedback samples](data/2026-10-25-table-retreat.csv) record the stopped state; they are not a complete motion trace.

## Software verification

- Broad backend suite: **254 passed**, 504.73 s.
- After final safety fixes, related connection/execution/gating/recovery tests: **89 passed**.
- Frontend: **21 passed**, production build successful; existing large bundle warning remains.
- Regression coverage includes simulation-only behavior with hardware connected, approval invalidation and consumption, replan from measured start, stop/edit/lease cancellation, inability to revive expired preparation, and rejection of manual control changes during preparation.
- Recovery loop tests cover successful departure, tracking failure, lease expiry, scene replacement and preserved servo goals/torque.
- One fresh static reviewer reproduced a preparation lease-renewal race. The regression failed before the fix and passed afterward; review concluded no remaining concrete blocking findings.

Final operating state: server running, robot connected, physical streaming disabled, synchronization off, motor torque retained. Existing user scenes were backed up and restored across server restarts. Simulation approvals are deliberately not restored after restart.

Follow-up adds end-of-episode angle reports and preserves connection/read-only and live safety guards. Subsequent focused tests also cover correct RMS/peak/last error aggregation, no fabricated measurements and stopped-vs-completed linked outcomes.

Final follow-up validation: **93 related backend tests passed**, **21 frontend tests passed**, and production build succeeded. Updated live server exposes `gym_execution.report`; reconnect was read-only, streaming off, torque retained. Latest shoulder temperature was 55°C. Physical completion is still blocked.
