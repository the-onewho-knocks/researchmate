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
pip install -e ".[dev]"        # add ".[ml]" for the local ML layer
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

## Tests
```
cd backend
pytest -q
```

Criteria, tiers, rule parameters, ML labels and hints live in `backend/config/framework/strawberry.v1.yaml`.
Bump PROMPT_VERSION in `.env` after changing prompts so cached results are invalidated.