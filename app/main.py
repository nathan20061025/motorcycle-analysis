from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app import __version__
from app.api import config, events, jobs, videos
from app.core import db
from app.services import jobs as job_service


@asynccontextmanager
async def lifespan(_):
    db.init()
    job_service.mark_stale()
    yield


app = FastAPI(title="Motorcycle Traffic Analysis", version=__version__, lifespan=lifespan)
for r in (videos.router, config.router, jobs.router, events.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": __version__}


app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="ui")
