"""Local process ownership and safe output paths for collection jobs."""

from pathlib import Path
from uuid import uuid4
import json
import os
import re
import subprocess
import threading
import time
import zipfile
from .collection_data import atomic_json

PROJECT = Path(__file__).resolve().parents[1]
RUNTIME = PROJECT / ".venv-collect/bin/python"
TERMINAL = {"completed", "cancelled", "failed", "interrupted"}


class CollectionJobs:
    def __init__(self):
        self.root = Path(
            os.environ.get("SO101_RECORDINGS_DIR", PROJECT / "recordings")
        ).resolve()
        self.processes = {}
        self.lock = threading.RLock()

    def ready(self):
        return RUNTIME.exists() and bool(
            list(
                (PROJECT / ".venv-collect/lib").glob(
                    "python*/site-packages/lerobot-0.6.1.dist-info"
                )
            )
        )

    def directory(self, job_id):
        if not re.fullmatch(r"[0-9a-f]{32}", job_id):
            raise KeyError("Collection job does not exist")
        path = self.root / job_id
        if not (path / "config.json").is_file():
            raise KeyError("Collection job does not exist")
        return path

    def get(self, job_id):
        with self.lock:
            directory = self.directory(job_id)
            status = json.loads((directory / "status.json").read_text())
            process = self.processes.get(job_id)
            if status["status"] not in TERMINAL:
                dead = process is not None and process.poll() is not None
                pid_file = directory / "worker.pid"
                pid = status.get("pid") or (
                    int(pid_file.read_text()) if pid_file.exists() else None
                )
                if process is None and pid:
                    try:
                        os.kill(pid, 0)
                    except ProcessLookupError:
                        dead = True
                    except PermissionError:
                        pass
                if dead:
                    status.update(
                        status="interrupted",
                        message="Worker stopped before finishing. Completed output is available only after verification.",
                        updated_at=time.time(),
                    )
                    atomic_json(directory / "status.json", status)
            status["cancel_requested"] = (directory / "cancel").exists()
            status["download_available"] = status["status"] in TERMINAL and status.get(
                "verified", False
            )
            if "successful_episodes" not in status:
                manifest = directory / "dataset/meta/collection.json"
                if manifest.is_file():
                    retained = [
                        a
                        for a in json.loads(manifest.read_text()).get("attempts", [])
                        if a.get("dataset_episode_index") is not None
                    ]
                    status["successful_episodes"] = sum(
                        bool(a.get("success")) for a in retained
                    )
                    status["unsuccessful_episodes"] = (
                        len(retained) - status["successful_episodes"]
                    )
            return status

    def list(self):
        if not self.root.exists():
            return []
        paths = sorted(
            self.root.glob("*/config.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:100]
        return [self.get(p.parent.name) for p in paths]

    def start(self, scene, config, session_id):
        with self.lock:
            if not self.ready():
                raise ValueError(
                    "Collection runtime is not installed. Run bash scripts/setup-collection.sh"
                )
            if any(s["status"] not in TERMINAL for s in self.list()):
                raise ValueError(
                    "A collection job is already running. Stop it or wait for it to finish."
                )
            job_id = uuid4().hex
            directory = self.root / job_id
            directory.mkdir(parents=True)
            created = time.time()
            atomic_json(
                directory / "config.json",
                {
                    "id": job_id,
                    "session_id": session_id,
                    "created_at": created,
                    "scene": scene.model_dump(),
                    "config": config.model_dump(),
                },
            )
            status = {
                "id": job_id,
                "name": config.name,
                "scene_id": config.scene_id,
                "scene_name": scene.name,
                "max_attempts": config.max_attempts,
                "status": "queued",
                "episode": 0,
                "episodes": config.episodes,
                "saved_episodes": 0,
                "frames": 0,
                "total_frames": 0,
                "seed": config.seed,
                "verified": False,
                "message": "Starting collection worker",
                "created_at": created,
                "dataset_path": str(directory / "dataset"),
            }
            atomic_json(directory / "status.json", status)
            try:
                with (directory / "worker.log").open("w") as output:
                    process = subprocess.Popen(
                        [
                            str(RUNTIME),
                            "-m",
                            "backend.collection_worker",
                            str(directory),
                        ],
                        cwd=PROJECT,
                        stdout=output,
                        stderr=subprocess.STDOUT,
                        env={
                            **os.environ,
                            "HF_HUB_OFFLINE": "1",
                            "HF_DATASETS_OFFLINE": "1",
                            "TOKENIZERS_PARALLELISM": "false",
                        },
                    )
                self.processes[job_id] = process
                (directory / "worker.pid").write_text(str(process.pid))
            except Exception as exc:
                status.update(status="failed", message=str(exc))
                atomic_json(directory / "status.json", status)
                raise
            return self.get(job_id)

    def cancel(self, job_id):
        with self.lock:
            status = self.get(job_id)
            if status["status"] not in TERMINAL:
                (self.directory(job_id) / "cancel").touch()
            return self.get(job_id)

    def archive(self, job_id):
        with self.lock:
            status = self.get(job_id)
            if not status["download_available"]:
                raise ValueError("Dataset is not finalized and verified yet")
            directory = self.directory(job_id)
            destination = directory / "dataset.zip"
            if not destination.exists():
                temporary = directory / "dataset.zip.tmp"
                with zipfile.ZipFile(
                    temporary, "w", compression=zipfile.ZIP_STORED
                ) as archive:
                    for path in sorted((directory / "dataset").rglob("*")):
                        if path.is_file() and not path.is_symlink():
                            archive.write(
                                path,
                                Path(status["name"])
                                / path.relative_to(directory / "dataset"),
                            )
                os.replace(temporary, destination)
            return destination, f"{status['name']}-{job_id[:8]}-lerobot.zip"

    def close(self):
        for job_id, process in self.processes.items():
            if process.poll() is None:
                self.cancel(job_id)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                self.get(job_id)
