"""Check which tables exist in the database."""
import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        'postgresql://postgres:tXoUhCreOiwCthjGiTEbzckBjXkysZuk@postgres.railway.internal:5432/railway'
    )
    rows = await conn.fetch(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
        "ORDER BY table_name"
    )
    print(f"Tables in database ({len(rows)}):")
    for r in rows:
        print(f"  - {r['table_name']}")
    await conn.close()

asyncio.run(main())
