import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from weasyprint import HTML


app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"

STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = STATIC_DIR / "uploads"
REPORT_DIR = STATIC_DIR / "reports"

STATIC_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


CATEGORIES = [
    "Electrical safety",
    "Plumbing and water pressure",
    "Hot water system",
    "Heating and cooling",
    "Smoke alarms",
    "Windows and locks",
    "Doors and locks",
    "Mould and damp",
    "Structural issues",
    "Pest issues",
    "Roof and gutters",
    "Appliances",
    "Gas safety",
    "General cleanliness",
]


def category_key(name: str) -> str:
    return name.lower().replace(" ", "_")


def safe_filename(name: str) -> str:
    return os.path.basename(name).replace("/", "_").replace("\\", "_")


@app.get("/", response_class=HTMLResponse)
async def show_form(request: Request):
    return templates.TemplateResponse(
        "form.html",
        {
            "request": request,
            "categories": CATEGORIES,
            "generated_date": datetime.now().strftime("%d %b %Y"),
        },
    )


@app.get("/generate")
async def generate_get():
    return RedirectResponse("/")


@app.post("/generate", response_class=HTMLResponse)
async def generate_report(request: Request):
    form = await request.form()

    agency = form.get("agency", "")
    property_manager = form.get("property_manager", "")
    property_address = form.get("property_address", "")

    report_data: Dict[str, Dict[str, Any]] = {}
    table_rows = []
    categories_out = []
    photo_urls: List[str] = []

    for category in CATEGORIES:
        key = category_key(category)
        status = form.get(f"{key}_status", "Not applicable")
        note = form.get(f"{key}_comment", "")

        photos = []
        uploads = form.getlist(f"{key}_photos")

        for upload in uploads:
            if not upload.filename:
                continue

            filename = f"{key}_{uuid.uuid4().hex}_{safe_filename(upload.filename)}"
            path = UPLOAD_DIR / filename
            content = await upload.read()

            with open(path, "wb") as f:
                f.write(content)

            photos.append(path.as_uri())
            photo_urls.append(path.as_uri())

        status_class = (
            "status-ok" if status == "Compliant"
            else "status-bad" if status == "Non compliant"
            else "status-na"
        )

        table_rows.append({
            "category": category,
            "status": status,
            "status_class": status_class,
            "summary": note,
        })

        categories_out.append({
            "name": category,
            "status": status,
            "cat_status_class": status_class.replace("status-", ""),
            "note": note,
        })

    non_compliant_count = sum(1 for r in table_rows if r["status"] == "Non compliant")

    reference = f"RMS-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
    pdf_filename = f"rms_{uuid.uuid4().hex}.pdf"
    pdf_path = REPORT_DIR / pdf_filename

    html = templates.get_template("report.html").render(
        {
            "agency": agency,
            "property_manager": property_manager,
            "property_address": property_address,
            "generated_date": datetime.now().strftime("%d %b %Y"),
            "reference": reference,
            "standards_checked": len(CATEGORIES),
            "non_compliant_count": non_compliant_count,
            "actions_required": non_compliant_count,
            "table_rows": table_rows,
            "categories": categories_out,
            "photo_urls": photo_urls,
        }
    )

    # CRITICAL FIX: use filesystem base URL
    HTML(
        string=html,
        base_url=STATIC_DIR.as_uri()
    ).write_pdf(str(pdf_path))

    return templates.TemplateResponse(
        "form.html",
        {
            "request": request,
            "categories": CATEGORIES,
            "generated_date": datetime.now().strftime("%d %b %Y"),
            "success_pdf_url": f"/static/reports/{pdf_filename}",
        },
    )


@app.get("/health")
async def health():
    return "ok"
