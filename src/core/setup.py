import io
import json
import os
import time

from h2ogpte import H2OGPTE

BASE_DIR = os.path.dirname(__file__)
SERVER_FILENAME = 'aml_guard_mcp.zip'
SERVER_FILE = os.path.join(BASE_DIR, '..', 'mcp', SERVER_FILENAME)


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


def upload_and_ingest_mcp(client: H2OGPTE, collection_id: str) -> str:
    """Upload and ingest the MCP server file into the collection."""
    with open(SERVER_FILE, 'rb') as f:
        upload_id = client.upload(SERVER_FILENAME, f)

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
    """Register the AML MCP tool with H2OGPTE (idempotent).

    Each call to add_custom_agent_tool creates a new registration without
    overwriting prior ones, so we explicitly delete any pre-existing
    registrations under the same tool_name before adding the new one.

    Notes on tool_args (per H2OGPTE SDK docs for add_custom_agent_tool):
      - tool_usage_mode is only valid for tool_type="remote_mcp"; passing it
        to a local_mcp registration is silently ignored or rejected.
      - enable_by_default=True attaches the tool to all agent runs without
        requiring per-call enabling. With False, the bundle is registered
        but never appears in get_agent_tools_dict() at runtime, so the
        agent never sees its functions.
    """
    # Clean up prior registrations: anything under SERVER_FILENAME, plus the
    # legacy 'amlguard' name some earlier setups used. Each new
    # add_custom_agent_tool call creates a fresh registration without
    # overwriting prior ones, so this prevents accumulating duplicates
    # across FastAPI restarts.
    _STALE_NAMES = {SERVER_FILENAME, "amlguard"}
    try:
        existing = client.get_custom_agent_tools() or []
        stale_ids = [
            getattr(t, "id", None)
            for t in existing
            if getattr(t, "tool_name", None) in _STALE_NAMES
            and getattr(t, "id", None)
        ]
        if stale_ids:
            removed = client.delete_custom_agent_tool(stale_ids)
            print(f"Removed {removed} stale custom agent tool registration(s).")
    except Exception as e:
        print(f"WARNING: could not clean up prior registrations: {e}")

    tool_ids = client.add_custom_agent_tool(
        tool_type="local_mcp",
        tool_args={
            'tool_name': SERVER_FILENAME,
            'enable_by_default': True,
        },
        custom_tool_path=SERVER_FILE
    )
    print(f"MCP tool registered: {tool_ids}")
    return tool_ids


def setup_agent_keys(client: H2OGPTE) -> None:
    """Ensure agent keys for MCP env vars exist, reusing or creating as needed."""
    required_keys = {
        "H2OGPTE_API_KEY": os.getenv("H2OGPTE_API_KEY"),
        "H2OGPTE_ADDRESS": os.getenv("H2OGPTE_ADDRESS"),
        "NEO4J_URI": os.getenv("NEO4J_URI"),
        "NEO4J_USERNAME": os.getenv("NEO4J_USERNAME"),
        "NEO4J_PASSWORD": os.getenv("NEO4J_PASSWORD"),  
        "NEO4J_DATABASE": os.getenv("NEO4J_DATABASE")
    }

    # Verify no keys are missing values
    missing = [k for k, v in required_keys.items() if v is None]
    if missing:
        raise ValueError(f"Missing environment variables: {', '.join(missing)}")

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

    key_assignments = [{"name": name, "key_id": kid} for name, kid in existing.items()]
    client.assign_agent_key_for_tool([{
        "tool_dict": {
            "tool": SERVER_FILENAME,
            "keys": key_assignments,
        }
    }])
    print("Agent keys associated with MCP tools.")