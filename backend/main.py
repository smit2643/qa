import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from core.logging import setup_logging

logger = setup_logging()


def create_app() -> FastAPI:
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            traces_sample_rate=0.1,
        )

    app = FastAPI(
        title="Bug0 API",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    from modules.auth.router import router as auth_router
    from modules.organizations.router import router as orgs_router
    from modules.projects.router import router as projects_router
    from modules.suites.router import router as suites_router
    from modules.tests.router import router as tests_router
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(orgs_router, prefix="/api/v1")
    app.include_router(projects_router, prefix="/api/v1")
    app.include_router(suites_router, prefix="/api/v1")
    app.include_router(tests_router, prefix="/api/v1")

    @app.get("/health", tags=["system"])
    def health():
        return {"status": "ok", "environment": settings.environment}

    logger.info(f"Bug0 API starting in {settings.environment} mode")
    return app


app = create_app()
