# Whole-arm safety and Example 11 round trip

The old controller could finish Example 11 with shoulder/camera contact. It then exported actuator **targets** as the pose. Changing the task reloaded those unreachable targets, producing the reported 6.8 mm overlap. The corrected controller exports measured angles and changes task instructions without resetting position, velocity, actuator state or simulation time.

## Motion checks

- IK candidates and interpolated joint segments are checked against all enabled robot self/environment/object collision geometry. Segment samples are at most 0.04 rad apart; this is a prefilter, not continuous collision detection.
- The entire candidate task is rehearsed with the same physics/controller as execution, checking contacts after every 1 ms step through release, retreat and verification. Execution repeats these checks and stops at the checked terminal state, including when updates are batched.
- Self-penetration above 0.02 mm, other arm penetration above 0.1 mm, or fingertip/source and held-object penetration above 1.5 mm stops the policy. These are compliant-contact tolerances, not clearance goals. Kinematic candidates reject body overlaps; intentional fingertip grasp contacts remain enabled.
- Joint limits and finite joint states are checked. The five arm joints must be within 0.03 rad of each commanded waypoint before the next phase; the closing finger is excluded from this tracking test because the grasped object intentionally stops it.
- A failed grasp or safety check opens the fingers, holds measured arm angles and allows gravity to settle released objects. No attachment, object pose writes or collision-mask changes are used during motion.
- Plate delivery centers the utensil body to avoid folding the wrist back into the shoulder. The planner also rehearses alternative handle contact points for thin utensils when the first pinch slips.

## Validation

[Per-step audit data](whole-arm-audit.json) records all eleven examples, each independently rehearsed and executed for 17,907 physics steps. All succeeded; no robot self-penetration was observed. Maximum non-grasp arm penetration was 0.052 mm, and final arm target error stayed below 0.0005 rad. Measured opposing jaw contact and actual destination support remain required for success.

Regression tests additionally cover Example 11 cup→plate→cup from folded and saved downward-wrist poses; between-waypoint collisions with clear endpoints; injected terminal self-contact; contact occurring only in leftover terminal batch steps; blocked and unreachable targets; table/object collisions; joint limits; stalled waypoint tracking; gravity after contact loss; measured save/load and state-preserving task changes. The complete example suite runs at batches of 1, 17 and 33 steps.

These checks operate on the collision shapes, masses, friction, actuator forces and compliant contacts in this model. IKEA geometry and physical properties include documented estimates, and servo/contact dynamics have not been calibrated against a physical robot. A verified path is evidence for the captured simulated scene, not a hardware safety certificate or a guarantee for every arrangement. Scene setup edits remain paused configuration changes, not physically simulated jogging.
