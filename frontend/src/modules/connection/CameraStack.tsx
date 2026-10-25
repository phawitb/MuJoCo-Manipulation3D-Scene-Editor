import type { CameraResult } from "./api";
export default function CameraStack({ cameras }: { cameras: CameraResult[] }) {
  return (
    <div className="connection-camera-stack">
      {cameras.map((camera) => (
        <figure key={camera.index} className="connection-camera-frame">
          <span className="camera-index">
            idx {camera.index}
            {camera.role ? ` · ${camera.role}` : ""}
          </span>
          {camera.available && camera.image ? (
            <img
              src={camera.image}
              alt={`${camera.role || "Scanned"} camera idx ${camera.index}`}
            />
          ) : (
            <p>{camera.error || "No image available"}</p>
          )}
        </figure>
      ))}
    </div>
  );
}
