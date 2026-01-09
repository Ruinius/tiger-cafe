# Upload and Document Processing Workflow Refactor Plan

## Current State Analysis

### Identified Issues

1. **Multiple Upload Paths with Inconsistent Behavior**
   - `upload_batch` (multi-file) vs `upload` (single file)
   - `upload_and_process_async_with_content` vs `upload_and_process_async`
   - Different handling of file content reading
   - Duplicate code between authenticated and test endpoints

2. **Confusing Status Flow**
   - Documents transition through: `UPLOADING` → `CLASSIFYING` → `INDEXING` → `INDEXED`/`CLASSIFIED`
   - Special case: Non-earnings announcements end at `CLASSIFIED` (not indexed)
   - `PENDING` status exists but usage is unclear
   - Status updates scattered across multiple functions

3. **Queue Processing Complexity**
   - Priority queue with two task types: `classification_indexing` and `financial_statements`
   - Worker thread management with shutdown events
   - Conditional auto-triggering of financial statements based on document type
   - Re-indexing vs initial indexing logic is convoluted

4. **Duplicate Detection Timing**
   - Happens during classification (after file upload)
   - Creates orphaned files if duplicate is confirmed
   - User confirmation flow is separate from main processing

5. **Error Handling Gaps**
   - File cleanup on errors is inconsistent
   - Database rollback logic is incomplete
   - Worker thread errors may leave documents in bad states

6. **Frontend Polling Issues**
   - `UploadContext` polls every 3 seconds
   - Dependency array issues can cause infinite loops
   - No WebSocket or SSE for real-time updates

7. **Processing Mode Confusion**
   - `PREVIEW` mode (for upload confirmation)
   - `FULL` mode (classification + indexing)
   - `INDEX_ONLY` mode (re-indexing)
   - Modes have overlapping responsibilities

---

## Proposed Refactor

### Core Principle: **Strict Sequential Processing**

**Problem**: Current queue allows concurrent processing of different pipeline stages (classification, indexing, financial extraction), causing race conditions and unpredictable results.

**Solution**: Enforce **one document at a time, end-to-end** processing. No document enters the pipeline until the previous document reaches a terminal state (`INDEXED`, `CLASSIFIED`, `PROCESSING_COMPLETE`, or `ERROR`).

---

### Phase 1: Simplify Status Model

**Goal**: Create a clear, linear status progression with explicit substates.

#### New Status Enum Structure
```python
class DocumentStatus(str, Enum):
    # Upload Phase
    UPLOADING = "uploading"
    UPLOAD_FAILED = "upload_failed"
    
    # Pre-Processing (Duplicate Check - happens BEFORE file upload)
    CHECKING_DUPLICATE = "checking_duplicate"
    AWAITING_CONFIRMATION = "awaiting_confirmation"  # User must confirm (duplicate or new)
    
    # Classification Phase
    CLASSIFYING = "classifying"
    CLASSIFICATION_FAILED = "classification_failed"
    
    # Indexing Phase (Earnings Announcements only)
    INDEXING = "indexing"
    INDEXING_FAILED = "indexing_failed"
    INDEXED = "indexed"  # Terminal state for earnings announcements (before financial extraction)
    
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
```

#### Changes
- Merge `indexing_status` and `analysis_status` into single `status` field
- Add `error_message` field for failure details
- Add `processing_metadata` JSON field for substatus tracking
- Add `current_step` field to track exact position in pipeline

---

### Phase 2: Pre-Upload Duplicate Detection

**Goal**: Detect duplicates BEFORE file upload to avoid orphaned files and wasted processing.

#### New Flow
```
1. User selects files in UI
2. Frontend computes quick hash (first 5KB of each file)
3. Frontend sends metadata to POST /documents/check-duplicates-batch
   - Payload: [{ filename, size, quick_hash }, ...]
4. Backend checks against existing documents
5. Backend returns: [{ filename, is_potential_duplicate, existing_doc_info }, ...]
6. Frontend shows confirmation dialog for duplicates
7. User confirms which files to upload
8. Only confirmed files proceed to upload
```

