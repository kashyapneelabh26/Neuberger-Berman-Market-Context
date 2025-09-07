from typing import Dict
from crewai import Agent, Task, Crew
from ..tools.data_fetchers import fetch_kpis
from ..tools.kpi_compute import normalize_kpis
from ..prompt_loader import Prompt
from ..tools import retrieval

def run_graph(req, rs) -> Dict:
    
    kpis = normalize_kpis(fetch_kpis(req.as_of_period_end, rs["benchmark_id"]))
    planner = Prompt("planner").render({"kpis_json": kpis, "banned_phrases": "we expect, we believe, positioned to"})
    writer_vars = {**kpis, "as_of": str(req.as_of_period_end), "benchmark_id": rs["benchmark_id"],
                   "banned_phrases": "we expect, we believe, positioned to", "word_target_min": 200, "word_target_max": 300,
                   "style_exemplars": "\n---\n".join(retrieval.get_style_exemplars(k=2)), "plan_text": planner}
    
    writer_prompt = Prompt("writer").render(writer_vars)

    WriterAgent = Agent(role="WriterAgent", goal="Write NB-style Market Context.", backstory="No outlook/attribution.", verbose=False, allow_delegation=False)
    
    ComplianceAgent = Agent(role="ComplianceAgent", goal="Enforce scope and numeric fidelity.", backstory="", verbose=False, allow_delegation=False)
    
    draft = Crew(agents=[WriterAgent], tasks=[Task(description=writer_prompt, agent=WriterAgent, expected_output="~200–300 words")], verbose=False).kickoff().raw
    
    comp = Prompt("compliance").render({"draft_text": draft, "kpis_json": kpis, "banned_phrases":"we expect, we believe, positioned to","word_target_min":200,"word_target_max":300})
    
    final_text = Crew(agents=[ComplianceAgent], tasks=[Task(description=comp, agent=ComplianceAgent, expected_output="Clean text")], verbose=False).kickoff().raw
    
    return {"final_text": final_text.strip(), "kpis": kpis}
