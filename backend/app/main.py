"""backend/app/main.py"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import get_services
from app.api.routes import evaluations, framework, health, upload
from app.core.config import get_settings
from app.core.errors import install_handlers
from app.core.logging import setup_logging
from app.jobs.cleanup import run_cleanup

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    svc = get_services()          # loads and validates the framework at startup

    async def janitor():
        while True:
            try:
                run_cleanup(svc)
            except Exception:
                log.exception("cleanup failed")
            await asyncio.sleep(3600)

    task = asyncio.create_task(janitor())
    yield
    task.cancel()


app = FastAPI(title="STRaWBERRY-LLM", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
install_handlers(app)

app.include_router(health.router, prefix="/api")
app.include_router(framework.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(evaluations.router, prefix="/api")