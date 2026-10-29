# Collect LeRobot demonstrations

Open the full-page **Collect** workspace from the header and select **Scene**: any of the 13 built-in examples or the current editor scene. Each job writes a separate dataset for that scene; use the scene filter under **Datasets** to browse results. A preset can be collected even when the live editor is empty. Presets use their own physical layout/reset pose plus your current cameras and appearance. Pause the editor before starting. Editing it afterward does not alter the captured job.

## Install once

```sh
bash scripts/setup-collection.sh
```

The collector uses **LeRobot 0.6.1** in a separate Python 3.12 environment, `.venv-collect`, with pinned dependencies. This keeps its NumPy/Pillow/PyTorch requirements separate from the editor. Run the usual `bash scripts/start.sh` to launch the app. Native MuJoCo OpenGL is required; the collector reports a failed job if unavailable.

## Capture and randomization

1. **Capture:** select a scene, enter a dataset name/instruction, and set **Episodes to generate**, starting seed, frame rate, resolution and duration mode. Position randomization defaults to **Reachable workspace · wide variation**. Choose **Around original positions** for a 1–40 cm local radius, or disable position variation.
2. **Randomization:** every palette has an **All** button, including custom colors already added to that palette. All nine built-in colors are selected by default for tabletop, motors, legs, floor, wall, background and objects. **Robot body keeps orange/yellow** by default. All patterns, all five environment layouts, lighting and material finishes start enabled. Individual values/scopes can still be deselected; pattern and layout groups also have All controls.
3. **Capture settings:** select one or more of **Main, Top, Front, Back, Wrist**. All five start selected; **Select all views** restores them. The dataset contains only selected views, and the job preview comes from the first selected view.
4. **Start collection:** view progress under **Datasets**. Visualization and download become available after finalization and official LeRobot readback validation. Use **Back to editor** to leave the full-page workspace with the scene preserved.

A disabled property retains its captured scene value. A nonempty color palette constrains both the base color and the secondary color of that surface's pattern, even if the pattern itself is locked. Motors remain independent of the robot body. Each property has an independent random stream: enabling another property does not change a previously enabled property's sample. Layout/lighting can affect perceived color in rendered images; palettes constrain material colors.

Attempt `i` uses `starting_seed + i`, starting at zero. **Episodes is the retained-episode target**, not an attempt count. By default only successful executions count. Rejected placements/failed executions use a new seed until the target is reached or **50 times the requested count in workspace mode**, or **five times in radius/disabled mode**, has been attempted. Exhaustion reports a failed/partial job with the actual saved count; verified prior episodes remain downloadable. Seeds are not recycled. Uniform choices may repeat and do not guarantee every combination appears in a small batch.

Workspace mode independently proposes source/destination XY positions across the table within a coarse 40 cm envelope of the robot base, excluding overlaps with other groups. This envelope is a search bound, not a guarantee of reach or an exhaustive reachable-area map. Physical rehearsal is the acceptance check. Local radius mode samples uniformly within a circle around each original position. Heights, orientations, other physical properties and unrelated objects stay fixed. Complete object footprints stay on the tabletop. The existing local-space containment check groups cup/bowl contents with their container, including lower-half cargo and spoon endpoints; examples 11 and 13 retain their starting relationships. Every randomized arrangement is rehearsed with the existing physical contact/collision checks before recording. Invalid arrangements are recorded as rejected attempts, never executed with a stale path.

Reproducibility requires the same complete input scene, configuration and generator/runtime version. Collection generator 2 now records explicit workspace/radius and automatic/fixed modes. The radius random stream is unchanged, and earlier exports remain readable. Legacy configurations containing an explicit radius without a position mode retain radius behavior; explicit max_seconds without a duration mode retains fixed behavior.

**Automatic · finish the task** derives a time allowance from the successful rehearsal (duration × 1.25 + 2 seconds, rounded up, at least 30 and at most 120 seconds). Actual recording ends when the task finishes. Fixed limits shorter than the rehearsal are rejected before recording unless failed episodes were explicitly enabled. Each recorded attempt stores rehearsal duration and its capture time allowance.

**Successful episodes only** is the default. Enable **Include failed episodes** to retain failed/timed-out attempts with their outcomes in metadata. **Stop collection** discards the current incomplete episode and retains already committed episodes. Stopping during encoding completes the current commit before stopping. Interrupted/error attempts retain seed, scene and captured-frame count in the manifest.

