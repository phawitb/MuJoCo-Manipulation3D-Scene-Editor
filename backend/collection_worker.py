"""One bounded collection job, in a dedicated process and GL context."""

from pathlib import Path
import json
from importlib.metadata import version
import os
import sys
import time
import traceback

from .collection_schema import CollectionConfig, VIEWS
from .collection_commit import commit_episode
from .collection_randomization import episode_scene
from .collection_data import CollectionCancelled, EpisodeRecorder, atomic_json, features
from .schema import Scene
from .simulation import Simulation
from .render import CameraRenderer


def collect(job_dir):
    job_dir = Path(job_dir)
    payload = json.loads((job_dir / "config.json").read_text())
    config = CollectionConfig.model_validate(payload["config"])
    source = Scene.model_validate(payload["scene"])
    status = {
        "id": payload["id"],
        "name": config.name,
        "status": "planning",
        "episode": 0,
        "episodes": config.episodes,
        "saved_episodes": 0,
        "frames": 0,
        "total_frames": 0,
        "seed": config.seed,
        "message": "Rehearsing the captured task",
        "pid": os.getpid(),
        "verified": False,
        "dataset_path": str(job_dir / "dataset"),
        "created_at": payload.get("created_at", time.time()),
    }

    def update(**values):
        status.update(values, updated_at=time.time())
        atomic_json(job_dir / "status.json", status)

    def cancelled():
        return (job_dir / "cancel").exists()

    class CancelSignal:
        def is_set(self):
            return cancelled()

    dataset = None
    manifest = {
        "generator": 1,
        "config": config.model_dump(),
        "cameras": list(VIEWS),
        "physics_hz": 1000,
        "repo_id": f"local/{config.name}",
        "units": {
            "state": "rad",
            "velocity": "rad/s",
            "effort": "Nm",
            "tcp": "meters, WXYZ quaternion",
            "action": "rad",
        },
        "action_semantics": "Actual commanded position target immediately after controller update, before physics integration. Controller runs at 1000 Hz; sampled action is not held for the whole camera interval. Dense trajectory contains every applied control.",
        "attempts": [],
    }
    terminal, error = "completed", None
    active_entry = None
    recorder = None

    def interrupted_attempt(outcome, message):
        if active_entry is not None:
            active_entry.update(
                outcome=outcome,
                message=message,
                success=False,
                frames=recorder.frames if recorder else 0,
                terminal_time=float(sim.data.time),
                dataset_episode_index=None,
            )
            manifest["attempts"].append(active_entry)

    update()
    try:
        from lerobot.configs.video import RGBEncoderConfig
        from lerobot.datasets.lerobot_dataset import LeRobotDataset
        from .planning import calculate_plan

        if cancelled():
            raise CollectionCancelled()
        if not source.task.source or not source.task.target:
            raise ValueError("Choose a pick object and a destination before collecting")
        base = Simulation(source)
        plan = calculate_plan(base, CancelSignal())
        if cancelled():
            raise CollectionCancelled()
        if not plan.get("verified"):
            raise ValueError(
                "Task rehearsal failed: " + plan.get("message", "No valid path")
            )
        manifest["controller_configuration"] = plan["configuration"]
        manifest["runtime_versions"] = {
            package: version(package)
            for package in ("lerobot", "mujoco", "numpy", "scipy", "pydantic", "pillow")
        }
        manifest["runtime_versions"]["python"] = sys.version.split()[0]
        width, height = map(int, config.resolution.split("x"))
        joint_names = [base.model.joint(i).name for i in range(6)]
        manifest["joint_names"] = joint_names
        writer_options = dict(
            repo_id=manifest["repo_id"],
            root=job_dir / "dataset",
            video_backend="pyav",
            rgb_encoder=RGBEncoderConfig(
                vcodec="h264", pix_fmt="yuv420p", crf=18, preset="fast", g=config.fps
            ),
            encoder_threads=2,
            image_writer_threads=0,
        )
        dataset = LeRobotDataset.create(
            **writer_options,
            fps=config.fps,
            robot_type="so101_mujoco",
            features=features(width, height, joint_names),
            use_videos=True,
            metadata_buffer_size=1,
        )
        for attempt in range(config.episodes):
            if cancelled():
                raise CollectionCancelled()
            if dataset is None:
                dataset = LeRobotDataset.resume(**writer_options)
            seed = config.seed + attempt
            scene = episode_scene(source, config.variation, seed)
            sim = Simulation(scene)
            sim.policy.configuration = plan["configuration"]
            sim.start_policy()
            recorder = None
            active_entry = {
                "attempt": attempt,
                "seed": seed,
                "scene": scene.model_dump(),
            }
            update(
                status="recording",
                episode=attempt + 1,
                frames=0,
                seed=seed,
                simulation_time=0,
                message=f"Recording episode {attempt + 1}",
            )

            def sample(frames, sim_time, preview):
                if frames == 1 or frames % max(1, config.fps // 2) == 0:
                    from PIL import Image

                    temporary = job_dir / "preview.tmp"
                    Image.fromarray(preview).save(temporary, format="JPEG", quality=80)
                    os.replace(temporary, job_dir / "preview.jpg")
                    update(frames=frames, simulation_time=sim_time)

            with CameraRenderer(sim, width, height) as renderer:
                recorder = EpisodeRecorder(dataset, renderer, config, sample, cancelled)
                while sim.running and sim.data.time < config.max_seconds - 0.0000001:
                    sim.step(
                        min(
                            1000 // config.fps,
                            round((config.max_seconds - sim.data.time) * 1000),
                        ),
                        before_step=recorder.before_step,
                    )
            success = sim.policy.success
            outcome = "succeeded" if success else "timeout" if sim.running else "failed"
            keep = recorder.frames > 0 and (success or config.include_failed)
            entry = {
                "attempt": attempt,
                "seed": seed,
                "success": success,
                "outcome": outcome,
                "message": sim.policy.message,
                "terminal_time": float(sim.data.time),
                "frames": recorder.frames,
                "dataset_episode_index": status["saved_episodes"] if keep else None,
                "scene": scene.model_dump(),
            }
            if keep:
                update(
                    status="encoding",
                    frames=recorder.frames,
                    message="Encoding all five camera streams",
                )
                try:
                    commit_episode(dataset, recorder, entry, job_dir / "dataset")
                finally:
                    # commit_episode closes the writer, including on rollback.
                    dataset = None
                status["saved_episodes"] += 1
                status["total_frames"] += recorder.frames
            else:
                dataset.clear_episode_buffer()
            manifest["attempts"].append(entry)
            active_entry = None
            update()
    except CollectionCancelled:
        terminal = "cancelled"
        interrupted_attempt("cancelled", "Incomplete episode discarded by request")
        if dataset is not None:
            dataset.clear_episode_buffer()
    except Exception as exc:
        terminal, error = "failed", str(exc)
        interrupted_attempt("error", str(exc))
        traceback.print_exc()
        if dataset is not None:
            try:
                dataset.clear_episode_buffer()
            except Exception:
                pass
    finally:
        if (job_dir / "dataset/meta").exists():
            try:
                update(
                    status="finalizing",
                    message="Finalizing and reading back the dataset",
                )
                if dataset is not None:
                    dataset.finalize()
                manifest.update(status=terminal, error=error)
                atomic_json(job_dir / "dataset/meta/collection.json", manifest)
                if status["saved_episodes"]:
                    from .collection_validate import verify_dataset

                    verification = verify_dataset(job_dir / "dataset")
                    atomic_json(
                        job_dir / "dataset/meta/collection-verification.json",
                        verification,
                    )
                    status["verified"] = True
            except Exception as exc:
                terminal, error = (
                    "failed",
                    f"Dataset finalization/verification failed: {exc}",
                )
                traceback.print_exc()
        message = error or (
            f"{status['saved_episodes']} episodes saved"
            if status["saved_episodes"]
            else "No complete episodes saved; inspect the task or enable failed episodes"
        )
        update(status=terminal, message=message, error=error, finished_at=time.time())
    return 1 if terminal == "failed" else 0


if __name__ == "__main__":
    sys.exit(collect(sys.argv[1]))