#### Implementation Details

**Frontend (Before Upload)**:
```javascript
// Compute quick hash from first 5KB of file
async function computeQuickHash(file) {
  const slice = file.slice(0, 5120) // 5KB
  const arrayBuffer = await slice.arrayBuffer()
  const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer)
  return Array.from(new Uint8Array(hashBuffer))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('')
}

// Check all files before upload
const fileMetadata = await Promise.all(
  files.map(async file => ({
    filename: file.name,
    size: file.size,
    quick_hash: await computeQuickHash(file)
  }))
)

const duplicateCheck = await axios.post('/documents/check-duplicates-batch', {
  files: fileMetadata
})
```

**Backend Endpoint**:
```python
@router.post("/check-duplicates-batch")
async def check_duplicates_batch(
    files: List[FileMetadata],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Check for potential duplicates before upload.
    Returns list of potential matches for user confirmation.
    """
    results = []
    for file_meta in files:
        # Check by filename + size first (fast)
        potential_dupe = db.query(Document).filter(
            Document.filename == file_meta.filename,
            Document.file_size == file_meta.size  # Add this field
        ).first()
        
        results.append({
            "filename": file_meta.filename,
            "is_potential_duplicate": potential_dupe is not None,
            "existing_document": {
                "id": potential_dupe.id,
                "uploaded_by": potential_dupe.user.name,
                "uploaded_at": potential_dupe.uploaded_at
            } if potential_dupe else None
        })
    
    return results
```

**Benefits**:
- No orphaned files
- Faster user feedback
- Reduced server load (no unnecessary uploads)
- User makes decision upfront

---

### Phase 3: Strict Sequential Queue with Single Worker

**Goal**: Process exactly one document at a time, end-to-end, with no concurrency.

#### New Queue Architecture

**Single FIFO Queue** (no priority, no task types):
```python
class DocumentQueue:
    def __init__(self):
        self._queue = queue.Queue()  # Simple FIFO, not PriorityQueue
        self._current_document_id = None
        self._lock = threading.Lock()
        self._worker_thread = None
    
    def enqueue(self, document_id: str):
        """Add document to queue. Will process when ready."""
        self._queue.put(document_id)
        self._ensure_worker()
    
    def _process_next(self):
        """Process one complete document lifecycle."""
        document_id = self._queue.get()
        
        with self._lock:
            self._current_document_id = document_id
        
        try:
            # Step 1: Classification
            classify_document_sync(document_id)
            
            # Step 2: Check if indexing needed
            doc = get_document(document_id)
            if doc.document_type == DocumentType.EARNINGS_ANNOUNCEMENT:
                # Step 3: Index document
                index_document_sync(document_id)
                
                # Step 4: Extract financial statements (blocking)
                extract_balance_sheet_sync(document_id)
                extract_income_statement_sync(document_id)
                extract_additional_items_sync(document_id)
                classify_non_operating_sync(document_id)
                
                # Mark complete
                update_status(document_id, DocumentStatus.PROCESSING_COMPLETE)
            else:
                # Non-earnings: just classify
                update_status(document_id, DocumentStatus.CLASSIFIED)
        
        except Exception as e:
            handle_error(document_id, e)
        
        finally:
            with self._lock:
                self._current_document_id = None
            self._queue.task_done()
```

#### Key Changes from Current Implementation

**Current (Problematic)**:
- Priority queue with 2 task types
- Classification/indexing can run while financial extraction runs
- Multiple documents in different stages simultaneously
- Race conditions when accessing shared resources (embeddings, database)

**New (Sequential)**:
- Single FIFO queue
- One document processes completely before next starts
- All steps are **synchronous** (blocking)
- Worker thread processes one document at a time
- No race conditions possible

#### Processing Flow

```
Document A enters queue
├─ Classify (blocking)
├─ Index (blocking)
├─ Extract BS (blocking)
├─ Extract IS (blocking)
├─ Extract Additional (blocking)
├─ Classify Non-Op (blocking)
└─ Mark COMPLETE

Document B enters queue (waits for A to finish)
├─ Classify (blocking)
└─ Mark CLASSIFIED (non-earnings, skips rest)

Document C enters queue (waits for B to finish)
...
```

