import os
import sqlite3


def migrate():
    db_path = "tiger_cafe.db"
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Step 1: Merging duplicate companies by ticker...")

    # Get all tickers that appear more than once (excluding NULL)
    cursor.execute(
        "SELECT ticker, COUNT(*) FROM companies WHERE ticker IS NOT NULL GROUP BY ticker HAVING COUNT(*) > 1"
    )
    duplicates = cursor.fetchall()

    if not duplicates:
        print("  No duplicates found.")
    else:
        for ticker, count in duplicates:
            print(f"  Found {count} records for ticker: {ticker}")
            cursor.execute("SELECT id, name FROM companies WHERE ticker = ?", (ticker,))
            recs = cursor.fetchall()

            # Decide which one to keep
            # Strategy: Keep the one with a "real" name (not "Processing..."), or the first one.
            main_id = None
            other_ids = []

            for rid, rname in recs:
                if rname != "Processing..." and main_id is None:
                    main_id = rid
                else:
                    if (
                        main_id is None and rid == recs[-1][0]
                    ):  # If all are processing, pick the last one
                        main_id = rid
                    else:
                        other_ids.append(rid)

            # If all were Processing..., main_id might still be None if we didn't pick one
            if main_id is None:
                main_id = other_ids.pop(0)

            print(f"    Keeping ID {main_id}, merging IDs {other_ids}")

            # Update all related tables to point to the main_id
            # Tables that reference companies.id:
            one_to_one_tables = ["financial_assumptions"]
            one_to_many_tables = [
                "documents",
                "financial_metrics",
                "analysis_results",
                "valuations",
            ]

            for table in one_to_one_tables:
                cursor.execute(
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"
                )
                if cursor.fetchone():
                    for oid in other_ids:
                        # If the main company already has a record, delete the one from the merging company
                        cursor.execute(
                            f"DELETE FROM {table} WHERE company_id = ? AND EXISTS (SELECT 1 FROM {table} WHERE company_id = ?)",
                            (oid, main_id),
                        )
                        # Then update any remaining one (if main didn't have one)
                        cursor.execute(
                            f"UPDATE {table} SET company_id = ? WHERE company_id = ?",
                            (main_id, oid),
                        )

            for table in one_to_many_tables:
                cursor.execute(
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"
                )
                if cursor.fetchone():
                    for oid in other_ids:
                        cursor.execute(
                            f"UPDATE {table} SET company_id = ? WHERE company_id = ?",
                            (main_id, oid),
                        )

            # Delete the merged company records
            for oid in other_ids:
                cursor.execute("DELETE FROM companies WHERE id = ?", (oid,))

        conn.commit()

    print("\nStep 2: Recreating companies table with UNIQUE ticker constraint...")

    # 1. Create temporary table
    cursor.execute("DROP TABLE IF EXISTS companies_new")
    cursor.execute("""
        CREATE TABLE companies_new (
            id VARCHAR NOT NULL, 
            name VARCHAR NOT NULL, 
            ticker VARCHAR, 
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
            updated_at DATETIME, 
            PRIMARY KEY (id),
            UNIQUE (ticker)
        )
    """)

    # 2. Copy data
    cursor.execute("""
        INSERT INTO companies_new (id, name, ticker, created_at, updated_at)
        SELECT id, name, ticker, created_at, updated_at FROM companies
    """)

    # 4. Swap tables
    cursor.execute("DROP TABLE companies")
    cursor.execute("ALTER TABLE companies_new RENAME TO companies")

    # 5. Recreate indexes on the new table
    cursor.execute("CREATE INDEX ix_companies_id ON companies (id)")
    cursor.execute("CREATE INDEX ix_companies_name ON companies (name)")
    cursor.execute("CREATE INDEX ix_companies_ticker ON companies (ticker)")

    conn.commit()
    conn.close()
    print("\nMigration completed successfully! Ticker is now a unique identifier.")


if __name__ == "__main__":
    migrate()
