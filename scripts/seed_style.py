# scripts/seed_style.py
import re, sys
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    print("Please run: pip install pdfplumber", file=sys.stderr)
    raise

RAW_DIR  = Path("data/raw")      # put PDFs here
SEED_DIR = Path("data/seeds")    # tone-only snippets will be written here
SEED_DIR.mkdir(parents=True, exist_ok=True)

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])", re.MULTILINE)

# Filter out portfolio/attribution/outlook-y text
BAN = re.compile(
    r"\b(portfolio|positioning|overweight|underweight|added|trimmed|sold|bought|we (expect|believe)|positioned|outlook|view)\b",
    re.IGNORECASE,
)

def strip_numbers(s: str) -> str:
    s = re.sub(r"\b\d{1,4}(\.\d+)?%?\b", " ", s)          # raw numbers / percents
    s = re.sub(r"\b(?:19|20)\d{2}\b", " ", s)             # years
    s = re.sub(r"\bQ[1-4]\b", " ", s)                     # quarters
    s = re.sub(r"\b[S&PXR]+\b", " ", s)                   # crude ticker-ish
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip()

def clean_sentence(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s

def extract_candidates(text: str):
    # rough cut to the “Market Context” area if present
    lowered = text.lower()
    if "market context" in lowered:
        start = lowered.index("market context")
        text = text[start:]
    sentences = [clean_sentence(x) for x in SENTENCE_SPLIT.split(text) if len(x.split()) >= 8]
    return [s for s in sentences if not BAN.search(s)]

def from_pdf(pdf_path: Path, max_snippets=5):
    with pdfplumber.open(pdf_path) as pdf:
        text = " ".join(page.extract_text() or "" for page in pdf.pages)
    cands = extract_candidates(text)
    # de-number & keep compact sentences to capture cadence
    out = []
    for s in cands:
        s2 = strip_numbers(s)
        if 8 <= len(s2.split()) <= 35:
            out.append(s2)
        if len(out) >= max_snippets:
            break
    return out

def main():
    if not RAW_DIR.exists():
        print("Create data/raw and place your PDFs there.", file=sys.stderr)
        sys.exit(1)
    any_written = False
    for pdf in RAW_DIR.glob("*.pdf"):
        seeds = from_pdf(pdf)
        if not seeds:
            print(f"[warn] no suitable sentences found in {pdf.name}", file=sys.stderr)
            continue
        out = SEED_DIR / (pdf.stem + ".txt")
        out.write_text("\n".join(seeds), encoding="utf-8")
        print(f"wrote {out} ({len(seeds)} snippets)")
        any_written = True
    if not any_written:
        sys.exit(2)

if __name__ == "__main__":
    main()
