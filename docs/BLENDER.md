# Blender: local image-to-solid workshop

Open **Blender** in Scene Studio, upload a PNG or JPEG, and enter the object's real width and height in millimetres. Choose dark foreground, light foreground, or PNG transparency. The image and processing stay on this computer; there is no external reconstruction service. The Blender desktop application is not required.

- **Silhouette extrusion** gives the largest connected outline a uniform depth. Visible holes remain through-holes in the exported mesh.
- **Revolve** rotates a front-on outer profile around its vertical centre. Width means diameter. The result is a closed solid, including top and bottom; it does not reconstruct hollow cups, handles, cavities or off-axis details.

Use a clear contrasting background with a margin around the subject. Set the threshold, create the object and inspect both the detected silhouette and the rotatable preview. Fine details are simplified to a maximum 64-cell silhouette resolution. If details touch in a way that prevents a closed solid, generation reports an error; clean the image or adjust the threshold.

Download the GLB to import into Blender or another glTF tool. The export uses glTF's Y-up coordinates; the portable Gym mesh retains Gym's Z-up coordinates. Dimensions are in metres in the file. Image texture is not projected onto the surface.

To use the object in Gym, select the destination session explicitly and click **Add to selected Gym**. The session must be paused. Import uses its current revision, sets the object on that session's table and assigns a fresh object ID. Reposition it in Gym as needed. The object is embedded in portable scene data, so saved scenes do not depend on the source photograph. Gym uses convex collision for imported meshes: visible holes and concavities are not physical openings. Generated objects receive the standard 50 g mass; adjust physical properties in Gym.

## Module and API

The frontend lives in `frontend/src/modules/blender` and exports `BlenderTab`. The backend lives in `backend/modules/blender`; its router has prefix `/api/blender`. The shell controls module registration. Reconstruction providers implement the `ReconstructionProvider` protocol, leaving room for another local engine without changing portable scene data.

`POST /api/blender/create` accepts JSON:

```json
{
  "image_base64": "<base64 PNG or JPEG, without a data URL prefix>",
  "filename": "object.png",
  "name": "My object",
  "mode": "extrude",
  "foreground": "dark",
  "threshold": 128,
  "width_m": 0.10,
  "height_m": 0.10,
  "depth_m": 0.03
}
```

Modes: `extrude`, `revolve`. Foreground: `dark`, `light`, `alpha`. Threshold: integer 0–255. Dimensions: 0.005–1 metre. Width and height independently scale the detected bounding box; no camera calibration or automatic dimension inference is performed. Revolve ignores depth and makes its horizontal dimensions equal to width.

Response: `object` (portable `SceneObject`), `glb_base64`, safe download `filename`, and `metadata` containing mode, dimensions, vertex/triangle counts, volume, watertightness, source image dimensions, detected-mask PNG and explanatory warnings. The decoded image is at most 6 MB, 4096 pixels per side and 12 million pixels total. Request bodies are bounded before parsing. Output is capped at 20,000 vertices and 40,000 triangles and verified as a closed, consistently wound solid. Two HTTP generation jobs may run concurrently; heavy work runs outside the event loop. Neither original photographs nor results are persisted by this module.

All approximate reconstructions require inspection. A single photograph cannot determine hidden geometry or physical scale. Revolve is suitable only when the object's visible outer profile is representative of a symmetric object.
