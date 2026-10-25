# Physical SO-101 calibration and realtime synchronization

User authorizes autonomous calibration and bounded physical tests. Execute on main; preserve v1. Keep EEPROM calibration unchanged unless a measured correction specifically requires it. Existing physical clears and all six encoder identities have been confirmed.

1. Establish the upstream new_calib zero convention and the installed LeRobot normalization. Back up current app settings and motor calibration. Compare actual pose with the model; derive a mapping with explicit provenance and measured constraints, not guessed zeros or inflated limits.
2. Reproduce calibration/schema and synchronization defects using backend tests. Update connection mapping/validation and Gym bridge only where evidence requires it. Preserve command-versus-measured separation, collision checking, velocity limits and controller lease.
3. Validate candidate angles in an isolated local MuJoCo model. Commission short motions one joint at a time away from stops; retain exact encoder traces and camera images. Stop on unexpected displacement, telemetry faults or interference. Do not sweep mechanical stops automatically.
4. Install the verified mapping, test real-to-Gym, then align the Gym to measured pose and test Gym-to-real with small bounded targets. Verify transmitted targets, independently read encoders, Gym pose, update rate, stop and heartbeat expiry. Preserve user scenes across any backend update.
5. Improve the connection UI and MCP only as needed for practical reuse; persist the calibrated mapping without automatically enabling physical movement after restart. Run focused backend/frontend checks, document achieved accuracy and limitations, commit and push main.

Review focus: half-tick zeros, gripper percent versus hinge radians, inverted directions, measured readings just outside command limits, deadband accumulation in streamed goals, stale serial handles and measured-pose broadcast.
