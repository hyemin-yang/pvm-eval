from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from pvm.core.errors import (
    AlreadyInitializedError,
    InvalidPromptTemplateError,
    NotValidProjectError,
    PromptNotFoundError,
    VersionNotFoundError,
)
from server.db.engine import Base, engine
from server.db import models as _models  # noqa: F401 — ensure models are registered
from server.routers import pages, projects, prompts, snapshots
from server.services.project_service import ProjectNotFoundError

_STATIC_DIR = Path(__file__).parent / "ui" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="pvm server",
    description="Prompt version management — REST API",
    version="0.1.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

# UI pages (no prefix)
app.include_router(pages.router)

# JSON API
app.include_router(projects.router)
app.include_router(prompts.router)
app.include_router(snapshots.router)


# ── Exception handlers ───────────────────────────────────────────────────────


@app.exception_handler(ProjectNotFoundError)
async def _project_not_found(request: Request, exc: ProjectNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"error": str(exc)})


@app.exception_handler(PromptNotFoundError)
async def _prompt_not_found(request: Request, exc: PromptNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"error": str(exc)})


@app.exception_handler(VersionNotFoundError)
async def _version_not_found(request: Request, exc: VersionNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"error": str(exc)})


@app.exception_handler(InvalidPromptTemplateError)
async def _invalid_template(request: Request, exc: InvalidPromptTemplateError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"error": str(exc)})


@app.exception_handler(AlreadyInitializedError)
async def _already_initialized(request: Request, exc: AlreadyInitializedError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"error": str(exc)})


@app.exception_handler(NotValidProjectError)
async def _not_valid_project(request: Request, exc: NotValidProjectError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"error": str(exc)})


# ── Entry point ───────────────────────────────────────────────────────────────


def run(host: str = "0.0.0.0", port: int = 8080, reload: bool = False) -> None:
    uvicorn.run("server.main:app", host=host, port=port, reload=reload)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="pvm-server")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface to bind")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args(argv)
    run(host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
