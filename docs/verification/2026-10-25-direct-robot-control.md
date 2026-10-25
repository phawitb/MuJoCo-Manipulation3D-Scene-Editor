# Direct robot control and motor handoff — 25 October 2026

## Delivered

- Restarted Studio while preserving five paused Gym sessions. Restarted the inactive VLA-Benchmark process that had leaked a follower serial handle; its source/configuration files were not changed.
- Gym Robot connection now has six degree sliders, measured/target values, an encoder-driven simplified SO-101 model, Home using the saved scene reset pose, Move robot to Gym pose, Torque On/Off, and Stop & hold.
- Explicit Connect & match Gym chains read-only connection and validated manual movement. HTTP/MCP connect alone stays read-only.
- One in-flight slider request; unsent values collapse to the latest target. Server control epochs invalidate stale target/Home/Match/Torque-on requests after Stop or reconnection. Stop/Off do not wait for an outstanding slider response.
- Manual motion holds with feedback. Path checks remain active; world stepping cancels manual control. Manual profile is isolated from normal Gym synchronization. Multi-axis reference interpolation follows the checked joint-space line rather than letting shorter axes finish early and cut a different path.
- New typed HTTP/MCP commands and documentation in CONNECTION.md. No EEPROM or calibration writes were made for this change.

## Confirmed cause of slow VLA mimic

Studio previously wrote Goal_Velocity RAM register 46 = 195 ticks/s on all six servos and left it there after disconnect. The installed LeRobot implementation used by VLA-Benchmark configures PID/acceleration but does not reset Goal_Velocity. All six registers were read back as 195 before repair.

The repair staged fresh measured hold goals and restored all six speed registers to 0. A new lifecycle saves the exact original value before any Studio override, restores it on disconnect/shutdown, and verifies readback. It releases the port and reports errors even if restoration fails. The final read-only physical probe again verified `[0, 0, 0, 0, 0, 0]`, all six motors still torque-on, and no serial owner after the probe closed.

Zero in this register means uncapped servo speed, not stop. References: [Waveshare ST3215](https://www.waveshare.com/wiki/ST3215_Servo), [LeRobot motors API](https://huggingface.co/docs/lerobot/main/en/api/motors). Installed source inspected: `SO101-V2/lerobot/src/lerobot/robots/so_follower/so_follower.py` and `motors/feetech/feetech.py`. VLA's Test Mimic invokes `lerobot-teleoperate`; its browser polling interval is only a status/log poll, not the motor loop.

This establishes removal of the persistent speed cap. A human-driven leader/follower mimic latency benchmark was not performed, so no external mimic latency claim is made. VLA-Benchmark's pre-existing modified config.yaml and untracked augment_configs were preserved.

## Physical UI tests

Chrome fullscreen, 1512 × 893 viewport, existing Gym session. Tests used real serial commands and measured encoder feedback, not fabricated positions.

1. Connect & match Gym moved the arm to the saved Gym pose.
2. All six sliders exercised through the web UI: approximately +2° base, +2° shoulder, −2° elbow, +2° wrist pitch, +5° wrist rotation, +5° gripper. Repeated keyboard slider events tested continuous replacement without a backlog.
3. Home returned from this nearby pose. Across 392 status samples over 20 seconds: no fault; status-request latency median 3.92 ms / p95 9.68 ms, feedback age median 26.31 ms / p95 57.68 ms. These are local status and feedback-age metrics, not end-to-end motor latency.
4. Final nearby-Home errors (encoder − desired): base −0.220°, shoulder −0.233°, elbow −0.031°, wrist pitch −0.014°, wrist rotation −0.044°, gripper +1.143°. The closed-jaw residual remains visible; it is not hidden by changing calibration.
5. Stop & hold and Disconnect exercised through the UI. Torque-release behavior was tested with the fake bus; the extended real arm was not intentionally released under gravity.

## Physical episode and remaining blocker

Example 01 calculation and Run simulation completed successfully at 17.91 simulated seconds. Run Realrobot was then pressed through the web UI. The real arm moved for 34.52 seconds (509 measured samples) until the existing guard stopped at 3.748 simulated seconds in descent: table / moving jaw overlap 0.46 mm. This episode is **stopped, not completed**.

| Joint | RMS error | Peak absolute error |
|---|---:|---:|
| Base | 0.195° | 0.887° |
| Shoulder | 0.392° | 1.296° |
| Elbow | 0.333° | 0.738° |
| Wrist pitch | 0.353° | 1.312° |
| Wrist rotation | 0.191° | 0.457° |
| Gripper | 0.142° | 0.417° |

Long Home-return attempts exposed gravity-hold disturbance and a different intermediate path from independent axis ramps. Fixes preserve an existing validated servo hold, use a 0.24 rad/s reference with bounded correction, and synchronize the reference along its validated line. Regression tests cover these cases. A guarded shoulder departure succeeded once, but subsequent attempts stopped; after gravity settling the current measured pose exceeded the 8 mm modeled-overlap limit. The final Home request was rejected before motion. The last interpolation fix has unit coverage but has **not** completed a live long-return retest from this blocked pose.

Final state: Studio and VLA servers running; physical streaming off; serial port free; torque retained; speed registers restored to zero. Physical repositioning/geometry verification is needed before further full-task testing. No collision rule was disabled, and no blind full-episode replay was implemented. Encoder agreement alone does not independently establish real geometry, table alignment, or successful physical grasping.

## Automated checks and review

- Backend focused regression: **152 passed** (API, connection/driver, manual, tracking, linked execution, real-run gate, episode report, MCP, modules, sessions, whole-arm safety, retreat).
- Frontend: **24 passed**, production TypeScript/Vite build passed. Existing bundle-size advisory remains.
- Fresh independent static review; important findings fixed: stale presets after Stop, manual-rate leakage into sync, stepping simulated objects during manual control, stop blocked by pending slider response, and stale feedback after path validation. Additional physical-test fixes have regression coverage for preserving servo holds and collinear joint references.

Rulings: keep measured feedback/collision/fault guards despite the request for unchecked replay; preserve external VLA files and repair the actual shared RAM cap; do not claim 100% matching or a completed physical episode. No review minors were deferred.
