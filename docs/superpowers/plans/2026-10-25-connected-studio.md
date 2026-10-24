# Connected studio implementation plan

Spec: ../specs/2026-10-25-connected-studio.md

## Global constraints

Work on main as explicitly requested. Do not move v1. No automatic torque enable, EEPROM writes or uncalibrated movement. Preserve user sessions. Explicit Gym session IDs for hardware ownership and generated-object insertion. Local images and device settings never leave this computer. UI/API share validation.

## Tasks

1. Connection module: backend/modules/connection (config, serial driver, camera service, router); TDD fake-device safety, atomic settings and camera failures. Actual motor inventory read-only after dependencies install. Interface prefix /api/connection; router factory with Registry getter.
2. Blender module: backend/modules/blender (schema, reconstruction, router), frontend/src/modules/blender; TDD image bounds and solid geometry, browser preview/export/import. Prefix /api/blender; image POST returns portable SceneObject plus GLB base64/metadata. No remote inference claim.
3. App shell and Gym module: move existing editor files into frontend/src/modules/gym; shared types/utilities remain where needed; independent feature registry, persistent tab state. Connection UI covers port/config/calibration, telemetry, jog/stop, explicit sync, camera scan/assign/preview. Frontend build and navigation tests.
4. Integration: backend module registration and lifecycle, MCP tools, docs, locked dependencies; isolated API and browser tests, real read-only hardware checks, preserve then restart live service, broad regressions and fresh final review.

## Review focus

Physical commands from stale or wrong session; initial enable snapping to old goals; calibration identity/zero mismatch; disconnect and concurrent sync; browser tab hiding while driving; camera hangs and shutdown; image decompression abuse; enabled-module omission; live-user session preservation.

## Progress

Planning: port /dev/cu.usbmodem5B141122411 discovered; OS reports five cameras. No calibration JSON or Blender app found. Use independent subsystem work per dispatching-parallel-agents; parent integrates shell/APIs after contracts are available.

Implementation: all three modules integrated, with shared session core and optional feature registration. Core Gym frontend files moved without behavioral changes except disabling hidden-tab shortcuts/rendering. Module tests cover reconstruction, connection safety, deployment selection, and browser workflows.

Review: fresh whole-change review identified hidden-document heartbeat renewal and existing-owner selection after reload. Both reproduced with failing browser tests, corrected, then passed with the navigation and camera-assignment tests. Internal Gym navigation continues explicit sync; hiding the browser stops it.

Hardware verification: USB adapter discovered; motor1 handshake failed at1Mbps. No motor writes or movement. Camera0–3 timed out; camera4 returned an OBS placeholder. Physical motion therefore remains unverified and disabled until actual motor response and verified mapping are supplied. This limitation is surfaced in the UI/docs, not replaced by a simulated success.

Live migration: backed up and restored14 sessions on2026-10-25; verified object/joint poses, cameras, table settings and reset pose. All restored paused, with plans invalidated for recalculation. Backup files stay local in ignored scene-backups/.

Packaging check: a clean temporary frontend copy with Gym and Connection folders physically removed still built successfully as a Blender-only application. No source edits to the remaining module were needed.

Final validation:182 backend tests,41 browser tests,21 frontend unit tests passed; production build, standalone Blender-only build, static checks and whitespace checks passed. Evidence and hardware limitations: ../../verification/2026-10-25-connected-studio.md.
