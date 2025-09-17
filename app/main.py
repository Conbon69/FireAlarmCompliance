from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from starlette.staticfiles import StaticFiles

from .evaluator import evaluate_checklist, evaluate
from .models import ChecklistRequest, ChecklistResponse, ChecklistPlan, ICSRequest
from .utils_ics import build_monthly_ics


app = FastAPI(title="Fire Alarm Compliance")

# CORS - open for MVP
app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)


REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "static"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=FileResponse)
def index() -> FileResponse:
	index_path = STATIC_DIR / "index.html"
	if not index_path.exists():
		raise HTTPException(status_code=404, detail="index.html not found")
	return FileResponse(str(index_path))


@app.get("/health")
def health() -> JSONResponse:
	return JSONResponse({"ok": True})


@app.post("/api/checklist", response_model=ChecklistPlan)
def api_checklist(req: ChecklistRequest) -> ChecklistPlan:
	return evaluate(req)


@app.get("/api/ics")
def api_ics(q: ICSRequest = Depends()) -> PlainTextResponse:
	ics_content = build_monthly_ics(
		summary=q.title,
		description=q.description,
		count=q.months,
		start_date=q.start_date,
	)
	return PlainTextResponse(content=ics_content, media_type="text/calendar; charset=utf-8")


if __name__ == "__main__":
	import uvicorn
	uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


