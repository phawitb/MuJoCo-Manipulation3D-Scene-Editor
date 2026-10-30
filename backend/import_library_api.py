"""Library writes reference a successfully placed object, never upload previews."""

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter()


@router.get("/api/imported-assets")
def imported_assets(request: Request):
    try:
        return request.app.state.imported_assets.list()
    except (OSError, ValueError) as exc:
        raise HTTPException(503, f"Imported library could not be read: {exc}") from exc


@router.get("/api/imported-assets/{asset_id}")
def imported_asset(asset_id: str, request: Request):
    try:
        return request.app.state.imported_assets.get(asset_id).model_dump()
    except KeyError as exc:
        raise HTTPException(404, "Imported asset not found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(503, f"Imported asset could not be read: {exc}") from exc


@router.post("/api/imported-assets")
def save_imported_asset(
    request: Request,
    session_id: str = Query(max_length=64),
    object_id: str = Query(max_length=64),
):
    try:
        session = request.app.state.sessions.get(session_id)
    except KeyError as exc:
        raise HTTPException(404, "Scene session not found") from exc
    with session.lock:
        obj = next(
            (
                o.model_copy(deep=True)
                for o in session.sim.scene.objects
                if o.id == object_id
            ),
            None,
        )
    if obj is None:
        raise HTTPException(
            404, "Place the imported object in the scene before saving it"
        )
    try:
        return request.app.state.imported_assets.save(obj)
    except (OSError, ValueError) as exc:
        raise HTTPException(
            503,
            f"Object is placed but could not be saved to the imported library: {exc}",
        ) from exc
