# Contact-only manipulation correction

The user observed unrealistic grasping in example06 and requested the most realistic physics practical across all examples. Prior weld-assisted success is not acceptable evidence for this request.

Diagnosis at459755d: proximity-only attachment activates an equality weld without bilateral jaw force and never checks loss of contact. Example06 remains held without either jaw force for3.064s;08 for1.044s;05 for1.546s. Old validation checked lift and final placement, not how the load was supported. Different observation batching also changed a marginal outcome.

Remove runtime grasp welds entirely. Objects must move solely from gravity, contact and bounded actuators. Compute grasp geometry from actual jaw positions and source orientation, require sustained opposing contacts before lifting, monitor slip/contact during carrying, and report a missed/dropped grasp rather than masking it. Stop must physically open the gripper. Rehearsal and live execution use the same controller and full-state snapshot. Keep current editor, cameras, API commands and imported scenes compatible.

Do not inflate friction or create invisible pads to make examples pass. Retain source robot geometry/force limits unless a documented diagnosis justifies an adjustment. Solver accuracy and speed changes must preserve gravity and contact realism. Approximate material parameters remain explicit: this is not hardware validation.

Re-run all ten arrangements and record physical success/failure, bilateral grip duration/force, maximum unsupported interval and released settling. Aim to make all ten work through grasp/path corrections; never change failure criteria to obtain success. Check loss of friction, missed grasp and opening while elevated. Add UI/API measured grip status and replace old assist wording. Generate close-up visual evidence for06 and representative other tasks.