Dataset cards show **successful / unsuccessful** retained episodes separately. **LeRobot format verified** confirms readable files, not task completion. The viewer explicitly warns for timed-out/failed episodes. Browser tests archive their own terminal fixtures under ignored `recordings/.test-artifacts/` so they do not appear as demonstrations.

Supported limits: 1–100 retained episodes (up to 5,000 workspace attempts or 500 local attempts), fixed limits of 1–120 simulated seconds each, 10/20/25/50 FPS, 320×240 or 640×480 RGB. One job runs at a time. Rendering may be slower than real time; physics time drives capture, so slow rendering does not skip scheduled frames. The editor stays usable. Files stay on this computer; no Hub upload occurs.

## Dataset contract

The official `LeRobotDataset.create/add_frame/save_episode/finalize` writer produces **LeRobot v3.0**, Parquet metadata/data and H.264 RGB videos. The repo ID is `local/<dataset-name>` and robot type is `so101_mujoco`.

| Feature | Shape | Meaning |
| --- | --- | --- |
| `observation.images.main/top/front/back/wrist` | H × W × 3 | Only selected camera features are present; video storage, reader returns C × H × W tensors |
| `observation.state` | 6 | Measured joint positions, radians |
| `observation.velocity` | 6 | Joint velocities, radians/second |
| `observation.effort` | 6 | Generalized actuator forces at the observed state, N·m for these hinge joints |
| `observation.tcp` | 7 | Gripper-frame XYZ in meters and WXYZ quaternion |
| `observation.sim_time` | 1 | Simulation time in seconds |
| `action` | 6 | Commanded joint-position targets, radians |

Standard LeRobot `timestamp`, `frame_index`, `episode_index`, `index`, `task_index`, task text and statistics are generated by the official writer. Exact joint names/order are stored in feature metadata. All six joints, including the gripper, use simulator radians, **not** hardware-normalized degrees/percentages.

The controller runs at **1000 Hz**. Capture happens after its target update and before physics integration. All selected cameras render that same state with no integration between views, and joint/action rows come from the same capture point. Camera poses come from the saved scene; Wrist follows its physical mount. Captures contain no editor overlays.

`action` is the command at the capture instant. It is **not held constant until the next video frame**: the controller continues to update at 1000 Hz. Use the dense trace for exact command replay, or explicitly resample/choose a prediction horizon when training a lower-rate policy. This export does not silently substitute next-frame measured positions for commanded actions.

## Files and provenance

Outputs are under `recordings/<job-id>/dataset/`, ignored by Git. Set `SO101_RECORDINGS_DIR` before starting the service to select another output directory.

```text
meta/info.json                         # standard LeRobot format/features
meta/tasks.parquet                     # instructions
meta/episodes/...                      # episode offsets, stats and video paths
data/chunk-*/file-*.parquet             # synchronized observations/actions
videos/observation.images.*/chunk-*/*.mp4
meta/collection.json                   # full configuration, attempts, seeds, scenes
meta/collection/episode_000000.json     # retained episode recipe and outcome
meta/collection-verification.json      # readback result
trajectories/episode_000000.npz         # every 1 ms controller/physics sample
```

Dense NPZ arrays: `time`, `qpos`, `qvel`, `effort`, `control`, `tcp`, and `sample_steps`. `sample_steps` maps dataset rows to dense trajectory indices. It permits exact comparison of sampled state/action/timestamps without interpolating. The manifest includes scene ID/name, runtime package versions, joint names, units and action semantics. Each recorded attempt includes its own rehearsed controller configuration, exact object positions and appearance recipe.

Every retained episode is finalized before the next writer resumes. This starts separate data/video shards; only metadata needs a rollback checkpoint. A failed encoding/write removes the incomplete episode and restores prior metadata. Recovery checkpoints are preserved if restoration itself fails. Downloads require a successful verification, including when earlier episodes survive a later error. Hard process termination/power loss is reported as interrupted and is not automatically resumed or presented as a verified download.

## Read locally

Use `.venv-collect/bin/python` (or another environment with compatible LeRobot dependencies):

```python
from pathlib import Path
import json
import numpy as np
from lerobot.datasets.lerobot_dataset import LeRobotDataset

root = Path("recordings/<job-id>/dataset")
manifest = json.loads((root / "meta/collection.json").read_text())
dataset = LeRobotDataset(manifest["repo_id"], root=root, video_backend="pyav")
frame = dataset[0]
print(frame["observation.state"], frame["action"])
camera = manifest["cameras"][0]
print(frame[f"observation.images.{camera}"].shape)
trace = np.load(root / "trajectories/episode_000000.npz")
print(trace["qpos"][trace["sample_steps"]].shape)
```

