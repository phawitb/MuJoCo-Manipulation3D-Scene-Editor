import { useCallback, useEffect, useRef, useState } from "react";
import { listImportedAssets, saveImportedAsset } from "./importedAssets";
import type { Asset, Scene } from "./types";

export function useImportedLibrary(
  scene: Scene | undefined,
  sessionId: string | undefined,
) {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [error, setError] = useState("");
  const saved = useRef(new Map<string, Promise<void>>());
  const refresh = useCallback(async () => {
    setAssets(await listImportedAssets());
  }, []);
  const save = useCallback(
    (sid: string, objectId: string) => {
      const key = `${sid}/${objectId}`;
      let pending = saved.current.get(key);
      if (!pending) {
        pending = saveImportedAsset(sid, objectId)
          .then(async () => {
            await refresh();
            setError("");
          })
          .catch((e) => {
            saved.current.delete(key);
            setError(e instanceof Error ? e.message : String(e));
            throw e;
          });
        saved.current.set(key, pending);
      }
      return pending;
    },
    [refresh],
  );
  useEffect(() => {
    void refresh().catch((e) =>
      setError(e instanceof Error ? e.message : String(e)),
    );
  }, [refresh]);
  const migrate = useCallback(async () => {
    if (scene && sessionId) {
      for (const obj of scene.objects) {
        if (obj.asset === "mesh" || obj.asset === "mujoco")
          await save(sessionId, obj.id);
      }
    }
  }, [save, scene, sessionId]);
  useEffect(() => {
    void migrate().catch((e) =>
      setError(e instanceof Error ? e.message : String(e)),
    );
  }, [migrate]);
  return {
    assets,
    error,
    save,
    retry: () => {
      void refresh()
        .then(migrate)
        .then(() => setError(""))
        .catch((e) => setError(e instanceof Error ? e.message : String(e)));
    },
  };
}
