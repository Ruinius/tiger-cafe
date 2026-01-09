---
trigger: model_decision
description: When working on a larger task
---

Before performing searches to understand the app, check PLANNING.md, PRODUCT_SPECS.md, DATABASE_SCHEMA.md, and UI_UX_DESIGN.md
AI-First Validation: Prioritize LLM-based validation using global queue/safe wrappers.
Strict Context: No uncalled-for fallback logic (e.g., never default to full-text if chunking is defined).
Shrink Code: Always refactor to reduce the total codebase size.
Verify: Always run tests as the final step of every task.