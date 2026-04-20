import argparse
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
load_dotenv(REPO / '.env')

from h2ogpte import H2OGPTE
from src.graph.connection import Neo4jConnection

BATCH_SIZE = 32
WRITE_BATCH = 200


def main():
    parser = argparse.ArgumentParser(description='Embed Layer 2 Chunks and write vectors to Neo4j.')
    parser.add_argument('--model', default=None, help='H2OGPTe embedding model (default: server default).')
    args = parser.parse_args()

    h2ogpte_url = os.getenv('H2OGPTE_URL') or os.getenv('H2OGPTE_ADDRESS')
    h2ogpte_key = os.getenv('H2OGPTE_API_KEY')
    if not h2ogpte_url or not h2ogpte_key:
        raise RuntimeError('Set H2OGPTE_URL (or H2OGPTE_ADDRESS) and H2OGPTE_API_KEY in .env')

    client = H2OGPTE(address=h2ogpte_url, api_key=h2ogpte_key)
    print('H2OGPTe client OK')

    conn = Neo4jConnection().connect()
    print('Neo4j connected')

    # Pull chunks
    rows = conn.run_query('MATCH (c:Chunk) RETURN c.chunk_id AS chunk_id, c.text AS text ORDER BY c.chunk_id')
    chunks = [(r['chunk_id'], r['text']) for r in rows if r['text']]
    print(f'{len(chunks)} chunks to embed')

    # Embed in batches
    vectors = {}
    dim = None
    start = time.time()
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        ids   = [cid for cid, _ in batch]
        texts = [txt for _, txt in batch]
        kwargs = {'chunks': texts}
        if args.model:
            kwargs['embedding_model'] = args.model
        embs = client.encode_for_retrieval(**kwargs)
        if dim is None:
            dim = len(embs[0])
            print(f'Embedding dimension: {dim}')
        for cid, vec in zip(ids, embs):
            vectors[cid] = vec
        print(f'  embedded {len(vectors):>3} / {len(chunks)} ({time.time() - start:.1f}s)')

    print(f'\nDone. {len(vectors)} vectors, dim={dim}.')

    # Write embeddings to Neo4j
    records = [{'chunk_id': cid, 'embedding': vec} for cid, vec in vectors.items()]
    cypher = '''
    UNWIND $records AS row
    MATCH (c:Chunk {chunk_id: row.chunk_id})
    CALL db.create.setNodeVectorProperty(c, 'embedding', row.embedding)
    RETURN count(*) AS n
    '''
    total = 0
    for i in range(0, len(records), WRITE_BATCH):
        n = conn.run_query(cypher, {'records': records[i:i + WRITE_BATCH]})[0]['n']
        total += n
    print(f'Wrote {total} embedding properties')

    # Create vector index
    conn.run_query(f'''
        CREATE VECTOR INDEX chunk_embeddings IF NOT EXISTS
        FOR (c:Chunk) ON (c.embedding)
        OPTIONS {{indexConfig: {{
            `vector.dimensions`: {dim},
            `vector.similarity_function`: 'cosine'
        }}}}
    ''')
    print(f'Vector index chunk_embeddings created ({dim}-dim cosine)')

    for _ in range(20):
        rows = conn.run_query(
            "SHOW INDEXES YIELD name, state WHERE name = 'chunk_embeddings' RETURN state"
        )
        state = rows[0]['state'] if rows else 'UNKNOWN'
        if state == 'ONLINE':
            break
        time.sleep(1)
    print(f'Index state: {state}')

    conn.close()
    print('Done.')


if __name__ == '__main__':
    main()
