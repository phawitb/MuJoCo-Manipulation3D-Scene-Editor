# Path preview and KALAS workbench

User delegates design and implementation decisions and requests autonomous research/testing. Build on the existing local React/MuJoCo/MCP application.

## Experience
- Native asset dragging shows a translucent 3D object and tabletop footprint at the same clamped position that drop will use; no scene mutation until release. Invalid/outside positions show no ghost. Cleanup on leave/drop/cancel.
- Selected objects move on the tabletop with arrow keys (world X/Y; 1 cm, Shift 1 mm). Ignore form fields, dialogs and running simulation. Bound whole footprint to table and coalesce repeated keys without losing final intent.
- Empty selection shows a current object list in Inspector. Clicking a row selects the same object/gizmo as viewport selection. A short emissive pulse/halo makes the selection visible in all views, including task source/target selection and clicking existing task labels.
- Calculate path precedes Run. A rainbow polyline depicts the measured gripper trajectory from a successful isolated MuJoCo rehearsal; live objects/arm do not move while calculating. Edits/physics invalidate the plan; camera moves do not. No stale result may re-enable Run. Pause/resume remains available.
- Ten named examples cover multiple source/target positions/orientations, containers/supports and clutter. Each must pass calculation and real released-object verification, with results recorded. User-arranged reachable scenes use the same planner, not an example-specific animation. Impossible scenes explicitly fail and retain user work.

## Architecture and approaches
1. Geometric-only IK preview is cheap but can advertise paths whose grasp/release fails; rejected.
2. Chosen: bounded candidate IK controller configurations, each rehearsed in an isolated model/data copy, recording true gripper poses and collisions. Run uses the verified configuration and unchanged initial physics state; retain proximity-gated grasp assistance with honest disclosure. Cost: planning seconds and bounded solvability, not a general motion-planning guarantee.
3. General sampling/optimization planner and perception stack deferred: disproportionate scope and does not alone solve contact grasping.

Scene edits stay atomic. Planning is asynchronous and cancellable, bounded in steps/attempts/wall time. Full state/model clone preserves velocities, controls, time and warmstart; no live scene mutation while planning. Store physics fingerprint separate from camera revision. Session/HTTP/MCP expose plan and examples consistently.

## Assets
Research exact requested IKEA articles and reusable model licensing first. Add kalas_bowl, kalas_cup, kalas_spoon, kalas_plate, preserving old IDs for saved scenes. Official dimensions: bowl diameter .12 m; plate diameter .19 m; spoon length .16 m; cup capacity .00023 m³. All unreported measurements explicitly estimated in docs/KALAS-SOURCES.md. Procedural tapered hollow containers with compound collision (no sealed convex cup), curved rim, shaped spoon. No unlicensed third-party geometry. Metadata and visible UI identify approximate reconstruction.

## Acceptance and limits
Tests cover preview vs actual drop, keyboard/input isolation, inspector/task selection halos, non-mutating calculation, stale/in-flight plan invalidation, rejection of unreachable/blocked scenes, plan/run consistency, ten examples, legacy save/import/MCP/reconnect. Existing grasp-assist and convex imported-mesh limits remain disclosed. No claim of dimensional metrology or guaranteed success for arbitrary scenes.
