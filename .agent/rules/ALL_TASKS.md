---
trigger: always_on
---

Before performing searches to understand the app, check PLANNING.md, PRODUCT_SPECS.md, DATABASE_SCHEMA.md, and UI_UX_DESIGN.md
Ask yourself if the fix is general and robust
All UI changes must strictly follow UI_UX_DESIGN.md
Fix Logic, Not Config: Fix failures via code, prompts, or regex
Do not create random fallback logic or values
Before creating new scripts, check /scripts
Create new scripts in /scripts instead of root
Create new migrations in the /migration instead of /scripts
Clean up after yourself, delete temporary scripts and logs after finishing
IMPORTANT: do not change LLM prompts unless asked explicitly
IMPORTANT: do not run code that will clear the database
IMPORTANT: do not delete the database!