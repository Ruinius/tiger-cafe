from app.database import SessionLocal
from app.models.company import Company
from app.models.user import User


def debug():
    db = SessionLocal()
    try:
        users = db.query(User).all()
        print(f"Users found: {len(users)}")
        for u in users:
            print(f"  User: id={repr(u.id)}, email={u.email}")

        companies = db.query(Company).all()
        print(f"Companies found: {len(companies)}")
        for c in companies:
            print(f"  Company: id={repr(c.id)}, ticker={c.ticker}, name={c.name}")

        # Check raw sql to see what columns really look like
        # result = db.execute(text("SELECT * FROM companies"))
        # for row in result:
        #     print(f"  Raw Company: {row}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    # We might need to import models to avoid mappers error?
    debug()
