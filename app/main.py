from fastapi import FastAPI, Query
from fastapi.responses import RedirectResponse
from .schemas import GenerateRequest, GenerateResponse
from .agent_router import generate

app = FastAPI(title="NB Market Context Writer (Agent Toggle)")

# app/main.py
@app.get("/")
def index():
    return {"message": "NB Market Context API. See /docs for Swagger UI."}

@app.get("/swagger")
def swagger_redirect():
    return RedirectResponse(url="/docs")

@app.get("/health")
def health():
	return {"status": "ok"}

@app.post("/generate/market-context", response_model=GenerateResponse)
def route_generate(req: GenerateRequest, backend: str | None = Query(default=None)):
    return generate(req, override_backend=backend)
