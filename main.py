import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from weasyprint import HTML


app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent

STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = STATIC_DIR / "uploads"
REPORT_DIR = STATIC_DIR / "reports"

STATIC_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

CATEGORIES: List[str] = [
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


def safe_filename(original_name: str) -> str:
    base = os.path.basename(original_name or "")
    base = base.replace("\\", "_").replace("/", "_").strip()
    if not base:
        base = "upload"
    return base


def category_key(category: str) -> str:
    return category.strip().lower().replace(" ", "_")


@app.get("/", response_class=HTMLResponse)
async def form_page(request: Request):
    return templates.TemplateResponse(
        "form.html",
        {
            "request": request,
            "categories": CATEGORIES,
            "generated_date": datetime.now().strftime("%d %b %Y"),
        },
    )


@app.post("/generate", response_class=HTMLResponse)
async def generate_report(request: Request):
    form = await request.form()

    agency = (form.get("agency") or "").strip()
    property_manager = (form.get("property_manager") or "").strip()
    property_address = (form.get("property_address") or "").strip()

    report_data: Dict[str, Dict[str, Any]] = {}

    for category in CATEGORIES:
        key = category_key(category)

        status = (form.get(f"{key}_status") or "").strip()
        comment = (form.get(f"{key}_comment") or "").strip()

        saved_photos: List[str] = []
        uploads = form.getlist(f"{key}_photos")

        for upload in uploads:
            if not getattr(upload, "filename", None):
                continue

            original = safe_filename(upload.filename)
            unique = uuid.uuid4().hex
            final_name = f"{key}_{unique}_{original}"
            file_path = UPLOAD_DIR / final_name

            contents = await upload.read()
            if not contents:
                continue

            with open(file_path, "wb") as f:
                f.write(contents)

            saved_photos.append(f"/static/uploads/{final_name}")

        report_data[category] = {
            "status": status,
            "comment": comment,
            "photos": saved_photos,
        }

    pdf_id = uuid.uuid4().hex
    pdf_filename = f"rms_report_{pdf_id}.pdf"
    pdf_path = REPORT_DIR / pdf_filename

    html_content = templates.get_template("report.html").render(
        {
            "agency": agency,
            "property_manager": property_manager,
            "property_address": property_address,
            "generated_date": datetime.now().strftime("%d %b %Y"),
            "data": report_data,
        }
    )

    HTML(string=html_content, base_url=str(BASE_DIR)).write_pdf(str(pdf_path))

    return templates.TemplateResponse(
        "form.html",
        {
            "request": request,
            "categories": CATEGORIES,
            "generated_date": datetime.now().strftime("%d %b %Y"),
            "success_pdf_url": f"/static/reports/{pdf_filename}",
        },
    )


@app.get("/health", response_class=HTMLResponse)
async def health():
    return "ok"
