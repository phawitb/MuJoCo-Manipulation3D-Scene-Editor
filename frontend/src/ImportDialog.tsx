import { useRef, useState } from "react";
import { FileBox, Upload, X } from "lucide-react";
import type { SceneObject } from "./types";
export function ImportDialog({
  close,
  add,
}: {
  close: () => void;
  add: (o: SceneObject) => Promise<void>;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null),
    [size, setSize] = useState("100"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const submit = async () => {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const mm = Number(size);
      if (!Number.isFinite(mm) || mm < 5 || mm > 1000)
        throw Error("Choose a longest side between 5 and 1,000 mm.");
      if (file.size > 10_000_000) throw Error("Maximum file size is 10 MB.");
      const response = await fetch(
        `/api/import?filename=${encodeURIComponent(file.name)}&size=${mm / 1000}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/octet-stream" },
          body: file,
        },
      );
      const data = await response.json();
      if (!response.ok) throw Error(data.detail || "Import failed");
      await add(data);
      close();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="modal-backdrop">
      <div
        className="workbench-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Import object"
      >
        <button
          className="close"
          disabled={busy}
          aria-label="Close import"
          onClick={close}
        >
          <X size={18} />
        </button>
        <span className="eyebrow">YOUR OBJECTS</span>
        <h2>Bring an object to the table.</h2>
        <p>STL, OBJ or self-contained GLB · up to 10 MB</p>
        <button
          className="file-drop"
          onClick={() => input.current?.click()}
          disabled={busy}
        >
          <FileBox size={32} />
          <strong>{file?.name || "Choose a file from your computer"}</strong>
          <span>
            {file
              ? `${(file.size / 1024).toFixed(0)} KB`
              : "20k vertices / 40k triangles maximum"}
          </span>
        </button>
        <input
          ref={input}
          data-testid="object-file"
          type="file"
          accept=".stl,.obj,.glb"
          hidden
          onChange={(e) => {
            setFile(e.target.files?.[0] || null);
            setError("");
          }}
        />
        <label>
          Longest side (mm)
          <input
            aria-label="Object longest side"
            type="number"
            min="5"
            max="1000"
            value={size}
            onChange={(e) => setSize(e.target.value)}
          />
        </label>
        <p className="import-note">
          The mesh is centered and scaled to this size. Collision uses a solid
          convex hull; hollow imported cups behave as solid objects. Use the
          library cup for pouring or insertion. Textures are replaced by an
          editable color.
        </p>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button
          className="primary-action"
          disabled={!file || busy}
          onClick={() => void submit()}
        >
          <Upload size={15} />
          {busy ? "Preparing object…" : "Import and place"}
        </button>
      </div>
    </div>
  );
}
