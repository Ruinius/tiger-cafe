---
trigger: model_decision
description: When working on a larger task
---

AI-First Validation: Prioritize LLM-based validation using global queue/safe wrappers.
Strict Context: No uncalled-for fallback logic (e.g., never default to full-text if chunking is defined).
Shrink Code: Always refactor to reduce the total codebase size.
Verify: Always run tests as the final step of every task.