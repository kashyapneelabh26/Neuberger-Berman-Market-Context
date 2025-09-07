from typing import Dict
from datetime import date
import os

SECTOR_ETF_MAP = {"InfoTech":"XLK","Financials":"XLF","Energy":"XLE","HealthCare":"XLV","Industrials":"XLI","CommServices":"XLC","ConsumerDisc":"XLY","ConsumerStaples":"XLP","Materials":"XLB","Utilities":"XLU","RealEstate":"XLRE"}

BENCHMARK_NAME = {"SPX_TR":"S&P 500 Total Return","R2000_TR":"Russell 2000 Total Return","R3000_TR":"Russell 3000 Total Return","AGG_TR":"US Agg Total Return"}

def fetch_kpis(as_of: date, benchmark_id: str) -> Dict:

    if os.getenv("MOCK", "true").lower() == "true":

        return {"benchmark_name": BENCHMARK_NAME.get(benchmark_id, benchmark_id), "benchmark_return_pct": 3.2,
                "vix_end": 14.1, "vix_change": 0.6, "ten_year_yield": 4.22, "ten_year_change_bps": 5,
                "inflation_series": "CPI YoY", "inflation_yoy_pct": 3.0,
                "sector_leaders": ["InfoTech", "Energy"], "sector_laggards": ["Utilities", "RealEstate"],
                "eps_growth_pct": 12.8, "eps_beat_rate_pct": 78.0}
    
    raise NotImplementedError("Replace MOCK with real Yahoo/FRED fetchers when ready.")
