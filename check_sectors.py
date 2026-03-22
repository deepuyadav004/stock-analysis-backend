from app.core.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text("SELECT * FROM sectors"))
    sectors = [dict(row) for row in result.mappings()]
    print(sectors)
