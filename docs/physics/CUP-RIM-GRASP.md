# Cup rim grasp validation

The cup's full diameter exceeded the jaw opening, so the previous controller rejected it. Cups now use a pinch near the rim: one finger inside, one outside, with opening determined by wall thickness. The pinch is inset 2 mm to clear the tapered inside wall. Six directions around the rim are rehearsed; an obstacle or contained utensil can make a candidate unusable.

The SO-101 has five arm axes. A position/pinch-axis IK objective allows the remaining orientation freedom during approach and lift. Delivery uses the measured cup-to-gripper transform and seeks an upright cup. Its 75 mm lift and 35 mm transfer/retreat clearances avoid unnecessary high poses beyond the arm's reach. Every candidate still undergoes complete dynamics rehearsal, including self-contact, wrist camera, table, other objects, torque limits, tracking and release. These are local candidate paths, not a complete motion planner: a failed search does not prove that no possible path exists.

There are no weld constraints, object-pose writes during execution, force increases or collision exclusions added for these tasks. Contents are observed, not attached. For spoons, handle, centre and bowl samples detect either end inside the cup; at least one must remain inside after lifting. Protruding contents are also checked against obstacles and the table. At completion, the spoon must also have real cup contact support and low velocity. Cup placement requires actual plate support, released jaw forces, an upright cup and its base footprint within the plate.

## Regression coverage

- Example 12: empty cup from `[-0.08,-0.07]` onto plate at `[-0.04,0.10]`.
- Example 13: same transport with a loose spoon in a measured resting pose.
- Both examples rehearsed and executed with batches of 1, 17 and 33 physics steps. Contacts are checked at every 1 ms step regardless of batch size.
- Continuous spoon→cup followed by cup→plate from the actual preceding physical state; no reset between tasks.
- Opening elevated jaws makes the cup fall under gravity.
- Injected loss of contents cannot report success.
- Side-lying cup, obstructed rim and oversized unreachable cup rejected without changing the live scene. Slight initial tilt may legitimately settle upright during the settle phase.
- Saved downward wrist reset, a shifted arrangement and a 1.05× cup use measured scene geometry.
- Browser tests load both examples, preview without moving objects, run to completion and inspect reported contents.

KALAS geometry, mass and friction are approximations. This validates these simulated cases; it is not hardware calibration or a guarantee for every user arrangement, arbitrary cargo, deformable cups or liquids.

## Measured contact audit

| Example | Lift | Minimum opposing jaw force | Largest jaw penetration | Unsupported carrying time |
| --- | --- | --- | --- | --- |
| 12 · Empty cup | 73.6 mm | 5.51 N | 0.163 mm | 0 ms |
| 13 · Cup with spoon | 73.0 mm | 5.73 N | 0.174 mm | 0 ms |

Both transports completed in 17.907 simulated seconds. All 6,602 carrying steps had a secure opposing jaw contact in each run. Machine-readable results: [empty cup](cup-rim-audit.json), [loaded cup](loaded-cup-audit.json). These forces are simulator outputs, not measurements from a physical gripper.

Initial rim-grasp implementation validation: **133 backend tests, 35 browser tests and 14 frontend unit tests passed**; production build passed. Both review findings (external collisions of protruding contents and handle-first spoon detection) have regression coverage. The continuous sequence using the exact example-12 layout passed independently after the full suite was started.

## Approach clearance (2026-10-25)

Cup approaches now request wall thickness **plus 20 mm** of jaw opening, instead of plus 5 mm. The fixed finger previously passed only 0.285 mm from the cup in the tested side-rim pose. Opening the moving finger alone cannot address that: the open-pose pinch reference is also shifted by half the margin, then the arm moves to the closed pinch pose while the jaw closes. The lift starts from this closing endpoint. Force limits and contact/collision checks are unchanged.

The same side-rim approach now clears the cup by 7.20 mm at the fixed jaw and 9.94 mm at the moving jaw (minimum distances over the collision geometry). Calculate path requires at least 6 mm of measured clearance, reserving 2 mm beyond the 4 mm minimum checked again before closing during execution. These stricter rehearsal acceptance checks do not change the commanded trajectory. Tests cover the candidates actually selected by Calculate path, and inject ±2 mm X or Y cup/cargo displacement **after** waypoints are calculated, without correcting the target. This tests these fixtures and individual position offsets, not arbitrary combined position/orientation errors or calibrated hardware accuracy.

Clearance update validation: 11 approach/uncertainty tests passed, including nominal 6 mm minimum clearance and eight ±2 mm displacement cases using the planner-selected candidates. The 18 existing cup regressions passed (continuous spoon→cup→plate, both new examples across step batches, opening-to-drop, spill/collision checks and geometry variants). Both browser cup examples completed. A narrower candidate is explicitly tested to stop with the jaws open before closing.

The broader opening/closing-motion regression run also passed all 76 cases (all examples and whole-arm safety). The subsequently added clearance gate and uncertainty reserve were checked by the focused final tests above.
