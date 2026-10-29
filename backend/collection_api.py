"""UI-facing collection control; no caller-supplied filesystem paths."""

import asyncio
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse
from .collection_schema import CollectionConfig, VIEWS
from .schema import MAX_SCENE_BYTES
from .collection_scenes import collection_scene, collection_catalog

router = APIRouter()


@router.get("/api/collection")
def capabilities(request: Request):
    jobs = request.app.state.collection
    return {
        "ready": jobs.ready(),
        "format": "LeRobot v3.0",
        "lerobot_version": "0.6.1",
        "cameras": list(VIEWS),
        "root": str(jobs.root),
        "defaults": CollectionConfig().model_dump(),
        "scenes": collection_catalog(),
    }


@router.get("/api/collection/jobs")
def list_jobs(request: Request):
    return request.app.state.collection.list()


@router.post("/api/sessions/{sid}/collection")
async def start(sid: str, request: Request):
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 64_000:
            raise HTTPException(413, "Collection settings too large")
    config = CollectionConfig.model_validate_json(body)
    try:
        session = request.app.state.sessions.get(sid)
    except KeyError as exc:
        raise HTTPException(404, "Session not found") from exc
    with session.lock:
        if session.sim.running:
            raise ValueError("Pause the simulation before starting collection")
        source = collection_scene(session.sim.export_scene(), config.scene_id)
        if not source.task.source or not source.task.target:
            raise ValueError(
                "Choose a pick object and destination, or load a task example first"
            )
        if len(source.model_dump_json().encode()) > MAX_SCENE_BYTES:
            raise ValueError("Scene exceeds collection size limit")
    return await asyncio.to_thread(
        request.app.state.collection.start, source, config, sid
    )


def get_job(request, job_id):
    try:
        return request.app.state.collection.get(job_id)
    except KeyError as exc:
        raise HTTPException(404, "Collection job not found") from exc


@router.get("/api/collection/jobs/{job_id}")
def status(job_id: str, request: Request):
    return get_job(request, job_id)


@router.post("/api/collection/jobs/{job_id}/cancel")
def cancel(job_id: str, request: Request):
    get_job(request, job_id)
    return request.app.state.collection.cancel(job_id)


@router.get("/api/collection/jobs/{job_id}/preview")
def preview(job_id: str, request: Request):
    get_job(request, job_id)
    path = request.app.state.collection.directory(job_id) / "preview.jpg"
    if not path.exists():
        raise HTTPException(404, "No frames captured yet")
    return FileResponse(
        path, media_type="image/jpeg", headers={"Cache-Control": "no-store"}
    )


@router.get("/api/collection/jobs/{job_id}/download")
async def download(job_id: str, request: Request):
    get_job(request, job_id)
    path, name = await asyncio.to_thread(request.app.state.collection.archive, job_id)
    return FileResponse(path, media_type="application/zip", filename=name)


def visualization_source(request, job_id):
    from .collection_jobs import RUNTIME
    from .collection_visualization import load_index

    status = get_job(request, job_id)
    if not status["download_available"]:
        raise HTTPException(
            409, "Dataset must be finalized and verified before visualization"
        )
    directory = request.app.state.collection.directory(job_id).resolve()
    root = (directory / "dataset").resolve()
    if not root.is_relative_to(directory):
        raise HTTPException(404, "Dataset not found")
    return root, load_index(root, RUNTIME)


@router.get("/api/collection/jobs/{job_id}/visualization")
def visualization(job_id: str, request: Request):
    import copy

    _, index = visualization_source(request, job_id)
    public = copy.deepcopy(index)
    for entry in public["episodes"]:
        for view, video in entry["videos"].items():
            video.pop("path")
            video["url"] = (
                f"/api/collection/jobs/{job_id}/episodes/{entry['index']}/video/{view}"
            )
    return public


def visualization_episode(request, job_id, episode):
    from .collection_visualization import find_episode

    root, index = visualization_source(request, job_id)
    entry = find_episode(index, episode)
    if entry is None:
        raise HTTPException(404, "Episode not found")
    return root, entry


@router.get("/api/collection/jobs/{job_id}/episodes/{episode}/signals")
def signals(job_id: str, episode: int, request: Request):
    from .collection_visualization import episode_signals

    root, entry = visualization_episode(request, job_id, episode)
    return episode_signals(root, entry)


@router.get("/api/collection/jobs/{job_id}/episodes/{episode}/video/{view}")
def video(job_id: str, episode: int, view: str, request: Request):
    from .collection_visualization import contained_file

    root, entry = visualization_episode(request, job_id, episode)
    if view not in entry["videos"]:
        raise HTTPException(404, "Camera was not recorded in this dataset")
    path = contained_file(root, entry["videos"][view]["path"])
    return FileResponse(path, media_type="video/mp4")
