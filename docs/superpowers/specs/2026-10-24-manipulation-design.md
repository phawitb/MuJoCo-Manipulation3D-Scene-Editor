# Manipulation workbench

The user delegates design and implementation decisions and requests a complete, tested local workflow: wrist view, editable front/down camera, spoon-to-cup example with a working policy, click-source/click-target instructions, Run simulation driving the arm, local object import, and comprehensive external control.

## Design decisions
Keep React/Three.js and authoritative MuJoCo. Four independently selectable views: main, top, front, wrist; default main with a front/wrist observation strip. Front camera editable numerically and by orbit, saved with scene. Wrist follows the model's actual wrist_cam pose and intrinsics. A task panel guides source then destination selection directly in the scene or collection; the example sets both. Run executes/resumes the policy; a separate Physics only action retains passive experiments. Pause freezes both; Stop releases and cancels.

Use numerical IK and smooth bounded joint targets, followed by actual MuJoCo stepping. The default policy explicitly uses grasp assistance: a temporary soft weld only after the gripper reaches the object and closes. Release removes the constraint; success is measured after settling, with the spoon inside the upright cup and unsupported by the gripper. This is a simulation task controller, not a hardware-ready controller or a promise that every arbitrary scene is solvable. Unreachable/invalid tasks fail visibly without teleporting objects. The model has five arm joints plus the gripper, so orientation planning must account for limited reach.

Imported STL, OBJ and self-contained GLB meshes are centered, sized in meters using an explicit longest-side control, validated, embedded in scene JSON and rendered from compiled MuJoCo geometry. Collision uses a convex hull; hollow imported vessels need decomposition and are not silently treated as hollow. Limit upload 10 MB, compiled mesh 20k vertices/40k faces and scene payload 8 MB. No server file path access.

Retain independent sessions. Each has an explicit ID; HTTP, WebSocket and MCP address the same session under one lock. A central worker ticks each active session independent of a browser. REST/OpenAPI plus official Python MCP SDK over stdio exposes list/create/read/delete sessions, full scene get/load/reset, add/update/remove objects, import, robot joints, camera edits, task configure/run/pause/stop/physics/step, snapshots and status. The GUI displays/copies session ID. No ambiguous automatic selection of a session. Local-only origins/hosts and bounded inputs.

## Alternatives
Pure contact grasp is more physically realistic but thin-spoon contact reliability is sensitive to mesh tolerances. Chosen: explicitly labeled grasp-assisted IK with measured release success. Hand animation/teleportation is rejected because it does not exercise simulation. Embedded HTTP MCP vs stdio: choose official stdio SDK bridge to the common HTTP service, preserving simple setup and avoiding a custom protocol implementation.

## Verification
Prove the example lifts, moves, releases, and settles successfully across repeated runs; observe actual arm motion and no object qpos writes by the controller. Check unreachable tasks, cancellation, pause/resume, stale edits, concurrent API/browser control, imported-file rejection and save/reload, all four camera behaviors and browser selection workflow. Exercise real MCP initialize/list/call via SDK client. Existing tests adapted only for intentional Run semantics changes. Document limits and evidence.

## Sources
- https://mujoco.readthedocs.io/en/stable/APIreference/APIfunctions.html (site Jacobian, stepping and pose functions)
- https://mujoco.readthedocs.io/en/stable/XMLreference.html#equality-weld (soft weld semantics)
- https://github.com/modelcontextprotocol/python-sdk (official MCP transport/tool implementation)
