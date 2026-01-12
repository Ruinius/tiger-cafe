import sqlite3


def check_line_items():
    conn = sqlite3.connect("tiger_cafe.db")
    cursor = conn.cursor()

    print("Balance Sheet Line Items:")
    cursor.execute("SELECT line_name FROM balance_sheet_line_items LIMIT 50;")
    rows = cursor.fetchall()
    for row in rows:
        print(f"  - {row[0]}")

    print("\nIncome Statement Line Items:")
    cursor.execute("SELECT line_name FROM income_statement_line_items LIMIT 50;")
    rows = cursor.fetchall()
    for row in rows:
        print(f"  - {row[0]}")


if __name__ == "__main__":
    check_line_items()
