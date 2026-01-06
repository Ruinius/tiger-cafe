---
trigger: always_on
---

# ANTIGRAVITY RULES

1. **Fix Logic, Not Config**: If AI fails, fix the code/prompt/regex. Do not suggest model parameter changes.
2. **AI-First**: Use LLMs for validation where possible. Always use the global queue/safe wrappers.
3. **Design Compliance**: All UI changes MUST follow `UI_UX_DESIGN.md`.
4. **Cycle**: Create Tests -> Implement Code -> Pass Tests -> Update Docs (`PLANNING.md`, `UI_UX_DESIGN.md`, `ARCHITECTURE.md`, `PRODUCT_SPECS.md`).