# Direct robot control and clean motor handoff

User delegates implementation choices. Preserve main and v1. Restart server first (done, five sessions preserved). Do not read or overwrite VLA-Benchmark config.yaml or its unrelated changes.

Cause under investigation: Studio writes Goal_Velocity=195 ticks/s on enable and leaves it in servo RAM. Installed LeRobot sets acceleration and PID but not Goal_Velocity on configure, so a persistent speed cap can slow another app. Capture/restore speed registers around Studio ownership; explicitly repair legacy speed caps using fresh measured hold before restoring normal zero-speed-register behavior. Never write EEPROM or alter calibration for this repair.

Robot connection: compact two-column panel, live model from measured MuJoCo kinematics and six degree sliders with measured/target indicators. Coalesce input to newest target; avoid a queued backlog. Home uses saved Gym reset_joints. Torque on holds fresh measured pose; Torque off explicitly releases (warn inline to support arm). Connect & match Gym is an explicit motion action, with a validated interpolation rather than teleporting goals. Maintain independent read-only connect for APIs. Manual movement preserves hard limits, whole-arm collision, stale-feedback, tracking and heartbeat stops; do not implement blind replay from a known invalid pose. Keep separate simulated/real episode execution and end-episode reports.

Use current React/Three/MuJoCo/FastAPI modules, new manual-control helper to avoid growing service.py further. Test fake motor register lifecycle, target replacement and cancellation, torque state, preview purity, and actual fullscreen web controls with bounded physical moves only after fresh pose validation. Final independent static review.
