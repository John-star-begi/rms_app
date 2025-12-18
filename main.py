import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
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


CATEGORY_EXPLANATIONS: Dict[str, List[str]] = {
    "Electrical safety": [
        "Switchboard and electrical fittings appear safe at the time of inspection.",
        "No visible hazards such as exposed wiring were identified.",
    ],
    "Plumbing and water pressure": [
        "Plumbing fixtures appear operational at the time of inspection.",
        "Water pressure is assessed by operation of taps and fixtures where accessible.",
    ],
    "Hot water system": [
        "Hot water is available at the time of inspection.",
        "System condition is assessed visually where accessible.",
    ],
    "Heating and cooling": [
        "Heating and or cooling systems are checked for basic operation where accessible.",
        "Assessment is limited to visible and accessible components at inspection time.",
    ],
    "Smoke alarms": [
        "Smoke alarms are checked for presence and basic operation where accessible.",
        "Compliance may require licensed verification depending on installation and location.",
    ],
    "Windows and locks": [
        "Windows and latches are checked for basic operation and security where accessible.",
        "Assessment includes visible damage and ability to secure openings.",
    ],
    "Doors and locks": [
        "External doors and locks are checked for secure closure and basic operation.",
        "Assessment includes visible damage and ability to lock as intended.",
    ],
    "Mould and damp": [
        "Visible signs of mould and damp are checked at the time of inspection.",
        "Assessment considers ventilation and visible water ingress indicators where present.",
    ],
    "Structural issues": [
        "Visible structural concerns are noted where present.",
        "Assessment is non invasive and limited to accessible areas.",
    ],
    "Pest issues": [
        "Visible signs of pest activity are noted where present.",
        "Assessment is limited to obvious indicators at inspection time.",
    ],
    "Roof and gutters": [
        "Roof and gutter condition is assessed visually where accessible.",
        "Assessment may be limited by access and line of sight.",
    ],
    "Appliances": [
        "Included appliances are checked for basic operation where accessible.",
        "Assessment does not replace licensed servicing where required.",
    ],
    "Gas safety": [
        "Visible gas related concerns are noted where present.",
        "Licensed testing may be required for full verification.",
    ],
    "General cleanliness": [
        "General cleanliness is noted to support presentation and habitability context.",
        "This is not a cleaning certification, only an observation at inspection time.",
    ],
}


def category_key(name: str) -> str:
    return name.lower().replace(" ", "_")


def safe_filename(name: str) -> str:
    base = os.path.basename(name or "")
    base = base.replace("/", "_").replace("\\", "_").strip()
    return base if base else "upload"


def status_classes(status: str) -> Tuple[str, str]:
    s = (status or "").strip()
    if s == "Compliant":
        return "status-ok", "ok"
    if s == "Non compliant":
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

    categories_out: List[Dict[str, Any]] = []
    table_rows: List[Dict[str, str]] = []

    non_compliant_photos: List[str] = []
    other_photos: List[str] = []

    for category in CATEGORIES:
        item = report_data.get(category, {})
        status = (item.get("status") or "").strip()
        note = (item.get("comment") or "").strip()
        photos = item.get("photos") or []

        table_status_class, cat_status_class = status_classes(status)

        summary = note.strip()
        if len(summary) > 120:
            summary = summary[:117].rstrip() + "..."

        table_rows.append(
            {
                "category": category,
                "status": status if status else "Not applicable",
                "status_class": table_status_class,
                "summary": summary,
            }
        )

        explanation = CATEGORY_EXPLANATIONS.get(category, [])
        categories_out.append(
            {
                "name": category,
                "status": status if status else "Not applicable",
                "cat_status_class": cat_status_class,
                "note": note,
                "explanation": explanation,
            }
        )

        if photos:
            if status == "Non compliant":
                non_compliant_photos.extend(photos)
            else:
                other_photos.extend(photos)

    photo_urls = non_compliant_photos + other_photos

    pdf_id = uuid.uuid4().hex
    pdf_filename = f"rms_report_{pdf_id}.pdf"
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
