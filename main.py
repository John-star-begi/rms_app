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
STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = STATIC_DIR / "uploads"
REPORT_DIR = STATIC_DIR / "reports"
TEMPLATE_DIR = BASE_DIR / "templates"

STATIC_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


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


def status_classes(status: str) -> Tuple[str, str]:
    if status == "Compliant":
        return "status-ok", "ok"
    if status == "Non compliant":
        return "status-bad", "bad"
    return "status-na", "na"


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
    return RedirectResponse(url="/")


@app.post("/generate", response_class=HTMLResponse)
async def generate_report(request: Request):
    form = await request.form()

    agency = (form.get("agency") or "").strip()
    property_manager = (form.get("property_manager") or "").strip()
    property_address = (form.get("property_address") or "").strip()

    report_data: Dict[str, Dict[str, Any]] = {}

    for category in CATEGORIES:
        key = category_key(category)

        status = (form.get(f"{key}_status") or "Not applicable").strip()
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

            photos.append(f"/static/uploads/{final_name}")

        report_data[category] = {
            "status": status,
            "comment": comment,
            "photos": photos,
        }

    non_compliant_count = sum(
        1 for item in report_data.values()
        if item.get("status") == "Non compliant"
    )

    standards_checked = len(CATEGORIES)
    actions_required = non_compliant_count

    reference = f"RMS-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"

    table_rows: List[Dict[str, str]] = []
    categories_out: List[Dict[str, Any]] = []

    non_compliant_photos: List[str] = []
    other_photos: List[str] = []

    for category in CATEGORIES:
        item = report_data[category]
        status = item["status"]
        note = item["comment"]
        photos = item["photos"]

        table_status_class, cat_status_class = status_classes(status)

        table_rows.append(
            {
                "category": category,
                "status": status,
                "status_class": table_status_class,
                "summary": note,
            }
        )

        categories_out.append(
            {
                "name": category,
                "status": status,
                "cat_status_class": cat_status_class,
                "note": note,
            }
        )

        if photos:
            if status == "Non compliant":
                non_compliant_photos.extend(photos)
            else:
                other_photos.extend(photos)

    # Make absolute URLs for WeasyPrint so it can actually fetch assets
    base = str(request.base_url).rstrip("/")
    logo_url = f"{base}/static/class-a-fix-logo.jpg"

    photo_urls: List[str] = []
    for p in (non_compliant_photos + other_photos):
        if p.startswith("http://") or p.startswith("https://"):
            photo_urls.append(p)
        else:
            photo_urls.append(f"{base}{p}")

    pdf_filename = f"rms_{uuid.uuid4().hex}.pdf"
    pdf_path = REPORT_DIR / pdf_filename

    html_content = templates.get_template("report.html").render(
        {
            "agency": agency,
            "property_manager": property_manager,
            "property_address": property_address,
            "generated_date": datetime.now().strftime("%d %b %Y"),
            "reference": reference,
            "standards_checked": standards_checked,
            "non_compliant_count": non_compliant_count,
            "actions_required": actions_required,
            "table_rows": table_rows,
            "categories": categories_out,
            "photo_urls": photo_urls,
            "logo_url": logo_url,
        }
    )

    # Critical: base_url must be an absolute URL so /static resolves
    HTML(string=html_content, base_url=str(request.base_url)).write_pdf(str(pdf_path))

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
