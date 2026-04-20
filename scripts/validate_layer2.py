import sys
from pathlib import Path

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
load_dotenv(REPO / '.env')

from src.graph.connection import Neo4jConnection
from src.mcp.schema import ANOMALY_REGISTRY

conn = Neo4jConnection().connect()
print('Connected to', conn._uri)

results = []


def check(name, passed, detail=''):
    status = 'PASS' if passed else 'FAIL'
    results.append((status, name, detail))
    print(f'{status}  {name}' + (f'  — {detail}' if detail else ''))


# 1. Node counts
EXPECTED = {
    'Person':       (1,   None),
    'Company':      (50,  None),
    'Intermediary': (1,   None),
    'Address':      (1,   None),
    'Jurisdiction': (1,   None),
    'Regulation':   (1,   1),
    'Section':      (10,  None),
    'Requirement':  (100, None),
    'Threshold':    (1,   None),
    'Chunk':        (100, None),
}
counts = {
    row['label']: row['n']
    for row in conn.run_query('MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n')
}
print('\n--- Node counts ---')
for label, (lo, hi) in EXPECTED.items():
    n = counts.get(label, 0)
    ok = n >= lo and (hi is None or n <= hi)
    bound = f'>={lo}' + (f', <={hi}' if hi is not None else '')
    check(f'Node count {label:<13}', ok, f'{n} ({bound})')

# 2. Edge counts
EXPECTED_EDGES = [
    'IS_OFFICER_OF', 'INTERMEDIARY_OF', 'REGISTERED_AT',
    'SHARES_ADDRESS_WITH', 'INCORPORATED_IN',
    'HAS_SECTION', 'NEXT_SECTION', 'HAS_REQUIREMENT',
    'DEFINES_THRESHOLD', 'HAS_CHUNK', 'NEXT_CHUNK',
]
edge_counts = {
    row['rel']: row['n']
    for row in conn.run_query('MATCH ()-[r]->() RETURN type(r) AS rel, count(*) AS n')
}
print('\n--- Edge counts ---')
for rel in EXPECTED_EDGES:
    n = edge_counts.get(rel, 0)
    check(f'Edge count {rel:<20}', n > 0, f'{n}')

# 3. Referential integrity
ORPHAN_CHECKS = [
    ('Section w/o Regulation',    'MATCH (s:Section)     WHERE NOT (:Regulation)-[:HAS_SECTION]->(s)        RETURN count(*) AS n'),
    ('Requirement w/o Section',   'MATCH (r:Requirement) WHERE NOT (:Section)-[:HAS_REQUIREMENT]->(r)       RETURN count(*) AS n'),
    ('Threshold w/o Requirement', 'MATCH (t:Threshold)   WHERE NOT (:Requirement)-[:DEFINES_THRESHOLD]->(t) RETURN count(*) AS n'),
    ('Chunk w/o Requirement',     'MATCH (c:Chunk)       WHERE NOT (:Requirement)-[:HAS_CHUNK]->(c)          RETURN count(*) AS n'),
    ('Company w/o Jurisdiction',  "MATCH (c:Company) WHERE c.jurisdiction <> '' AND NOT (c)-[:INCORPORATED_IN]->(:Jurisdiction) RETURN count(*) AS n"),
    ('Person w/o company link',   'MATCH (p:Person) WHERE NOT (p)-[:IS_OFFICER_OF]->(:Company) RETURN count(*) AS n'),
]
print('\n--- Referential integrity ---')
for name, cypher in ORPHAN_CHECKS:
    n = conn.run_query(cypher)[0]['n']
    check(f'No orphans — {name:<30}', n == 0, f'{n} orphan(s)')

# 4. Uniqueness constraints
EXPECTED_CONSTRAINTS = {
    ('Person', 'node_id'), ('Company', 'node_id'), ('Intermediary', 'node_id'),
    ('Address', 'node_id'), ('Jurisdiction', 'jurisdiction_id'),
    ('Regulation', 'regulation_id'), ('Section', 'section_id'),
    ('Requirement', 'requirement_id'), ('Threshold', 'threshold_id'),
    ('Chunk', 'chunk_id'),
}
found = set()
rows = conn.run_query(
    'SHOW CONSTRAINTS YIELD labelsOrTypes, properties, type '
    'WHERE type CONTAINS "UNIQUE" RETURN labelsOrTypes, properties'
)
for row in rows:
    for lbl in row['labelsOrTypes']:
        for prop in row['properties']:
            found.add((lbl, prop))
