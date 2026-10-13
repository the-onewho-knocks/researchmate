# STRaWBERRY-LLM

Checklist-based paper-draft assessment: rules -> small ML -> Gemini, in a fixed pipeline.

- Tier A criteria (counting/parsing) are decided by code.
- Tier B criteria (cue phrases) are decided by rules or a small sentence classifier; uncertain ones escalate.
- Tier C criteria (judgment) and escalated ones go to Gemini, batched per component group.
- Every verdict carries `source` (rule | ml | llm), `confidence` and evidence verified against the source text.

## Backend
```
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt   # or: pip install -e ".[dev]"; add ".[ml]" for the local ML layer
copy ..\.env.example .env      # then set GEMINI_API_KEY
uvicorn app.main:app --reload
```
Without GEMINI_API_KEY the app still runs: Tier A/B are answered locally, Tier C shows "needs review".

## Frontend
```
cd frontend
npm install
npm run dev
```

## Machine Learning Model 
```
pip install sentence-transformers scikit-learn joblib numpy
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

Fix suggestions: with `GEMINI_API_KEY` set, the highest-priority failed criteria (max 12) get one batched AI call for a text-specific fix (`config/prompts/suggest.md`). Without a key, each item shows the checklist hint instead. Effort/impact ranking is plain code (`app/services/report/priority.py`).

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | which layers are available |
| GET | `/api/framework` | the checklist (no rule parameters) |
| POST | `/api/uploads` | upload `.pdf`, `.docx` or `.tex` |
| POST | `/api/evaluations` | `{document_id, coach?, suggest?}` -> report with `paragraphs` and ranked `todo` |
| GET | `/api/evaluations/{document_id}` | stored report |
| POST | `/api/evaluations/compare` | `{before_id, after_id}` -> score deltas and per-criterion changes |
