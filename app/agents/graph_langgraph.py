# app/agents/graph_langgraph.py
from typing import Dict, TypedDict
from langgraph.graph import StateGraph, END
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from ..tools.data_fetchers import fetch_kpis
from ..tools.kpi_compute import normalize_kpis
from ..prompt_loader import Prompt
from ..tools import retrieval

import os

# single LLM config (works with OpenAI / Azure OpenAI via env)
llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL","gpt-4o-mini"), temperature=0.2)

class MCState(TypedDict):
    req: dict    # GenerateRequest.model_dump()
    rs: dict     # resolved strategy (benchmark_id, asset_class)
    kpis: dict   # normalized KPI dict (source of truth)
    draft: str
    final: str

def writer_node(state: MCState) -> MCState:
    kpis = state["kpis"]
    style = "\n---\n".join(retrieval.get_style_exemplars(2))

    # 1) plan from KPIs
    plan = Prompt("planner").render({
        "kpis_json": kpis,
        "banned_phrases": "we expect, we believe, positioned to",
    })

    # 2) writer prompt (data-bound)
    wtext = Prompt("writer").render({
        **kpis,
        "as_of": state["req"]["as_of_period_end"],
        "benchmark_id": state["rs"]["benchmark_id"],
        "banned_phrases": "we expect, we believe, positioned to",
        "word_target_min": 200,
        "word_target_max": 300,
        "style_exemplars": style,
        "plan_text": plan,
    })

    # 3) system tone charter (optional but recommended)
    tone_system = ""
    try:
        tone_system = Prompt("tone_system").render({"style_exemplars": style})
    except Exception:
        pass  # if tone_system prompt not present, continue gracefully

    chain = ChatPromptTemplate.from_messages([
        ("system", tone_system or "Write in a professional, neutral, client-friendly tone; no outlook or attribution."),
        ("system", "You are a factual financial writing assistant. Use only the provided KPIs for numbers."),
        ("user", "{p}"),
    ]) | llm

    draft = chain.invoke({"p": wtext}).content
    state["draft"] = draft
    return state

def compliance_node(state: MCState) -> MCState:
    kpis = state["kpis"]
    ctext = Prompt("compliance").render({
        "draft_text": state["draft"],
        "kpis_json": kpis,
        "banned_phrases": "we expect, we believe, positioned to",
        "word_target_min": 200,
        "word_target_max": 300,
    })

    chain = ChatPromptTemplate.from_messages([
        ("system", "Ensure scope (no outlook/attribution) and exact numeric fidelity; if a number is not in KPIs, remove that sentence."),
        ("user", "{p}"),
    ]) | llm

    state["final"] = chain.invoke({"p": ctext}).content.strip()
    return state

def run_graph(req, rs) -> Dict:
    # fetch + normalize KPIs (MOCK=true returns stubs)
    kpis = normalize_kpis(fetch_kpis(req.as_of_period_end, rs["benchmark_id"]))

    graph = StateGraph(MCState)
    graph.add_node("writer", writer_node)
    graph.add_node("compliance", compliance_node)
    graph.set_entry_point("writer")
    graph.add_edge("writer", "compliance")
    graph.add_edge("compliance", END)

    app = graph.compile()
    out = app.invoke({
        "req": req.model_dump(),
        "rs": rs,
        "kpis": kpis,
        "draft": "",
        "final": "",
    })
    return {"final_text": out["final"], "kpis": kpis}
