# Prompt changelog

Released prompts are frozen: a change means a new `_vN+1.md` file, an entry here, and a config switch.
`prompts/lockfile.json` holds the sha256 of every frozen prompt; `tests/test_prompts.py` fails if one changes.

## 2026-10-06
- `smoke_helper_v1`, `smoke_reasoner_v1`: M3 smoke test only. Locked after the smoke run.
- `query_gen_v1`, `relevance_summary_v1`: retrieval helpers (ideas adapted from Halawi et al. 2024).
- `r1_halawi_scratchpad_v1` … `r5_superforecaster_checklist_v1`: the K=5 reasoning variants.
- `disagreement_v1`, `update_v1`: AIA supervisor.
