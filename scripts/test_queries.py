"""
Manual test for all queries.py functions against the live AuraDB.
Uses entity names/IDs confirmed present from 111_load_layer1_entities.ipynb.
"""

import sys
from pathlib import Path
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
load_dotenv(REPO / '.env')

from src.graph.connection import Neo4jConnection
from src.graph.queries import (
    get_entity_subgraph,
    get_entity_network,
    get_intermediary_network,
    get_typology_path,
    vector_search_typology_chunks,
)

conn = Neo4jConnection().connect()
print('Connected to', conn._uri)
print()

PASS = 0
FAIL = 0

def check(name, rows, expect_min=1):
    global PASS, FAIL
    if len(rows) >= expect_min:
        print(f'PASS  {name}  — {len(rows)} row(s)')
        if rows:
            first = {k: str(v)[:80] for k, v in rows[0].items()}
            print(f'      sample: {first}')
        PASS += 1
    else:
        print(f'FAIL  {name}  — got {len(rows)} rows (expected >={expect_min})')
        FAIL += 1
    print()


# ── Layer 1 ───────────────────────────────────────────────────────────────────

# get_entity_subgraph — Company by name
rows = get_entity_subgraph(conn, 'BLAIRMORE HOLDINGS, INC.')
check('get_entity_subgraph (Company by name)', rows)

# get_entity_subgraph — Person by name
rows = get_entity_subgraph(conn, 'Hussain Nawaz Sharif')
check('get_entity_subgraph (Person by name)', rows)

# get_entity_network — Company ownership chain
rows = get_entity_network(conn, 'BLAIRMORE HOLDINGS, INC.', depth=2)
check('get_entity_network (Company, depth=2)', rows)

# get_entity_network — Person shell network
rows = get_entity_network(conn, 'MINERVA NOMINEES LIMITED', depth=2)
check('get_entity_network (Person, depth=2)', rows)

# get_intermediary_network — fetch first intermediary name dynamically
intermediary_rows = conn.run_query('MATCH (i:Intermediary) RETURN i.name AS name LIMIT 1')
if intermediary_rows:
    iname = intermediary_rows[0]['name']
    rows = get_intermediary_network(conn, iname)
    check(f'get_intermediary_network ({iname!r})', rows)
else:
    print('SKIP  get_intermediary_network — no Intermediary nodes found')
    print()

# ── Layer 2 ───────────────────────────────────────────────────────────────────

# get_typology_path — MAS-626
rows = get_typology_path(conn, 'MAS-626')
check('get_typology_path (MAS-626)', rows, expect_min=10)

# vector_search_typology_chunks — only if embeddings are loaded
chunk_check = conn.run_query('MATCH (c:Chunk) WHERE c.embedding IS NOT NULL RETURN count(c) AS n')
if chunk_check[0]['n'] > 0:
    # Use an existing chunk's vector to confirm the index works
    seed = conn.run_query('MATCH (c:Chunk) WHERE c.embedding IS NOT NULL RETURN c.embedding AS emb LIMIT 1')
    rows = vector_search_typology_chunks(conn, seed[0]['emb'], top_k=5)
    check('vector_search_typology_chunks (self-similarity)', rows)

    rows = vector_search_typology_chunks(conn, seed[0]['emb'], typology_id='MAS-626', top_k=3)
    check('vector_search_typology_chunks (scoped to MAS-626)', rows)
else:
    print('SKIP  vector_search_typology_chunks — run embed_chunks.py first')
    print()

# ── Summary ───────────────────────────────────────────────────────────────────
conn.close()
print(f'{PASS} PASS  /  {FAIL} FAIL')
sys.exit(1 if FAIL else 0)
