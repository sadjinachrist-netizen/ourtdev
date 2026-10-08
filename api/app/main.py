from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.core.config import get_settings
from app.modules.auth.router import router as auth_router
from app.modules.contents.router import router as contents_router
from app.modules.events.router import router as events_router
from app.modules.festival.router import router as festival_router
from app.modules.media.router import router as media_router
from app.modules.members.router import router as members_router
from app.modules.programs.router import router as programs_router
from app.modules.projects.router import router as projects_router
from app.modules.resources.router import router as resources_router
from app.modules.users.router import router as users_router
from app.shared.errors import register_exception_handlers
from app.shared.schemas import HealthResponse

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description="API de la plateforme communautaire ourtdev.com (TDEV).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

api_v1 = APIRouter(prefix="/api/v1")


@api_v1.get("/health", response_model=HealthResponse, tags=["health"])
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=__version__,
        env=settings.app_env,
    )


api_v1.include_router(auth_router)
api_v1.include_router(users_router)
api_v1.include_router(contents_router)
api_v1.include_router(festival_router)
api_v1.include_router(events_router)
api_v1.include_router(programs_router)
api_v1.include_router(members_router)
api_v1.include_router(projects_router)
api_v1.include_router(resources_router)
api_v1.include_router(media_router)

app.include_router(api_v1)
