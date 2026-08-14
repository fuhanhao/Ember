import pathlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from mine.config import settings
from mine.api.health import router as health_router
from mine.api.sources import router as sources_router
from mine.api.articles import router as articles_router
from mine.api.monitor import router as monitor_router
from mine.api.lifecycle import router as lifecycle_router
from mine.api.cookies import router as cookies_router
from mine.api.apify_keys import router as apify_keys_router

STATIC_DIR = pathlib.Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(sources_router, prefix="/mine/v1")
app.include_router(articles_router, prefix="/mine/v1")
app.include_router(monitor_router, prefix="/mine/v1")
app.include_router(lifecycle_router, prefix="/mine/v1")
app.include_router(cookies_router, prefix="/mine/v1")
app.include_router(apify_keys_router, prefix="/mine/v1")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")
