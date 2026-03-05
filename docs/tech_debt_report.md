# Tech Debt & Spaghetti Code Scan Report

Generated: 2026-03-05

---

## 1. Monster Files (Primary Concern)

| File | Lines | Issues |
|------|-------|--------|
| `routers/documents.py` | **1789** | Mixes 15+ test endpoints with production code, handles upload/chunks/status/deletion in one file |
| `services/extraction_orchestrator.py` | **1424** | God class coordinating 4 pipeline phases with massive try-except blocks |
| `app_agents/document_classifier.py` | **942** | 80+ debug prints, step-by-step logic should be broken out |
| `app_agents/balance_sheet_extractor.py` | **868** | All extraction logic in one file |
| `app_agents/income_statement_extractor.py` | **829** | Same pattern |
| `utils/historical_calculations.py` | **801** | 50+ standalone functions, no cohesion |

---

## 2. Code Duplication (DRY Violations)

**Duplicated functions across extractor files:**

- `_deduplicate_line_items` - exists in:
  - `app_agents/amortization_extractor.py`
  - `app_agents/other_assets_extractor.py`
  - `app_agents/other_liabilities_extractor.py`

- `_normalize_value` - in:
  - `app_agents/organic_growth_extractor.py`
  - `app_agents/income_statement_extractor.py`

- `_within_tolerance` - in:
  - `app_agents/other_assets_extractor.py`
  - `app_agents/other_liabilities_extractor.py`

**Solution:** Extract to `app_agents/extractor_helpers.py` or similar shared module.

---

## 3. Debug Code Left in Production

Found **80+ debug print statements** in production code:

- `app_agents/document_classifier.py`: ~60 debug prints (STEP 1, STEP 2, etc.)
- `routers/income_statement.py`: Debug print for first 5 line items
- `routers/balance_sheet.py`: Same pattern

Example:
```python
print(f"\n[DEBUG] Income Statement found for document {document_id}")
print(f"[DEBUG] Currency: {income_statement.currency}, Unit: {income_statement.unit}")
```

---

## 4. Test Functions in Production Routers

Found **16 `*_test` endpoints** directly in router files instead of in `tests/`:

```python
# routers/documents.py - 11 test functions
async def upload_batch_test(...)
async def upload_document_test(...)
async def list_documents_test(...)
async def get_document_file_test(...)
async def confirm_upload_test(...)
async def replace_and_index_test(...)
async def rerun_indexing_test(...)
async def delete_document_test(...)
async def delete_document_permanent_test(...)
async def get_financial_statement_progress_test(...)
async def get_document_status_test(...)
async def get_document_chunks_test(...)

# routers/companies.py
async def get_company_historical_calculations_test(...)

# routers/historical_calculations.py
def get_historical_calculations_test(...)
def recalculate_historical_calculations_test(...)

# routers/balance_sheet.py
async def delete_financial_statements_test(...)
```

**Risk:** These are enabled via `if DEBUG:` but expose internal endpoints and clutter production code.

---

## 5. Lazy Imports (Circular Dependency Smell)

Multiple files use runtime imports to avoid circular import errors:

```python
# services/extraction_orchestrator.py
from app.app_agents.balance_sheet_extractor import extract_balance_sheet  # inside function

from app.services.classification_service import classify_non_operating_items_task  # inside function

# utils/document_queue_v2.py
from app.services.extraction_orchestrator import run_full_extraction_pipeline  # inside function
```

**This indicates tight coupling between modules.**

---

## 6. Magic Numbers Hardcoded

| Value | Locations | Should Be Constant |
|-------|-----------|-------------------|
| `1_000_000` | 1 place | `MIN_SHARES_THRESHOLD` |
| `10` | 2 places | `MAX_BATCH_UPLOAD` |
| `5000` | 2 places | `TEXT_PREVIEW_LENGTH` |
| `0.01` | 8+ places | `FLOAT_TOLERANCE` |
| `0.20` (20%) | 1 place | `MAX_FAILURE_RATE` |
| `1_000_000` | shares validation | `MIN_VALID_SHARES` |

---

## 7. Broad Exception Handling

Found **60+ instances** of:
```python
except Exception as e:
    # swallows all errors silently
```

This masks bugs and makes debugging difficult. Errors are often logged but execution continues without proper error propagation.

---

## 8. Missing Separation of Concerns

### routers/documents.py
Handles multiple unrelated responsibilities:
- File upload
- Batch upload
- Duplicate checking
- Queue status
- Chunk retrieval
- Document listing
- Document deletion
- Financial statement progress
- Status streaming

### services/extraction_orchestrator.py
Coordinates entire pipeline but should be split into separate pipeline classes:
- `IngestionPipeline`
- `ExtractionPipeline`
- `AnalysisPipeline`

---

## Priority Recommendations

### Immediate (P0)
1. **Remove all debug print statements** - Search for `print("[DEBUG]` and remove

### High (P1)
2. **Move test endpoints to `tests/e2e/` directory** - Create proper test-only routes
3. **Extract duplicate helper functions** - Create `app_agents/extractor_helpers.py`

### Medium (P2)
4. **Refactor `routers/documents.py`** - Split by responsibility into separate routers:
   - `document_upload.py`
   - `document_chunks.py`
   - `document_status.py`
   - `document_deletion.py`

5. **Add constants file** - Create `app/constants.py` for magic numbers

6. **Add specific exception types** - Replace broad `Exception` catch with specific types

### Lower (P3)
7. **Refactor extraction orchestrator** - Split into pipeline phase classes
8. **Add type hints throughout** - Many functions lack proper typing

---

## Notes

- This scan was performed by analyzing the codebase structure, function definitions, and code patterns
- Some patterns (like lazy imports) may be acceptable tradeoffs for this architecture but should be documented
- The DEBUG-gated test endpoints are a convenience pattern but should be reviewed for security
