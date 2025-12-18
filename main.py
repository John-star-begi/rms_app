import os
import uuid
import shutil
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from playwright.async_api import async_playwright


# --------------------------------------------------
# PLAYWRIGHT HARD FIX FOR RENDER
# --------------------------------------------------

os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "/ms-playwright"
os.environ["PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD"] = "1"


# --------------------------------------------------
# PATH SETUP
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
REPORTS_DIR = BASE_DIR / "reports"

REPORTS_DIR.mkdir(exist_ok=True)

app = FastAPI()

# STATIC FILES
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/reports", StaticFiles(directory=REPORTS_DIR), name="reports")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# ---------- RMS CATEGORY DEFINITIONS ----------

CATEGORY_DEFINITIONS = [
    {
        "key": "bathroom",
        "name": "Bathroom",
        "legislation": "Schedule 4, Clause 1",
        "checklist": [
            "Washbasin present and connected to hot and cold water",
            "Shower or bath installed",
            "Shower or bath connected to hot and cold water",
            "Showerhead meets minimum 3-star WELS rating"
        ]
    },
    {
        "key": "electrical_safety",
        "name": "Electrical safety",
        "legislation": "Schedule 4, Clause 2",
        "checklist": [
            "Modern switchboard installed",
            "Circuit breakers installed",
            "Safety switch (RCD) installed",
            "No visible electrical hazards observed"
        ]
    },
    {
        "key": "heating",
        "name": "Heating",
        "legislation": "Schedule 4, Clause 3",
        "checklist": [
            "Fixed heater installed in main living area",
            "Heater permanently installed",
            "Heater operational at inspection time",
            "Heater suitable for intended space"
        ]
    },
    {
        "key": "kitchen",
        "name": "Kitchen",
        "legislation": "Schedule 4, Clause 4",
        "checklist": [
            "Dedicated kitchen area provided",
            "Sink connected to hot and cold water",
            "Stovetop with minimum two burners installed",
            "Oven operational if installed"
        ]
    },
    {
        "key": "laundry",
        "name": "Laundry",
        "legislation": "Schedule 4, Clause 5",
        "checklist": [
            "Laundry facilities provided",
            "Hot and cold water connections available",
            "Appropriate drainage present"
        ]
    },
    {
        "key": "lighting",
        "name": "Lighting",
        "legislation": "Schedule 4, Clause 6",
        "checklist": [
            "Functional lighting in habitable rooms",
            "Lighting available in kitchen, bathroom and toilet",
            "Lighting operational at inspection time"
        ]
    },
    {
        "key": "locks",
        "name": "Locks",
        "legislation": "Schedule 4, Clause 7",
        "checklist": [
            "External doors fitted with locks",
            "Locks can be unlocked from inside without a key",
            "Locks operational at inspection time"
        ]
    },
    {
        "key": "mould_and_damp",
        "name": "Mould and damp",
        "legislation": "Schedule 4, Clause 8",
        "checklist": [
            "No mould caused by building defects observed",
            "No rising damp present",
            "No water penetration observed"
        ]
    },
    {
        "key": "structural_soundness",
        "name": "Structural soundness",
        "legislation": "Schedule 4, Clause 9",
        "checklist": [
            "Property structurally sound",
            "No major structural defects observed",
            "Property weatherproof"
        ]
    },
    {
        "key": "toilets",
        "name": "Toilets",
        "legislation": "Schedule 4, Clause 10",
        "checklist": [
            "Toilet installed",
            "Toilet operational",
            "Connected to sewer or approved system",
            "Located in suitable room"
        ]
    },
    {
        "key": "ventilation",
        "name": "Ventilation",
        "legislation": "Schedule 4, Clause 11",
        "checklist": [
            "Adequate ventilation to habitable rooms",
            "Bathroom ventilation provided",
            "Toilet ventilation provided",
            "Laundry ventilation provided if applicable"
        ]
    },
    {
        "key": "vermin_proof_bins",
        "name": "Vermin-proof bins",
        "legislation": "Schedule 4, Clause 12",
        "checklist": [
            "Rubbish bin provided",
            "Recycling bin provided",
            "Bins vermin-proof and usable",
            "Meet local council standards"
        ]
    },
    {
        "key": "window_coverings",
        "name": "Window coverings",
        "legislation": "Schedule 4, Clause 13",
        "checklist": [
            "Curtains or blinds fitted where required",
            "Provide privacy",
            "Block light",
            "Blind cords secured safely"
        ]
    },
    {
        "key": "windows",
        "name": "Windows",
        "legislation": "Schedule 4, Clause 14",
        "checklist": [
            "Openable windows function",
            "Secure latches fitted",
            "No broken glass observed"
        ]
    }
]


# ---------- ROUTES ----------

@app.get("/", response_class=HTMLResponse)
async def form(request: Request):
    return templates.TemplateResponse("form.html", {"request": request})


@app.post("/generate")
async def generate_report(request: Request):

    form = await request.form()

    report_id = f"RMS-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
    report_dir = REPORTS_DIR / report_id
    report_dir.mkdir(exist_ok=True)

    categories = []
    table_rows = []
    all_photos = []

    non_compliant_count = 0

    for cat_def in CATEGORY_DEFINITIONS:
        key = cat_def["key"]

        status = form.get(f"{key}_status")
        note = form.get(f"{key}_notes")

        status_class = "ok"
        if status == "Non compliant":
            status_class = "bad"
            non_compliant_count += 1
        elif status == "Not applicable":
            status_class = "na"

        photos = []
        uploads = form.getlist(f"{key}_photos")

        for upload in uploads:
            if upload.filename:
                safe_name = f"{uuid.uuid4().hex}_{upload.filename}"
                photo_path = report_dir / safe_name

                with open(photo_path, "wb") as buffer:
                    shutil.copyfileobj(upload.file, buffer)

                photo_url = photo_path.resolve().as_uri()
                photos.append(photo_url)
                all_photos.append(photo_url)

        categories.append({
            "name": cat_def["name"],
            "legislation": cat_def["legislation"],
            "checklist": cat_def["checklist"],
            "status": status,
            "status_class": status_class,
            "note": note,
            "photos": photos
        })

        table_rows.append({
            "name": cat_def["name"],
            "status": status,
            "status_class": f"status-{status_class}",
            "summary": (
                "Meets minimum standard"
                if status == "Compliant"
                else "Does not meet minimum standard"
            )
        })

    context = {
        "property_address": form.get("property_address"),
        "generated_date": datetime.now().strftime("%d %b %Y"),
        "reference": report_id,
        "overall_status": "Compliant" if non_compliant_count == 0 else "Action required",
        "standards_checked": len(CATEGORY_DEFINITIONS),
        "non_compliant_count": non_compliant_count,
        "actions_required": non_compliant_count,
        "categories": categories,
        "table_rows": table_rows,
        "all_photos": all_photos
    }

    html = templates.get_template("report.html").render(context)

    html_path = report_dir / "report.html"
    html_path.write_text(html, encoding="utf-8")

    pdf_path = report_dir / f"{report_id}.pdf"

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--single-process"
            ]
        )

        page = await browser.new_page()

        await page.goto(
            html_path.resolve().as_uri(),
            wait_until="networkidle"
        )

        await page.pdf(
            path=str(pdf_path),
            format="A4",
            print_background=True
        )

        await browser.close()

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=pdf_path.name
    )
