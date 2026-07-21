from fastapi import FastAPI

from src.routers import chat, health, search

app = FastAPI(title="arXiv Paper Curator")

app.include_router(health.router)
app.include_router(search.router)
app.include_router(chat.router)
