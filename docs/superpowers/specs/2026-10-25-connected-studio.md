# Connected Scene Studio

The existing editor becomes Gym. Add Setting Connection and Blender as independently registered frontend and backend modules. Retain existing Gym scenes and APIs. The user authorizes autonomous implementation, physical-device inspection and bounded trial movement, and work on main; v1 remains the frozen backup.

## Connection

Discover serial ports; connect read-only to six SO-101 Feetech motors at 1 Mbps, IDs 1–6. Report identity, encoder, voltage, temperature and torque; never write EEPROM or silently calibrate. Persist explicit per-joint encoder-zero, direction and limits with a confirmation state tied to the chosen port. Raw encoder readings are not calibrated simulation angles. Missing calibration must be visible and block motion.

Provide a calibration editor, bounded joint jog, explicit enable/stop, measured status and two explicit realtime modes: physical arm to Gym and Gym to arm. Exactly one session owns a hardware link. Reconnect/startup never auto-enables motion. Guard position limits, velocity, stale telemetry, tracking error, simulation collision and large initial pose differences; stop streaming on faults. Holding position must be distinct from releasing torque. All serial I/O serialized. Retain actual measured feedback separately from target.

Discover camera indices and preview frames; back/front/wrist assignments persist on disk. Failures and permission-denied/unavailable cameras reported honestly. Frames stay local. Avoid blocking application event loop on camera/device reads; bounded scans and exclusive camera ownership.

## Blender

Local image-to-mesh creation: upload PNG/JPEG, inspect image, choose silhouette extrusion (general objects) or revolve (front-on symmetric objects), set real dimensions and threshold/depth. Preview generated solid mesh, download GLB, add to an explicitly selected Gym session. Label this as an approximate reconstruction from the silhouette: a single picture cannot recover hidden surfaces or real dimensions. No external upload or paid service. Blender-compatible export works even without the Blender desktop application installed. Keep provider interfaces replaceable for future reconstruction engines.

## Architecture/API

Frontend tabs own folders under src/modules; shared shell and tab registry supports VITE_STUDIO_MODULES. Gym stays mounted across tab switches to preserve scene/session/view state. Backend feature folders own schemas, service, routes and tests. SO101_MODULES enables selected feature routes. Device settings are local atomic JSON outside portable scenes. MCP exposes typed settings, discovery, verification, motion/sync/stop, physical camera frames and reconstruction; all use the same backend logic as UI. Localhost access guards remain enforced.

## Acceptance

Regression-test Gym; fake-device tests cover every write guard and failure mode; real device verification starts read-only. Real small movement only after calibrated mapping is established, otherwise clearly report the unmet calibration requirement. Camera scan and preview verified on available hardware. Reconstruction tests assert valid watertight volume and dimensions, malformed-image bounds, downloads and Gym import. Browser tests cover navigation, persistence, workflow and error feedback. Build and broad existing tests pass. Preserve user sessions before restarting services.
