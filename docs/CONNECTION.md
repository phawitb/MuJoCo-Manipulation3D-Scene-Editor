# Local SO-101 and camera connections

Setting Connection saves the port and camera assignments. Connect the arm from Gym; one serialized serial owner is shared by the UI and MCP. The HTTP/MCP connect operation only reads identity and telemetry. The Gym **Connect robot** button is also read-only. Movement requires an explicit Tool position, joint control, or Run Realrobot command. Opening the controls panel alone never moves the arm. Neither operation changes calibration or EEPROM.

## Hardware requirements and calibration

The driver expects Feetech STS3215 model 777, protocol 0, 1 Mbps, motor IDs 1–6 in this order: `shoulder_pan`, `shoulder_lift`, `elbow_flex`, `wrist_flex`, `wrist_roll`, `gripper`. Serial use checks both macOS cu/tty aliases, obtains a process lock, and requests exclusive serial access. Do not run another motor application against the same device.

Before motion, supply and explicitly confirm six joint mappings: `zero_raw`, `direction` (+1 or −1), `raw_min`, `raw_max`, and `radians_per_tick` (default 2π/4096). These values must come from a verified physical calibration; a current encoder reading is **not** automatically the zero angle. The mapping is `radians = (raw − zero_raw) × direction × radians_per_tick`. Confirmed settings bind to the serial path, USB identity, and verified six-motor model inventory. Reconnection always starts with motion disabled. A saved calibration alone never enables motion.

Physical motion also requires a valid Gym session, raw and simulation joint bounds, a collision-safe measured pose and commanded path, fresh telemetry, acceptable motor voltage/temperature, and a live controller heartbeat. The simulator can guard the configured scene only; it cannot sense obstacles missing from that scene.

Enable first stages the current measured position, including a validated load compensation retained from a normal stop in the same connection, as the hold goal, sets a conservative RAM goal velocity of at most 0.3 radians/second under the supplied mapping, and then enables torque. Joint jogs are limited to ±0.05 radians and rate limited. `gym_to_real` requires initial agreement within 0.15 radians, rejects subsequent target jumps greater than 0.3 radians, uses bounded proportional/integral feedback to reduce load and deadband error, limits command speed to 0.3 rad/s and acceleration to 1.2 rad/s², and stops on tracking error above 0.15 radians. `real_to_gym` writes measured pose into the selected Gym session and sends no physical motor commands. Stop the motion mode before starting this read-only mode.

An active controller must renew its lease through `/heartbeat` every second; expiry at three seconds stops streaming. Cartesian control and range recovery stop at the freshly measured raw encoder positions, clear compensation, and preserve existing torque. Legacy joint synchronization can retain validated learned load compensation in memory across a normal stop/start; faults, failed holds, calibration changes and reconnection clear it. Stale collision validation falls back to a fresh uncompensated hold. Compensation is never saved as calibration. **They do not release torque.** If communication fails, a hold cannot be confirmed: new commands stop, the fault remains visible, and motor torque may remain on. There is no automatic recovery or automatic re-enable. Torque release is available only through the explicit **Torque Off** control; support the arm before releasing it. No EEPROM endpoint is exposed.

## Separate simulation and physical execution

Connect a calibrated arm in Gym, load an example, and press **Calculate path**, then **Run simulation**. Neither action starts physical motion. A successful simulation saves its initial task for the separate **Run Realrobot** button. That button reads measured physical angles and rehearses the saved task again with full collision checks before enabling physical following. An invalid initial pose, failed rehearsal, stale controller heartbeat or changed scene prevents motor commands. Editing the scene invalidates approval; simulate again. Starting a physical attempt consumes its approval, including when that attempt later stops. Manual mapping, alignment, enable and sync controls are locked during preparation; Stop remains available.

Physical execution uses Cartesian waypoints from the successful rehearsal: world XYZ of `gripperframe`, xyzw orientation, and jaw opening in radians. Each target is solved by bounded IK from the latest real encoder state. Gym’s joints and clock are not replayed or advanced. The five positioning axes cannot satisfy arbitrary six-dimensional poses: unreachable orientation/position requests are rejected, not silently relaxed.

