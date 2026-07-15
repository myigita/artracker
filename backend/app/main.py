from fastapi import FastAPI
from .routes import router, subjects_router, platforms_router

app = FastAPI()
app.include_router(router)
app.include_router(subjects_router)
app.include_router(platforms_router)