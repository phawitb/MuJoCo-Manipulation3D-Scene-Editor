# Connection workflow cleanup

Approved scope: user delegates implementation and real-device verification, without further design questions. Work on main; preserve v1.

## Design
Setting Connection stores a serial port and camera roles. Scan returns images for every checked index in a vertical stack, with index badges; Verify is outside the cards and checks the robot without motion and only assigned camera views. Gym owns the connect, mapping, feedback, jog and realtime controls through an optional module contribution. Scene replacements stop physical streaming before changing the scene. The browser records its current session in the URL so refresh reuses it.

## Task 1: Device contracts and scene replacement guard
Write failing tests for saved ports, read-only verification (connected/disconnected/failure), selected-only camera snapshots, scan image payloads and scene replacement stopping the owning controller. Implement shared HTTP/MCP contracts and serial-before-session lock ordering. Verify focused pytest suite.

## Task 2: Settings and Gym controls
Extract existing robot controls into an optional Gym panel. Remove session selection and motion from Settings. Show scanned images without an extra click; align Scan with count input. Save configuration explicitly, clear stale verification when edited, and Verify only saved settings. Preserve heartbeat, stop and calibration guards. Remember session URL and clear scene selection state on load. Verify TypeScript build, existing tests and browser clicks.

## Task 3: End-to-end verification
Restart backend preserving current sessions. Click Scan/Verify, compare assigned indices, connect from Gym, check current measured pose, exercise bounded actual motion then stop and hold. Verify scene replacement and reload do not accumulate sessions. Capture UI evidence without committing private camera frames. Run one fresh independent review, fix important findings, document results, commit/push main.

## Review focus
Lease ownership across internal tab switches and browser hiding; stop accessibility during pending requests; optional connection module removal; setup changes vs saved verification; no torque/goals during Verify; no old scene accumulation; lock order during scene replacement.

## Completion record
- Device tests were first run RED (four missing-contract/image failures), then implemented GREEN.
- Tasks 1–3 completed inline. Focused final backend suite 78/78; frontend 21/21; production build passed. See docs/verification/2026-10-25-connection-workflow.md for commands' scope, live-device/browser evidence and limits.
- Final independent review: two important stale-setup findings, both reproduced RED and verified GREEN through actual browser interaction; no deferred findings. Refreshed setup invalidates in-flight verification generations as well as existing results.
- User's explicit autonomous main-branch instruction governed execution; no extra approval or isolated development branch was introduced.
