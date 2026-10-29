# Seeded LeRobot collection

The user requests an operational collector: all five camera views, synchronized joint state and trajectory, per-episode seeded environment variation with explicit palettes (robot orange/yellow; table white/gray/black), exported in LeRobot format. Design discretion and direct implementation are authorized by this continuing task.

## Chosen approach
Use official LeRobot 0.6.1 Dataset v3 writer in a separate Python 3.12 environment. A dedicated local process clones the paused scene and rehearses its task once, then repeats the validated policy with independently seeded visual recipes. Persistent renderer captures main/top/front/back/wrist from the same MjData without physics advances between views. A browser-only screenshot recorder would omit native camera geometry and synchronize poorly; importing the training stack into the editor would conflict with its pinned dependencies.

## Data contract
At each 10/20/25/50 Hz sample, after policy update and before physics integration, save five RGB videos, six measured joint positions (rad), velocities (rad/s), generalized actuator forces, six commanded position targets (rad) as action, TCP pose (XYZ meters + WXYZ), and simulation time. Physics/controller remain at 1000 Hz. Full 1000 Hz state/action/TCP trajectory is saved per episode as compressed NPZ. Action is the actual instantaneous controller target, not a target inferred from observation or held for the entire frame interval. LeRobot's uniform timestamps align exactly with the supported frame rates. Outcome and terminal time live in per-episode provenance; incomplete episodes are not published.

## Randomization
Independent enablement via nonempty value lists: robot, motor, table, legs, floor, wall, background and object palettes; robot/table/floor/wall patterns; environment layout; optional light and finish variation. Empty lists lock the value. Separate RNG streams per property ensure unrelated choices cannot perturb a selected palette. Episode seed = base + attempt index. Include full config, scene, seed, camera configuration, units, action semantics and controller configuration in local provenance. Store everything locally; no automatic Hub upload.

## Workflow and limits
Collect panel configures name, language instruction, episodes (1–100), FPS, resolution (640×480/320×240), timeout and include-failed option. Defaults keep only successful episodes. A background job shows planning/recording/finalizing/completed/cancelled/failed, progress, preview and saved path/download. One worker at a time, unique job folders, no overwrite. Stop discards the in-progress episode and finalizes completed ones. Failed attempts and cancellation are explicit in manifest. On restart interrupted jobs are marked interrupted. A ZIP is available only after finalization and verification. Preserve editor state throughout.

## Verification
Validate palette bounds/determinism, physics invariance and recorder hook alignment. Exercise official writer and reader on a real short multi-camera episode, inspect Parquet/video frame counts and dense trace alignment, test successful task collection and cancellation, test API validation and UI job/export flow. Existing backend physics and frontend tests remain passing.
