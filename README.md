# NB Market Context Writer

> **Purpose:** Generate the **Market Context** section of monthly/quarterly portfolio commentaries with strict numeric fidelity and NB-style tone.  
> **Backends supported:** `none` (baseline template), `crewai`, `langchain`, `langgraph` (my personal favorite for this).  
> **Use modes:** Import as a **Python library** or call via **FastAPI** service.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Problem Focus & Why](#problem-why)
3. [Architecture Overview](#arch-overview)
4. [Data & Guardrails](#data-guardrails)
5. [Prompts & Style Seeding](#prompts-style)
6. [Execution & Usage](#execution-usage)
   - [Run as an API](#run-api)
   - [Call from CLI (curl)](#call-cli)
   - [Use as a Library (Super-Agent Mode)](#use-library)
   - [Run Tests](#run-tests)
7. [Design Decisions](#design-decisions)
8. [Key Assumptions & Trade-offs](#assumptions-tradeoffs)
9. [Extensions (What I’d Add With More Time)](#roadmap)
10. [Operational Notes (Deployment, Observability, Security)](#ops)
11. [Common Errors](#troubleshooting)
12. [Repo Layout](#repo-layout)
13. [API Contract](#api-contract)
14. [Tools Inventory](#tools)
15. [Rationale: Why this Stack vs Alternatives](#rationale)

---

<a id="quick-start"></a>

## 1. Quick Start (To run the code)

```bash
# 1) Enter repo
cd /path/to/nb-market-context

# 2) Python env + deps
python3 -m venv .venv
source .venv/bin/activate          
pip install -r requirements.txt

# 3) Ingest NB style from 3 PDFs (tone seeds)
pip install pdfplumber
# I plan on using LLamaindex parser to extract the text from commentaries in an extension
# copy sample commentaries into data/raw/ and then run this command to generate seeds
python scripts/seed_style.py        # writes numbers-stripped seeds to data/seeds/

# 4) Set keys + mock
export OPENAI_API_KEY='your openai key'       # needed for crewai/langchain/langgraph
export OPENAI_MODEL=gpt-4o-mini     
export MOCK=true                    

# 5) Run API
uvicorn app.main:app --reload

# 6) Run in a new terminal, from repo root, and try all backends

curl -s -X POST 'http://127.0.0.1:8000/generate/market-context?backend=none'      -H 'Content-Type: application/json' -d @samples/sample_request_spx.json | jq

curl -s -X POST 'http://127.0.0.1:8000/generate/market-context?backend=crewai'    -H 'Content-Type: application/json' -d @samples/sample_request_spx.json | jq

curl -s -X POST 'http://127.0.0.1:8000/generate/market-context?backend=langchain' -H 'Content-Type: application/json' -d @samples/sample_request_spx.json | jq

curl -s -X POST 'http://127.0.0.1:8000/generate/market-context?backend=langgraph' -H 'Content-Type: application/json' -d @samples/sample_request_spx.json | jq

# Swagger UI
open http://127.0.0.1:8000/docs    

```

<a id="problem-why"></a>
## 2. Problem Focus & Why

**Goal**  
Automate generation of the **Market Context** section in monthly/quarterly portfolio commentaries so it is timely, consistent, and on-brand—while explicitly excluding attribution, positioning, trades, and outlook.

**Why this matters**  
- **Throughput & consistency:** Product Specialists currently handcraft long sections with wide stylistic variance. Automation standardizes tone and structure across strategies.  
- **Latency reduction:** Time-to-publish shrinks when market facts are assembled and phrased automatically.  
- **Compliance safety:** Tight scope avoids forward-looking statements and attribution claims in this section.  
- **Fund-agnostic reuse:** A single pipeline can serve many strategies when it takes strategy/benchmark as inputs and pulls market data from pluggable sources.

**Key constraints addressed**  
- **Numeric fidelity:** All numbers must come from a single KPI source of truth (benchmark return, rates, inflation, volatility, sectors, earnings). No hallucinated digits.  
- **NB tone:** Output should read like prior NB commentaries. I bias style using **tone seeds** extracted from historical “Market Context” paragraphs (numbers removed).  
- **Scope discipline:** Prompts and a compliance pass forbid attribution/positioning/outlook language.  
- **Auditability:** Prompts are versioned files; KPIs and assumptions are echoed in the response for review.

**Non-goals (out of scope)**  
- Portfolio attribution, trades/positioning, outlook or forecasts  
- Full RAG over internal research (future enhancement)  
- Complex charting/visualization in this prototype

**Success criteria**  
- Generates a 200–300 word Market Context that:  
  - Uses only provided KPIs for all digits  
  - Matches NB tone and avoids banned phrases  
  - Includes a clear, factual benchmark sentence  
- Works across backends (baseline, CrewAI, LangChain, LangGraph) with the same API.

---


<a id="arch-overview"></a>
## 3. Architecture Overview

**High-level flow (two-step agentic pipeline with guardrails)**

```text
fetch_kpis()  ──►  KPI dict (source of truth)
        │
        ▼
   Planner (LLM) ──► outline (no numbers)
        │
        ▼
   Writer (LLM)  ──► 200–300 words, NB tone, uses only KPI digits
        │
        ▼
Compliance (LLM + code) ──► strip outlook/attribution, verify digits, enforce length
        │
        ▼
 Final Market Context text

```
**Why this structure:**
- **Separation of concerns**: planning, drafting, and compliance are distinct steps for clarity and testability.  
- **Determinism on facts**: a single KPI dictionary is the numeric source of truth; prompts forbid any other numbers.  
- **Safety**: the compliance pass removes out-of-scope language (outlook/attribution) and checks digits against KPIs.  
- **Composability**: easy to insert future nodes (Fact Check/RAG, Redline QA, Citations). \

**Selectable Backends**
- **none:** deterministic baseline (no LLM) for smoke tests and outages.\
- **crewai:** persona-style multi-agent execution (Writer + Compliance).\
- **langchain:** simple prompt chain with OpenAI adapters.\
- **langgraph:** explicit graph/state machine (nodes = Writer, Compliance; edges = success/retry).\

**Core modules**

- `app/tools/data_fetchers.py` — fetch_kpis(); switches between MOCK=true and real connectors.
- `app/tools/kpi_compute.py` — normalize_kpis(); validates, coerces types, computes derived fields.
- `app/tools/retrieval.py` — loads sanitized tone seeds from data/seeds/*.txt.
- `prompts/` — versioned prompt templates + JSON sidecars (required vars, temperature).
- `app/agents/*` — backend-specific graphs/runners.
- `app/pipeline.py` — baseline (no‑LLM) template writer.
- `app/agent_router.py` — one entrypoint to select backend and run the flow.
- `app/main.py` — FastAPI thin wrapper for HTTP access.

**Data contract in/out**

- Input (request):
    -  `{ as_of_period_end, strategy_name, benchmark_id, asset_class }`

- Internal facts: KPI dict (benchmark return, VIX, 10Y yield, CPI, sector leaders/laggards, EPS growth & beat rate).\

- Output (response):

    - `{ text, kpis, assumptions }`

**Error Handling and Guard Rails**

- If KPIs are missing/invalid → fail fast with a clear message.
- Compliance node re-checks:
- digits in text ⊆ digits in kpis (tolerant to formatting),
- banned phrases removed,
- word count within bounds; retries if needed (LangGraph path).

**Extension points**

- Plug real KPI sources (FRED, IBES, internal index data).
- Add Fact‑Check (RAG) node over macro notes.
- Add style QA node before finalization.


<a id='data-guardrails'> </a>
## 4. Data & Guardrails

### KPI source of truth
- Single KPI dictionary containing: benchmark return; VIX level/Δ; 10Y yield/Δbp; CPI YoY; sector leaders/laggards; EPS growth & beat rate.
- `MOCK=true` returns stable KPIs for demos. In production, replace with real data sources:
  - Index/sector: internal analytics, Bloomberg/FactSet, or Yahoo Finance.
  - Rates/Inflation: FRED (10Y, CPI).
  - Earnings: FactSet IBES / internal earnings store.

### Guardrails
- Writer prompt: use only KPIs for all numbers.
- Compliance prompt: remove any digits not present in KPIs; strip outlook/attribution; enforce word count.
- Post‑processing backstop: ensure the benchmark return sentence exists.

### Common Queries
- **Q:** Why do I use two LLM calls?
  - **A:** Separation (Writer vs Compliance) improves safety, reduces redlines, and simplifies debugging.

- **Q:** Can I plug in Bloomberg/FactSet?
  - **A:** Yes. Implement provider adapters in `app/tools/data_fetchers.py` returning the same KPI schema.

- **Q:** Can I add Outlook later?
  - **A:** Yes, as a separate node with a different banned-phrase set and distinct prompts, subject to compliance review.

<a id='prompts-style'> </a>

## 5. Prompts & Style Seeding

**Prompts**
- Stored in `prompts/` with `.json` sidecars specifying required variables and temperature.
- `planner.txt` → produce an outline from KPIs (no numbers).
    - ```
        -Task: Turn KPIs into a structured outline the Writer must follow.

        Input KPIs (source of truth):
        {{ kpis_json }}

        Rules:
        - Do not add numbers; just reference which facts SHOULD appear.
        - If a KPI is missing/null, mark the corresponding block "omit".
        - Prioritize macro items with non-trivial moves (e.g., |Δbp| ≥ 5).

        Return an ordered outline of 3–4 bullets:
        - Benchmark return & shock(s)
        - Macro (vol, rates, inflation, FX/commodities if provided)
        - Sector leadership & laggards
        - Earnings (if provided)

        Avoid phrases: {{ banned_phrases }}
 
- `writer.txt` → 200–300 words, NB tone, KPI digits only, follows the plan.
    - ```
        You are a financial analyst at Neuberger Berman.

        Goal: Write a 200–300 word “Market Context” section for client materials.
        Scope: Market context only. Do NOT include attribution, portfolio positioning, trade rationale, or outlook.

        Data policy:
        - Treat the “Facts” block as the ONLY source of numbers. Do not invent, interpolate, or recompute figures.
        - If any field is missing or null, omit that sentence rather than guessing.

        Required order:
        1) Benchmark return and any notable shock(s)
        2) Macro drivers: volatility (VIX), rates (10Y level & Δbp), inflation (series + YoY), FX/commodities (if provided)
        3) Sector rotation: 2–3 leaders, 2–3 laggards (by sector name only)
        4) Earnings backdrop: EPS growth and beat rate (if provided)

        Voice & style:
        - Professional, neutral, client-friendly; active voice; past tense.
        - Avoid superlatives and causal claims unless the event is explicitly listed as a shock.
        - Vary sentence length; keep paragraphs tight (2–3 sentences each).
        - Avoid these phrases entirely: {{ banned_phrases }}

        Facts (source of truth):
        - Period end: {{ as_of }}
        - Benchmark: {{ benchmark_name }} ({{ benchmark_id }}) return: {{ benchmark_return_pct }}%
        - VIX end / Δ: {{ vix_end }} / {{ vix_change }}
        - 10Y yield end / Δbp: {{ ten_year_yield }} / {{ ten_year_change_bps }}
        - Inflation ({{ inflation_series }} YoY): {{ inflation_yoy_pct }}%
        - Sectors: leaders {{ sector_leaders }}; laggards {{ sector_laggards }}
        - Earnings: EPS growth {{ eps_growth_pct }}%; beat rate {{ eps_beat_rate_pct }}%

        STYLE EXEMPLARS (tone only; numbers removed):
        ---
        {{ style_exemplars }}
        ---

        PLANNED OUTLINE:
        {{ plan_text }}

        Output constraints:
        - Length: {{ word_target_min }}–{{ word_target_max }} words.
        - Use only the numbers above. If a number is missing, omit that statement.
        - No portfolio language, no outlook, no recommendations, no performance attribution.

        Return ONLY the final text.
 
- `compliance.txt` → clean, verify, enforce constraints.
    - ```
        Task: Enforce scope and numeric fidelity for the generated “Market Context”.

        Inputs:
        - Draft text:
        {{ draft_text }}

        - KPI dictionary (sole numeric source):
        {{ kpis_json }}

        Banned phrases (remove if present): {{ banned_phrases }}

        Checks (apply in order):
        1) Scope: remove any outlook, recommendations, portfolio attribution/positions/trades.
        2) Numbers: replace any numeric mention that does not EXACTLY match the KPI dictionary; if uncertain, delete that sentence.
        3) Coverage: ensure at least the benchmark return sentence appears. If missing, append one using KPI values.
        4) Length: keep {{ word_target_min }}–{{ word_target_max }} words after edits.
        5) Tone: professional, neutral, past tense; no causal claims unless explicitly in Planner notes.

        Return ONLY the cleaned text.
 

**Style seeds from PDFs**
- `scripts/seed_style.py` extracts 2–5 short sentences per PDF from the “Market Context” section.
- Removes digits, dates, quarters, and outlook‑style verbs.
- Saved to `data/seeds/*.txt` and loaded by `app/tools/retrieval.py`.
- I would like to create an agent that does this as well as an extension.

<a id='execution-usage'> </a>

## 6. Execution and Usage

<a id='run-api'> </a>

### 6.1 Run as an API

```bash
uvicorn app.main:app --reload
open http://127.0.0.1:8000/docs
```

<a id='call-cli'> </a>

### 6.2 Call from CLI using curl

```bash
# Baseline
curl -s -X POST 'http://127.0.0.1:8000/generate/market-context?backend=none'      -H 'Content-Type: application/json' -d @samples/sample_request_spx.json | jq

#CrewAI
curl -s -X POST 'http://127.0.0.1:8000/generate/market-context?backend=crewai'    -H 'Content-Type: application/json' -d @samples/sample_request_spx.json | jq

#Langchain
curl -s -X POST 'http://127.0.0.1:8000/generate/market-context?backend=langchain' -H 'Content-Type: application/json' -d @samples/sample_request_spx.json | jq

#Langgraph
curl -s -X POST 'http://127.0.0.1:8000/generate/market-context?backend=langgraph' -H 'Content-Type: application/json' -d @samples/sample_request_spx.json | jq

```

<a id='use-library'> </a>

### 6.3 Use as a library when NB decides to combine this with the Super Agent

```python
from app.schemas import GenerateRequest
from app.agent_router import generate

req = GenerateRequest(
    as_of_period_end="2025-06-30",
    strategy_name="NB US Equity Fund",
    benchmark_id="SPX_TR",
    asset_class="equities",
)

resp = generate(req, override_backend="langgraph")  # or none/crewai/langchain
print(resp.text)
```

<a id='run-tests'> </a>

### 6.4 Running Tests

```bash
pytest -q
PYTHONPATH=. python3 tests/scratch_test.py  #needs OPENAI_API_KEY
```

<a id="design-decisions"></a>

## 7. Design Decisions

### 7.1 KPI-First, Style-Second
- **Decision:** All digits originate from a single KPI dictionary; style is layered on via sanitized exemplars.
- **Rationale:** Eliminates numeric hallucinations while preserving NB cadence.
- **Trade-off:** Slightly less “creative” prose in exchange for verifiable accuracy.

### 7.2 Two-Step Generation (Writer → Compliance)
- **Decision:** Separate drafting from compliance cleanup.
- **Rationale:** Clear responsibilities, easier debugging, targeted retries.
- **Trade-off:** Extra LLM call and a bit more latency

### 7.3 Guardrails in Both Prompting and Code
- **Decision:** Banned-phrase lexicon, KPI-only digit rules in prompts **and** post-processing checks.
- **Rationale:** Dual-layer enforcement catches edge-cases a single layer might miss.
- **Trade-off:** More components to maintain but safer outputs.

### 7.4 Prompt Files with JSON Sidecars
- **Decision:** Store prompts in `prompts/*.txt` with `*.json` sidecars declaring variables and LLM params.
- **Rationale:** Auditable, versioned, portable (works with CrewAI/LangChain/LangGraph).
- **Trade-off:** More files to deal with.

### 7.5 Multiple Orchestration Backends
- **Decision:** Support `none`, `crewai`, `langchain`, `langgraph` under a common interface.
- **Rationale:** Demonstrates breadth; lets platform teams pick based on SLOs and tooling.
- **Trade-off:** Extra maintenance for all of these but we will only actually use one. I wanted to show a few examples so that we could compare results and see which one works best. **LangGraph** recommended for production.

### 7.6 Baseline Path (`backend=none`)
- **Decision:** Deterministic template with KPI interpolation and minimal heuristics.
- **Rationale:** Smoke tests, outage fallback, predictable demos.
- **Trade-off:** Less fluent tone and is perfect for CI and reliability drills.

### 7.7 Style Seeds from PDFs (Numbers Stripped)
- **Decision:** Extract short sentences from prior “Market Context” sections, remove digits/dates.
- **Rationale:** NB voice without leaking historical numbers or compliance risks.
- **Trade-off:** One-time setup; strong tone benefits.

### 7.8 Pluggable Data Fetchers
- **Decision:** `fetch_kpis()` hides source (MOCK/FRED/Bloomberg/IBES); `normalize_kpis()` enforces schema.
- **Rationale:** Swap providers without touching agent logic.
- **Trade-off:** Requires clear contracts and validation.

### 7.9 API + Library Dual-Use
- **Decision:** FastAPI for HTTP access and importable Python functions for a super-agent.
- **Rationale:** Fits both service and embedded modes.
- **Trade-off:** Slight duplication of entrypoints




<a id="assumptions-tradeoffs"></a>

## 8. Key Assumptions & Trade-offs

### 8.1 Assumptions
- **Input metadata available:** `strategy_name`, `benchmark_id`, `asset_class`, `as_of_period_end`.
- **Comparable data exists:** For all strategies/periods (or MOCK for dev).
- **Scope limited:** Only **Market Context**; no attribution, trades, or outlook.
- **Tone seeds permissible:** Sanitized excerpts from prior NB public materials.

### 8.2 Trade-offs Chosen
- **Quality vs Latency:** Two LLM passes (Writer + Compliance) chosen for higher safety.
- **Breadth vs Simplicity:** Three agent stacks supported to match JD and showcase flexibility and **LangGraph** preferred for production.
- **Determinism vs Fluency:** Baseline (`none`) ensures deterministic outputs but agent paths give better prose.
- **Generalization vs Specialization:** Fund-agnostic design but strategy-specific lexicons can be layered later.

### 8.3 Unclean Data Handling:
- **KPI fields missing:** Hard fail with validation error; do not generate prose.
- **Seeds absent:** Fall back to tone charter only; still compliant, slightly flatter voice.
- **LLM unavailable:** Use baseline path; service remains operational.
- **Guardrails fail (outlook/rogue digits):** Compliance node rewrites; in LangGraph, auto-retry with tighter bounds.

### 8.4 Extensions
- Deep RAG over internal research.
- Per-strategy micro-styles and sector lexicons.
- Automated chart generation or dynamic footnotes.
- Portfolio-specific commentary (attribution/positions/outlook).


<a id="roadmap"></a>

## 9. Extensions (What I’d Add With More Time)

### 9.1 Data Integrations
- **FRED adapters** for 10Y yield and CPI with caching and release-calendar awareness.
- **Earnings feed** (IBES/internal): consensus growth, beat/miss rates by sector.
- **Index & sector returns** via internal analytics or Bloomberg/FactSet with a fallback.

### 9.2 LangGraph Enhancements
- **Fact Check (RAG) node:** retrieve internal weekly macro notes; ensure phrasing matches house views.
- **Redline (Style QA) node:** enforce cadence, sentence length, and jargon list; provide diffs.
- **Citations/Footnotes node:** emit source attributions (e.g., “FRED, CPI YoY”) and a compact data table.
- **Retry controller:** automatic re-prompts on word-count or digit mismatches, with bounded iterations.

### 9.3 Evaluation & Governance
- **Golden set** of KPI fixtures + expected outputs; diff-based regression tests across backends.
- **Prompt governance**: sign-off workflow, version labels in outputs, and change logs.
- **Bias/tonality monitor**: periodic audits to ensure neutrality and compliance.


#### Not very relevant ideas right now
### 9.4 UX & Productivity
- **Docs aside-panel preview**: live render vs. seeds; toggle between backends for comparison.
- **One-click export**: Word/PowerPoint/PDF snippet with standardized formatting.
- **Editor hints**: highlight digits not in KPI dict; on-hover explanations for each number.

### 9.5 Platformization
- **Containerized service** with health/readiness endpoints.
- **Multi-tenant configs**: per-strategy style packs and banned-phrases overlays.
- **Rate limiting & quotas** per user/team; cost telemetry per request.


<a id="ops"></a>

## 10. Operational Notes (Deployment, Observability, Security)

### 10.1 Deployment
- **Containerize** FastAPI app; pin Python and dependency versions.
- **Runtime**: Uvicorn/Gunicorn behind an ingress (NGINX/App Gateway).
- **Config** via environment variables or Key Vault (OPENAI keys, model names, data provider tokens).
- **Blue/green** or **rolling** deployments; health checks on `/docs` and a lightweight `/healthz`.

### 10.2 Observability
- **Structured logs**: request id, KPI hash, prompt checksum, backend used, latency per node.
- **Metrics**: p50/p95 latency; token usage; retry counts; compliance failure rate.
- **Tracing (OTel)**: spans for Planner, Writer, Compliance, post-checks; propagate correlation ids.
- **Alerting**: on surge in compliance failures or external API error rates.

### 10.3 Security
- **Secrets management**: never commit keys; pull from Key Vault or environment at boot.
- **Network egress controls**: restrict outbound to approved LLM and data endpoints.
- **Input validation**: strict Pydantic models; reject unknown fields; sanitize strings.
- **No PII**: commentary is market-only; style seeds are sanitized and number-free.

### 10.4 Reliability & Fallbacks
- **MOCK mode** ensures deterministic demos and graceful degradation when data feeds fail.
- **Baseline backend (`none`)** for outages of LLM providers; still returns a usable paragraph.
- **Circuit breakers** for flaky data sources; cached last-good KPI bundle per benchmark.

### 10.5 Compliance & Audit
- **Prompt/version pinning**: include prompt IDs and commit SHAs in logs.
- **Banned phrase audits**: periodic scans of outputs; diffs mailed to reviewers.
- **Data lineage**: store lightweight provenance (provider, timestamp) for each KPI field.

<a id="troubleshooting"></a>
## 11. Common Errors

### 11.1 Common Issues

- **401 Invalid API key**
  - **Symptom:** `AuthenticationError: incorrect API key`
  - **Fix:** `export OPENAI_API_KEY=sk-...` (or configure Azure OpenAI env vars). Confirm the key has access to the selected model.

- **Seeds not applied**
  - **Symptom:** Output sounds generic; style exemplars missing.
  - **Fix:** Run `python scripts/seed_style.py` after placing PDFs in `data/raw/`. Confirm files in `data/seeds/*.txt`. Restart the app.

- **404 at root**
  - **Symptom:** Visiting `/` returns 404.
  - **Fix:** Use Swagger at `/docs` or call the API via `curl`/client.

- **Import errors when running scripts**
  - **Symptom:** `ModuleNotFoundError: app.something`.
  - **Fix:** Run from repo root and set `PYTHONPATH=.` or `pip install -e .` (if you package it).

- **CrewAI path raises invalid key/model**
  - **Symptom:** Exception inside CrewAI/LLM call.
  - **Fix:** Verify `OPENAI_API_KEY`, `OPENAI_MODEL`, and set `MOCK=true` until real KPI connectors are configured.

- **LangGraph retry loop**
  - **Symptom:** Multiple retries logged for compliance failures.
  - **Fix:** Lower temperature in `writer.json`, increase `max_tokens`, or reduce `word_target_max` to hit constraints more consistently.


---

<a id="repo-layout"></a>

## 12. Repo Layout

```pgsql

Neuberger-Berman-Market-Context/
├─ app/
│  ├─ main.py
│  ├─ agent_router.py
│  ├─ pipeline.py
│  ├─ schemas.py
│  ├─ strategy_defaults.py
│  ├─ prompt_loader.py
│  ├─ tools/
│  │   ├─ data_fetchers.py
│  │   ├─ kpi_compute.py
│  │   └─ retrieval.py
│  └─ agents/
│      ├─ graph_crewai.py
│      ├─ graph_langchain.py
│      └─ graph_langgraph.py
├─ prompts/
│  ├─ planner.txt / planner.json
│  ├─ writer.txt / writer.json
│  └─ compliance.txt / compliance.json
├─ data/
│  ├─ raw/
│  └─ seeds/
├─ scripts/
│  └─ sanitize_seed_style.py
├─ samples/
│  ├─ sample_request_spx.json
│  └─ sample_request_r2k.json
├─ tests/
│  ├─ test_smoke.py
│  └─ scratch_test.py
├─ requirements.txt
├─ README.md
└─ .env.example

```



<a id="api-contract"></a>

## 13. API Contract

**Endpoint**  
`POST /generate/market-context?backend=none|crewai|langchain|langgraph`

**Request Body**
```json
{
  "as_of_period_end": "2025-06-30",
  "strategy_name": "NB US Equity Fund",
  "benchmark_id": "SPX_TR",
  "asset_class": "equities"
}
```

**Response Body**
```json
{
  "text": "200–300 words of Market Context ...",
  "kpis": {
    "benchmark_name": "S&P 500 Total Return",
    "benchmark_return_pct": 3.2,
    "vix_end": 14.1,
    "vix_change": 0.6,
    "ten_year_yield": 4.22,
    "ten_year_change_bps": 5,
    "inflation_series": "CPI YoY",
    "inflation_yoy_pct": 3.0,
    "sector_leaders": ["InfoTech", "Energy"],
    "sector_laggards": ["Utilities", "RealEstate"],
    "eps_growth_pct": 12.8,
    "eps_beat_rate_pct": 78.0
  },
  "assumptions": {
    "benchmark_id": "SPX_TR",
    "asset_class": "equities",
    "notes": "Agent backend: langgraph"
  }
}

```

### Error Codes

- `400` KPI validation failure
- `401` LLM Authentication Failure
- `502` Upstream LLM/data provider failure
- `503` Retry-exhausted or backend unavailable

<a id='tools'> </a>

## 14. Tools & Libraries

- **LLM:** OpenAI GPT (e.g., `gpt-4o-mini`) via **LangChain** / **CrewAI** / **LangGraph**
- **Web service:** **FastAPI** + **Uvicorn**
- **Prompt rendering:** **Jinja2** templating
- **PDF parsing / style seeds:** **pdfplumber**
- **Validation:** **Pydantic** models
- **Testing:** **Pytest**
- **(Optional / roadmap):** **OpenTelemetry** for tracing, **Prometheus** metrics



<a id="rationale"></a>

## 15. Rationale: Why this Stack vs Alternatives

- **LangGraph** — explicit control flow, retries, and state → ideal for compliance loops, word-count enforcement, and deterministic behavior. Its graph primitives (nodes, edges, state) make it straightforward to add future steps like Fact Check (RAG) or Redline QA without rewriting orchestration.
- **LangChain** — mature adapters/utilities → quick prompt chains, easy model/provider swaps, and abundant community patterns. Useful for fast iteration and clean integration with OpenAI/Azure OpenAI.
- **CrewAI** — multi-agent personas align with the internship’s “sub-agents” theme; demonstrates orchestration patterns (Writer + Compliance) and tool routing in a familiar agent-first API.
- **FastAPI** — clean, type-safe contracts via Pydantic; auto-generated Swagger; production-friendly (CORS, middlewares, dependency injection). It also lets the super-agent call this as a microservice or import functions directly as a library.

**Alternatives considered**
- **LlamaIndex** — excellent for heavy RAG over internal research. Deferred because this submission focuses strictly on Market Context (no research retrieval). It becomes compelling once we add a Fact Check node pulling from internal macro notes.
- **Custom orchestration** (pure asyncio/state machine) — maximal control, but slower to ship and harder to maintain under a 3–5 hour time-box. The chosen libraries give us reliability features (retries, state) out of the box.

**Why not a single backend?**
- **Interview value & platform optionality.** The same input/output contract runs across `crewai`, `langchain`, and `langgraph`. Teams can pick based on SLOs and familiarity. **LangGraph** is the production recommendation for its determinism and extensibility; the others showcase breadth and align with the stated tech stack.


