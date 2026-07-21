from fastapi import FastAPI

from src.routers import health

app = FastAPI(title="arXiv Paper Curator")

app.include_router(health.router)
