from fastapi import FastAPI

from src.routers import health, search

app = FastAPI(title="arXiv Paper Curator")

app.include_router(health.router)
app.include_router(search.router)
