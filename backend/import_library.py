"""Local, portable imported templates; no dependency on a running scene."""

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import threading

from .schema import SceneObject, MAX_SCENE_BYTES

_LOCK = threading.RLock()
_ASSET_ID = re.compile(r"imported_[0-9a-f]{64}\Z")


class ImportLibrary:
    def __init__(self, root=None, *, max_assets=256, max_bytes=256_000_000):
        self.root = Path(
            root
            or os.environ.get("SO101_IMPORT_LIBRARY")
            or Path(__file__).resolve().parents[1] / "imported-assets"
        )
        self.max_assets = max_assets
        self.max_bytes = max_bytes

    @contextmanager
    def _write_lock(self):
        self.root.mkdir(parents=True, exist_ok=True)
        with _LOCK, (self.root / ".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def _path(self, asset_id):
        if not _ASSET_ID.fullmatch(asset_id):
            raise KeyError("Imported asset not found")
        return self.root / (asset_id + ".json")

    def get(self, asset_id):
        path = self._path(asset_id)
        try:
            with path.open("rb") as stream:
                data = stream.read(MAX_SCENE_BYTES + 1)
        except FileNotFoundError as exc:
            raise KeyError("Imported asset not found") from exc
        if len(data) > MAX_SCENE_BYTES:
            raise ValueError("Saved imported asset exceeds its size limit")
        obj = SceneObject.model_validate_json(data)
        if obj.asset not in ("mesh", "mujoco"):
            raise ValueError("Library entries must be imported objects")
        return obj

    def _summary(self, asset_id, obj):
        if obj.package:
            dimensions = obj.package.dimensions
        else:
            dimensions = [
                max(obj.mesh.vertices[i::3]) - min(obj.mesh.vertices[i::3])
                for i in range(3)
            ]
        return dict(
            id=asset_id,
            name=obj.name,
            category="Imported",
            dimensions=[d * obj.scale for d in dimensions],
            mass=obj.mass,
            color=obj.color,
            imported=True,
            description=(
                "MuJoCo package · original physics"
                if obj.package
                else "Imported mesh · convex hull collision"
            ),
        )

    def list(self):
        return sorted(
            (
                self._summary(path.stem, self.get(path.stem))
                for path in self.root.glob("imported_*.json")
            ),
            key=lambda item: (item["name"].casefold(), item["id"]),
        )

    def save(self, obj):
        # Revalidate to avoid accepting unchecked model_copy updates from callers.
        obj = SceneObject.model_validate(obj.model_dump())
        if obj.asset not in ("mesh", "mujoco"):
            raise ValueError("Only imported mesh or MuJoCo objects can be saved")
        obj.id = "imported_template"
        obj.position = [0, 0, 0]
        obj.quaternion = [1, 0, 0, 0]
        identity = obj.model_dump(exclude={"id", "position", "quaternion", "name"})
        digest = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        asset_id = "imported_" + digest
        target = self._path(asset_id)
        data = obj.model_dump_json().encode()
        if len(data) > MAX_SCENE_BYTES:
            raise ValueError("Imported object exceeds the library asset size limit")
        with self._write_lock():
            if target.exists():
                return self._summary(asset_id, self.get(asset_id))
            entries = list(self.root.glob("imported_*.json"))
            if (
                len(entries) >= self.max_assets
                or sum(p.stat().st_size for p in entries) + len(data) > self.max_bytes
            ):
                raise ValueError(
                    "Imported library is full; archive unused files from its local storage folder"
                )
            temp_path = None
            try:
                with tempfile.NamedTemporaryFile(
                    dir=self.root, prefix=".import-", delete=False
                ) as stream:
                    temp_path = Path(stream.name)
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temp_path, target)
                with _directory_fd(self.root) as directory:
                    os.fsync(directory)
            finally:
                if temp_path is not None:
                    temp_path.unlink(missing_ok=True)
        return self._summary(asset_id, obj)


@contextmanager
def _directory_fd(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        yield fd
    finally:
        os.close(fd)
