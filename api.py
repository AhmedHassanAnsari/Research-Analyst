import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from Agent import Output, run_research

app = FastAPI(title="Research Analyst API")

origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ResearchRequest(BaseModel):
    query: str
    user_id: str | None = None
    session_id: str | None = None


@app.post("/research")
async def research(request: ResearchRequest) -> Output:
    return await run_research(
        request.query,
        user_id=request.user_id,
        session_id=request.session_id,
    )
