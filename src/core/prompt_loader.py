from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(agent_name: str) -> str:
    with open(_PROMPTS_DIR / f"{agent_name}_sys.md") as f:
        return f.read()


def load_message(agent_name: str) -> str:
    with open(_PROMPTS_DIR / f"{agent_name}_message.md") as f:
        return f.read()