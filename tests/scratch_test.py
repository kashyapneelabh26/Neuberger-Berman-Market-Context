from app.schemas import GenerateRequest
from app.agent_router import generate

req = GenerateRequest(
    as_of_period_end="2025-06-30",
    strategy_name="NB US Equity Fund",
    benchmark_id="SPX_TR",
    asset_class="equities",
)

for backend in ["none", "crewai", "langchain"]:
    print(f"\n=== Backend: {backend} ===")
    resp = generate(req, override_backend=backend)
    print(resp.text, "\n")
