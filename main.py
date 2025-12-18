import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from weasyprint import HTML


# --------------------------------------------------
# App setup
# --------------------------------------------------

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


# --------------------------------------------------
# Categories
# --------------------------------------------------

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


def category_key(name: str) -> str:
    return name.lower().replace(" ", "_")


def safe_filename(name: str) -> str:
    base = os.path.basename(name or "")
    base = base.replace("/", "_").replace("\\", "_").strip()
    return base if base else "upload"


# --------------------------------------------------
# Routes
# --------------------------------------------------

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


@app.post("/generate", response_class=HTMLResponse)
async def generate_report(request: Request):
    form = await request.form()

    property_address = (form.get("property_address") or "").strip()

    report_data: Dict[str, Dict[str, Any]] = {}
    all_photos: List[str] = []

    # ----------------------------------------------
    # Collect category data and photos
    # ----------------------------------------------

    for category in CATEGORIES:
        key = category_key(category)

        status = (form.get(f"{key}_status") or "").strip()
        comment = (form.get(f"{key}_comment") or "").strip()

        photos: List[str] = []
        uploads = form.getlist(f"{key}_photos")

        for upload in uploads:
            if not getattr(upload, "filename", None):
                continue

            filename = safe_filename(upload.filename)
            unique = uuid.uuid4().hex
            final_name = f"{key}_{unique}_{filename}"
            file_path = UPLOAD_DIR / final_name

            content = await upload.read()
            if not content:
                continue

            with open(file_path, "wb") as f:
                f.write(content)

            photo_url = f"/static/uploads/{final_name}"
            photos.append(photo_url)
            all_photos.append(photo_url)

        report_data[category] = {
            "status": status,
            "comment": comment,
            "photos": photos,
        }

    # ----------------------------------------------
    # Derived values
    # ----------------------------------------------

    non_compliant_count = sum(
        1 for item in report_data.values()
        if item["status"] == "Non compliant"
    )

    reference = f"RMS-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"

    pdf_id = uuid.uuid4().hex
    pdf_filename = f"rms_report_{pdf_id}.pdf"
    pdf_path = REPORT_DIR / pdf_filename

    # ----------------------------------------------
    # Render PDF HTML
    # ----------------------------------------------

    html_content = templates.get_template("report.html").render(
        {
            "property_address": property_address,
            "generated_date": datetime.now().strftime("%d %b %Y"),
            "reference": reference,
            "data": report_data,
            "non_compliant_count": non_compliant_count,
            "photos": all_photos,
        }
    )

    HTML(string=html_content, base_url=str(BASE_DIR)).write_pdf(str(pdf_path))

    # ----------------------------------------------
    # Return form with download link
    # ----------------------------------------------

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
