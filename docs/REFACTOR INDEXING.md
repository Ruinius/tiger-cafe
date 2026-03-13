# Refactor: Remove Embedding-Based Indexing

## Goal

Remove all Gemini embedding generation and semantic search from the document indexing
pipeline. Replace with keyword-based text search. Retain chunking infrastructure
because `find_top_numeric_chunks` depends on it for number density calculations.

---

## What We Are Removing

### Embedding functions (in `app/utils/document_indexer.py`)
- `save_chunk_embedding()` — writes `{doc_id}_chunk_{n}_embedding.json` to disk
- `load_chunk_embedding()` — reads those JSON files back
- `delete_chunk_embeddings()` — cleans them up
- The entire `generate_embedding_safe()` call loop inside `index_document_chunks()`

### Semantic search functions (in `app/utils/document_section_finder.py`)
- `_find_document_section_legacy()` — full-document embedding scan (the core semantic search)
- `find_document_section()` — legacy wrapper around the above
- `collect_top_chunk_texts()` — calls `find_document_section` in a loop for top-k results
- `rank_chunks_by_query()` — takes a list of chunk indices and re-ranks them by embedding similarity
- `cosine_similarity()` — only used by the above
- `_chunk_search_range()`, `_penalize_edge_chunks()` — helpers only used by `_find_document_section_legacy`

### Stored embedding files (in `data/storage/`)
- All `{doc_id}_chunk_{n}_embedding.json` files can be deleted
- The `full_text.txt` cache and `chunks_metadata.json` files should be **kept**

---

## What We Are Keeping

### Chunking infrastructure (in `app/utils/document_indexer.py`)
- `index_document_chunks()` — keep, but **strip out all embedding generation**. It should
  only: extract full text, save it to `{doc_id}_full_text.txt`, compute chunk metadata
  (`num_chunks`, `chunk_size`, `total_characters`), and save `{doc_id}_chunks_metadata.json`.
- `get_chunk_metadata()` / `save_chunk_metadata()` — keep
- `get_chunk_text()` — keep
- `load_full_document_text()` — keep
- `_extract_page_range_text()` — keep (used internally)

### Section finder utilities (in `app/utils/document_section_finder.py`)
- `find_top_numeric_chunks()` — keep, no changes needed (pure regex number counting)
- `get_chunk_with_context()` — keep, no changes needed (pure text slice by chunk index)
- `_count_numbers()` — keep (used by `find_top_numeric_chunks`)

---

## Replacement Strategy

There are **two distinct patterns**, one for each group of agents.

---

### Group 1 — Financial Statement extractors (BS, IS, GAAP)

**No re-ranking needed at all.**

`find_top_numeric_chunks` already returns chunks ordered by number density, which is
the right heuristic for locating dense financial tables. The only post-processing
needed is **chunk exclusion**: if the balance sheet extractor already locked in chunk N,
the income statement extractor should treat chunk N as lowest priority (or skip it entirely).

`find_top_numeric_chunks` returns an ordered list — callers can simply move
already-claimed chunk indices to the back of that list before iterating.

**`rank_chunks_by_query` is removed entirely for these agents.** The candidate list from
`find_top_numeric_chunks` is iterated in density order, with already-used chunks
deprioritised by moving them to the back (or skipping them if a better candidate exists).

---

### Group 2 — Footnote/narrative extractors (amortization, other assets, other liabilities, organic growth, shares outstanding)

**Use `_extract_context_around_keywords` from the full document text.**

This function already exists in `shares_outstanding_extractor.py` and works as follows:
1. Load the full cached document text (`load_full_document_text`)
2. Find every occurrence of each keyword (case-insensitive substring scan)
3. Extract ±`context_chars` characters around each match
4. Merge overlapping windows
5. Join with `\n...\n` separators

This produces a compact, focused text that contains every mention of the search terms,
without any API calls. The resulting text is passed directly to the LLM extractor.

This function should be **moved to `app/utils/document_section_finder.py`** as a shared
utility (its current location in `shares_outstanding_extractor.py` is
accidental — it ended up there first).

`collect_top_chunk_texts` is removed entirely and replaced by this pattern.

```python
# Signature after moving to document_section_finder.py
def extract_context_around_keywords(
    text: str,
    keywords: list[str],
    context_chars: int = 250,
) -> str:
    """Return merged keyword-context snippets from a full document text string."""
```

Callers load the full text themselves via `load_full_document_text`, then call this function.

---

## Agent-by-Agent Changes

### Group 1: Financial Statement Extractors

#### `balance_sheet_extractor.py`
**Current:** `find_top_numeric_chunks` → `rank_chunks_by_query` → iterate  
**New:** `find_top_numeric_chunks` → iterate in density order directly  
No re-ranking. The balance sheet has no prior extractor to avoid.

#### `income_statement_extractor.py`
**Current:** `find_top_numeric_chunks` → `rank_chunks_by_query` → iterate  
**New:** `find_top_numeric_chunks` → **remove balance sheet chunk from front of list** → iterate in density order  
The balance sheet chunk index is already passed in as `balance_sheet_chunk_index`. Move
that index to the back of the candidate list (don't skip entirely, in case it's the only
option) before iterating.

