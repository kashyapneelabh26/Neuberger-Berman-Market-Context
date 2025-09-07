# app/tools/retrieval.py
from typing import List
from pathlib import Path
import re

# Robustly locate the repo root (nb-market-context/)
# retrieval.py -> tools -> app -> <repo_root> (parents[3])
_REPO_ROOT = Path(__file__).resolve().parents[3]

# Prefer repo_root/data/seeds, but also fall back to CWD/data/seeds
_CANDIDATES = [
    _REPO_ROOT / "data" / "seeds",
    Path.cwd() / "data" / "seeds",
]

_FALLBACK_SEEDS = [
    "The period was marked by heightened volatility as policy headlines drove swift moves across risk assets.",
    "Inflation data showed further cooling while long-term yields were little changed; sector leadership skewed toward technology and energy.",
]

_NUM = re.compile(r"\b\d{1,4}(\.\d+)?%?\b")
_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
_QUARTER = re.compile(r"\bQ[1-4]\b")

def _strip_numbers(text: str) -> str:
    text = _NUM.sub(" ", text)
    text = _YEAR.sub(" ", text)
    text = _QUARTER.sub(" ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()

def _seed_dir() -> Path | None:
    for p in _CANDIDATES:
        if p.exists() and any(p.glob("*.txt")):
            return p
    return None

def _load_seed_texts() -> List[str]:
    p = _seed_dir()
    if not p:
        return _FALLBACK_SEEDS
    seeds: List[str] = []
    for f in sorted(p.glob("*.txt")):
        txt = f.read_text(encoding="utf-8").strip()
        if txt:
            # split on newlines so multiple snippets per file are respected
            for line in txt.splitlines():
                s = _strip_numbers(line.strip())
                if s:
                    seeds.append(s)
    return seeds or _FALLBACK_SEEDS

def get_style_exemplars(k: int = 2) -> List[str]:
    seeds = _load_seed_texts()
    return seeds[:k]
