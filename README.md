# STRaWBERRY-LLM

Checklist-based paper-draft assessment: rules -> small ML -> local Qwen + Gemini, in a fixed pipeline.

- Tier A criteria (counting/parsing) are decided by code.
- Tier B criteria (cue phrases) are decided by rules or a small sentence classifier; uncertain ones escalate.
- Tier C criteria (judgment) and escalated ones go to an LLM, batched per component group.
- Every verdict carries `source` (rule | ml | llm), `provider` (gemini | local), `confidence` and evidence verified against the source text.

## LLM routing

Two providers share the work. The split exists to keep Gemini inside its rate limit, not to
hit an exact ratio: the local model does the bulk, Gemini does the high-impact and uncertain parts.

| Priority | Work | Provider |
|---|---|---|
| P0 | Title, abstract, introduction (every criterion) | Gemini, one batched call |
| P1 | Tier B elsewhere | Gemini while the token budget lasts, then local |
| P2 | Tier C elsewhere | local |
| P3 | Unanswered or `needs_review` from local (max `GEMINI_ESCALATION_MAX`) | Gemini, if quota remains |
| — | Fix suggestions and coach feedback | Gemini, falling back to local |

Guards:
- `GEMINI_TOKEN_SHARE` (default `0.30`) caps Gemini at that share of the estimated judging tokens. The heuristic above decides the *order*; this is the hard cut, so a paper with many tier-B sections cannot push Gemini over budget.
- `GEMINI_MAX_CALLS_PER_EVAL` / `GEMINI_MAX_INPUT_TOKENS` cap the per-evaluation budget.
- `GEMINI_RPM` / `GEMINI_TPM` / `GEMINI_RPD` are tracked locally; the daily counter is persisted in `data/gemini_quota.json` so restarts do not reset it.
- A real 429 opens a circuit breaker for `GEMINI_CIRCUIT_BREAKER_S`; work silently moves to the local model instead of failing the request.
- Per-provider calls and tokens are stored in `report.usage.by_provider` and in `data/usage.jsonl`; `python -m scripts.cost_report` prints the split.

The local model is any OpenAI-compatible server (LM Studio, Ollama, vLLM). Local judging uses a
compact `{id, met, evidence}` schema with grammar-constrained JSON: a 4B model rambles in free-text
fields and truncates the JSON otherwise.

## Backend
```
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt   # or: pip install -e ".[dev]"
copy ..\.env.example .env         # then set GEMINI_API_KEY and the local LLM settings
uvicorn app.main:app --reload
```
Without any LLM the app still runs: Tier A/B are answered locally, Tier C shows "needs review".

### Local model (optional but recommended)
Start LM Studio (or Ollama) with an OpenAI-compatible server, then set in `.env`:
```
LOCAL_LLM_ENABLED=true
LOCAL_LLM_BASE_URL=http://localhost:1234/v1
LOCAL_LLM_MODEL=qwen/qwen3-4b-2507
LOCAL_LLM_API_KEY=<token from the LM Studio server tab>
```
Load the model with a context length of at least 8192 and keep it resident; the pipeline calls it
several times per evaluation.

## Frontend
```
cd frontend
npm install
npm run dev
```

## Machine Learning Model (optional)
The ML layer needs an embedder, which competes with the local LLM for VRAM. When a local LLM is
running, set `ML_ENABLED=false` (the default in `.env.example`): tier B then falls back to rules
and the LLM instead of the zero-shot classifier. To use it:
```
pip install -e ".[ml]"
python scripts/check_ml.py
```

## Tests
```
cd backend
pytest -q
```

Criteria, tiers, rule parameters, ML labels and hints live in `backend/config/framework/strawberry.v1.yaml`.
Bump PROMPT_VERSION in `.env` after changing prompts so cached results are invalidated.

## Using the report

- **Checklist** tab: every criterion with its verdict, quoted evidence, and a concrete fix. "Show in text" jumps to the paragraph.
- **Read along** tab: the paper section by section; evidence is highlighted in the text (green = found, red = problem, amber = needs your check) with the matching criteria beside each section.
- **To fix** sidebar (sticky): open items ranked by impact vs effort. Tick items off yourself; ticks are kept in the browser across revisions.
- **Revised your draft?** Upload the new version; items you fixed are ticked automatically and a comparison tab shows score changes per component and per criterion.

Fix suggestions: the highest-priority failed criteria (max 12) get one batched AI call for a text-specific fix (`config/prompts/suggest.md`). Gemini handles this when its quota allows, otherwise the local model does. Without any LLM, each item shows the checklist hint instead. Effort/impact ranking is plain code (`app/services/report/priority.py`).

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | which layers are available |
| GET | `/api/framework` | the checklist (no rule parameters) |
| POST | `/api/uploads` | upload `.pdf`, `.docx` or `.tex` |
| POST | `/api/evaluations` | `{document_id, coach?, suggest?}` -> report with `paragraphs` and ranked `todo` |
| GET | `/api/evaluations/{document_id}` | stored report |
| POST | `/api/evaluations/compare` | `{before_id, after_id}` -> score deltas and per-criterion changes |
