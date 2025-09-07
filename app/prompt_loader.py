import json, pathlib
from jinja2 import Template
from typing import Dict, Any

PROMPTS_DIR = pathlib.Path(__file__).resolve().parent.parent / "prompts"

class Prompt:

    def __init__(self, name: str):
        
        self.name = name
        self.text = (PROMPTS_DIR / f"{name}.txt").read_text(encoding="utf-8")
        self.meta = json.loads((PROMPTS_DIR / f"{name}.json").read_text(encoding="utf-8"))

    def render(self, variables: Dict[str, Any]) -> str:

        missing = [k for k in self.meta.get("required_vars", []) if k not in variables]
        if missing: raise ValueError(f"Missing variables for prompt '{self.name}': {missing}")
        return Template(self.text).render(**variables)