#### Queue Status Endpoint

```python
@router.get("/processing-queue-status")
async def get_queue_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get current queue status for UI display.
    """
    return {
        "current_document_id": queue._current_document_id,
        "queue_length": queue._queue.qsize(),
        "queued_documents": list(queue._queue.queue)  # Preview
    }
```

**Frontend Display**:
```
Processing Queue
├─ Currently Processing: AAPL Q3 2023 (Step 3/7: Indexing...)
└─ In Queue: 2 documents
    ├─ MSFT Q3 2023
    └─ GOOGL Q3 2023
```

---

### Phase 4: Unified Upload Handler

**Goal**: Single upload endpoint with consistent behavior and pre-upload duplicate check.

#### New Upload Flow
```
POST /documents/upload-batch
├─ Accept 1-10 files (already confirmed by user after duplicate check)
├─ Create Document records with status=UPLOADING
├─ Save files to disk (parallel async)
├─ Set status=PENDING
├─ Enqueue for processing (FIFO)
└─ Return document IDs immediately
```

#### Implementation
```python
@router.post("/upload-batch")
async def upload_batch(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload multiple documents (up to 10).
    Files should already be confirmed by user after duplicate check.
    """
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 files")
    
    document_ids = []
    
    # Phase 1: Create records and save files (can be parallel)
    for file in files:
        doc_id = str(uuid.uuid4())
        file_path = save_file_sync(file, doc_id)
        
        # Create document record
        doc = Document(
            id=doc_id,
            user_id=current_user.id,
            filename=file.filename,
            file_path=file_path,
            file_size=file.size,  # New field
            status=DocumentStatus.PENDING,
            company_id=None,  # Will be set during classification
        )
        db.add(doc)
        document_ids.append(doc_id)
    
    db.commit()
    
    # Phase 2: Enqueue for sequential processing
    for doc_id in document_ids:
        document_queue.enqueue(doc_id)
    
    return {
        "document_ids": document_ids,
        "message": f"Uploaded {len(document_ids)} documents. Position in queue: {document_queue.qsize()}"
    }
```

---

### Phase 5: Replace Polling with Server-Sent Events (SSE)

**Goal**: Real-time status updates without polling overhead.

#### SSE Implementation

**Backend**:
```python
from sse_starlette.sse import EventSourceResponse

@router.get("/status-stream")
async def status_stream(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    SSE endpoint for real-time document status updates.
    """
    async def event_generator():
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break
            
            # Get all active documents
            active_docs = get_active_documents(current_user.id)
            
            # Send update
            yield {
                "event": "status_update",
                "data": json.dumps({
                    "documents": active_docs,
                    "queue_status": get_queue_status()
                })
            }
            
            # Wait before next update
            await asyncio.sleep(2)
    
    return EventSourceResponse(event_generator())
```

**Frontend**:
```javascript
useEffect(() => {
  const eventSource = new EventSource(
    `${API_BASE_URL}/documents/status-stream`,
    { headers: { Authorization: `Bearer ${token}` } }
  )
  
  eventSource.addEventListener('status_update', (event) => {
    const data = JSON.parse(event.data)
    setDocuments(data.documents)
    setQueueStatus(data.queue_status)
  })
  
  return () => eventSource.close()
}, [token])
```

---

### Phase 6: Atomic Operations and Rollback

**Goal**: Ensure database and filesystem consistency.

#### Implementation
- Wrap all file operations in try/finally blocks
- Implement `cleanup_failed_upload(document_id)` function
- Use database transactions with explicit rollback
- Add periodic cleanup job for orphaned files

---

### Phase 7: Consolidate Test Endpoints

**Goal**: Reduce code duplication between authenticated and test endpoints.

#### Implementation
- Create `@optional_auth` decorator
- Consolidate logic into internal functions
- Test endpoints call same internal functions
- Remove duplicate code

---

## Migration Strategy

