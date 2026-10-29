# Scene-specific collection and broad defaults

User requests All on every color palette, all variation choices enabled by default except robot body colors, datasets selectable by scene, both task objects repositioned per episode, and configurable generated episode count. Prior design discretion/direct implementation authorization continues.

Implement within existing collector: one selected scene per dataset, current scene or any of 13 examples. Keep user cameras/appearance for presets; preset physical layout/robot are authoritative. Separate datasets are labeled/filterable by scene. All nine supplied colors for non-robot palettes; robot orange/yellow retained. Enable all patterns/layouts/lighting/finishes by default. All controls also include custom colors already in their palette.

Position variation defaults on, independently samples XY offsets for source and destination in a configurable 1–5 cm radius (default 2 cm). Preserve Z, orientation and existing contained-object relationships (spoon in source cup; loose spoon carried with cup). Keep complete footprints on the tabletop. Rehearse each randomized arrangement using existing real contact/collision/path checks; failed planning attempts consume a new seed and are recorded, never reused as valid trajectories.

Episodes specifies retained episode target (default successes only). Bound attempts to five times target; if exhausted, report a clear incomplete error and allow download of verified retained data. Include-failed retains recordable failed/timed-out episodes; invalid plans are never executed. Per-attempt recipe and controller config persist. Existing synchronization/rollback contract unchanged. UI explains target/attempt distinction, scene and actual progress.

Alternatives considered: reusing one original path invalid after placement changes; randomizing across the entire table wastes time on unreachable arrangements. Chosen local bounded offsets plus rehearsal, with configurable radius and reproducible seed stream. Multi-scene batch orchestration is outside this change: each job/dataset selects one scene.
