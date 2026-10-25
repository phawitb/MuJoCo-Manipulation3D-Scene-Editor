# Connected Studio verification — 2026-10-25

Final backend verification covered every backend test file in four independent processes after all safety fixes: 23 + 14 + 57 + 88 = **182 passed**, no failures. The groups split cup manipulation, planning/whole-arm safety, contact/examples/extraction, and the remaining API/device/import tests. This includes real MuJoCo trajectory execution; physical serial movement uses fake-driver tests only.

Frontend verification: **21 unit tests passed**, **41 Playwright browser tests passed**, production TypeScript/Vite build passed. Blender browser tests additionally verified actual composited mesh pixels for extrusion, revolve, and return from a hidden tab. Connection regressions reproduced and then fixed hidden-browser heartbeat renewal and recovering an existing owner after page reload. Formatting/static checks and git whitespace checks passed.

A separate temporary frontend copy with the Gym and Connection folders physically removed built successfully, demonstrating the Blender tab can ship independently. No edits to Blender were needed.

Live update preserved **14 user sessions**. The post-restart check compared joint positions, object positions/orientations, camera settings, table settings and reset joints to the local backup. Sessions were restored paused and plans invalidated for recalculation.

Initial hardware inspection did not receive a motor acknowledgement. After the user confirmed motor power and cabling, a repeated handshake verified all six STS3215 motors at 1 Mbps. The live Connection service then returned 30 consecutive healthy samples with telemetry age below 100 ms, voltage 12.2–12.4 V and temperature 32–35 °C. Torque remained off; no motor goal, torque or EEPROM writes were sent.

The existing local LeRobot follower calibration matches the six motors' stored homing offsets and encoder limits, including decoded negative offsets. This confirms the calibration belongs to the connected bus, but does not independently verify the zero angles and rotation directions against this MuJoCo model. Motion and realtime mirroring remain disabled pending that physical alignment check. See [Connection guide](../CONNECTION.md).

Repeated camera inspection received frames at indices 0–4: index 0 sees the robot, index 1 is dark, index 2 is a working webcam, index 3 shows an Iriun startup placeholder, and index 4 shows an OBS placeholder. Receiving a JPEG is not proof that the camera is aimed at the robot or assigned to a front/back/wrist role. No roles were inferred automatically.

The first frame of webcam 2 was nearly black while a later frame was properly exposed. The capture worker now drains 700 ms of startup frames before encoding, retaining the existing four-second process deadline. Two regression cases first failed for stale black output and undetected capture loss, then passed after the fix; the connection and capture suites passed **26 tests**. Real cameras 0 and 2 returned exposed images in 2.37 and 2.56 seconds in the direct service check. The live server was updated with a fresh backup and verified restoration of all 14 scenes, and the read-only motor connection was restored.

Image reconstruction is local silhouette extrusion or solid revolve with entered dimensions, not recovery of unseen surfaces or texture. Gym uses convex collision for imported meshes. See [Blender guide](../BLENDER.md).

## Follow-up: powered hardware and reconnected cameras

After the user explicitly cleared the work area and authorized physical trials, the VLA-Benchmark connection code was inspected as a reference. It uses the same follower identity and calibration, LeRobot degree normalization for the five arm joints, and a 0–100 range for the gripper. Those values cannot be passed directly to the Gym's radians interface. Its torque-preserving handoff also stages measured goals before enabling torque.

Replugging USB had left the previous serial handle stale. An explicit disconnect/reconnect restored fresh readings from all six motors. Camera 0 sees the arm, camera 1 remains dark even after startup frames, camera 2 is the computer webcam, and cameras 3/4 are virtual-camera placeholders. The camera 0 image still does not establish every joint's physical zero and sign.

Physical commissioning used bounded encoder-relative commands, independently of Gym trajectories: staged the measured pose, set RAM goal velocity to 50 ticks/s, enabled torque, monitored all six encoders and health, and moved only shoulder pan and gripper. The initial 12-tick pan command produced no measured movement. A 28-tick pan command produced 14 ticks of movement and triggered the probe's precision stop; the fault handler held the freshly measured pose. A separate 28-tick gripper opening produced 15 ticks, and a return command ended 14 ticks above its initial value. These measurements establish physical actuation, **not** precise target tracking. The tested sub-degree accuracy criterion failed. Stored dead zones are 10 ticks in both directions; proportional gain is 16, consistent with the existing LeRobot setup. No gains, calibration or EEPROM settings were altered to force the test to pass.

The elbow encoder reads 3120 while the existing calibrated maximum is 3109, so no elbow motion or whole-arm Gym path was attempted. Automatic synchronization remains off; no confirmed MuJoCo angle mapping was installed. Final read-only telemetry is healthy, and motor torque remains enabled to preserve the pose. Final pan/gripper readings are 2070/2052 versus initial 2056/2038; the probe did not return exactly to its starting pose. Detailed commanded/measured values are in [hardware-probe.json](2026-10-25-hardware-probe.json).
