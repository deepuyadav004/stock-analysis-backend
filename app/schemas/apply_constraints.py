"""One-off migration: add UNIQUE constraints required for ON CONFLICT upserts."""
from sqlalchemy import text
from app.core.database import engine

migrations = [
    (
        "companies_name_key",
        "companies",
        "ALTER TABLE companies ADD CONSTRAINT companies_name_key UNIQUE (name)",
    ),
    (
        "exchanges_code_key",
        "exchanges",
        "ALTER TABLE exchanges ADD CONSTRAINT exchanges_code_key UNIQUE (code)",
    ),
    (
        "listings_company_exchange_key",
        "listings",
        "ALTER TABLE listings ADD CONSTRAINT listings_company_exchange_key UNIQUE (company_id, exchange_id)",
    ),
]

with engine.begin() as conn:
    for constraint_name, table, ddl in migrations:
        exists = conn.execute(
            text("SELECT 1 FROM pg_constraint WHERE conname = :name"),
            {"name": constraint_name},
        ).scalar_one_or_none()

        if exists:
            print(f"SKIP  {constraint_name} (already exists)", flush=True)
        else:
            conn.execute(text(ddl))
            print(f"OK    {constraint_name}", flush=True)

print("Done.")
