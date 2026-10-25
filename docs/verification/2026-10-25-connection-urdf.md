# Robot connection: SO-101 URDF viewer

Replaced the schematic line/sphere arm with an actual URDF-loaded SO-101 model.
Inspected Hybridge-VLA's `static/index.html` URDF joint/mesh viewer as the local
reference. Exported the description from this project's existing SO-101 MJCF
instead of copying Hybridge-VLA's different base frame and gripper input scale.
The viewer includes 18 CAD mesh instances plus wrist-camera primitives.

The six calibrated encoder angles map by joint name, in radians. Unknown or
incomplete feedback shows a waiting state rather than an invented zero pose.
Model loading has an error/retry state; geometry and materials are released on
unmount. The viewport renders on changes, with orbit and zoom controls.
No physical command, calibration, collision, or replay behavior was changed.

Validation:
- Frontend: 26 tests passed; TypeScript and Vite production build passed.
- URDF regression: all link positions/orientations agree with MuJoCo at zero
  plus 25 deterministic varied joint poses, within 1e-10 absolute tolerance.
  Joint limits, referenced mesh files, and shared public asset link checked.
- Vite serves URDF successfully; production output contains URDF and STL assets.
- Fullscreen Chrome: opened Robot connection with actual six-motor encoder
  feedback and inspected full CAD model. Browser error log was empty.
- Used read-only serial connection; sent no motion or torque commands.
  Disconnected after inspection (enabled=false, sync=off).
- Screenshot: `docs/screenshots/robot-connection-urdf.png`.

Dependency installation note: existing lock metadata requests unavailable
`@jridgewell/resolve-uri@^3.2.0` and `camera-controls@^3.2.0`. Installed the new
`urdf-loader@0.12.6` through an isolated npm prefix and copied its exact registry
lock entry and package into the working install. Existing dependency resolutions
were preserved. Fresh installation of the whole pre-existing dependency tree
was not validated; this existing lock inconsistency remains separate work.
