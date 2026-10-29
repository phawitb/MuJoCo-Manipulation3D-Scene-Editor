# Full-page collection and dataset viewer

User requests selectable capture views, a full-screen Collect page and visualization inside Datasets, referencing the local Lerobot-Dataset-Manager. Prior direct-implementation/design discretion applies. Reference inspected read-only: static/index.html visualizer, episode selection, synchronized camera streams, scrub/play controls, named joint trajectory series.

Extend the existing application, no external app dependency. Capture chooses a nonempty unique subset of main/top/front/back/wrist; default all five. Features, recording, preview, validation and provenance must use the same chosen list. Preview uses the first selected camera. Existing five-view datasets remain readable.

Collect becomes a full-viewport page with Back to editor, horizontal tabs, wide responsive settings columns and dataset cards. Editor state stays mounted but inert while page is open. No browser/OS fullscreen permission required.

Verified datasets expose an episode viewer: searchable/selectable episodes, task/outcome/seed, selected recorded camera videos, shared playback/pause/speed/frame scrub, six named joint position/action/velocity series with current-frame cursor and numeric readout. Preserve v3 per-camera file offsets, including older multi-episode video shards. Browser playback uses one shared simulation-frame clock; all videos seek to offset + frame/fps (pause while media catches up) and graphs use the same sampled trace index. Never show unselected camera placeholders as recorded data.

Only terminal verified local jobs can be viewed. Build a small index from official LeRobot metadata using the isolated collection runtime (cache for older outputs). Signals use existing dense NPZ at sample_steps. Video requests resolve only metadata-derived paths under the dataset root and support HTTP byte ranges. No path parameters from clients beyond validated job/episode/view identifiers. Visualization is read-only; editing/deleting/augmenting datasets is outside scope.