missing = EXPECTED_CONSTRAINTS - found
print('\n--- Constraints ---')
check('All uniqueness constraints present', not missing,
      f'missing {missing}' if missing else f'{len(found)} constraints found')

# 5. Embeddings and vector index
print('\n--- Embeddings ---')
rows = conn.run_query('MATCH (c:Chunk) RETURN count(c) AS total, count(c.embedding) AS with_emb')
total, with_emb = rows[0]['total'], rows[0]['with_emb']

if with_emb == 0:
    print('SKIP  No chunks have embeddings yet. Run embed_chunks.py first.')
else:
    check('Embedding coverage — all chunks embedded', with_emb == total, f'{with_emb}/{total}')

    rows = conn.run_query('''
        MATCH (c:Chunk) WHERE c.embedding IS NOT NULL
        RETURN size(c.embedding) AS dim, count(*) AS n ORDER BY n DESC
    ''')
    dims = {r['dim']: r['n'] for r in rows}
    check('Embedding dimension is consistent', len(dims) == 1, f'dims={dims}')

    rows = conn.run_query(
        "SHOW INDEXES YIELD name, state, type WHERE name = 'chunk_embeddings' RETURN state, type"
    )
    if not rows:
        check("Vector index 'chunk_embeddings' exists", False, 'not found')
    else:
        state = rows[0]['state']
        idx_type = rows[0].get('type', '')
        check("Vector index 'chunk_embeddings' ONLINE",
              state == 'ONLINE' and 'VECTOR' in (idx_type or '').upper(),
              f'state={state}, type={idx_type}')

        rows = conn.run_query('''
            MATCH (c:Chunk) WHERE c.embedding IS NOT NULL
            WITH c LIMIT 1
            CALL db.index.vector.queryNodes('chunk_embeddings', 3, c.embedding)
            YIELD node, score
            RETURN count(node) AS n, max(score) AS max_score
        ''')
        n = rows[0]['n']
        max_score = rows[0]['max_score']
        detail = f'{n} hits, max_score={max_score:.3f}' if max_score is not None else f'{n} hits'
        check('Vector search returns results', n >= 1, detail)

# 6. Anomaly pattern smoke tests
print('\n--- Anomaly patterns ---')
for name, pat in ANOMALY_REGISTRY.items():
    try:
        rows = conn.run_query(pat.cypher, pat.params or {})
        check(f'Pattern {name:<35}', len(rows) > 0, f'{len(rows)} row(s)')
    except Exception as e:
        check(f'Pattern {name:<35}', False, f'ERROR: {type(e).__name__}: {e}')

# 7. Cross-layer bridge
print('\n--- Cross-layer bridge ---')
rows = conn.run_query('''
    MATCH (c:Company)-[:INCORPORATED_IN]->(j:Jurisdiction {aml_risk_rating: 'high'})
    WITH c, j LIMIT 1
    MATCH (r:Requirement {regulation_id: 'MAS-626'})
    WHERE r.paragraph STARTS WITH '4.1'
    RETURN c.name AS company, j.name AS jurisdiction,
           r.paragraph AS para, substring(r.text, 0, 120) AS text_snippet
    ORDER BY r.paragraph LIMIT 5
''')
check('Cross-layer bridge query returns results', len(rows) > 0, f'{len(rows)} row(s)')
for row in rows:
    print(f"  {row['company']:<45} ({row['jurisdiction']})  para {row['para']}: {row['text_snippet']}...")

# Summary
pass_count = sum(1 for s, *_ in results if s == 'PASS')
fail_count = sum(1 for s, *_ in results if s == 'FAIL')
print(f'\n{pass_count} PASS  /  {fail_count} FAIL  (total {len(results)})')
if fail_count:
    print('\nFailures:')
    for status, name, detail in results:
        if status == 'FAIL':
            print(f'  - {name}  ({detail})')

conn.close()
sys.exit(1 if fail_count else 0)
