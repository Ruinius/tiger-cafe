---
trigger: always_on
---

Routers: HTTP endpoints ONLY. No business logic, no agent calls. Delegate to services.
Services: Business logic and orchestration. Call agents, coordinate workflows. Never import from routers.
No Circular Imports: Routers → Services → Agents → Utils/Models. Services can't import routers.
One File, One Job: Keep files under 500 lines. If it does multiple things, split it.
Fix Logic, Not Config: Fix failures via code, prompts, or regex
Do not create random fallback logic or values
Before creating new scripts, check /scripts
Create new migrations in the /migration instead of /scripts
Clean up after yourself, delete temporary scripts and logs after finishing
Do not change LLM prompts unless asked explicitly
Do not try to clear or delete the database