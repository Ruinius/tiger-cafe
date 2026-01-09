# Files Affected by Upload Refactor

## Backend Files

### 🆕 New Files to Create

1. **`app/models/document_status.py`**
   - New unified `DocumentStatus` enum
   - Replaces scattered status definitions

2. **`app/utils/document_queue_v2.py`**
   - New sequential FIFO queue implementation
   - Single worker thread
   - Replaces `app/utils/document_processing_queue.py`

3. **`app/services/upload_handler.py`**
   - Unified upload logic
   - File saving with rollback
   - Duplicate detection integration

4. **`app/services/cleanup_service.py`**
   - Daily cleanup job for failed uploads
   - Orphaned file detection and removal

5. **`app/schemas/file_metadata.py`**
   - Schema for pre-upload duplicate check
   - `FileMetadata` model for quick hash

6. **`migrations/add_unified_status_fields.py`**
   - Migration script for new document fields
   - Backfill logic for existing documents

### ✏️ Existing Files to Modify

#### Models
7. **`app/models/document.py`**
   - Add `status` field (String, indexed)
   - Add `file_size` field (Integer)
   - Add `error_message` field (Text)
   - Add `processing_metadata` field (Text/JSON)
   - Add `current_step` field (String)
   - Mark `indexing_status` and `analysis_status` as deprecated

8. **`app/models/__init__.py`**
   - Export new `DocumentStatus` enum
   - Export new schemas

#### Routers
9. **`app/routers/documents.py`** ⚠️ **MAJOR CHANGES**
   - Add `POST /check-duplicates-batch` endpoint
   - Modify `POST /upload-batch` to use new queue
   - Add `GET /processing-queue-status` endpoint
   - Add `GET /status-stream` (SSE endpoint)
   - Remove old `upload_and_process_async*` functions
   - Update `GET /upload-progress` to use new status field
   - **PRESERVE**: Re-run endpoints (no changes needed)

10. **`app/routers/balance_sheet.py`**
    - Update `process_balance_sheet_async` to use new status enum
    - Update status transitions to use unified `status` field
    - **PRESERVE**: `POST /{document_id}/balance-sheet/re-run` (no changes)

11. **`app/routers/income_statement.py`**
    - Update `process_income_statement_async` to use new status enum
    - Update status transitions to use unified `status` field
    - **PRESERVE**: `POST /{document_id}/income-statement/re-run` (no changes)

#### Services
12. **`app/services/document_processing.py`**
    - Update to use new `DocumentStatus` enum
    - Remove `DocumentProcessingMode` enum
    - Simplify to synchronous processing functions
    - Add error handling with cleanup

#### Utils
13. **`app/utils/document_indexer.py`**
    - Update status updates to use new `status` field
    - No functional changes

14. **`app/utils/duplicate_detector.py`**
    - Add quick hash comparison logic
    - Add file size comparison

15. **`app/database.py`**
    - No changes (unless adding scheduler for cleanup job)

#### Configuration
16. **`migrate_baseline_schema.py`**
    - Update expected tables/columns
    - Add new fields to verification

17. **`config/config.py`**
    - Add `USE_NEW_UPLOAD_WORKFLOW` feature flag
    - Add cleanup job configuration

### 🗑️ Files to Deprecate (Not Delete Yet)

18. **`app/utils/document_processing_queue.py`**
    - Mark as deprecated
    - Keep for rollback capability
    - Delete after successful migration

---

## Frontend Files

### 🆕 New Files to Create

19. **`frontend/src/hooks/useSSEConnection.js`**
    - Custom hook for SSE connection management
    - Auto-reconnect logic
    - Event handling

20. **`frontend/src/utils/fileHash.js`**
    - Quick hash computation (first 5KB)
    - SHA-256 implementation using Web Crypto API

21. **`frontend/src/components/modals/DuplicateConfirmationModal.jsx`**
    - Shows duplicate detection results
    - User confirmation UI
    - File selection for upload

### ✏️ Existing Files to Modify

#### Contexts
22. **`frontend/src/contexts/UploadContext.jsx`** ⚠️ **MAJOR CHANGES**
    - Remove polling logic (replaced by SSE)
    - Add SSE connection management
    - Add queue status state
    - Add duplicate check logic

#### Hooks
23. **`frontend/src/hooks/useUploadManager.js`**
    - Add pre-upload duplicate check
    - Update to use new upload endpoint
    - Add queue position tracking

24. **`frontend/src/hooks/useDocumentData.js`**
    - Update to use new `status` field
    - Update status display logic
    - **PRESERVE**: Re-run functionality (no changes)

#### Components - Modals
25. **`frontend/src/components/modals/UploadModal.jsx`**
    - Add duplicate check before upload
    - Show quick hash computation progress
    - Integrate with `DuplicateConfirmationModal`

