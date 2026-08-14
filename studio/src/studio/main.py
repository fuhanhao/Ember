from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from studio.config import settings
from studio.api.auth import router as auth_router
from studio.api.users import router as users_router
from studio.api.feed import router as feed_router
from studio.api.notebooks import router as notebooks_router
from studio.api.generate import router as generate_router
from studio.api.generated import router as generated_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(feed_router, prefix="/api/v1")
app.include_router(notebooks_router, prefix="/api/v1")
app.include_router(generate_router, prefix="/api/v1")
app.include_router(generated_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ember-studio"}