### Step 1: Add New Status Field (Non-Breaking)
- Add `status` field to Document model (nullable)
- Populate from existing `indexing_status` + `analysis_status`
- Run migration script to backfill

### Step 2: Implement New Upload Handler (Parallel)
- Create new endpoint `/documents/upload-v2`
- Test thoroughly with new status model
- Keep old endpoint for backwards compatibility

### Step 3: Refactor Queue (Parallel)
- Create new queue module `document_queue_v2.py`
- Migrate tasks gradually
- Monitor both queues during transition

### Step 4: Update Frontend (Coordinated)
- Add SSE support
- Switch to new upload endpoint
- Remove polling logic
- Deploy frontend and backend together

### Step 5: Deprecate Old Code
- Mark old endpoints as deprecated
- Remove after 1 week grace period
- Clean up old queue and status logic

---

## Testing Plan

### Unit Tests
- Upload handler with various file types
- Status transitions (valid and invalid)
- Queue task processing
- Duplicate detection logic
- Error handling and rollback

### Integration Tests
- End-to-end upload flow
- Multi-file batch upload
- Duplicate detection flow
- SSE connection and updates
- Queue processing with retries

### Load Tests
- 100 concurrent uploads
- Queue throughput
- SSE connection limits
- Database transaction performance

---

## Success Metrics

1. **Reliability**: 99.9% upload success rate
2. **Performance**: \u003c 5s from upload to classification complete
3. **User Experience**: Real-time status updates (\u003c 500ms latency)
4. **Code Quality**: 50% reduction in upload-related code
5. **Error Rate**: \u003c 0.1% orphaned files or stuck documents

---

## Timeline Estimate

- **Phase 1 (Status Model)**: 2 days
- **Phase 2 (Upload Handler)**: 3 days
- **Phase 3 (Queue Refactor)**: 4 days
- **Phase 4 (Duplicate Detection)**: 2 days
- **Phase 5 (SSE)**: 3 days
- **Phase 6 (Atomic Operations)**: 2 days
- **Phase 7 (Consolidation)**: 1 day
- **Testing \u0026 Migration**: 3 days

**Total**: ~20 days (4 weeks)

---

## Risks and Mitigation

### Risk 1: Breaking Changes
**Mitigation**: Parallel implementation, feature flags, gradual rollout

### Risk 2: SSE Browser Compatibility
**Mitigation**: Fallback to polling for unsupported browsers

### Risk 3: Queue Backlog During Migration
**Mitigation**: Run both queues in parallel, monitor queue depth

### Risk 4: Data Migration Issues
**Mitigation**: Dry-run migration script, backup database, rollback plan

---

## End-to-End Consistency Review

### ✅ Issues Fixed:
1. **Phase numbering corrected** - Phases now flow logically (Pre-upload duplicate → Upload → Queue → SSE)
2. **Database schema changes added** - New `file_size` and `status` fields documented
3. **Status transitions clarified** - Terminal states explicitly defined
4. **Error handling enhanced** - Cleanup policy for failed uploads specified
5. **Timeline adjusted** - Phases reordered to match implementation sequence

---

## Open Questions - ANSWERED

1. Should we support resumable uploads for large files? **NO NEED**
2. Do we need document versioning (replace vs new version)? **NO NEED**
3. Should duplicate detection be configurable (strict vs fuzzy)? **NO NEED**
4. What's the retention policy for failed uploads? **DELETE** (cleanup job runs daily)
5. Should we add upload quotas per user? **NO NEED FOR NOW**

---

## Database Schema Changes Required

### New Fields for `documents` Table:
```python
class Document(Base):
    # ... existing fields ...
    
    # NEW: Single unified status field (replaces indexing_status + analysis_status)
    status = Column(String, nullable=False, default=DocumentStatus.PENDING, index=True)
    
    # NEW: File size for duplicate detection
    file_size = Column(Integer, nullable=True)
    
    # NEW: Error tracking
    error_message = Column(Text, nullable=True)
    
    # NEW: Processing metadata (JSON)
    processing_metadata = Column(Text, nullable=True)  # JSON: {current_step, step_details, etc.}
    
    # NEW: Current step in pipeline
    current_step = Column(String, nullable=True)  # e.g., "3/7: Indexing"
    
    # DEPRECATED (will be removed after migration):
    # indexing_status
    # analysis_status
```

