from __future__ import annotations
import asyncio, asyncpg

async def main():
    conn = await asyncpg.connect(host='localhost', port=5432, user='postgres', password='postgres', database='postgres')
    try:
        await conn.execute('DROP DATABASE ourtdev_test')
    except Exception:
        pass
    await conn.execute('CREATE DATABASE ourtdev_test')
    await conn.close()

    with open('/home/gedeonkp/Documents/projet/tdev/ourtdev/database/01_schema.sql', 'r') as f:
        schema = f.read()

    # Split into statements
    lines = schema.split('\n')
    code_lines = [l for l in lines if not l.strip().startswith('--')]
    code = '\n'.join(code_lines)

    statements = []
    current = []
    for line in code.split('\n'):
        stripped = line.strip()
        if stripped == 'BEGIN;':
            continue
        if stripped == 'COMMIT;':
            continue
        if stripped:
            current.append(stripped)
        if line.rstrip().endswith(';'):
            stmt = ' '.join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
    if current:
        stmt = ' '.join(current).strip()
        if stmt:
            statements.append(stmt)

    print(f'Found {len(statements)} statements')

    conn = await asyncpg.connect(host='localhost', port=5432, user='postgres', password='postgres', database='ourtdev_test')

    for i, stmt in enumerate(statements):
        try:
            await conn.execute(stmt)
        except Exception as e:
            err = str(e)
            if 'referenced table' in err or 'relation' in err:
                print(f'  SKIP {i} (fun): {err[:80]}')
            else:
                print(f'  FAIL {i}: {err[:80]}')

    rows = await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname='public'")
    print(f'Tables: {len(rows)}')
    for r in rows:
        print(' ', r['tablename'])

    await conn.close()
    print('Done')

asyncio.run(main())
