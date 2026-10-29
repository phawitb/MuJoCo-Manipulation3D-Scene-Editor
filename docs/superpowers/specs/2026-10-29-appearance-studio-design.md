# Appearance Studio

The user delegates design choices for extensive visual diversity before future robot data collection. Extend the existing React/Three + MuJoCo application in place, keeping v1 as the base. No new dependencies.

## Approach
Use an authoritative, portable appearance configuration in Scene. Generate deterministic procedural textures in Python and reuse their pixels in native MuJoCo and the browser. Browser-only decoration would miss training observations; external HDRI/image downloads would weaken portability. The two renderers share scene content and light parameters but are not pixel-identical.

## Scope
Robot body/motor colors and patterned materials; tabletop, legs, floor and wall colors; solid, checker, stripes, dots, wood, terrazzo, tiles and noise patterns; finish and pattern scale. Open, studio, room, warehouse and panel backdrops contain visual-only geometry outside the worktable. Configurable key light position/color/intensity, fill, ambient and shadows. Six curated presets. Seeded randomization with independent scopes and mild/balanced/wide ranges. Save/load full recipes and export a bounded batch of recipes for future collection. No claim that visual diversity alone guarantees robustness.

Appearance commands are paused-only and preserve measured qpos, velocities, controls, simulation time, controller and plan. Appearance does not change physics, cameras or task placement. Scene reset and example loading retain appearance. Old scenes receive defaults. Inputs are strictly validated. A seed identifies a randomization operation with scopes, strength and generator version; full exported values remain authoritative after hand edits.

## Verification
Test compatibility, input bounds, deterministic seeds/scopes, unchanged integration state and physical parameters, save/load, native patterned image differences, API commands and browser workflow including narrow screens. Check production build and existing relevant regressions, then full suite. Runtime restarts must load updated backend.
