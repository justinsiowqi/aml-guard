import argparse
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
load_dotenv(REPO / '.env')

from src.graph.connection import Neo4jConnection

DATA = REPO / 'data' / 'layer_1'
ENT = DATA / 'entities'
LNK = DATA / 'links'

BATCH_SIZE = 500


def df_records(path, rename=None, drop=None):
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    if rename:
        df = df.rename(columns=rename)
    if drop:
        df = df.drop(columns=[c for c in drop if c in df.columns])
    return df.to_dict(orient='records')


def batch_run(conn, cypher, records, batch_size=BATCH_SIZE):
    total = 0
    for i in range(0, len(records), batch_size):
        chunk = records[i:i + batch_size]
        conn.run_query(cypher, {'records': chunk})
        total += len(chunk)
    return total


def main():
    parser = argparse.ArgumentParser(description='Load Layer 1 entities into Neo4j.')
    parser.add_argument('--reset', action='store_true', help='Wipe Layer 1 nodes before loading.')
    args = parser.parse_args()

    conn = Neo4jConnection().connect()
    print('Connected to', conn._uri)

    if args.reset:
        for label in ('Person', 'Company', 'Intermediary', 'Address', 'Jurisdiction'):
            conn.run_query(f'MATCH (n:{label}) DETACH DELETE n')
        print('Layer 1 wiped.')

    # Constraints
    CONSTRAINTS = [
        'CREATE CONSTRAINT person_node_id        IF NOT EXISTS FOR (n:Person)       REQUIRE n.node_id IS UNIQUE',
        'CREATE CONSTRAINT company_node_id       IF NOT EXISTS FOR (n:Company)      REQUIRE n.node_id IS UNIQUE',
        'CREATE CONSTRAINT intermediary_node_id  IF NOT EXISTS FOR (n:Intermediary) REQUIRE n.node_id IS UNIQUE',
        'CREATE CONSTRAINT address_node_id       IF NOT EXISTS FOR (n:Address)      REQUIRE n.node_id IS UNIQUE',
        'CREATE CONSTRAINT jurisdiction_id       IF NOT EXISTS FOR (n:Jurisdiction) REQUIRE n.jurisdiction_id IS UNIQUE',
    ]
    for c in CONSTRAINTS:
        conn.run_query(c)
    print(f'Applied {len(CONSTRAINTS)} constraints.')

    # Nodes
    ICIJ_RENAME = {'sourceID': 'source_leak'}
    ICIJ_DROP = ['node_type']

    for label, filename in [
        ('Person', 'persons.csv'),
        ('Company', 'companies.csv'),
        ('Intermediary', 'intermediaries.csv'),
    ]:
        records = df_records(ENT / filename, rename=ICIJ_RENAME, drop=ICIJ_DROP)
        n = batch_run(conn, f'UNWIND $records AS row MERGE (n:{label} {{node_id: row.node_id}}) SET n += row', records)
        print(f'{label:<16} {n:>5} nodes')

    records = df_records(ENT / 'addresses.csv')
    n = batch_run(conn, 'UNWIND $records AS row MERGE (n:Address {node_id: row.node_id}) SET n += row', records)
    print(f'{"Address":<16} {n:>5} nodes')

    records = df_records(ENT / 'jurisdictions.csv')
    n = batch_run(conn, 'UNWIND $records AS row MERGE (n:Jurisdiction {jurisdiction_id: row.jurisdiction_id}) SET n += row', records)
    print(f'{"Jurisdiction":<16} {n:>5} nodes')

    # Edges
    records = df_records(LNK / 'is_officer_of.csv')
    n = batch_run(conn, '''
        UNWIND $records AS row
        MATCH (s:Person  {node_id: row.source_id})
        MATCH (t:Company {node_id: row.target_id})
        MERGE (s)-[r:IS_OFFICER_OF]->(t)
        SET r.role        = row.relationship,
            r.source_leak = row.source_leak,
            r.status      = row.status,
            r.start_date  = row.start_date,
            r.end_date    = row.end_date,
            r.link        = row.link
    ''', records)
    print(f'IS_OFFICER_OF:       {n:>5} edges')

    records = df_records(LNK / 'intermediary_of.csv')
    n = batch_run(conn, '''
        UNWIND $records AS row
        MATCH (s:Intermediary {node_id: row.source_id})
        MATCH (t:Company      {node_id: row.target_id})
        MERGE (s)-[r:INTERMEDIARY_OF]->(t)
        SET r.source_leak = row.source_leak,
            r.status      = row.status,
            r.start_date  = row.start_date,
            r.end_date    = row.end_date,
            r.link        = row.link
    ''', records)
    print(f'INTERMEDIARY_OF:     {n:>5} edges')

    records = df_records(LNK / 'registered_at.csv')
    n = batch_run(conn, '''
        UNWIND $records AS row
        MATCH (s         {node_id: row.source_id})
        MATCH (t:Address {node_id: row.target_id})
        MERGE (s)-[r:REGISTERED_AT]->(t)
        SET r.source_leak = row.source_leak,
            r.link        = row.link
    ''', records)
    print(f'REGISTERED_AT:       {n:>5} edges')

    records = df_records(LNK / 'shares_address_with.csv')
    n = batch_run(conn, '''
        UNWIND $records AS row
        MATCH (s:Company {node_id: row.source_id})
        MATCH (t:Company {node_id: row.target_id})
        MERGE (s)-[r:SHARES_ADDRESS_WITH]->(t)
        SET r.address_node_id = row.link,
            r.source_leak     = row.source_leak
    ''', records)
    print(f'SHARES_ADDRESS_WITH: {n:>5} edges')

    records = df_records(LNK / 'similar.csv')
    n = batch_run(conn, '''
        UNWIND $records AS row
        MATCH (s:Company {node_id: row.source_id})
        MATCH (t:Company {node_id: row.target_id})
        MERGE (s)-[r:SIMILAR_TO]->(t)
        SET r.source_leak = row.source_leak,
            r.link        = row.link
    ''', records)
    print(f'SIMILAR_TO:          {n:>5} edges')

    result = conn.run_query('''
        MATCH (c:Company), (j:Jurisdiction)
        WHERE c.jurisdiction = j.jurisdiction_id AND c.jurisdiction <> ''
        MERGE (c)-[:INCORPORATED_IN]->(j)
        RETURN count(*) AS edges
    ''')
    print(f'INCORPORATED_IN:     {result[0]["edges"]:>5} edges')

    conn.close()
    print('Done.')


if __name__ == '__main__':
    main()
