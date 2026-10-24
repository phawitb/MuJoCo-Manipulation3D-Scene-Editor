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
| 12 · Empty cup | 73.9 mm | 5.73 N | 0.154 mm | 0 ms |
| 13 · Cup with spoon | 72.9 mm | 5.36 N | 0.169 mm | 0 ms |

Both transports completed in 17.907 simulated seconds. All 6,602 carrying steps had a secure opposing jaw contact in each run. Machine-readable results: [empty cup](cup-rim-audit.json), [loaded cup](loaded-cup-audit.json). These forces are simulator outputs, not measurements from a physical gripper.

Final regression run: **133 backend tests, 35 browser tests and 14 frontend unit tests passed**; production build passed. Both review findings (external collisions of protruding contents and handle-first spoon detection) have regression coverage. The continuous sequence using the exact example-12 layout passed independently after the full suite was started.
