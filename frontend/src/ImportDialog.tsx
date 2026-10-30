import { useRef, useState } from "react";
import { FileBox, Upload, X } from "lucide-react";
import type { SceneObject } from "./types";

function encodedFile(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(Error(`Cannot read ${file.name}`));
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1]);
    reader.readAsDataURL(file);
  });
}

export function ImportDialog({
  close,
  add,
}: {
  close: () => void;
  add: (o: SceneObject) => Promise<void>;
}) {
  const input = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);
  const zipInput = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<"mesh" | "package">("mesh");
  const [file, setFile] = useState<File | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [zip, setZip] = useState<File | null>(null);
  const [preview, setPreview] = useState<SceneObject | null>(null);
  const [size, setSize] = useState("100");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const chooseMode = (next: "mesh" | "package") => {
    setMode(next);
    setError("");
  };
  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      if (mode === "package" && preview) {
        await add(preview);
        close();
        return;
      }
      let response: Response;
      if (mode === "package") {
        if (zip) {
          if (zip.size > 10_000_000) throw Error("ZIP must be at most 10 MB.");
          response = await fetch("/api/import/package", {
            method: "POST",
            headers: { "Content-Type": "application/zip" },
            body: zip,
          });
        } else {
          if (
            !files.length ||
            files.length > 256 ||
            files.reduce((n, f) => n + f.size, 0) > 20_000_000
          )
            throw Error(
              "Choose a package with at most 256 files and 20 MB total.",
            );
          const entries = await Promise.all(
            files.map(async (f) => ({
              path: f.webkitRelativePath || f.name,
              data: await encodedFile(f),
            })),
          );
          response = await fetch("/api/import/package", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ files: entries }),
          });
        }
      } else {
        if (!file) return;
        const mm = Number(size);
        if (!Number.isFinite(mm) || mm < 5 || mm > 1000)
          throw Error("Choose a longest side between 5 and 1,000 mm.");
        if (file.size > 10_000_000) throw Error("Maximum file size is 10 MB.");
        response = await fetch(
          `/api/import?filename=${encodeURIComponent(file.name)}&size=${mm / 1000}`,
          {
            method: "POST",
            headers: { "Content-Type": "application/octet-stream" },
            body: file,
          },
        );
      }
      const data = await response.json();
      if (!response.ok)
        throw Error(
          typeof data.detail === "string"
            ? data.detail
            : "Cannot import this object. Check the package files and supported formats.",
        );
      if (mode === "package") setPreview(data);
      else {
        await add(data);
        close();
      }
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
        <div className="package-import-tabs">
          <button
            disabled={busy}
            aria-pressed={mode === "mesh"}
            onClick={() => chooseMode("mesh")}
          >
            Mesh file
          </button>
          <button
            disabled={busy}
            aria-pressed={mode === "package"}
            onClick={() => chooseMode("package")}
          >
            MuJoCo package
          </button>
        </div>
        {mode === "mesh" ? (
          <>
            <p>STL, OBJ or self-contained GLB · up to 10 MB</p>
            <button
              className="file-drop"
              onClick={() => input.current?.click()}
              disabled={busy}
            >
              <FileBox size={32} />
              <strong>
                {file?.name || "Choose a file from your computer"}
              </strong>
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
              The mesh is centered and scaled to this size. Collision uses a
              solid convex hull; hollow imported cups behave as solid objects.
              Use the library cup for pouring or insertion. Textures are
              replaced by an editable color.
            </p>
          </>
        ) : (
          <>
            <p>
              A single rigid MuJoCo object · original size, part colors and
              physics
            </p>
            <div className="package-import-tabs">
              <button
                disabled={busy}
                onClick={() => folderInput.current?.click()}
              >
                Choose folder
              </button>
              <button disabled={busy} onClick={() => zipInput.current?.click()}>
                Choose ZIP
              </button>
            </div>
            <input
              ref={(node) => {
                folderInput.current = node;
                node?.setAttribute("webkitdirectory", "");
              }}
              data-testid="package-folder"
              type="file"
              multiple
              hidden
              onChange={(e) => {
                setFiles(Array.from(e.target.files || []));
                setZip(null);
                setPreview(null);
                setError("");
              }}
            />
            <input
              ref={zipInput}
              data-testid="package-zip"
              type="file"
              accept=".zip"
              hidden
              onChange={(e) => {
                setZip(e.target.files?.[0] || null);
                setFiles([]);
                setPreview(null);
                setError("");
              }}
            />
            <p>
              {zip
                ? zip.name
                : files.length
                  ? `${files[0].webkitRelativePath.split("/")[0]} · ${files.length} files`
                  : "Select the folder containing object.xml or scene.xml and its mesh assets."}
            </p>
            {preview?.package && (
              <div className="package-summary" data-testid="package-summary">
                <strong>{preview.name}</strong>
                <dl>
                  <div>
                    <dt>Original size</dt>
                    <dd>
                      {preview.package.dimensions
                        .map((v) => (v * 1000).toFixed(1))
                        .join(" × ")}{" "}
                      mm
                    </dd>
                  </div>
                  <div>
                    <dt>Mass</dt>
                    <dd>{(preview.mass * 1000).toFixed(1)} g</dd>
                  </div>
                  <div>
                    <dt>Visible parts</dt>
                    <dd>
                      {
                        preview.package.geoms.filter(
                          (g) => g.group !== 3 && g.group !== 4,
                        ).length
                      }
                    </dd>
                  </div>
                  <div>
                    <dt>Collision parts</dt>
                    <dd>
                      {
                        preview.package.geoms.filter(
                          (g) => g.contype || g.conaffinity,
                        ).length
                      }
                    </dd>
                  </div>
                </dl>
                <p>
                  Original colors, center of mass, inertia and contact settings
                  retained. Ready to place on your table.
                </p>
              </div>
            )}
            <p className="import-note">
              Folder: up to 20 MB / 256 files. ZIP: up to 10 MB (20 MB
              expanded). Includes local XML and OBJ/STL meshes. Moving internal
              joints and image textures are not supported yet. Floors and lights
              from the example scene stay out of your workspace.
            </p>
          </>
        )}
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button
          className="primary-action"
          disabled={busy || (mode === "mesh" ? !file : !zip && !files.length)}
          onClick={() => void submit()}
        >
          <Upload size={15} />
          {busy
            ? "Preparing object…"
            : mode === "package" && !preview
              ? "Review package"
              : "Import and place"}
        </button>
      </div>
    </div>
  );
}
