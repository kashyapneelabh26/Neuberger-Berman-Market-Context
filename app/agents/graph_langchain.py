import os
from typing import Dict
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from ..tools.data_fetchers import fetch_kpis
from ..tools.kpi_compute import normalize_kpis
from ..prompt_loader import Prompt
from ..tools import retrieval

llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL","gpt-4o-mini"), temperature=0.2)

def run_graph(req, rs) -> Dict:

    kpis = normalize_kpis(fetch_kpis(req.as_of_period_end, rs["benchmark_id"]))

    planner = Prompt("planner").render({"kpis_json": kpis, "banned_phrases": "we expect, we believe, positioned to"})
    
    wvars = {**kpis, "as_of": str(req.as_of_period_end), "benchmark_id": rs["benchmark_id"],
             "banned_phrases": "we expect, we believe, positioned to", "word_target_min":200, "word_target_max":300,
             "style_exemplars": "\n---\n".join(retrieval.get_style_exemplars(k=2)), "plan_text": planner}
    
    wtext = Prompt("writer").render(wvars)
    
    draft = (ChatPromptTemplate.from_messages([("system","You are a factual financial writing assistant. Avoid outlook and attribution."),("user","{p}")]) | llm).invoke({"p": wtext}).content
    
    ctext = Prompt("compliance").render({"draft_text": draft, "kpis_json": kpis, "banned_phrases": "we expect, we believe, positioned to", "word_target_min":200, "word_target_max":300})
    
    final_text = (ChatPromptTemplate.from_messages([("system","Ensure scope and numeric fidelity."),("user","{p}")]) | llm).invoke({"p": ctext}).content
    
    return {"final_text": final_text.strip(), "kpis": kpis}
