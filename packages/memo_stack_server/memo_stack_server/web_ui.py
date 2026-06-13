"""Static memory browser mount."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from starlette.staticfiles import StaticFiles


def mount_web_ui(app: FastAPI, *, enabled: bool) -> None:
    if not enabled:
        return
    web_root = Path(__file__).with_name("web")
    assets_root = web_root / "assets"
    app.mount(
        "/ui/assets",
        StaticFiles(directory=str(assets_root), check_dir=True),
        name="memo-stack-ui-assets",
    )

    @app.get("/ui", include_in_schema=False)
    async def memo_stack_ui_redirect() -> RedirectResponse:
        return RedirectResponse(url="/ui/")

    @app.get("/ui/", include_in_schema=False)
    async def memo_stack_ui_index() -> FileResponse:
        return FileResponse(web_root / "index.html")
