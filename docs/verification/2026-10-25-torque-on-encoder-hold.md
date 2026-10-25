# Torque On: measured encoder hold

Observed the reported error with shoulder encoder 850 and calibration minimum
858: 8 ticks (0.703125 degrees) below the saved range. The user confirmed the
trigger was Torque On. That action incorrectly reused conversion/validation
for a new motion target while trying to seed the servo's current hold pose.

Changed only the explicit Torque On hold to use freshly read raw encoder values.
It never clamps to a boundary or changes calibration. Added strict integer
0–4095 telemetry validation before any write, explicit joint/raw bounds in
motion rejection messages, and live `limit_violations` status/UI diagnostics.
Home, slider targets and other movement still use existing limit/path checks.

Validation:
- 124 backend tests passed across connection, driver, manual controls/guards,
  tracking, linked execution, real-run gate and episode report suites.
- New regressions prove out-of-calibration holding writes exactly the measured
  encoder vector before torque, does not start motion or alter calibration,
  and subsequent Home is rejected without writes. Invalid negative, >4095,
  NaN and fractional encoder readings are rejected before torque/goal writes.
- Frontend 26 tests passed; TypeScript/Vite production build passed.
- Preserved all five scenes across backend restart.
- Clicked Torque On in fullscreen Chrome against the physical arm. All six
  motors reported torque on. Before/goal/after raw encoders were identical:
  `[2078, 850, 3106, 2926, 1039, 2060]`. Observed angle difference: 0 degrees
  on each encoder at the post-action sample (not a claim of zero mechanical
  displacement below encoder resolution).
- Motion remains inactive: enabled=false, sync=off, manual_target=null.
  Left the user's arm connected with torque holding, not automatically released.
- Shoulder and elbow still exceed the combined motion limits; visible warnings
  and disabled Home/sliders reflect this. No trajectory was run from this pose.

Screenshot: `docs/screenshots/torque-on-encoder-hold.png`.
