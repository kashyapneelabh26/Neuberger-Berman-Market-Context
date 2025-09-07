from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, Field
from datetime import date

class PortfolioMeta(BaseModel):

    sector_exposure: Optional[Dict[str, float]] = None
    region_exposure: Optional[Dict[str, float]] = None
    style_tilt: Optional[List[str]] = None
    market_cap_tilt: Optional[Literal["small","mid","large","all"]] = "all"
    currency_base: Optional[str] = "USD"

class GenerateRequest(BaseModel):

    as_of_period_end: date
    strategy_name: str
    benchmark_id: Optional[str] = None
    asset_class: Optional[Literal["equities","multi_asset","fixed_income","alternatives"]] = None
    region: Optional[str] = "US"
    portfolio_meta: Optional[PortfolioMeta] = None
    style: Dict[str, object] = Field(default_factory=lambda: {"tone":"professional","word_count_target": 240})

class KPIBundle(BaseModel):
    benchmark_name: str
    benchmark_return_pct: float
    vix_end: Optional[float] = None
    vix_change: Optional[float] = None
    ten_year_yield: Optional[float] = None
    ten_year_change_bps: Optional[int] = None
    inflation_series: Optional[str] = None
    inflation_yoy_pct: Optional[float] = None
    sector_leaders: Optional[List[str]] = None
    sector_laggards: Optional[List[str]] = None
    eps_growth_pct: Optional[float] = None
    eps_beat_rate_pct: Optional[float] = None

class GenerateResponse(BaseModel):
    text: str
    kpis: KPIBundle
    assumptions: Dict[str, str]
