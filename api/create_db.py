from __future__ import annotations
import asyncio
import asyncpg
import re

async def main():
    # Connect to postgres
    conn = await asyncpg.connect(host='localhost', port=5432, user='postgres', password='postgres', database='postgres')
    
    # Drop and create test database
    try:
        await conn.execute('DROP DATABASE ourtdev_test')
    except Exception:
        pass
    await conn.execute('CREATE DATABASE ourtdev_test')
    await conn.close()
    
    # Connect to ourtdev_test
    conn = await asyncpg.connect(host='localhost', port=5432, user='postgres', password='postgres', database='ourtdev_test')
    
    # Read schema file
    with open('/home/gedeonkp/Documents/projet/tdev/ourtdev/database/01_schema.sql', 'r') as f:
        content = f.read()
    
    # Remove comments (lines starting with --)
    lines = content.split('\n')
    code_lines = []
    in_block_comment = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('--'):
            continue
        code_lines.append(line)
    code = '\n'.join(code_lines)
    
    # Remove dollar-quoted strings to avoid breaking on semicolons inside
    # Pattern: $tag$...$tag$ where tag is alphanumeric or empty
    code = re.sub(r'\$(?:\w+\$|).*?\$\w+\$|.*?\$\$', '$$$', code, flags=re.DOTALL)
    # Also remove any remaining dollar-quoted content that doesn't match the pattern
    code = re.sub(r'\$.*?\$', '$$$', code, flags=re.DOTALL)
    
    # Split into statements by semicolon
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
            stmt = ' '.join(current)
            if stmt:
                statements.append(stmt)
            current = []
    
    if current:
        stmt = ' '.join(current)
        if stmt:
            statements.append(stmt)
    
    print(f'Found {len(statements)} statements')
    
    # Execute each statement
    success = 0
    for i, stmt in enumerate(statements):
        stmt = stmt.strip()
        if not stmt:
            continue
        try:
            await conn.execute(stmt)
            success += 1
        except Exception as e:
            msg = str(e).lower()
            if 'transaction' in msg or 'aborted' in msg:
                print(f'  SKIP {i}: {str(e)[:100]}')
            else:
                print(f'  FAIL {i}: {str(e)[:120]}')
    
    # Check tables
    rows = await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
    print(f'Tables: {len(rows)}')
    for r in rows:
        print(' ', r['tablename'])
    
    await conn.close()
    print(f'Done: {success} statements executed')

asyncio.run(main())
