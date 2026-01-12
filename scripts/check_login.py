from app.core.security import verify_password
from app.database import SessionLocal
from app.models.user import User


def check():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "dev@example.com").first()
        if user:
            print(f"User found: {user.email}")
            print(f"Hash: {user.hashed_password}")
            is_valid = verify_password("devpassword", user.hashed_password)
            print(f"Password 'devpassword' valid? {is_valid}")
        else:
            print("User NOT found")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    check()
