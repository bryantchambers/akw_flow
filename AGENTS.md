# Project agent instructions

Read BIOLOGICAL_RESEARCH_AUTHENTICATION_FRAMEWORK.md before delegation or specialist access.
User requires gpt-6.1-sol at medium reasoning for workers and fork_turns="none".
Never send full conversation context to Rosalind. No nested delegation or automatic model escalation.
Use one worker at a time by default. Stop launch retries on credit exhaustion.
No hard billing limit is available in the native spawn tool; never describe a prompt word limit as a hard token cap.
Preserve current artifacts; finish and verify incomplete tasks instead of repeating research.

Use the durable user Miniforge environment at `/maps/projects/caeg/people/gfx654/miniforge3/envs/qmodel` (`mamba activate qmodel`). Do not create continuing project environments in `/tmp`. Preserve active jobs during environment migration. User permits up to 40 CPU threads for regional modelling.
