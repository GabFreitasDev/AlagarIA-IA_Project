from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401
from app.config import get_settings
from app.database import init_database
from app.routes.health import router as health_router
from app.routes.ingestion import router as ingestion_router
from app.routes.risk import router as risk_router

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="API para consumo do JSON Gold de risco por bairro.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_database()


app.include_router(health_router)
app.include_router(ingestion_router)
app.include_router(risk_router)