### Migration Steps:
1. Add new fields as nullable
2. Backfill `status` from `indexing_status` + `analysis_status`
3. Backfill `file_size` from filesystem (if file exists)
4. Mark old fields as deprecated
5. Remove old fields after grace period

---

## Complete User Flow (End-to-End)

### 1. Pre-Upload Phase
```
User selects files
  ↓
Frontend computes quick hash (first 5KB)
  ↓
POST /documents/check-duplicates-batch
  ↓
Backend checks: filename + size + quick_hash
  ↓
Returns: [{ filename, is_duplicate, existing_doc }]
  ↓
Frontend shows confirmation dialog
  ↓
User confirms which files to upload
```

### 2. Upload Phase
```
POST /documents/upload-batch (confirmed files only)
  ↓
Create Document records (status=UPLOADING)
  ↓
Save files to disk (parallel async)
  ↓
Update status=PENDING
  ↓
Enqueue for processing (FIFO)
  ↓
Return document IDs + queue position
```

### 3. Processing Phase (Sequential, One at a Time)
```
Queue Worker picks next document
  ↓
status=CLASSIFYING
  ↓
Classify document (LLM call)
  ↓
If earnings announcement:
  │
  ├─ status=INDEXING
  ├─ Index document (embeddings)
  ├─ status=EXTRACTING_BALANCE_SHEET
  ├─ Extract balance sheet
  ├─ status=EXTRACTING_INCOME_STATEMENT
  ├─ Extract income statement
  ├─ status=EXTRACTING_ADDITIONAL_ITEMS
  ├─ Extract organic growth, amortization, etc.
  ├─ status=CLASSIFYING_NON_OPERATING
  ├─ Classify non-operating items
  └─ status=PROCESSING_COMPLETE ✓ (terminal)
  
If non-earnings:
  │
  └─ status=CLASSIFIED ✓ (terminal)

If error at any step:
  │
  └─ status=*_FAILED (terminal)
     └─ Cleanup: delete file, mark for review
```

### 4. Real-Time Updates (SSE)
```
Frontend connects to /status-stream
  ↓
Backend sends updates every 2s:
  - Current document being processed
  - Queue length
  - All active documents with status
  ↓
Frontend updates UI in real-time
  ↓
Connection closes when all documents terminal
```

---

## Error Handling & Cleanup Policy

### Error States (Terminal):
- `UPLOAD_FAILED` - File save failed
- `CLASSIFICATION_FAILED` - LLM classification failed
- `INDEXING_FAILED` - Embedding generation failed
- `EXTRACTION_FAILED` - Financial statement extraction failed

### Cleanup Actions:
1. **Immediate**: Delete uploaded file from disk
2. **Database**: Mark document with error status + message
3. **User Notification**: Show error in UI via SSE
4. **Retry**: No automatic retries (user must re-upload)

### Daily Cleanup Job:
```python
@scheduler.scheduled_job('cron', hour=2)  # 2 AM daily
def cleanup_failed_uploads():
    """Delete files for documents in error states older than 7 days."""
    cutoff_date = datetime.utcnow() - timedelta(days=7)
    
    failed_docs = db.query(Document).filter(
        Document.status.in_([
            DocumentStatus.UPLOAD_FAILED,
            DocumentStatus.CLASSIFICATION_FAILED,
            DocumentStatus.INDEXING_FAILED,
            DocumentStatus.EXTRACTION_FAILED
        ]),
        Document.uploaded_at < cutoff_date
    ).all()
    
    for doc in failed_docs:
        if os.path.exists(doc.file_path):
            os.remove(doc.file_path)
        db.delete(doc)
    
    db.commit()
```

---

## Timeline Estimate (REVISED)

**Phase Order Adjusted for Implementation Logic:**

- **Phase 1 (Database Schema)**: 1 day
  - Add new fields
  - Migration script
  - Backfill existing data
  
