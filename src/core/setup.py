import io
import json
import os
import time

from h2ogpte import H2OGPTE

MCP_CONFIG_PATH = "config/mcp_config.json"
_PLACEHOLDERS = {
    "YOUR_SPLUNK_MCP_URL": "SPLUNK_MCP_URL",
    "YOUR_JIRA_MCP_URL": "JIRA_MCP_URL",
}

def _load_mcp_config() -> str:
    """Read mcp_config.json and substitute MCP URLs from the environment."""
    with open(MCP_CONFIG_PATH, "r") as f:
        content = f.read()

    for placeholder, env_var in _PLACEHOLDERS.items():
        url = os.getenv(env_var)
        if not url:
            raise ValueError(f"{env_var} must be set in .env")
        if placeholder not in content:
            raise ValueError(
                f"Expected placeholder '{placeholder}' not found in {MCP_CONFIG_PATH}"
            )
        content = content.replace(placeholder, url)

    return content


def create_collection(client: H2OGPTE, collection_name: str, collection_desc: str) -> str:
    """Create a new H2OGPTE collection for the Splunk agent."""
    collection_id = client.create_collection(
        name=collection_name,
        description=collection_desc,
    )
    print(f"Collection created: {collection_id}")
    return collection_id


def create_chat(client: H2OGPTE, collection_id: str) -> str:
    """Create a new chat session in the specified collection."""
    chat_session_id = client.create_chat_session(collection_id)
    print(f"Chat session created: {chat_session_id}")
    return chat_session_id


def upload_and_ingest_mcp_config(client: H2OGPTE, collection_id: str) -> str:
    """Upload and ingest the MCP config file into the collection."""
    json_bytes = _load_mcp_config().encode()
    upload_id = client.upload(MCP_CONFIG_PATH, io.BytesIO(json_bytes))

    ingest_job = client.ingest_uploads(
        collection_id=collection_id,
        upload_ids=[upload_id],
        ingest_mode="agent_only",
    )

    print("Waiting for ingestion...")
    while True:
        job_status = client.get_job(ingest_job.id)
        if job_status.completed:
            print("Ingestion complete.")
            break
        if job_status.failed:
            raise RuntimeError(f"Ingestion failed: {job_status.errors}")
        time.sleep(2)

    return upload_id


def register_mcp_tool(client: H2OGPTE) -> list:
    """Register the Splunk MCP tool with H2OGPTE."""
    json_str = _load_mcp_config()

    tool_ids = client.add_custom_agent_tool(
        tool_type="remote_mcp",
        tool_args={
            "mcp_config_json": json_str,
            "enable_by_default": False,
        },
        custom_tool_path=MCP_CONFIG_PATH,
    )
    print(f"MCP tool registered: {tool_ids}")
    return tool_ids


def setup_agent_keys(client: H2OGPTE) -> None:
    """Ensure agent keys for MCP env vars exist, reusing or creating as needed."""
    required_keys = {
        "H2OGPTE_API_KEY": os.getenv("H2OGPTE_API_KEY"),
        "H2OGPTE_ADDRESS": os.getenv("H2OGPTE_ADDRESS"),
        "SPLUNK_MCP_TOKEN": os.getenv("SPLUNK_MCP_TOKEN"),
        "JIRA_URL": os.getenv("JIRA_URL"),
        "JIRA_USERNAME": os.getenv("JIRA_USERNAME"),
        "JIRA_API_TOKEN": os.getenv("JIRA_API_TOKEN"),
    }

    existing = {
        k["name"]: k["id"]
        for k in client.get_agent_keys()
        if k["name"] in required_keys
    }

    for name, value in required_keys.items():
        if name not in existing:
            result = client.add_agent_key([
                {
                    "name": name,
                    "value": value,
                    "key_type": "private",
                    "description": f"{name} for MCP server",
                }
            ])
            existing[name] = result[0]["agent_key_id"]
            print(f"  Created agent key: {name}")
        else:
            print(f"  Reusing agent key: {name}")

    with open(MCP_CONFIG_PATH, "r") as f:
        mcp_config = json.load(f)
    tool_names = list(mcp_config["mcpServers"].keys())

    key_assignments = [{"name": name, "key_id": kid} for name, kid in existing.items()]
    for tool_name in tool_names:
        client.assign_agent_key_for_tool([{
            "tool_dict": {
                "tool": tool_name,
                "keys": key_assignments,
            }
        }])
    print("Agent keys associated with MCP tools.")