The executor checks every link and swept joint segment, including table, objects and predicted carried-object geometry. Carried geometry follows the estimated real tool transform for collision checks; this does not attach the physical object or prove a grasp. The collision world is an explicit rehearsal estimate, not a camera observation. Pause, Stop, faults, heartbeat expiry and scene replacement cancel execution.

Between endpoints, predicted object poses advance with measured tool/orientation/jaw progress, starting from the last checked geometry rather than jumping to the next planned world. Release is sampled every 10 ms and simulation waits for the jaw to open before retreating (bounded timeout). A simulated negative closing preload becomes a physical closed-jaw goal of zero, not a command outside the calibrated range. IK reserves half an encoder tick inside bounds, and collision checks validate the exact quantized commands sent to the servos.

Endpoint arrival requires distance ≤3 mm, rotation error ≤3°, and jaw error ≤1.5°. IK reserves accuracy by rejecting solutions beyond 1 mm/1°. Final arrival requires six consecutive measured frames. Intermediate targets preserve the bounded actuator ramp. A completed report means tool goals were reached according to encoder forward kinematics; physical grasp and placement remain unverified.

The same behavior applies to HTTP/WebSocket/MCP scene commands: `run` is always simulation-only, `real_run` requires the owning calibrated connection and a successful simulation. Renew `/heartbeat` throughout preparation and execution; leaving the controlling browser cancels preparation and stops streaming. Manual jogging and the explicit realtime direction controls remain available in Robot connection.

## API

All endpoints live under `/api/connection` and inherit the application's localhost access guard. Request models reject unknown fields, invalid bounds and nonfinite numbers. Blocking device work runs off the application event loop. `create_router(service=None)` resolves `request.app.state.connection`, and `ConnectionService.shutdown()` closes resources during application shutdown.

| Method/path | Body or output |
| --- | --- |
| GET `/ports` | `{ports:[{port,description,serial_number,vid,pid}],error?}` |
| GET `/status` | Connection, owner, identity, calibration state, measured telemetry and age, target, fault, lease, `gym_execution` phase/message/session |
| GET `/settings` | Calibration and camera assignments |
| POST `/connect` | `{port,session_id}`; reads identities and telemetry |
| POST `/disconnect`, `/align`, `/enable`, `/stop`, `/heartbeat` | `{session_id}` |
| PUT `/calibration` | `{session_id,identity,confirmed:true,joints:[{name,zero_raw,direction,raw_min,raw_max,radians_per_tick}]}` |
| POST `/jog` | `{session_id,joint:0..5,delta_rad:-0.05..0.05}` |
| POST `/sync` | `{session_id,mode:"off"|"real_to_gym"|"gym_to_real"}` |
| POST `/cameras/scan` | `{max_index:0..7}`; default 4; inclusive scan |
| PUT `/cameras/assignments` | `{back:int|null,front:int|null,wrist:int|null}`; unique indices |
| GET `/cameras/{index}/frame` | Local JPEG snapshot; `Cache-Control: no-store` |

Motion/calibration ownership conflicts return HTTP 409, schema/argument failures 422, and device availability failures 503 where applicable. Responses include measured `telemetry[].position_rad` only when calibration matches; `target_rad` remains the compensated motor command, separate from measurement. `desired_rad` is the requested Gym pose; `tracking_error_rad` is measured minus desired; `compensation_rad` is the bounded learned load bias. The UI shows Gym target, per-joint difference and largest angle error while Gym → Real arm is active. MCP `connection_status` returns the same fields.

## Feedback and tracking limits