26. **`frontend/src/components/modals/UploadProgressModal.jsx`**
    - Update to use SSE instead of polling
    - Add queue position display
    - Update status display for new status enum

#### Components - Views
27. **`frontend/src/components/views/document/DocumentExtractionView.jsx`**
    - Update status display to use new enum
    - **PRESERVE**: All re-run buttons and logic
    - Update progress tracker to show new status names

28. **`frontend/src/components/views/company/DocumentList.jsx`**
    - Update document status badges
    - Add queue position indicator

#### Utils
29. **`frontend/src/utils/formatting.js`**
    - Add status formatting for new enum values
    - Add queue position formatting

---

## Documentation Files

30. **`docs/DATABASE_SCHEMA.md`**
    - Update `documents` table schema
    - Add new fields documentation
    - Mark deprecated fields

31. **`docs/PRODUCT_SPECS.md`**
    - Update upload workflow documentation
    - Add duplicate detection flow
    - Update status progression

32. **`docs/ARCHITECTURE.md`** (if exists)
    - Update queue architecture diagram
    - Add SSE connection documentation

33. **`docs/API.md`** (if exists)
    - Add new endpoints
    - Update status enum values
    - Add SSE endpoint documentation

---

## Test Files

### 🆕 New Test Files

34. **`tests/test_document_queue_v2.py`**
    - Test sequential processing
    - Test queue ordering
    - Test error handling

35. **`tests/test_upload_handler.py`**
    - Test file upload
    - Test duplicate detection
    - Test rollback on errors

36. **`tests/test_cleanup_service.py`**
    - Test daily cleanup job
    - Test file deletion logic

37. **`frontend/src/__tests__/useSSEConnection.test.jsx`**
    - Test SSE connection
    - Test reconnection logic
    - Test event handling

### ✏️ Existing Test Files to Update

38. **`tests/test_documents.py`**
    - Update to use new status enum
    - Add tests for new endpoints
    - Update upload flow tests

39. **`tests/test_document_processing.py`**
    - Update to use new queue
    - Update status assertions

40. **`frontend/src/__tests__/UploadContext.test.jsx`**
    - Remove polling tests
    - Add SSE tests
    - Add duplicate check tests

---

## Configuration Files

41. **`requirements.txt`** (or `pyproject.toml`)
    - Add `sse-starlette` (for SSE support)
    - Add `apscheduler` (for cleanup job, if not already present)

42. **`.env.example`**
    - Add `USE_NEW_UPLOAD_WORKFLOW=false`
    - Add cleanup job configuration

---

## Re-Run Flow Compatibility

### ✅ Files That Must NOT Change (Re-run Functionality)

These files contain re-run logic that must remain compatible:

1. **`app/routers/balance_sheet.py`**
   - `POST /{document_id}/balance-sheet/re-run` ✅ No changes
   - Re-run logic is independent of upload queue

2. **`app/routers/income_statement.py`**
   - `POST /{document_id}/income-statement/re-run` ✅ No changes
   - Re-run logic is independent of upload queue

3. **`frontend/src/components/views/document/DocumentExtractionView.jsx`**
   - Re-run buttons ✅ Preserved
   - Only update status display, not re-run logic

### 🔄 Re-Run Flow Considerations

**How Re-runs Work with New Queue:**

```
User clicks "Re-run Balance Sheet"
  ↓
POST /documents/{id}/balance-sheet/re-run
  ↓
Directly calls process_balance_sheet_async()
  ↓
Does NOT go through upload queue
  ↓
Updates document status directly
  ↓
SSE pushes update to frontend
```

**Key Points:**
- Re-runs bypass the upload queue entirely
- Re-runs update the same `status` field
- SSE will show re-run progress in real-time
- No conflicts with sequential queue (re-runs are on-demand)

---

## Summary

### File Count by Category:
- **New Backend Files**: 6
- **Modified Backend Files**: 12
- **Deprecated Backend Files**: 1
- **New Frontend Files**: 3
- **Modified Frontend Files**: 9
- **Documentation Files**: 4
- **New Test Files**: 4
- **Modified Test Files**: 3
- **Configuration Files**: 2

**Total Files Affected**: ~44 files

### Critical Path Files (Must be done first):
1. `app/models/document.py` (schema changes)
2. `migrations/add_unified_status_fields.py` (migration)
3. `app/models/document_status.py` (new enum)
4. `app/utils/document_queue_v2.py` (new queue)
5. `app/routers/documents.py` (new endpoints)

### Low-Risk Files (Can be done in parallel):
- Frontend SSE implementation
- Cleanup service
- Test files
- Documentation updates
