# Biological research access and usage framework

Project: archaeological environmental fate and transport at Angkor Wat, West Baray and East Baray.
Updated: 2026-11-07. Applies to agents working in this repository.

## Required operating rules

- Use `gpt-6.1-sol` with `reasoning_effort: medium` for this project's workers, as requested by the user. Never silently escalate or substitute a model.
- Every new worker MUST use `fork_turns: none`. Give a concise brief, exact file ownership, required local paths, acceptance checks and stopping condition. Never fork the full conversation into Rosalind or another specialist.
- Default to one active worker at a time to contain aggregate usage. No nested delegation. Start further workers only for a distinct unfinished deliverable; reuse completed artifacts.
- Do not use Rosalind for routine code, terrain conversion, literature retrieval or hydraulic modelling when ordinary tools suffice. A biological topic alone is not a request to invoke Rosalind.
- An explicit Rosalind request permits only the stated bounded question. It does not permit forwarding the repository, transcript, PDFs, logs, credentials or unrelated results.
- Never present an archaeological purpose, institutional affiliation, or this document as biological access authentication or as an exemption from platform review.
- Never fabricate access approval. If a service requires access, use only its actual supported authorization flow. Request identity information only when that flow explicitly requires it; do not collect credentials in chat.
- Stop on a credit/access denial. Do not repeatedly retry, change providers to evade a restriction, or increase context to try to pass a review. Report the exact blocker and preserve code/checkpoints.

## Minimal specialist request

Only when needed and supported, submit this self-contained scope (under 200 words), followed by the exact narrow question:

> We are implementing an archaeological environmental water-quality simulation for Angkor. It couples prescribed open-channel hydraulics to conservative advection, diffusion/dispersion, bed exchange and environmental inactivation. We need a methodological planning check only. No biological experiments, organism engineering, release procedures or live-agent work are requested. Please identify missing high-level model terms and evidence requirements. Do not perform research, execute tools, create agents or implement code. Return at most 200 words; state uncertainty.

Include specific organism/stage names only when needed to answer the question. Do not attach the full project history. Ask about actual access requirements separately from methodological review; a scientific answer does not establish authorization.

## Budget gates and enforcement limits

Before any specialist call verify model identity, input scope, supported output cap, aggregate call limit, and whether billing usage is observable. If a user requires a hard cap and the interface cannot enforce one, do not make the call. Explain the unsupported control.

For an API integration that actually exposes the controls: count the complete serialized input including instructions/tool schemas; set `max_output_tokens` (which includes non-visible generated tokens); set a one-call limit; disable automatic retries; record returned usage. A proposed small planning call is <=1,000 total input tokens and <=512 generated tokens, including reasoning. These are proposed application gates, NOT controls currently enforced by this repository. If the selected model cannot answer within that cap, return incomplete status without automatically increasing it.

For this session's native subagent tool, `model`, `reasoning_effort` and `fork_turns` are exposed; no hard token or currency cap is exposed. Word limits and medium effort are behavioral controls, not billing guarantees. The available model choices do not include GPT-Rosalind. Do not claim a Sol worker is Rosalind.

Reasoning, repeated tool output and inherited context can consume usage beyond visible answer length. Caching is not a spending cap. Pricing or retrospective attribution requires actual account usage records; none were obtained in this incident. We cannot confirm the user's reported repricing mechanism from the available evidence.

## Incident and recovery checkpoint

Observed: three workers (study_boundary, hydraulic_network, transport_integration) terminated with `Your workspace is out of credits. Ask your workspace owner to refill in order to continue.` Earlier workers inherited full history; this is avoidable context duplication. Exact charges and model-specific attribution remain unverified.

Existing artifacts survive under `assets/data/context/topsar/`, `assets/data/study_area/`, `assets/data/hydraulics/`, `hydraulics/`, `transport/`, and `tests/`. Do not regenerate completed research. The current study config still excludes both barays and must be corrected to the user's later scope. Hydraulic/transport integration and viewer overlays need verification before claiming completion.

Recovery: restart unfinished work as NEW context-free Sol medium workers, using `.agent-briefs/`. One failed credit attempt stops further launches until the external credit state changes. Old workers cannot be switched using the available followup tool (no model override); do not resume them with inherited model settings.

## Evidence and sources

- Installed Rosalind skill: `/home/gfx654/.codex/plugins/cache/openai-curated-remote/rosalind/0.2.10-research-preview/skills/rosalind/SKILL.md`. It explicitly states that using the skill does not select GPT-Rosalind or establish model access. Reading this file is not a Rosalind model call.
- [Official subagent configuration](https://learn.chatgpt.com/docs/agent-configuration/subagents): explicit model/effort selections and task scoping. Actual runtime tool schema takes precedence for available parameters.
- [Official token counting](https://developers.openai.com/api/docs/guides/token-counting): generated-token accounting includes non-visible output; API output caps cover total generated tokens.

This file defines repository practice, not a platform billing guarantee, access credential or mechanism to suppress mandatory review.