The outer loop slews its internal reference at 0.24 rad/s and applies proportional gain 0.8 and integral gain 1.2. A 0.12-second velocity feedforward term, filtered with a 0.10-second time constant, reduces direction-change lag. It differentiates the limited reference, not encoder readings, and remains inside the same correction and output bounds. Integral correction changes by at most 0.04 rad/s and is capped at ±0.1 rad; total correction is capped at ±0.12 rad. Integration pauses inside a dead zone of max(0.003 rad, two encoder ticks) and has anti-windup under command-rate and joint-limit saturation. Output braking reserves stopping distance before the intersection of calibrated raw and model limits, including encoder rounding. MuJoCo compliant-stop residuals within the existing 0.002 rad physics tolerance are projected onto the hard model limit for requested motor targets; larger violations stop execution, and measured physical pose checks stay strict. Cycles older than 0.2 seconds and feedback older than 0.2 seconds after streamed collision validation stop synchronization. These software bounds do not establish an independent physical acceleration measurement.

Each motor returns one checked RAM 40–69 frame for position, torque, voltage and temperature. The driver checks raw packet length and motor identity as well as SDK checksum/device status. Physical tests observed isolated temperature jumps; their underlying cause remains unconfirmed. A first reading ≥50°C triggers at most four additional reads with no intervening goal writes. Acceptance requires three readings within 3°C below 65°C; any two readings ≥65°C, no consensus within five reads, or a communication/device/voltage error faults. This does not raise the 65°C cutoff or automatically resume after a fault. `temperature_rechecks` counts confirmation events and is visible in the UI; `last_temperature_check` exposes the motor and raw readings through HTTP/MCP for diagnosis.

## Cameras and settings

Camera frames stay local. Scan and Verify show frames side by side with index badges and horizontal scrolling on smaller screens. Verify displays only assigned camera roles. Each preview is a refreshed JPEG snapshot, not a continuous video stream. Camera operations use exclusive, killable subprocesses with a four-second capture deadline. A scan reports unavailable, permission-denied, or timed-out devices individually; a stalled index does not block the application event loop indefinitely. The default five-index scan can take about twenty seconds. Camera labels represent local numeric indices and may need reassignment if the OS changes device enumeration.

Settings are atomic JSON at `$SO101_SETTINGS_DIR/connection.json`, default `~/.config/so101-studio/connection.json`, outside portable scenes. They contain the robot port, calibration and camera assignments. No active motion, serial connection, or synchronization state is restored at startup.

## Verification on 2026-10-25

All six STS3215 motors now verify successfully. A device-specific mapping was installed from the verified existing LeRobot calibration using the upstream `new_calib` midpoint convention; gripper closed position maps to hinge zero. No EEPROM calibration was changed. The application preserves fractional midpoint zeros.

Bounded physical tests passed for real-to-Gym and outward/return Gym-to-real movement on all six joints. The complete movement test sampled feedback ages up to 63.2 ms and final target errors up to 3.36° (loaded elbow). Encoder-to-Gym mirroring differed by no more than one tick across the sampled runs. This does not establish independent absolute link-angle or millimeter accuracy. Stop and a three-second controller lease expiry were verified with torque preserved. See the [physical test report](verification/2026-10-25-physical-sync.md) for evidence and limitations.

Subsequent continuous-motion testing reduced elbow RMS tracking error from 2.87° to 0.58° on the same trajectory; final stationary error was 0.03°. A separate 117-second six-axis test passed with final elbow error 0.10°. These are encoder-based results for tested poses, not a guarantee for every load or an independent geometric calibration. See the [continuous-sync report](verification/2026-10-25-continuous-sync.md).

A broader repeat subsequently covered 11 poses plus simultaneous multi-axis motion. Filtered velocity feedforward reduced continuous elbow RMS from 0.606° to 0.513° and wrist-roll RMS from 0.977° to 0.540°, with small regressions in some pose-transition measurements. See the [broad repeat report](verification/2026-10-25-broad-sync-repeat.md) for exact tested angular ranges, retained tradeoffs, recorded traces and extended settling checks.

Camera 0 produced an overhead arm image; camera 1 was dark. Built-in and virtual sources were also enumerated. A successful capture alone does not establish a useful workspace view. No camera role was assigned by guessing an index.

