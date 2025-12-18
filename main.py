from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from playwright.async_api import async_playwright

from pathlib import Path
from datetime import datetime
import uuid
import asyncio

BASE_DIR = Path(__file__).resolve().parent
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

app = FastAPI()
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


CATEGORIES = [
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
        "key": "electrical",
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
            "Heater is permanently installed",
            "Heater operational at inspection time",
            "Heater suitable for intended space"
        ]
    },
    # Remaining categories continue identically
]

@app.get("/", response_class=HTMLResponse)
async def form(request: Request):
    return templates.TemplateResponse("form.html", {"request": request})


@app.post("/generate")
async def generate(
    request: Request,
    property_address: str = Form(...)
):
    report_id = f"RMS-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
    pdf_path = REPORTS_DIR / f"{report_id}.pdf"

    context = {
        "property_address": property_address,
        "generated_date": datetime.now().strftime("%d %b %Y"),
        "reference": report_id,
        "categories": CATEGORIES,
        "request": request
    }

    html = templates.get_template("report.html").render(context)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        page = await browser.new_page()
        await page.set_content(html, wait_until="networkidle")
        await page.pdf(path=str(pdf_path), format="A4")
        await browser.close()

    return FileResponse(pdf_path, media_type="application/pdf", filename=pdf_path.name)