- **Phase 2 (Pre-Upload Duplicate Detection)**: 2 days
  - Frontend quick hash computation
  - Backend check endpoint
  - UI confirmation dialog

- **Phase 3 (Strict Sequential Queue)**: 4 days
  - New queue architecture
  - Synchronous processing functions
  - Error handling & cleanup
  - Queue status endpoint

- **Phase 4 (Unified Upload Handler)**: 2 days
  - Single upload endpoint
  - File saving logic
  - Queue integration

- **Phase 5 (SSE Real-Time Updates)**: 3 days
  - Backend SSE endpoint
  - Frontend SSE client
  - Remove polling logic

- **Phase 6 (Atomic Operations & Cleanup)**: 2 days
  - Transaction management
  - File cleanup on errors
  - Daily cleanup job

- **Phase 7 (Test Endpoint Consolidation)**: 1 day
  - `@optional_auth` decorator
  - Refactor test endpoints

- **Testing & Migration**: 3 days
  - Unit tests
  - Integration tests
  - Gradual rollout

**Total**: ~18 days (3.5 weeks)

---

## Success Metrics (REVISED)

1. **Reliability**: 
   - 99.9% upload success rate
   - Zero race conditions
   - Zero orphaned files

2. **Performance**: 
   - < 3s from upload to classification complete (single doc)
   - < 2min for full earnings announcement processing
   - Queue throughput: 1 doc every 2-3 minutes (acceptable for sequential)

3. **User Experience**: 
   - Real-time status updates (< 500ms latency via SSE)
   - Clear queue position visibility
   - Upfront duplicate detection (no wasted uploads)

4. **Code Quality**: 
   - 50% reduction in upload-related code
   - Single queue implementation (vs. priority queue)
   - Unified status model (vs. dual status fields)

5. **Error Rate**: 
   - < 0.1% orphaned files (cleanup job handles rest)
   - < 1% stuck documents (sequential processing prevents this)
   - 100% error visibility (all errors surfaced to user)

---

## Critical Path Dependencies

```
Phase 1 (Schema) 
  ↓
Phase 2 (Duplicate Detection) ← Can start in parallel
  ↓
Phase 3 (Sequential Queue) ← Depends on Phase 1
  ↓
Phase 4 (Upload Handler) ← Depends on Phase 2 & 3
  ↓
Phase 5 (SSE) ← Depends on Phase 3 & 4
  ↓
Phase 6 (Cleanup) ← Depends on Phase 1
  ↓
Phase 7 (Consolidation) ← Depends on all above
```

**Parallel Work Opportunities:**
- Phase 2 can start while Phase 1 is in progress
- Phase 6 can be developed alongside Phase 3-5
- Frontend SSE client (Phase 5) can be built while backend queue (Phase 3) is being developed

---

## Rollback Plan

### If Issues Arise During Migration:

1. **Database Rollback**:
   - Keep old `indexing_status` and `analysis_status` fields
   - Revert to old queue (`document_processing_queue.py`)
   - Switch frontend back to polling

2. **Feature Flag**:
   ```python
   USE_NEW_UPLOAD_WORKFLOW = os.getenv("USE_NEW_UPLOAD_WORKFLOW", "false") == "true"
   
   if USE_NEW_UPLOAD_WORKFLOW:
       return upload_batch_v2(files, db, current_user)
   else:
       return upload_batch_v1(files, db, current_user)
   ```

3. **Gradual Rollout**:
   - Week 1: Internal testing only
   - Week 2: 10% of uploads use new workflow
   - Week 3: 50% of uploads
   - Week 4: 100% migration, deprecate old code

---

## Final Checklist Before Implementation

- [ ] All phases reviewed for consistency
- [ ] Database schema changes documented
- [ ] Error handling strategy defined
- [ ] Cleanup policy specified
- [ ] Timeline realistic and achievable
- [ ] Dependencies mapped
- [ ] Rollback plan in place
- [ ] Success metrics measurable
- [ ] User flow tested end-to-end (on paper)
- [ ] Open questions answered

**Status**: ✅ **PLAN READY FOR IMPLEMENTATION**

