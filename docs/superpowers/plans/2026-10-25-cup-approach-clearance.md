# Cup approach clearance

User requests more opening margin so slight pose error does not prevent a cup rim grasp. Existing opening adds only 5 mm and leaves the fixed finger near the wall. Increase cup approach opening to wall thickness plus 20 mm, centre that clearance around the rim, then move to the measured pinch pose while closing. Preserve contact-only force limits, collision checks and other utensil grasps. Validate positive clearance on both fingers before closing, fixed planned paths under ±2 mm object-position disturbances, empty/loaded cup execution and the spoon→cup→plate sequence. Rehearsal requires 6 mm of actual jaw clearance (4 mm execution minimum plus 2 mm position reserve). Reject tighter candidates rather than silently accepting nominal success. User already authorizes autonomous implementation and delivery.

- [x] Reproduce narrow fixed-jaw clearance.
- [x] Widen and centre approach; close with a coordinated arm motion.
- [x] Validate measured clearance, perturbations and existing regressions.
- [x] Review, update live backend with scene backups, commit and push.

Evidence: initial fixed-jaw clearance 0.2846 mm failed the geometry regression. Widened side-rim pose measured 7.196/9.941 mm. An earlier feasible oblique candidate had only 2.686 mm, so physical clearance gating was added; jitter regressions exposed the need for an additional 2 mm planning reserve. Final: 11 clearance tests, 18 cup regressions and 2 browser executions passed. Fresh reviewer found no blockers in coordinated closing; subsequent clearance/reserve corrections were covered by failing-before/passing-after tests. Live scenes backed up and restored paused before update.
