from pathlib import Path

import yaml

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "agents.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f)


def get_agent_config(agent_name: str) -> dict:
    """Return the config dict for a given agent.

    Args:
        agent_name: Key under ``agents`` in agents.yaml
                    (e.g. "host", "inventory", "query").

    Returns:
        A dict with the agent's configuration (e.g. llm, agent_type, agent_tools).

    Raises:
        KeyError: If the agent name is not found in the config.
    """
    config = _load_config()
    return config["agents"][agent_name]