import json

from sqlalchemy import MetaData, create_engine, select
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./tiger_cafe.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()
metadata = MetaData()
metadata.reflect(bind=engine)

data = {}

for table_name in metadata.tables:
    table = metadata.tables[table_name]
    result = db.execute(select(table)).fetchall()
    data[table_name] = [dict(row._mapping) for row in result]


# Handle non-serializable objects (like Decimal or datetime)
def default_serializer(obj):
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    from decimal import Decimal

    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Type {type(obj)} not serializable")


with open("db_dump.json", "w") as f:
    json.dump(data, f, indent=2, default=default_serializer)

print("Database dumped to db_dump.json")
db.close()
