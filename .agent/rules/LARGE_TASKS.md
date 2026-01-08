---
trigger: model_decision
description: When working on a larger task
---

Fix Logic, Not Config: Fix failures via code, prompts, or regex. Never suggest changing model parameters.
AI-First Validation: Prioritize LLM-based validation using global queue/safe wrappers.
Strict Context: No uncalled-for fallback logic (e.g., never default to full-text if chunking is defined).
UI Compliance: All UI changes must strictly follow UI_UX_DESIGN.md.
Shrink Code: Always refactor to reduce the total codebase size.
Verify: Always run tests as the final step of every task.
Scalability: Ask yourself if the fix is general and robust.