# Local SO-101 and camera connections

The Setting Connection module uses one serialized serial owner shared by the UI and MCP. Select an existing Gym session, choose the port, and connect. Connection only reads motor identity and telemetry. It never calibrates motors, writes EEPROM, enables torque, or starts synchronization automatically.

## Hardware requirements and calibration

The driver expects Feetech STS3215 model 777, protocol 0, 1 Mbps, motor IDs 1–6 in this order: `shoulder_pan`, `shoulder_lift`, `elbow_flex`, `wrist_flex`, `wrist_roll`, `gripper`. Serial use checks both macOS cu/tty aliases, obtains a process lock, and requests exclusive serial access. Do not run another motor application against the same device.

Before motion, supply and explicitly confirm six joint mappings: `zero_raw`, `direction` (+1 or −1), `raw_min`, `raw_max`, and `radians_per_tick` (default 2π/4096). These values must come from a verified physical calibration; a current encoder reading is **not** automatically the zero angle. The mapping is `radians = (raw − zero_raw) × direction × radians_per_tick`. Confirmed settings bind to the serial path, USB identity, and verified six-motor model inventory. Reconnection always starts with motion disabled. A saved calibration alone never enables motion.

Physical motion also requires a valid Gym session, raw and simulation joint bounds, a collision-safe measured pose and commanded path, fresh telemetry, acceptable motor voltage/temperature, and a live controller heartbeat. The simulator can guard the configured scene only; it cannot sense obstacles missing from that scene.

Enable first stages the current measured position as the hold goal, sets a conservative RAM goal velocity of at most 0.3 radians/second under the supplied mapping, and then enables torque. Joint jogs are limited to ±0.05 radians and rate limited. `gym_to_real` requires initial agreement within 0.15 radians, rejects subsequent target jumps greater than 0.3 radians, ramps from the previous command to cross servo deadband, limits each streamed step, and stops on tracking error above 0.15 radians. `real_to_gym` writes measured pose into the selected Gym session and sends no physical motor commands. Stop the motion mode before starting this read-only mode.

An active controller must renew its lease through `/heartbeat` every second; expiry at three seconds stops streaming. Stop and disconnect attempt to hold fresh measured position if this service enabled motion, then preserve existing torque. **They do not release torque.** If communication fails, a hold cannot be confirmed: new commands stop, the fault remains visible, and motor torque may remain on. There is no automatic recovery or automatic re-enable. No torque-release or EEPROM endpoint is exposed.

## API

All endpoints live under `/api/connection` and inherit the application's localhost access guard. Request models reject unknown fields, invalid bounds and nonfinite numbers. Blocking device work runs off the application event loop. `create_router(service=None)` resolves `request.app.state.connection`, and `ConnectionService.shutdown()` closes resources during application shutdown.

| Method/path | Body or output |
| --- | --- |
| GET `/ports` | `{ports:[{port,description,serial_number,vid,pid}],error?}` |
| GET `/status` | Connection, owner, identity, calibration state, measured telemetry and age, target, fault, lease |
| GET `/settings` | Calibration and camera assignments |
| POST `/connect` | `{port,session_id}`; reads identities and telemetry |
| POST `/disconnect`, `/align`, `/enable`, `/stop`, `/heartbeat` | `{session_id}` |
| PUT `/calibration` | `{session_id,identity,confirmed:true,joints:[{name,zero_raw,direction,raw_min,raw_max,radians_per_tick}]}` |
| POST `/jog` | `{session_id,joint:0..5,delta_rad:-0.05..0.05}` |
| POST `/sync` | `{session_id,mode:"off"|"real_to_gym"|"gym_to_real"}` |
| POST `/cameras/scan` | `{max_index:0..7}`; default 4; inclusive scan |
| PUT `/cameras/assignments` | `{back:int|null,front:int|null,wrist:int|null}`; unique indices |
| GET `/cameras/{index}/frame` | Local JPEG snapshot; `Cache-Control: no-store` |

Motion/calibration ownership conflicts return HTTP 409, schema/argument failures 422, and device availability failures 503 where applicable. Responses include measured `telemetry[].position_rad` only when calibration matches; `target_rad` remains separate from measurement.

## Cameras and settings

Camera frames stay local. Each preview is a refreshed JPEG snapshot, not a continuous video stream. Camera operations use exclusive, killable subprocesses with a four-second capture deadline. A scan reports unavailable, permission-denied, or timed-out devices individually; a stalled index does not block the application event loop indefinitely. The default five-index scan can take about twenty seconds. Camera labels represent local numeric indices and may need reassignment if the OS changes device enumeration.

Settings are atomic JSON at `$SO101_SETTINGS_DIR/connection.json`, default `~/.config/so101-studio/connection.json`, outside portable scenes. They contain calibration and camera assignments only. No active motion, serial connection, or synchronization state is restored at startup.

## Verification on 2026-10-25

All six STS3215 motors now verify successfully. A device-specific mapping was installed from the verified existing LeRobot calibration using the upstream `new_calib` midpoint convention; gripper closed position maps to hinge zero. No EEPROM calibration was changed. The application preserves fractional midpoint zeros.

Bounded physical tests passed for real-to-Gym and outward/return Gym-to-real movement on all six joints. The complete movement test sampled feedback ages up to 63.2 ms and final target errors up to 3.36° (loaded elbow). Encoder-to-Gym mirroring differed by no more than one tick across the sampled runs. This does not establish independent absolute link-angle or millimeter accuracy. Stop and a three-second controller lease expiry were verified with torque preserved. See the [physical test report](verification/2026-10-25-physical-sync.md) for evidence and limitations.

Camera 0 produced an overhead arm image; camera 1 was dark. Built-in and virtual sources were also enumerated. A successful capture alone does not establish a useful workspace view. No camera role was assigned by guessing an index.

To send Gym motion to the connected arm, stop existing sync, press **Match Gym to real arm**, then **Enable at current pose**, and select **Gym → Real arm**. Start with small changes; loading an unrelated example can exceed the guarded pose-jump limit. To mirror measured angles without commands, select **Real arm → Gym** while motion is disabled. Calibration persists locally; connection and active movement do not auto-resume after restart.

The browser renews its lease only while the document is visible. Hiding/leaving the browser sends a best-effort Stop & hold; if that request cannot arrive, the lease expires. Switching between the application's Gym and Connection tabs keeps explicit synchronization available. Reloading never adopts an existing owner automatically: select the existing owner session explicitly, or disconnect it.

Protocol references: [official LeRobot SO-101 setup and calibration](https://huggingface.co/docs/lerobot/so101), [Feetech register and model tables](https://github.com/huggingface/lerobot/blob/main/src/lerobot/motors/feetech/tables.py). The installed Feetech SDK signatures were inspected before the read-only probe.
