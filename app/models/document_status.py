import enum


class DocumentStatus(str, enum.Enum):
    # Upload Phase
    UPLOADING = "uploading"
    UPLOAD_FAILED = "upload_failed"
    PENDING = "pending"  # Initial state after upload before processing

    # Pre-Processing (Duplicate Check - happens BEFORE file upload)
    CHECKING_DUPLICATE = "checking_duplicate"
    AWAITING_CONFIRMATION = "awaiting_confirmation"  # User must confirm (duplicate or new)
    DUPLICATE_DETECTED = "duplicate_detected"

    # Classification Phase
    CLASSIFYING = "classifying"
    CLASSIFICATION_FAILED = "classification_failed"

    # Indexing Phase (Earnings Announcements only)
    INDEXING = "indexing"
    INDEXING_FAILED = "indexing_failed"
    INDEXED = "indexed"  # Milestone state: Indexing complete, financial extraction next

    # Non-Earnings Announcements
    CLASSIFIED = "classified"  # Terminal state for non-earnings docs

    # Financial Statement Processing (Earnings Announcements only)
    EXTRACTING_BALANCE_SHEET = "extracting_balance_sheet"
    EXTRACTING_INCOME_STATEMENT = "extracting_income_statement"
    EXTRACTING_ADDITIONAL_ITEMS = "extracting_additional_items"
    CLASSIFYING_NON_OPERATING = "classifying_non_operating"
    PROCESSING_COMPLETE = "processing_complete"  # Terminal state for fully processed earnings docs

    # Error States
    EXTRACTION_FAILED = "extraction_failed"
