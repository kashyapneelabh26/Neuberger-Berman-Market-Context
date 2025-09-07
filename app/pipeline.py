import os
from typing import Dict
from .schemas import GenerateRequest, GenerateResponse, KPIBundle
from .strategy_defaults import STRATEGY_DEFAULTS, DEFAULTS_BY_ASSET
from .prompt_loader import Prompt
from .tools.data_fetchers import fetch_kpis
from .tools.kpi_compute import normalize_kpis
from .tools import retrieval
from openai import OpenAI

client = OpenAI() if (os.getenv("OPENAI_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY")) else None
BANNED = ["we expect", "we believe", "positioned to"]

def resolve_strategy(req: GenerateRequest) -> Dict[str, str]:

    out = {"benchmark_id": req.benchmark_id, "asset_class": req.asset_class}
    defaults = STRATEGY_DEFAULTS.get(req.strategy_name)
    
    if defaults:
        out["benchmark_id"] = out["benchmark_id"] or defaults["benchmark_id"]
        out["asset_class"] = out["asset_class"] or defaults["asset_class"]
   
    out["asset_class"] = out["asset_class"] or "equities"
    out["benchmark_id"] = out["benchmark_id"] or DEFAULTS_BY_ASSET.get(out["asset_class"], {}).get("benchmark_id", "SPX_TR")
    
    return out

def plan_blocks(kpis: Dict) -> Dict:
    
    rendered = Prompt("planner").render({"kpis_json": kpis, "banned_phrases": ", ".join(BANNED)})
    
    return {"rendered": rendered}

def write_commentary(req: GenerateRequest, kpis: Dict, plan_text: str) -> str:

    exemplars = retrieval.get_style_exemplars(k=2)
    variables = {**kpis, "as_of": str(req.as_of_period_end), "benchmark_id": resolve_strategy(req)["benchmark_id"],
                 "banned_phrases": ", ".join(BANNED), "word_target_min": 200, "word_target_max": 300,
                 "style_exemplars": "\n---\n".join(exemplars), "plan_text": plan_text}
    prompt_text = Prompt("writer").render(variables)

    if client is None:
        return (f"In {variables['as_of']}, {kpis['benchmark_name']} returned {kpis['benchmark_return_pct']}%. "
                f"VIX ended {kpis['vix_end']} and the 10-year Treasury yield finished near {kpis['ten_year_yield']}%. "
                f"Inflation ({kpis['inflation_series']}) was {kpis['inflation_yoy_pct']}% YoY. "
                f"Leaders: {', '.join(kpis['sector_leaders'])}; laggards: {', '.join(kpis['sector_laggards'])}. "
                f"EPS growth {kpis['eps_growth_pct']}% with beat rate {kpis['eps_beat_rate_pct']}%.")
    
    resp = client.chat.completions.create(model=os.getenv("OPENAI_MODEL","gpt-4o-mini"), temperature=0.2,
        messages=[{"role":"system","content":"You are a factual financial writing assistant. Avoid outlook and attribution."},
                  {"role":"user","content": prompt_text}])
    
    return resp.choices[0].message.content.strip()

def compliance_clean(text: str, kpis: Dict) -> str:

    t = text

    for phrase in BANNED:
        t = t.replace(phrase, "")

    if f"{kpis['benchmark_return_pct']}%" not in t:
        t += f" In the period, the benchmark returned {kpis['benchmark_return_pct']}%."
    
    return t.strip()

def generate(req: GenerateRequest) -> GenerateResponse:

    rs = resolve_strategy(req)
    kpis = normalize_kpis(fetch_kpis(req.as_of_period_end, rs["benchmark_id"]))
    plan = plan_blocks(kpis)
    draft = write_commentary(req, kpis, plan["rendered"])
    final = compliance_clean(draft, kpis)

    return GenerateResponse(text=final, kpis=KPIBundle(**kpis),
        assumptions={"benchmark_id": rs["benchmark_id"], "asset_class": rs["asset_class"], "notes":"Baseline (MOCK KPIs if no keys)."})
