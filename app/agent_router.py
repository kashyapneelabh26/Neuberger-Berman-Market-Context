import os
from .schemas import GenerateRequest, GenerateResponse, KPIBundle
from .pipeline import generate as baseline_generate
from .strategy_defaults import STRATEGY_DEFAULTS, DEFAULTS_BY_ASSET

def _resolve(req: GenerateRequest):

    out = {"benchmark_id": req.benchmark_id, "asset_class": req.asset_class}
    d = STRATEGY_DEFAULTS.get(req.strategy_name)

    if d:
        out["benchmark_id"] = out["benchmark_id"] or d["benchmark_id"]
        out["asset_class"] = out["asset_class"] or d["asset_class"]

    out["asset_class"] = out["asset_class"] or "equities"
    out["benchmark_id"] = out["benchmark_id"] or DEFAULTS_BY_ASSET.get(out["asset_class"],{}).get("benchmark_id","SPX_TR")
    
    return out

def generate(req: GenerateRequest, override_backend: str | None = None) -> GenerateResponse:

    backend = (override_backend or os.getenv("AGENT_BACKEND","none")).lower()
    
    if backend == "none":
        return baseline_generate(req)
    
    rs = _resolve(req)
    
    if backend == "crewai":
        from .agents.graph_crewai import run_graph as run
    
    elif backend == "langchain":
        from .agents.graph_langchain import run_graph as run

    elif backend == "langgraph":
        from .agents.graph_langgraph import run_graph as run
    
    else:
        return baseline_generate(req)
    
    result = run(req, rs)
    
    return GenerateResponse(
        text=result["final_text"],
        kpis=KPIBundle(**result["kpis"]),
        assumptions={"benchmark_id": rs["benchmark_id"], "asset_class": rs["asset_class"], "notes": f"Agent backend: {backend}"},
    )

