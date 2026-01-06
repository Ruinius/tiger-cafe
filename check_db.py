import sqlite3


def check_db():
    conn = sqlite3.connect("tiger_cafe.db")
    cursor = conn.cursor()

    print("Tables:")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    for table in tables:
        print(f"  - {table[0]}")

    print("\nCompanies:")
    cursor.execute("SELECT id, name, ticker FROM companies;")
    companies = cursor.fetchall()
    for company in companies:
        print(f"  - {company}")

    print("\nDocuments:")
    cursor.execute("SELECT id, filename, company_id, status FROM documents;")
    docs = cursor.fetchall()
    for doc in docs:
        print(f"  - {doc}")


if __name__ == "__main__":
    check_db()
