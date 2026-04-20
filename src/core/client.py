import os

from dotenv import load_dotenv
from h2ogpte import H2OGPTE


def create_client() -> H2OGPTE:
    """Create and return an authenticated H2OGPTE client."""
    load_dotenv()

    api_key = os.getenv("H2OGPTE_API_KEY")
    address = os.getenv("H2OGPTE_ADDRESS")

    if not api_key or not address:
        raise ValueError("H2OGPTE_API_KEY and H2OGPTE_ADDRESS must be set in .env")

    print(f"Connecting to {address}...")
    client = H2OGPTE(address=address, api_key=api_key)
    print("Client created successfully.")
    return client