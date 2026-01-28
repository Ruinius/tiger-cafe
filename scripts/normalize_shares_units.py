import os
import sys

# Add project root to sys.path to allow imports from app
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Ensure we run from the project root so that relative paths work correctly
os.chdir(project_root)

if project_root not in sys.path:
    sys.path.append(project_root)

from sqlalchemy.orm import joinedload  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.document import Document  # noqa: E402
from app.utils.line_item_utils import convert_from_ones, convert_to_ones  # noqa: E402


# Helper to convert a specific field
def process_field(shares, val_field, unit_field, target_unit, doc_filename, doc_id):
    val = getattr(shares, val_field)
    unit_name = getattr(shares, unit_field)

    # Check if we have a value, a unit, and that unit differs from target
    if val is not None and unit_name and target_unit.lower().strip() != unit_name.lower().strip():
        try:
            val_ones = convert_to_ones(float(val), unit_name)
            val_converted = convert_from_ones(val_ones, target_unit)

            print(
                f"  [Doc {doc_filename}] Converting {val_field}: {val} {unit_name} -> {val_converted:.2f} {target_unit}"
            )

            setattr(shares, val_field, val_converted)
            setattr(shares, unit_field, target_unit)
            return True
        except Exception as e:
            print(f"  [Error] Converting {val} {unit_name} to {target_unit} for doc {doc_id}: {e}")
    return False


def normalize_shares():
    db = SessionLocal()
    try:
        print("Checking for share unit inconsistencies...")
        documents = (
            db.query(Document)
            .options(joinedload(Document.income_statement), joinedload(Document.shares_outstanding))
            .all()
        )

        modified_count = 0
        total_checked = 0

        for doc in documents:
            if not doc.income_statement or not doc.shares_outstanding:
                continue

            total_checked += 1
            target_unit = doc.income_statement.unit
            if not target_unit:
                continue

            shares = doc.shares_outstanding
            modified = False

            if process_field(
                shares,
                "basic_shares_outstanding",
                "basic_shares_outstanding_unit",
                target_unit,
                doc.filename,
                doc.id,
            ):
                modified = True

            if process_field(
                shares,
                "diluted_shares_outstanding",
                "diluted_shares_outstanding_unit",
                target_unit,
                doc.filename,
                doc.id,
            ):
                modified = True

            if modified:
                modified_count += 1

        if modified_count > 0:
            db.commit()
            print(f"\nSuccessfully updated {modified_count} out of {total_checked} documents.")
        else:
            print(f"\nNo inconsistencies found in {total_checked} documents.")

    finally:
        db.close()


if __name__ == "__main__":
    normalize_shares()
