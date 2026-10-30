import type { Asset, AssetId, SceneObject, Vec3 } from "./types";

async function libraryRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const data = await response.json();
  if (!response.ok)
    throw Error(
      typeof data.detail === "string"
        ? data.detail
        : "Imported library is unavailable",
    );
  return data as T;
}

export const listImportedAssets = () =>
  libraryRequest<Asset[]>("/api/imported-assets");
export const getImportedTemplate = (id: string) =>
  libraryRequest<SceneObject>(`/api/imported-assets/${encodeURIComponent(id)}`);
export const saveImportedAsset = (sessionId: string, objectId: string) =>
  libraryRequest<Asset>(
    `/api/imported-assets?${new URLSearchParams({ session_id: sessionId, object_id: objectId })}`,
    { method: "POST" },
  );

export function instantiateAsset(
  asset: Asset,
  position: Vec3,
  template?: SceneObject,
): SceneObject {
  if (asset.imported && !template)
    throw Error("Imported object template is unavailable");
  const id = `object_${crypto.randomUUID().replaceAll("-", "")}`;
  if (template)
    return {
      ...structuredClone(template),
      id,
      position: [...position],
      quaternion: [1, 0, 0, 0],
    };
  return {
    id,
    name: asset.name,
    asset: asset.id as AssetId,
    position,
    quaternion: [1, 0, 0, 0],
    scale: 1,
    mass: asset.mass,
    friction: [0.7, 0.005, 0.0001],
    collision: true,
    color: asset.color,
  };
}
