# Persistent imported library and imported-object grasp repair

User explicitly requested continuing without repeat questions. Work in the existing feature checkout and preserve live scenes/datasets.

## Approved scope and approach
- Persist successfully placed imported meshes/packages in a local server-side asset library. Show an Imported category alongside built-ins, searchable and reusable by + or drag in later sessions/restarts. Deduplicate content, keep full portable physics/visual data, create unique scene object IDs on each insertion. Import preview alone must not save; UI must report storage failures. Existing imported objects in live sessions should be migrated once so LinkTrack already imported is reusable. Avoid adding test fixtures to the user's real library.
- Reproduce reported planning failure using a copy of the exact live scene (LinkTrack source → KALAS cup). Diagnose contact and reachability; prefer declared package grasp sites over bounding-box center when appropriate, preserve real contact-only and collision checks. No success label unless full rehearsal succeeds. Do not reposition user objects without reason or weaken validation to force success.

## Execution
- [x] Independent library task: backend storage/API and frontend shelf/reuse, persistence and dedup tests, browser flow.
- [x] Planning task: reproduce current failure, inspect measured grasp and delivery constraints, failing regression then targeted fix and full physical rehearsal.
- [x] Review integration, run relevant tests/build and browser checks, preserve paused sessions before restarting, verify the user's exact scene.

Ruling: apply dispatching-parallel-agents skill to these independent domains; library implementation owns storage/API/frontend while main agent owns planning/policy. User approval is already provided; no further design gate.

## Findings and rulings
- Exact reproduction failed with the original orientation error. Inspecting the solver showed that the low-transfer trial reached Place and failed while planning Retreat at 8 cm. Lower withdrawal alone did not fix high-transfer candidates. A 3.5 cm transfer clearance plus shorter checked withdrawal succeeds through physical release/settling.
- Ruling: keep the existing physically secure grasp; declared-site handling was an initial hypothesis, not the observed cause. Add two low-clearance configurations only for imported mesh/package objects, and try bounded 8/5/3.5 cm withdrawal candidates without relaxing collision, pose or physical verification. Existing cup withdrawal remains unchanged.
- Regression fixture retains the user's exact initial poses, inertial and collision data with primitive visual proxies; no personal calibration metadata or dense imported visual meshes are needed for the test. Initial test failed as reported; fixed test rehearses and executes successfully, leaves the live simulation untouched and checks no attachment and contact penetration limits.

- Final integration: 43 backend library/import/API tests, 30 planner/contact/safety tests, 16 frontend unit tests and 3 isolated browser tests passed; build succeeded. Fresh reviewer found no material issues. Actual LinkTrack migrated to persistent shelf, and the live current scene's isolated rehearsal returned verified/ready (9 attempts, 17.907 s) without moving live objects. Keep changes on existing local feature branch; no merge/push requested.
