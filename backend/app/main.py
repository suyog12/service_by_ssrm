from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import get_pool, close_pool
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.users import router as users_router
from app.api.v1.endpoints.roles import router as roles_router
from app.api.v1.endpoints.tenants import router as tenants_router
from app.api.v1.endpoints.menu import router as menu_router 
from app.api.v1.endpoints.ingredients import router as ingredients_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_pool()
    print("Database pool initialized")
    yield
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router,    prefix="/api/v1")
app.include_router(users_router,   prefix="/api/v1")
app.include_router(roles_router,   prefix="/api/v1")
app.include_router(tenants_router, prefix="/api/v1")
app.include_router(menu_router,    prefix="/api/v1")
app.include_router(ingredients_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running"
    }