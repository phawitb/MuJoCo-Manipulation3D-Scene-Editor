# Verification — contact-only physics v3.1

2026-10-24 · MuJoCo 3.17.0 · macOS Apple Silicon · Python 3.12.

- **90 backend tests passed** in 161.57 seconds. This includes each of the ten original arrangements executed with 1-, 17- and 33-step observation batches, custom yaw angles, a changed robot base, unreachable/blocked scenes, legacy spoon variations, scene import/export, HTTP/WebSocket and real MCP integration.
- **13 frontend unit tests passed**, strict TypeScript and production build passed. The existing large 3D bundle warning remains (~1.24 MB before gzip).
- **22 browser scenarios passed** in 1.8 minutes. Example06 specifically verifies measured opposing forces in the UI/API, contact-only mode and released completion. Existing placement, arrows, camera, import, persistence and reconnect flows also pass.
- **125 automated tests total**, plus an independent every-1-ms physical audit of all ten examples. Every case succeeded with 6,602/6,602 secure carrying samples, no active attachment constraint and 0 ms unsupported carrying time.
- Native close-up video and frames were inspected for examples01,06,08 (cup, bowl, plate). See [detailed root cause, measurements, source documentation and video](PHYSICS-AUDIT.md).

## Regression evidence

The original three regressions failed against assisted physics: invisible constraint during carrying, opening the gripper without the object falling, and proximity without contact accepted as a grasp. They now pass. A separate regression catches geometric containment without destination support (observed RED then GREEN). A loss-of-contact test also proves that failure allows passive falling instead of freezing mid-air; reverting that behavior made the test fail before restoration passed. Existing workspace-boundary tests caught the distinction between normal grasp failure and a numerical/workspace guard; guards still pause immediately.

The previous fixed-step-duration tests were updated to retain their original simulated time budgets after the integration step changed from 2 ms to 1 ms. Success/contact thresholds were strengthened, not relaxed. Original example positions, source meshes, object masses, friction and arm actuator force limits were retained. Gripper effort is reduced from the source model's 2.94 Nm limit to 0.5 Nm.

## Decisions and limitations

- The user's realism requirement supersedes assisted-mode behavior. There is no weld option. Previously successful assisted scenes may correctly fail physical grasp validation.
- Work stays on a dedicated branch in the existing checkout; coupled controller/session/UI changes are implemented inline, with one independent final review. This preserves the local app path; it provides less filesystem isolation than a separate checkout.
- The planner tries bounded physical candidates and can reject solvable scenes. It does not guarantee arbitrary placement success.
- A dropped grasp leaves passive physics running for 1.5 seconds; explicit Pause/Stop and numerical guards still freeze the scene. Stop queues a physical jaw opening; physics or Step must advance it.
- Contacts remain a soft rigid-body approximation; peak measured jaw overlap is about 0.5–0.7 mm. KALAS dimensions/material properties and hardware calibration remain the limits documented in [KALAS-SOURCES.md](KALAS-SOURCES.md).
- Local open scenes were backed up in ignored scene-backups/ folders and restored across the service update. Their positions/cameras remain; physics time and old plans reset. No private backups are pushed.

The earlier assisted-mode report is retained as [historical evidence](VERIFICATION-V3-ASSISTED.md), not current physical-grasp validation.

## Independent review and fixes

One independent whole-branch review found no critical issues and independently passed 41 focused physical tests. It found one important issue: measured grip telemetry stayed cached after cancellation or failure while passive physics moved the object. Both cases were reproduced with failing regressions. Packets now measure the completed physics state regardless of controller status; both regressions and all seven contact regressions pass. The minor video-command quoting issue was also corrected. No review findings were deferred. After these fixes, the complete 90-test backend suite passed again and the example06 browser scenario passed again (23.0 seconds). The first browser rerun encountered the 16-session capacity limit; closing a backed-up empty test session resolved the environment issue without product changes.

The review validated the removal of attachment constraints, selected-source/opposing-jaw contact checks, passive falling and physical destination support. It declined to certify hardware calibration, universal arbitrary-scene success, imported concave meshes or public hosting. These remain the documented scope limits, not claims of this fix. Stop intentionally pauses physics and queues jaw opening for the next Step/Physics command.

## Library layout and native drag correction

2026-10-24: At 1512 × 800 the asset grid compressed four rows to approximately 29 px each while their artwork/labels needed 163 px. Content-sized grid rows now retain complete cards and overflow scrolls within the library. An explicit transparent native drag image suppresses the browser's card/control snapshot; the existing tabletop object preview remains.

Three new browser regressions first failed and then passed: complete card contents at 1512 × 800 and 1280 × 720, and a real native mouse drag that supplies no visible drag image and still places the selected object. The complete browser run passed 22 cases and exposed three pre-existing synthetic-event/render-readiness races; those tests now wait for canvas layout, tolerate an initially absent canvas, use a real mouse drop or repeat dragover as native dragging does. All three then passed together (6.4 s), covering all 25 browser scenarios across these runs. Frontend unit tests (13), TypeScript and production build passed; the existing bundle-size warning remains. Backend physics was unchanged.

Browser checks used isolated ports 5174/8766 because the user's live server was at its session limit. Live scenes were not reset. [Inspected library screenshot](screenshots/library-complete.png).
