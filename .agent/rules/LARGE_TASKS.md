---
trigger: model_decision
description: When working on a larger task
---

Prioritize LLM-based validation using global queue/safe wrappers
No uncalled-for fallback logic (e.g., never default to full-text if chunking is defined)
Always refactor to reduce the total codebase size
Always run tests as the final step of every task