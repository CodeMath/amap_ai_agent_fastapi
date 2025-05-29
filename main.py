from fastapi import FastAPI

from app.agents.api.agent_router import router as agent_router
from dependencies import init_app

app = FastAPI(on_startup=[init_app])

app.include_router(agent_router, prefix="/api")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
