# Cup rim grasp implementation plan

> Execute inline using executing-plans and TDD. User authorizes design decisions, changes, physical tests and existing GitHub delivery.

**Goal:** Pick an upright cup by its rim, place it on a plate, and carry a cup containing a physically supported spoon after a preceding spoon insertion.

**Architecture:** Extend the existing contact-only controller with rim grasp candidates derived from the cup profile and measured pose. Keep whole-arm collision checks, actuator forces and real friction. Rehearse alternative rim angles; carry upright from measured grasp geometry. Verify any contained utensils remain supported in the cup. Add examples and regression/browser tests using existing pick/place UI.

**Spec:** User request in this conversation, 2026-10-25. Destination confirmed by user as plate; rim-grasp work applies independently.

**Constraints:** No welds, teleportation, disabled collisions or weakened success checks. Preserve current user sessions. Candidate failure must remain explicit. Existing arbitrary-scene limits still apply.

- [x] Reproduce cup-width rejection, add failing rim-grasp/lift tests.
- [x] Implement near-rim pinch, candidate angles and upright transfer, validate empty-cup contact, release and support.
- [x] Validate contained spoon after actual spoon→cup execution; detect spills and blocked rim candidates without attaching contents.
- [x] Add empty/loaded cup examples and tests across poses/scales/batch sizes; retain all previous examples.
- [x] Run physics/UI regressions, fresh final code review, preserve/update live app and push.

Review focus: loaded-container collisions and spills, tilted/oversized cups, grasp force vs proximity, static/dynamic obstacles, same-state rehearsal/execution and schema/API compatibility.

Final validation: backend 133 passed; browser 35 passed; frontend unit 14 passed; production build passed. Exact example-12 spoon insertion followed by cup transport also passed independently. Fresh final review found two safety gaps (protruding cargo collision and handle-first cargo detection); both have failing-before/passing-after regression tests. Contact audits and screenshot are in docs/physics and docs/screenshots. Existing 10 live scenes were backed up and restored paused, with object-pose roundoff below 5e-16, original cameras/table/reset poses/time preserved.

Decision: consecutive tasks use existing Pick/Place selection; examples 12/13 cover empty and loaded transport without introducing a queue UI. Users select cup→plate after spoon→cup finishes.
