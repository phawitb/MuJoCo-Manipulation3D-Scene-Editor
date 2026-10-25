# Separate simulation and real execution; table-clearance investigation

User authorizes autonomous changes, calibration inspection and physical/web testing. Keep main; preserve v1. Use existing architecture; no collision disabling or arbitrary calibration offsets.

1. Diagnose geometry/feedback/hold separately. Reproduce minimum gripper-to-table clearance in isolated physics and inspect fresh hardware/camera evidence. Establish a physically achievable grasp with clearance; do not force success by widening collision tolerances.
2. Run simulation never enables or follows hardware. Capture the initial scene of a successful simulation; edits invalidate that approval. Separate Run Realrobot replays that scene only after a fresh, collision-checked rehearsal from measured physical angles. Expose typed API/MCP semantics and visible states.
3. Address current measured-pose overlap through a bounded, validated retreat if feasible: preserve all collision checks, allow only decreasing existing table penetration during departure, and reject new collisions. Never conceal overlap by changing table height or encoder zeros without measurement evidence.
4. Regression tests before implementation; run actual fullscreen web workflow for three examples, record software and physical outcomes separately. Verify final stopped state; final independent static review as required by executing-plans.

Evidence: original tabletop spoon grasp minimum table clearance is -0.009 mm in successful virtual run. Raising pinch by 1–3 mm (negative depth offset) clears table but loses opposing spoon-handle contact. Thus simply reducing tracking error is insufficient for robust hardware grasp; investigate thicker grasp region.

## Execution ledger

- Implemented separate `run` and `real_run`; successful initial clone, edit invalidation, consume-on-physical-attempt, replan from fresh measured angles, owner/calibration gates, cancellation on stop/edit/lease. Expired preparation cannot be revived by renewed heartbeat. Manual mapping/alignment/enable/sync blocked during preparation.
- Existing hold preservation prevents silently replacing a verified compensated hold with uncompensated encoder hold on ordinary faults. Table recovery checks every contact throughout motion and does not alter collision masks, table geometry, model tolerances or calibration.
- Ruling: prefer a small elbow retreat over further shoulder correction — shoulder had a persistent 52-tick error with increasing temperature — do not increase torque or keep advancing a stalled goal.
- Physical elbow retreat attempted through the web UI; actual encoder remained unchanged, controller stopped at tracking threshold. Shoulder error 52 ticks (4.57°), elbow error 27 ticks (2.37°), fresh servo status bytes 0, supply 12.2 V, torque on. This does not identify the physical cause.
- UI fullscreen 1512×893: examples 01, 02, 05 passed simulation-only, motors not enabled. Repeated example 01 then clicked Run Realrobot; rejected before motor writes by table/gripper overlap 4.02 mm at measured joint pose.
- Ruling: do not report three successful physical runs or geometric calibration success. Repeated feedback failures prevent safe continuation from the current physical pose; broad authorization does not resolve an unknown obstruction. User requested ignoring cameras, so no new visual calibration claim is made.
- Fresh static reviewer found a preparation lease-revival race; reproduced RED and fixed GREEN. Reviewer reported no remaining concrete blocking findings. Added retreat-loop regression coverage for success, tracking failure, expired lease and scene replacement.

## Follow-up: end-of-episode comparison

User requested automatic immediate motion on Connect and no checks until the entire real episode ends. Ruling: keep connection read-only and preserve live guards in the currently stalled, model-overlapping pose — fresh encoder feedback still shows no shoulder/elbow progress and shoulder temperature has risen to 54°C — do not force unmonitored movement. Implement the safe requested portion: publish six-joint endpoint/peak/RMS encoder-vs-Gym statistics after completed or stopped episodes. Sample during execution without publishing partial reports; retain sample age to distinguish stale last-known feedback from fresh final feedback. Added aggregation and linked stop/completion regressions (RED then GREEN).
