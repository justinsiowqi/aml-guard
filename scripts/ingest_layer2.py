import argparse
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
load_dotenv(REPO / '.env')

from src.graph.connection import Neo4jConnection

EX = REPO / 'data' / 'layer_2' / 'extracted'
BATCH_SIZE = 500


def df_records(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False).to_dict(orient='records')


def batch_run(conn, cypher, records, batch_size=BATCH_SIZE):
    total = 0
    for i in range(0, len(records), batch_size):
        conn.run_query(cypher, {'records': records[i:i + batch_size]})
        total += len(records[i:i + batch_size])
    return total


def main():
    parser = argparse.ArgumentParser(description='Ingest Layer 2 (MAS Notice 626) into Neo4j.')
    parser.add_argument('--reset', action='store_true', help='Wipe Layer 2 before reloading.')
    args = parser.parse_args()

    conn = Neo4jConnection().connect()
    print('Connected to', conn._uri)

    if args.reset:
        for label in ('Chunk', 'Threshold', 'Requirement', 'Section', 'Regulation'):
            conn.run_query(f'MATCH (n:{label}) DETACH DELETE n')
        print('Layer 2 wiped.')

    # Constraints
    CONSTRAINTS = [
        'CREATE CONSTRAINT regulation_id   IF NOT EXISTS FOR (n:Regulation)  REQUIRE n.regulation_id  IS UNIQUE',
        'CREATE CONSTRAINT section_id      IF NOT EXISTS FOR (n:Section)     REQUIRE n.section_id     IS UNIQUE',
        'CREATE CONSTRAINT requirement_id  IF NOT EXISTS FOR (n:Requirement) REQUIRE n.requirement_id IS UNIQUE',
        'CREATE CONSTRAINT threshold_id    IF NOT EXISTS FOR (n:Threshold)   REQUIRE n.threshold_id   IS UNIQUE',
        'CREATE CONSTRAINT chunk_id        IF NOT EXISTS FOR (n:Chunk)       REQUIRE n.chunk_id       IS UNIQUE',
    ]
    for c in CONSTRAINTS:
        conn.run_query(c)
    print(f'Applied {len(CONSTRAINTS)} constraints.')

    # Nodes
    for label, filename, key in [
        ('Regulation',  'regulations.csv',  'regulation_id'),
        ('Section',     'sections.csv',     'section_id'),
        ('Requirement', 'requirements.csv', 'requirement_id'),
        ('Threshold',   'thresholds.csv',   'threshold_id'),
        ('Chunk',       'chunks.csv',       'chunk_id'),
    ]:
        records = df_records(EX / filename)
        n = batch_run(conn, f'UNWIND $records AS row MERGE (n:{label} {{{key}: row.{key}}}) SET n += row', records)
        print(f'{label:<14} {n:>4} nodes')

    # Edges derived from node properties
    edges = [
        ('HAS_SECTION', '''
            MATCH (r:Regulation), (s:Section)
            WHERE s.regulation_id = r.regulation_id
            MERGE (r)-[:HAS_SECTION]->(s)
            RETURN count(*) AS n
        '''),
        ('NEXT_SECTION', '''
            MATCH (s:Section)
            WITH s.regulation_id AS reg, s, toInteger(s.section_number) AS sn
            ORDER BY reg, sn
            WITH reg, collect(s) AS ordered
            UNWIND range(0, size(ordered) - 2) AS i
            WITH ordered[i] AS a, ordered[i + 1] AS b
            MERGE (a)-[:NEXT_SECTION]->(b)
            RETURN count(*) AS n
        '''),
        ('HAS_REQUIREMENT', '''
            MATCH (s:Section), (req:Requirement)
            WHERE req.section_id = s.section_id
            MERGE (s)-[:HAS_REQUIREMENT]->(req)
            RETURN count(*) AS n
        '''),
        ('DEFINES_THRESHOLD', '''
            MATCH (req:Requirement), (t:Threshold)
            WHERE req.regulation_id = t.regulation_id AND req.paragraph = t.paragraph
            MERGE (req)-[:DEFINES_THRESHOLD]->(t)
            RETURN count(*) AS n
        '''),
        ('HAS_CHUNK', '''
            MATCH (req:Requirement), (c:Chunk)
            WHERE req.regulation_id = c.regulation_id AND req.paragraph = c.paragraph
            MERGE (req)-[:HAS_CHUNK]->(c)
            RETURN count(*) AS n
        '''),
        ('NEXT_CHUNK', '''
            MATCH (c:Chunk)
            WITH c.regulation_id AS reg, c.paragraph AS para, c, toInteger(c.chunk_index) AS idx
            ORDER BY reg, para, idx
            WITH reg, para, collect(c) AS ordered
            UNWIND range(0, size(ordered) - 2) AS i
            WITH ordered[i] AS a, ordered[i + 1] AS b
            MERGE (a)-[:NEXT_CHUNK]->(b)
            RETURN count(*) AS n
        '''),
    ]
    for name, cypher in edges:
        n = conn.run_query(cypher)[0]['n']
        print(f'{name:<20} {n:>4} edges')

    # CROSS_REFERENCES from CSV
    records = df_records(EX / 'cross_references.csv')
    n = batch_run(conn, '''
        UNWIND $records AS row
        MATCH (src:Requirement {regulation_id: row.regulation_id, paragraph: row.source_paragraph})
        MATCH (tgt:Requirement {regulation_id: row.regulation_id, paragraph: row.target_paragraph})
        MERGE (src)-[r:CROSS_REFERENCES]->(tgt)
        SET r.context = row.context
    ''', records)
    print(f'{"CROSS_REFERENCES":<20} {n:>4} edges attempted')

    conn.close()
    print('Done.')


if __name__ == '__main__':
    main()
