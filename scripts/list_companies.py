from app.database import SessionLocal
from app.models.company import Company

db = SessionLocal()
companies = db.query(Company).all()
for c in companies:
    print(f"ID: {c.id}, Name: {c.name}, Ticker: {c.ticker}")
db.close()
