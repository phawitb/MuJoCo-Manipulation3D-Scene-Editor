"""Disposable backend + built UI for imported-library browser tests."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.staticfiles import StaticFiles
import uvicorn

from backend.main import app


if __name__ == "__main__":
    with TemporaryDirectory(prefix="so101-library-browser-") as storage:
        os.environ["SO101_IMPORT_LIBRARY"] = storage
        app.mount(
            "/",
            StaticFiles(
                directory=Path(__file__).resolve().parents[2] / "frontend" / "dist",
                html=True,
            ),
            name="test-ui",
        )
        uvicorn.run(app, host="127.0.0.1", port=18865, log_level="warning")