#### `gaap_reconciliation_extractor.py`
**Current:** `find_top_numeric_chunks` → `rank_chunks_by_query` → iterate  
**New:** `find_top_numeric_chunks` → **deprioritise balance sheet and income statement chunks** → iterate  
Same pattern as IS extractor. Move already-claimed chunk indices to the back.

---

### Group 2: Footnote / Narrative Extractors

All of these replace `collect_top_chunk_texts` with the `extract_context_around_keywords`
pattern. The shared utility moves to `document_section_finder.py`.

#### `amortization_extractor.py`
**Current:** `collect_top_chunk_texts(query_texts=["amortize", "amortization", "reconciliation"], ...)`  
**New:**
```python
full_text = load_full_document_text(document_id, file_path)
focused_text = extract_context_around_keywords(
    full_text, ["amortize", "amortization", "reconciliation"], context_chars=500
)
```

#### `other_assets_extractor.py`
**Current:** `collect_top_chunk_texts(query_texts=query_terms, ...)` where `query_terms`
are the balance sheet "other assets" line item names  
**New:**
```python
full_text = load_full_document_text(document_id, file_path)
focused_text = extract_context_around_keywords(full_text, query_terms, context_chars=500)
```

#### `other_liabilities_extractor.py`
**Current:** Same pattern as `other_assets_extractor`  
**New:** Same replacement

#### `organic_growth_extractor.py`
**Current (chunk search):** `collect_top_chunk_texts(query_texts=["constant currency organic growth", "constant currency", "organic growth"], ...)`  
**New:**
```python
full_text = load_full_document_text(document_id, file_path)
focused_text = extract_context_around_keywords(
    full_text,
    ["constant currency organic growth", "constant currency", "organic growth"],
    context_chars=500,
)
```
**IS chunk lookup (`get_chunk_with_context` with `is_chunk_index`):** no change.

#### `shares_outstanding_extractor.py`
Already uses this exact pattern in Attempt 2. The only change is that
`_extract_context_around_keywords` is renamed/moved to the shared utility;
the logic inside the agent is unchanged.

---

## Files Modified Summary

| File | Change |
|---|---|
| `app/utils/document_indexer.py` | Strip embedding generation loop from `index_document_chunks`; delete `save_chunk_embedding`, `load_chunk_embedding`, `delete_chunk_embeddings` |
| `app/utils/document_section_finder.py` | Delete `_find_document_section_legacy`, `find_document_section`, `collect_top_chunk_texts`, `rank_chunks_by_query`, `cosine_similarity`, `_chunk_search_range`, `_penalize_edge_chunks`. Add `extract_context_around_keywords` (moved from shares_outstanding_extractor). Remove numpy import block. |
| `app/app_agents/balance_sheet_extractor.py` | Remove `rank_chunks_by_query` import and call; iterate `find_top_numeric_chunks` result directly |
| `app/app_agents/income_statement_extractor.py` | Same; also deprioritise `balance_sheet_chunk_index` in candidate list |
| `app/app_agents/gaap_reconciliation_extractor.py` | Same; deprioritise BS and IS chunk indices in candidate list |
| `app/app_agents/amortization_extractor.py` | Replace `collect_top_chunk_texts` with `load_full_document_text` + `extract_context_around_keywords` |
| `app/app_agents/other_assets_extractor.py` | Same |
| `app/app_agents/other_liabilities_extractor.py` | Same |
| `app/app_agents/organic_growth_extractor.py` | Replace `collect_top_chunk_texts` call only; `get_chunk_with_context` unchanged |
| `app/app_agents/shares_outstanding_extractor.py` | Delete local `_extract_context_around_keywords`; import from `document_section_finder` instead |
| `app/utils/gemini_client.py` | Verify `generate_embedding_safe` has no other callers; if not, delete it |

---

## Migration Notes

### Existing stored embeddings
Existing `data/storage/{doc_id}_chunk_*_embedding.json` files are now orphaned.
A one-time cleanup script or a note to manually delete them is sufficient. Do NOT delete
`{doc_id}_full_text.txt` or `{doc_id}_chunks_metadata.json`.

### Re-indexing
Documents do not need to be re-indexed. The chunking metadata and full text are already
stored. The old embedding files will simply be ignored once `load_chunk_embedding` is removed.

### `generate_embedding_safe` (in `gemini_client.py`)
Search for other callers before removing. If it is only called from `document_indexer.py`
and `document_section_finder.py`, it can be deleted from `gemini_client.py` as well.

---

## Why Not Embeddings?

- The documents we process (financial PDFs) are highly structured and keyword-rich.
  The phrases we search for ("Balance Sheet", "amortization", "organic growth") appear
  literally in the document — semantic distance adds no value over exact substring matching.
- Each embedding call is a Gemini API round-trip, adding latency and token cost during
  indexing and during every search.
- `find_top_numeric_chunks` already does the hard filtering work for the financial
  statement extractors; ranking the survivors by keyword presence is sufficient.
- For the footnote extractors (amortization, other assets/liabilities, organic growth),
  the query terms are specific literal phrases or line item names — substring search is
  more precise and faster.
