# Connected Studio verification — 2026-10-25

Final backend verification covered every backend test file in four independent processes after all safety fixes: 23 + 14 + 57 + 88 = **182 passed**, no failures. The groups split cup manipulation, planning/whole-arm safety, contact/examples/extraction, and the remaining API/device/import tests. This includes real MuJoCo trajectory execution; physical serial movement uses fake-driver tests only.

Frontend verification: **21 unit tests passed**, **41 Playwright browser tests passed**, production TypeScript/Vite build passed. Blender browser tests additionally verified actual composited mesh pixels for extrusion, revolve, and return from a hidden tab. Connection regressions reproduced and then fixed hidden-browser heartbeat renewal and recovering an existing owner after page reload. Formatting/static checks and git whitespace checks passed.

A separate temporary frontend copy with the Gym and Connection folders physically removed built successfully, demonstrating the Blender tab can ship independently. No edits to Blender were needed.

Live update preserved **14 user sessions**. The post-restart check compared joint positions, object positions/orientations, camera settings, table settings and reset joints to the local backup. Sessions were restored paused and plans invalidated for recalculation.

Hardware inspection is not a successful physical motion test. The USB serial adapter was present, but motor 1 did not acknowledge the SO-101 handshake; no motor writes occurred. No verified encoder-to-simulation mapping was available. Camera 0–3 timed out; camera 4 returned an OBS placeholder. Physical realtime operation remains unverified until those device/calibration prerequisites are met. See [Connection guide](../CONNECTION.md).

Image reconstruction is local silhouette extrusion or solid revolve with entered dimensions, not recovery of unseen surfaces or texture. Gym uses convex collision for imported meshes. See [Blender guide](../BLENDER.md).
