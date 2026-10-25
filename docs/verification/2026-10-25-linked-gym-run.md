# Connected Gym run and horizontal cameras — 2026-10-25

## Outcome

The camera layout change passed UI checks. Connected Run now starts physical following automatically, with simulation paced by measured feedback, but **the requested three complete real-arm task executions did not pass**. Do not treat this feature as validated for unattended manipulation.

## Browser and camera checks

Used the actual Chrome window in fullscreen landscape (window 1512 × 949; page viewport 1512 × 893), with the existing Gym session. Scan showed indices 0, 1 and 2 side by side with corner badges. Verify showed only saved Back 0 and Wrist 1, also side by side; Front remains unassigned. All six motors responded. Wrist capture was mostly dark, so successful capture is not proof of a usable workspace view. Camera photos remain local and are not committed.

## UI task attempts with connected hardware

| Example | Actions | Result |
| --- | --- | --- |
| 01 · Spoon into cup | Connect robot → Load example → Calculate path → Run simulation | Rehearsal succeeded. Real motors followed Gym into Descend. The physical geometry guard stopped both at ~3.76 simulated seconds, reporting moving jaw/table overlap 0.14 mm. No physical grasp completed. |
| 02 · Cup on the left | Select → Load example → Calculate path | Rejected before motion: the current measured pose mapped to gripper/table overlap 5.02 mm. Run was not permitted. |
| 05 · Spoon into bowl | Select → Load example → Calculate path | Same measured-start collision; no motor movement. |

The larger overlap after stopping is consistent with the measured arm settling under load after the fault hold discarded compensation. It is an encoder-to-model result, not a direct observation of physical penetration. Table/base alignment, grasp clearance, load compensation and fault-hold behavior require further validation before claiming a successful tabletop transfer. Existing guards were retained; no calibration, hard limits or collision tolerances were relaxed to force a pass.

Earlier attempts exposed unbounded compensation near the wrist joint stop, then a sub-microradian MuJoCo soft-stop residual. The controller now brakes within existing hardware/model bounds with anti-windup; only the already permitted MuJoCo residual (≤0.002 rad) is projected to a hard-bounded requested target. Physical measured-pose limits remain strict.

The [recorded final attempt](data/2026-10-25-linked-example01.csv) contains read-only polling samples (~5 Hz, separate status/scene requests). During enabled following, joint RMS errors were 0.101°, 0.576°, 0.370°, 0.625°, 0.109°, 0.061° (pan, lift, elbow, wrist flex, wrist roll, gripper). Largest sampled error was 1.73°. These numbers describe the partial approach only, not a complete task or absolute geometric accuracy. Physical cup/spoon objects were not placed in the workspace; virtual-object success would not have established a real object transfer.

## Implementation and review

- Calculate reads a fresh starting pose without movement. Run validates plan and start agreement, then enables linked execution.
- The physical worker advances up to ten 1 ms simulation steps per feedback update; it waits when measured lag exceeds 0.035 rad. The standalone simulation clock cannot concurrently advance that session.
- Normal completion requires five final feedback frames within 0.015 rad; this branch is covered with a fake driver, not yet demonstrated by a full real-arm task.
- Pause, stop, fault, scene replacement and switching to passive physics stop linked hardware motion. Failed task settling cannot stream an open-gripper command to the real arm.
- A fresh independent static review found the passive-physics transition and failed-policy settling gaps. Both were reproduced in regression tests and fixed.
- Header and visible fault banner distinguish following, waiting, paused, completed and stopped states.

Final hardware state: connected, synchronization off, motion streaming disabled, torque preserved. Current measured pose is blocked by the configured table guard; no automatic recovery movement is performed.

## Software verification

- Full backend suite: **244 passed** in 490.21 seconds, including all advertised simulated task examples at multiple stepping batch sizes.
- After the final execution-status reset fix, connection/coordinator/tracking regression subset: **69 passed**, including the newly added regression (14 coordinator cases).
- Frontend: **21 passed**; TypeScript and production build passed. Existing large Three.js bundle warning remains.
- Changed Python modules passed selected runtime-error lint checks; whitespace checks passed.

Software test success does not override the incomplete physical results above.
