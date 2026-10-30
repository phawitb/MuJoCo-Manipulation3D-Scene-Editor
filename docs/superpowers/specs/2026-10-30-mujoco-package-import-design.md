# MuJoCo object package import

Status: proposed design; approach 1 selected by the user, awaiting design approval.

## Intent

Extend Import object to accept a folder or ZIP such as `/Users/phawit/Downloads/mujoco-package (3)`. Add its object to the current table while preserving the package's visual parts, original metric size and object physics. Imported objects must survive save/reopen and remain available in collection recipes and native camera recording.

The supplied package describes one rigid LinkTrack object: 49 colored visual mesh geoms, five collision primitives, a free joint, explicit 45 g mass, center of mass, full inertia tensor and contact parameters. Its scene.xml also supplies a demonstration floor and light; these must not replace the user's scene. XML is authoritative for simulation; descriptive JSON files retain provenance without overriding it.

## Approaches

1. **Native object package semantics — selected by user.** Read the package's object, meshes and physics, convert them into validated portable object data, and reconstruct them within this application's MuJoCo model. More integration work, but retains independent visual and collision geometry and measured/declared physical properties.
2. **Flatten into the existing mesh importer — not selected.** Simpler, but loses per-part colors, compound collision and explicit inertia. Unsuitable for the requested simulation/data use.

## User flow

- Keep existing STL/OBJ/GLB imports working as before.
- Add a MuJoCo package choice with **Choose folder** and **Choose ZIP**. Folder selection uploads its relative file tree, with no manual server path entry required.
- Inspect before adding: display object name, original dimensions, mass, visual/collision counts and any unsupported content. The sample is recognized as LinkTrack.
- Default to original size and original colors. Import one movable object, with all its pieces attached, resting just above the current table. Do not import the sample floor, lights, robot, global simulation options or demonstration placement.
- Preserve original object colors until the user explicitly chooses an object color override or enables object-color randomization. Offer restoring package colors.
- Errors leave the current scene unchanged. If required features cannot be preserved, reject with a clear reason; do not silently flatten or discard them.

## Supported package scope

Initial support targets a single rigid object like the supplied package, with XML includes, referenced OBJ/STL mesh assets, visual mesh/primitive geoms, collision primitives or convex mesh geoms, and explicit or MuJoCo-computed inertia. Static child bodies may be flattened with correct transforms and aggregate inertia. Allow at most one root free joint and no moving internal joints.

Prefer object.xml when supplied, resolving assets.xml and package-local includes. Otherwise identify a single movable object in scene.xml; reject ambiguous multiple-object input with an actionable message. Treat filesystem and archive names as untrusted, reject traversal/absolute paths, symlinks, external resource references, XML entities, plugins and unsupported executable extensions. Compile only validated, isolated object input, never the original whole scene or arbitrary includes from disk.

Articulated mechanisms, actuators, tendons, equality constraints, external textures/material image files, multiple independent dynamic objects and arbitrary MuJoCo scenes are outside this first version. Validate unsupported physics constructs rather than ignoring them. RGBA colors and supported material scalar properties are retained; image-textured packages require a future texture import extension. No claim that arbitrary imports automatically have a successful pick/place policy.

## Portable representation and integration

- Add a distinct package object asset with validated embedded mesh arrays, per-part transforms, RGBA/material values, collision/contact attributes and inertial data. Never retain active filesystem dependencies. Include source filenames and bounded provenance JSON as metadata only.
- Preserve SI units and original relative poses. Canonicalize to a centered object frame for compatibility with existing placement/bounds logic; transform geometry, center of mass and optional sites consistently so the physics is unchanged.
- Namespace all reconstructed names by object id; multiple imports of the same package cannot collide with each other or the robot.
- Separate visual geoms from hidden collision geoms using the app's established groups. Both browser geometry packets and native recording use the reconstructed model.
- Default mass, friction and inertia come from the package, without the old mesh importer's 50 g mass or convex-hull replacement. Preserve per-geom friction/contact settings until explicitly overridden. Existing Inspector mass/friction edits must either be implemented consistently for package objects or clearly disabled with an explanation; never show active controls that do nothing.
- Uniform scaling, if supported through the existing Inspector, scales positions and mesh/primitive sizes. With mass held fixed by the separate mass control, inertia scales by scale squared. Changing mass scales the inertia tensor proportionally. Document this behavior in the UI. Retain off-diagonal inertia and COM offsets.
- Update catalog profiles, selection, placement, object bounds, appearance overrides and collection randomization for package objects. Use real compound bounds. Preserve the established physical rehearsal requirement before capture.
- Existing scene format remains backward compatible. Saved scenes and episode recipes carry the complete portable package. Keep the 8 MB scene budget and enforce it before insertion.

## Bounds and errors

Builder may choose conservative file-count/mesh-count/triangle budgets after measuring the supplied fixture, but must accept it without simplification or losing features. Bound both compressed upload size and expanded archive size, directory upload size, number of files, XML recursion and aggregate decoded geometry. Validate all geometry, transforms, mass and positive physically valid inertia. Reject unsupported constructs and missing assets with a specific filename and reason.

## Validation and delivery

1. Regression tests retain existing standalone mesh import behavior.
2. Package folder and ZIP paths yield equivalent portable objects, including a ZIP with a containing root folder.
3. Import the supplied package; verify mass, COM, full inertia, source colors, separate collision pieces and dimensions against the input. Check duplicate import names, save/reopen and recording renderability.
4. Run physics settling/contact checks on the current table. Do not claim grasp success without successful rehearsal.
5. Test malformed archives, traversal, missing assets, oversized content, unsupported articulated objects and invalid inertia. Failed imports must leave scenes intact.
6. Browser check: choose folder and ZIP, review summary, import, select/move object, restore source colors and save/reopen. Inspect the actual rendered result.
7. Run focused backend tests, frontend checks/build and relevant collection regression tests. Preserve active user scenes before any required backend restart.

Implementation structure, exact API transport, conservative limits and test-fixture construction are builder decisions. No new external services, uploads to a third party or dependency installation is required by this design.
