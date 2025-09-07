from app.pipeline import compliance_clean
from app.prompt_loader import Prompt

def test_compliance_injects_benchmark_if_missing():
    t = "Volatility was elevated."
    kpis = {"benchmark_return_pct": 3.2}
    out = compliance_clean(t, kpis)
    assert "3.2%" in out
    
def test_writer_template_renders():
    p = Prompt("writer")
    variables = {"as_of": "2025-06-30", "benchmark_name": "S&P 500 Total Return", "benchmark_id": "SPX_TR",
        "benchmark_return_pct": 3.2, "vix_end": 14.1, "vix_change": 0.6, "ten_year_yield": 4.22,"ten_year_change_bps": 5,
        "inflation_series": "CPI YoY", "inflation_yoy_pct": 3.0,"sector_leaders": ["InfoTech","Energy"], "sector_laggards": ["Utilities","RealEstate"],
        "eps_growth_pct": 12.8, "eps_beat_rate_pct": 78.0, "banned_phrases": "we expect, we believe, positioned to","word_target_min": 200, "word_target_max": 300, "style_exemplars": "example", "plan_text": "- bullets"}
    txt = p.render(variables)
    assert isinstance(txt, str) and len(txt) > 10
