# Cartesian real-arm control

Approved direction: the user requested execution of the endpoint-first design, independent real trajectories, whole-arm collision checks, repair of existing motor problems, and physical testing without further decisions.

## Goal and architecture
A real command names a tool-center position, task-relevant orientation and jaw opening. Real joint targets are solved from measured encoders, not copied from simultaneous simulated joint positions. MuJoCo remains the kinematic/collision oracle and simulation rehearsal engine. A serial controller remains the sole hardware owner.

The tool frame is `gripperframe`; the UI names it explicitly. Contact-specific grasp offsets remain policy-owned. The five positioning axes constrain reachable orientations; unreachable targets must fail before motion. Manual joint sliders remain diagnostics.

## Observability
Encoder forward kinematics is an estimate, not independent physical measurement. Status, UI and reports must label it `encoder_fk`. Calibrated external pose observations may later correct absolute position; absent physical camera calibration/markers, never assert camera verification or successful physical object manipulation. Endpoint arrival alone is not evidence of grasp or release.

## Constraints
- Preserve all whole-arm/table/object collision checks, joint/raw limits, measured telemetry guards, Stop and ownership/heartbeat semantics.
- No motor EEPROM writes and no modifications to VLA-Benchmark or Hybridge-VLA.
- Preserve existing scenes across runtime restart, leave v1 unchanged, develop on main as previously requested.
- Connect is read-only; explicit movement commands operate hardware.
- Physical tests start with small free-space endpoint goals and measured holds; do not certify object-task success from simulated contacts.
- Reuse Python/MuJoCo/SciPy/FastAPI and React/Three; no ROS migration.

## Alternatives and chosen approach
Joint replay is unsuitable as the primary success criterion. Vision-only control cannot operate reliably without calibrated, visible observations. Chosen: Cartesian execution with encoder feedback now, explicit sensor provenance and interfaces for calibrated vision; physical vision validation remains pending until measurable references exist.

## Completion evidence
Tests distinguish endpoint arrival from joint equality, enforce whole-arm collision/path limits and cancellation, and reject stale/unreachable goals. UI/API/MCP expose consistent endpoint status. Hardware evidence records encoder-estimated endpoint error separately from physical task verification. Existing motor nonresponse must be diagnosed and reported honestly.
