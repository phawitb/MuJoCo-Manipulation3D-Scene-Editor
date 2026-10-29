"""Rollback a failed episode without copying previously encoded videos.

The pinned official writer's resume() starts new data/video shards. Finalize each
committed episode and reopen with resume before recording the next one, so only
metadata is mutable across commits. A regression injects a failure after one
camera of the second episode has already been written.
"""

from contextlib import suppress
from pathlib import Path
import shutil
from .collection_data import atomic_json


def commit_episode(dataset, recorder, entry, root):
    root = Path(root)
    metadata = root / "meta"
    checkpoint = root.parent / "metadata-checkpoint"
    shutil.copytree(metadata, checkpoint)
    existing = {
        p.relative_to(root)
        for p in root.rglob("*")
        if p.is_file() and "images" not in p.relative_to(root).parts
    }
    restored = False
    try:
        dataset.save_episode(parallel_encoding=False)
        index = entry["dataset_episode_index"]
        recorder.save_trace(root / f"trajectories/episode_{index:06}.npz")
        atomic_json(metadata / f"collection/episode_{index:06}.json", entry)
        dataset.finalize()
        restored = True
    except Exception:
        # Close buffered Parquet writers before removing incomplete shards.
        with suppress(Exception):
            dataset.finalize()
        # The pinned writer retries finalize() from destructors. Detach its
        # remaining handles before restoration so a later retry cannot mutate
        # restored metadata. Capture uses synchronous image writes, no queues.
        for owner in (dataset.writer, dataset.meta):
            handle = owner._pq_writer
            owner._pq_writer = None
            if handle is not None:
                with suppress(Exception):
                    handle.close()
            owner._finalized = True
        dataset._is_finalized = True
        for path in root.rglob("*"):
            if path.is_file() and path.relative_to(root) not in existing:
                path.unlink()
        shutil.rmtree(metadata)
        shutil.copytree(checkpoint, metadata)
        restored = True
        raise
    finally:
        if restored:
            shutil.rmtree(checkpoint)