Recheck a dataset:

```sh
.venv-collect/bin/python -m backend.collection_validate recordings/<job-id>/dataset
```

Verification compares all row counts and every sampled state/action/timestamp with the dense trajectory; checks every camera's video frame count; and decodes first/middle/last images per episode through the official reader. It does not evaluate learned-policy robustness.

## Visualize recorded episodes

Under **Datasets**, choose **Visualize dataset** on a verified job. The viewer follows the episode-list, synchronized video and joint-chart workflow of the local Lerobot-Dataset-Manager, implemented directly in this app.

- Browse/search episodes by number, seed or outcome. Task, success/timeout outcome, seed, frame count and recorded camera names remain visible.
- **Play/Pause**, previous/next frame, timeline scrub and 0.25×/0.5×/1×/2× speed controls share a frame clock. Each camera seeks to its own episode offset plus the selected frame time; the chart advances only after all views decode that frame. Playback may slow while decoding rather than letting cameras drift. It stops on the final frame and never shows the next episode's first frame.
- Choose measured position, commanded target, velocity or actuator effort. Six named joint series share a cursor; legend buttons toggle individual series, clicking the graph seeks, and numeric joint/TCP values follow the displayed frame. State/target units are simulator radians, not normalized hardware values.
- Changing episode stops playback and resets the timeline. **Back to datasets** returns to the list; **Back to editor** exits Collect. Background editor controls are inert while Collect is open.

Existing five-camera outputs are supported, including older v3 video files containing more than one episode. A small `meta/collection-viewer-v1.json` cache is generated from official Parquet episode metadata on first view. Sampled signals come from the recorded dense trace at `sample_steps`. Streaming supports HTTP byte ranges. Only terminal verified jobs can be viewed; the viewer does not modify episodes or upload data.

## HTTP API

All endpoints use the existing local service at port 8765:

| Method / route | Result |
| --- | --- |
| `GET /api/collection` | Runtime readiness, defaults, format, camera list |
| `POST /api/sessions/{sid}/collection` | Select the preset or clone the paused editor scene; launch a job with `CollectionConfig` JSON |
| `GET /api/collection/jobs` | Latest 100 jobs |
| `GET /api/collection/jobs/{id}` | Progress, errors, verification/download availability |
| `POST /api/collection/jobs/{id}/cancel` | Request cooperative stop |
| `GET /api/collection/jobs/{id}/preview` | Latest JPEG from the first selected camera |
| `GET /api/collection/jobs/{id}/download` | Verified dataset ZIP |
| `GET /api/collection/jobs/{id}/visualization` | Episode list, per-camera offsets/URLs and joint names |
| `GET /api/collection/jobs/{id}/episodes/{episode}/signals` | Sampled joint/TCP signals for that episode |
| `GET /api/collection/jobs/{id}/episodes/{episode}/video/{view}` | Recorded MP4 with byte-range support |

Example configuration:

```json
{
  "scene_id": "kalas-cup-front",
  "name": "orange-yellow-training",
  "task": "Pick up the spoon and place it in the cup.",
  "episodes": 10,
  "seed": 42,
  "fps": 20,
  "cameras": ["front", "wrist"],
  "resolution": "640x480",
  "duration_mode": "auto",
  "max_seconds": 30,
  "include_failed": false,
  "variation": {
    "robot_colors": ["#f1792e", "#ffd11f"],
    "table_colors": ["#ffffff", "#808080", "#202020"],
    "table_patterns": ["solid", "wood", "checker"],
    "environments": ["studio", "room", "warehouse"],
    "lighting": true,
    "positions": true,
    "position_mode": "workspace",
    "position_radius": 0.02
  }
}
```

`cameras` must contain 1–5 distinct valid view names; omission retains the legacy all-five default. Empty palette/pattern/layout arrays mean locked. `scene_id: null` means the current editor scene. Omitted fields receive the broad defaults exposed by the capabilities endpoint: all colors except robot orange/yellow, all patterns/layouts, lighting, finishes and positions. Pass `positions: false`, `lighting: false`, `finishes: false` and empty lists for the scopes you want to lock. Unknown keys and invalid scene IDs are rejected.

This version varies visual properties and source/destination positions while retaining the selected task. Camera poses, dynamics and sensor noise are not randomized. Split training/evaluation by seeds and environment families, then validate the trained policy on held-out conditions and hardware before claiming robustness.
