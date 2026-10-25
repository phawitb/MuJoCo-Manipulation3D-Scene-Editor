# Robot base lift: 22.2 mm

User reported that the physical gripper touches the tabletop in the current
pose while the model appears below it. Read encoder radians were
`[-0.0866699145, -1.6712720684, 1.6942817802, 1.2977477466, -1.5454856438, -0.0030679616]`.
With the existing base Z=0.754 m and tabletop Z=0.750 m, the lowest jaw CAD
vertex was at 0.727804916 m. A world-Z lift of 0.0222 m puts it at 0.750004916 m.
This is a one-pose model alignment using the user's contact observation;
it does not claim independently measured physical calibration accuracy.

Added the scene field, collision-enabled support, Inspector control, browser
preference, reset/example retention and matching connection URDF mount/table
rendering. Set 22.2 mm in the live owner's scene through the Inspector and saw
"Base lift saved". The API confirmed the value and physical pedestal geometry.
Five existing sessions were preserved during backend restart. No motion or
torque command was sent as part of this change; encoder inspection used the
read-only connection API. Physical sync remains off.

Checks:
- 36 tests passed for pedestal, saved reset pose, whole-arm safety and manual
  controls (before the extra mount-packet assertion was added).
- 82 tests passed for pedestal (all four tests), connection, manual controls,
  sessions and real-run gating. These suites overlap the previous run.
- Frontend: 27 tests passed; TypeScript/Vite production build passed.
- All seven link origins moved upward by exactly the lift; joint coordinates
  stayed identical. Lowest visible jaw is within 0.1 mm of the table in the
  supplied pose. Table penetration over 1 mm is absent after correction.
- Reset and all 13 example loads retain the lift; scene round trip retains it.
- Isolated simulation examples 01, 02 and 03 each calculated a verified path
  and completed successfully with the raised base and collision rules enabled.
  See `2026-10-25-raised-base-examples.json`. These were simulated runs, not
  physical robot task runs.
- Fullscreen Chrome shows the URDF on its support with the gripper at tabletop
  level: `docs/screenshots/robot-base-lift.png`.

Existing elbow/gripper limit warnings remain independent of mounting height.
No joint limit or collision check was relaxed.
