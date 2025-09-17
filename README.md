## Fire Alarm Compliance (MVP)

Minimal FastAPI app that generates a plain‑English checklist for home smoke/CO alarms from JSON rules (baseline + optional state overlay). A tiny frontend posts inputs and renders results; an ICS endpoint produces monthly reminders.

> Disclaimer: Informational only; codes vary. Confirm with your local Authority Having Jurisdiction (AHJ).

### Features
- JSON rule engine with inheritance/overlays: `rules/US/common.json`, `rules/US/CA/common.json`
- Compact rule schema: conditions + recommendations + testing
- API endpoints: POST `/api/checklist`, GET `/api/ics`, health `GET /health`
- Static frontend served at `/` with copy/export and calendar reminder
- Render-friendly (Procfile + render.yaml), no database

### Project layout
```text
app/            # FastAPI app, evaluator, models, ICS utility
static/         # index.html, app.js, styles.css
rules/          # JSON rules (US baseline + state overlays)
tests/          # pytest cases for evaluator
Procfile        # Render web process
render.yaml     # Render service definition
requirements.txt
```

## Local development

### Prereqs
- Python 3.11+

### Install deps
```bash
pip install -r requirements.txt
```

### Run the server
```bash
make dev
# or
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open:
- UI: `http://localhost:8000/`
- Health: `http://localhost:8000/health` → `{ "ok": true }`

### Tests
```bash
make test
# or
python -m pytest -q
```

## API

### POST /api/checklist
Request body (ChecklistRequest):
```json
{
  "state": "US-CA",
  "property_type": "single_family",
  "bedrooms": 3,
  "floors": 2,
  "has_fuel_appliance": true,
  "has_attached_garage": false,
  "year_bucket": "y2011_plus",
  "interconnect_present": "unknown",
  "permit_planned": false
}
```

Response (ChecklistPlan, abbreviated):
```json
{
  "recommendations": [
    { "type": "smoke", "place": "each_bedroom", "note": null, "source": "model_code", "citation": "NFPA 72" }
  ],
  "testing": [ { "action": "test", "frequency": "monthly" } ],
  "notes": ["Permit work may trigger hardwired, interconnected upgrades. Verify with your AHJ."],
  "jurisdiction_chain": ["US/common", "US/CA/common"]
}
```

### GET /api/ics
Query params (ICSRequest): `email` (ignored for now), `frequency=monthly`, `months` (default 12), `start_date=YYYY-MM-DD`, `title`, `description`.

Example:
```bash
curl "http://localhost:8000/api/ics?months=12&title=Test%20smoke/CO%20alarms"
```
Returns `text/calendar` content for a monthly recurring event.

## Rules schema (compact)
- `meta`: `{ jurisdiction, version, inherits? }`
- `rules`: array of rule objects
- `testing`: default testing actions for the jurisdiction

Rule:
```json
{
  "id": "us-co-baseline",
  "when": { "any": [ { "eq": { "has_fuel_appliance": true } }, { "eq": { "has_attached_garage": true } } ] },
  "recommend": [ { "type": "co", "place": "near_sleeping_areas", "citation": "NFPA 72", "source": "model_code" } ],
  "notes": ["...optional note..."],
  "priority": 10
}
```

`when` supports: `always`, `eq` (map of exact matches), `all`/`any`/`not`, and simple `gte/gt/lte/lt` (e.g., `{ "gte": { "floors": 2 } }`).

## Deployment (Render)
- Repo includes `render.yaml` and `Procfile`.
- Render web service (Python 3.11) installs with `pip install -r requirements.txt` and starts:
```text
web: gunicorn -w 1 -k uvicorn.workers.UvicornWorker app.main:app
```
- Auto-deploy on push to main per `render.yaml`.
- Health check: `/health`.
- Env var `RULES_DIR=./rules` (used by the rules loader).

## Frontend
- Served from `/static` (index at `/`).
- Form posts to `/api/checklist`; results show grouped smoke/CO recommendations, testing, notes, and jurisdiction chain. Buttons: “Copy checklist”, “Add to calendar (ICS)”. AHJ button performs a Google search for local requirements.


