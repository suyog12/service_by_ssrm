from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import get_pool, close_pool
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.users import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — initialize DB pool
    await get_pool()
    print("Database pool initialized")
    yield
    # Shutdown — close DB pool
    await close_pool()
    print("Database pool closed")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # tighten this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running"
    }