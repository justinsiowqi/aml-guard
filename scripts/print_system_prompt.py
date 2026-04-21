"""Print the fully-resolved AML system prompt with all placeholders filled."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.mcp.schema import GRAPH_SCHEMA_HINT, PATTERN_HINTS
from src.agent.config import AML_MAX_ITERATIONS

template = (Path(__file__).resolve().parents[1] / "src/prompts/aml_sys.md").read_text()

prompt = template.format(
    GRAPH_SCHEMA_HINT=GRAPH_SCHEMA_HINT,
    PATTERN_HINTS=PATTERN_HINTS,
    AML_MAX_ITERATIONS=AML_MAX_ITERATIONS,
)

print(prompt)