For manual Gym motion outside a task, stop existing sync, press **Match Gym to real arm**, then **Enable at current pose**, and select **Gym → Real arm**. Loading an example stops manual streaming; complete Calculate path and Run simulation, then use Run Realrobot for a tool-space task. To mirror measured angles without commands, select **Real arm → Gym** while motion is disabled. Calibration persists locally; connection and active movement do not auto-resume after restart.

The browser renews its lease only while the document is visible. Hiding/leaving the browser sends a best-effort Stop & hold; if that request cannot arrive, the lease expires. Switching between the application's Gym and Connection tabs keeps explicit synchronization available. Reloading preserves the session URL but never resumes motion automatically.

Protocol references: [official LeRobot SO-101 setup and calibration](https://huggingface.co/docs/lerobot/so101), [Feetech register and model tables](https://github.com/huggingface/lerobot/blob/main/src/lerobot/motors/feetech/tables.py). The installed Feetech SDK signatures were inspected before the read-only probe.

### Shallow table departure

`POST /retreat` with `session_id` (MCP `lift_robot_clear_of_table`) only supports an empty scene and an existing jaw/table overlap up to 8 mm. It prefers a small elbow lift and checks monotonic separation of every table contact, hard joint limits, other collisions, measured progress and the controller lease. It does not disable collision geometry or change calibration. Unchanged joints retain their held goals; a stalled joint is not driven harder. This is a recovery operation, not permission to run tasks from intersecting poses.

### Tool controls and episode report

**Tool position** accepts world coordinates in millimetres and preserves the current tool orientation and jaw opening. **Use current position** fills the target fields. Joint sliders remain available for diagnostics. Status shows the encoder-estimated XYZ and target distance/orientation/jaw errors; it never labels the estimate camera-verified.

`POST /api/connection/tool-target` (MCP `robot_tool_target`) accepts `session_id`, `control_epoch`, `position` (three world metres), optional normalized `quaternion` (xyzw), and optional `opening_rad`. Omitted orientation/opening use the current measured values. Requires torque on, paused Gym, valid calibration and a heartbeat. Stop invalidates delayed requests.

`connection_status.tool` exposes `measured`, `target`, `error`, `frame=world`, `tool_frame=gripperframe`, `measurement_source=encoder_fk`, and `object_verified=false`. `gym_execution.report` gives final endpoint errors, samples, elapsed time, peak/RMS distance to the active target, and measurement age. It explicitly identifies `environment_source=simulation_rehearsal`; there is no independent camera-based pose or physical object-success claim. No report is invented before feedback exists.

## Direct controls and application handoff

Robot connection includes six sliders in degrees, measured and target angles, a live SO-101 URDF model driven only by encoder feedback, **Home position**, **Move robot to Gym pose**, **Torque On**, **Torque Off**, and **Stop & hold**. Home uses the selected scene’s saved `robot.reset_joints`. Manual targets replace the previous target; mouse events do not build a movement queue. A bounded outer feedback loop continues holding the target until Stop, a scene change, disconnect, or lease expiry. “Holding target” requires settled feedback within 1° for arm joints and 1.5° for the gripper; measured residuals stay visible. This is not a claim of perfect geometric alignment.

Manual movement has separate 0.24 rad/s reference, 0.8 rad/s output, and 2.4 rad/s² acceleration bounds. Normal Gym synchronization retains its original slower profile. Every proposed path and measured update checks joint limits and collisions. To leave a shallow pre-existing overlap (up to 8 mm), manual motion permits unchanged or separating contacts only, without allowing deeper or new collisions. Physical task execution still requires its original collision-free preflight. Scene stepping also stops manual control before moving simulated objects.

Read `/api/connection/status` for `control_epoch`, `manual_target`, `manual_phase`, `control_limits`, and `robot_preview`. New motion commands must carry the current epoch; Stop, torque release, disconnect, and server restart invalidate delayed requests. All joint targets use radians at the API boundary:

| POST endpoint | Body beyond `session_id` | MCP tool |
|---|---|---|
| `/api/connection/target` | `control_epoch`, `joints` (six radians) | `robot_joint_target` |
| `/api/connection/home` | `control_epoch` | `robot_home` |
| `/api/connection/match-gym` | `control_epoch` | `match_robot_to_gym` |
| `/api/connection/torque` | `control_epoch`, `enabled` | `robot_torque` |

Torque On stages a fresh measured hold before enabling. Torque Off immediately cancels command producers and verifies all six torque states; it never automatically resumes the previous motion. Stop/Off requests do not wait for an outstanding slider HTTP response. Continue heartbeats at least once a second while manually driving or holding a target.

Studio now saves each servo’s original RAM Goal_Velocity before overriding it, and restores those exact values with readback on disconnect/shutdown. Restoration first stages fresh measured positions so removing the cap cannot chase an old goal. If restoration fails, the error is returned and the port is released; no EEPROM is written. This prevents Studio’s former 195 ticks/s cap from carrying into VLA-Benchmark’s LeRobot mimic mode. The legacy cap on the attached arm was explicitly repaired to 0 and verified on all six motors. **0 means uncapped servo speed, not stopped.** See [verification and measurements](verification/2026-10-25-direct-robot-control.md).

### Torque On outside the motion range

Torque On seeds all six servo goal registers with the freshly measured raw
encoder values before enabling torque. It is a stationary hold, not a request
to move to Home, Gym, or the nearest calibration boundary. Raw feedback must
still be finite integer ticks in 0–4095, with valid motor identity, voltage,
temperature, owner, calibration, and command epoch.

An arm positioned by hand with torque off can lie outside the saved motion
range. Torque On may hold that exact position, but motion continues to require
calibrated encoder limits, model joint limits, and whole-arm collision checks.
No limits are expanded and no encoder or target is silently clamped.

`GET /api/connection/status` (also MCP `connection_status`) includes
`limit_violations`: an array of `{name, angle_rad, min_rad, max_rad, raw,
raw_min, raw_max}` for measured angles outside the combined calibration/Gym
range. The UI shows these values and disables direct motion controls until the
measured pose is back within range. Support the arm before releasing torque
and repositioning it. Review joint mapping if the stored calibration is wrong.

### Base lift and tabletop alignment

Select **SO-101 arm → Base transform → Base lift (mm)** to add a solid support
under the simulated robot. The value raises the full kinematic chain in world Z;
joint zeros and encoder calibration are unchanged. The support participates in
MuJoCo collision checks. Robot connection renders the same support and tabletop
height through `robot_mount` in connection status.

The portable scene/API field is `robot.pedestal_height`, in metres (0–0.2).
Set it with the existing `robot` command, e.g.
`{"type":"robot","patch":{"pedestal_height":0.0222}}` via REST/MCP.
Changes invalidate the calculated path. Reset and examples retain the lift;
scene files store it and the browser remembers it for new workspaces. Old scene
files with no field retain a zero lift; opening a file uses that file's value.

For this arm, 22.2 mm was estimated from the reported tabletop-touching pose and
its encoder readings. It aligns that pose's lowest jaw CAD vertex with the
simulated tabletop. This is a mounting correction based on one reported contact
pose, not independent measurement of the physical mount or calibration of all
joint angles. The CAD base foot's existing 1.6 mm clearance is filled by the
support, so its rendered thickness is 23.8 mm with the default base transform.

### Bounded range recovery and current hardware limitation

**Return inside limits** / `recover_robot_limits` handles up to two joints ≤0.5° outside the combined range. It reads actual servo deadbands, verifies the whole arm at half-encoder-tick intervals, moves one joint at a time by at most 1.5°, then requires a fresh stationary hold before the next. It never changes calibration or EEPROM. A stall cancels and holds the exact measured raw encoder position.

The 2026-10-25 Cartesian update has **not** passed physical task execution: bounded probes of the attached elbow produced at most one encoder tick and could not recover the initial range violation. Software tests and simulated-bus task execution are separate evidence. See the [Cartesian verification report](verification/2026-10-25-cartesian-real-control.md) for measured results; earlier synchronization reports are historical and do not establish current hardware readiness.
