from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from weasyprint import HTML
from datetime import datetime
import os

app = FastAPI()

# -------------------------------
# Folders
# -------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
UPLOAD_DIR = os.path.join(STATIC_DIR, "uploads")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

templates = Jinja2Templates(directory="templates")

# -------------------------------
# RMS Categories
# -------------------------------
CATEGORIES = [
    "Bathroom",
    "Electrical safety",
    "Lighting",
    "Kitchen",
    "Laundry",
    "Locks",
    "Heating",
    "Mould and damp",
    "Structural soundness",
    "Toilets",
    "Ventilation",
    "Vermin-proof bins",
    "Window coverings",
    "Windows",
]

# -------------------------------
# Routes
# -------------------------------

@app.get("/", response_class=HTMLResponse)
async def rms_form(request: Request):
    return templates.TemplateResponse(
        "rms.html",
        {
            "request": request,
            "categories": CATEGORIES,
            "generated_date": datetime.now().strftime("%d %b %Y"),
        },
    )


@app.post("/generate", response_class=HTMLResponse)
async def generate_rms(request: Request):
    form = await request.form()

    agency = form.get("agency")
    property_manager = form.get("property_manager")
    property_address = form.get("property_address")

    categories_data = {}

    for cat in CATEGORIES:
        key = cat.lower().replace(" ", "_").replace("-", "_")

        status = form.get(f"{key}_status")
        comment = form.get(f"{key}_comment", "")

        photos = form.getlist(f"{key}_photos")

        saved_photos = []
        for photo in photos:
            if not photo.filename:
                continue

            filename = f"{key}_{photo.filename}"
            filepath = os.path.join(UPLOAD_DIR, filename)

            with open(filepath, "wb") as f:
                f.write(await photo.read())

            saved_photos.append(f"static/uploads/{filename}")

        categories_data[key] = {
            "name": cat,
            "status": status,
            "comment": comment,
            "photos": saved_photos,
        }

    html = templates.get_template("rms.html").render(
        request=request,
        agency=agency,
        property_manager=property_manager,
        property_address=property_address,
        data=categories_data,
        generated_date=datetime.now().strftime("%d %b %Y"),
    )

    pdf_bytes = HTML(string=html, base_url=BASE_DIR).write_pdf()

    output_path = os.path.join(STATIC_DIR, "rms_report.pdf")
    with open(output_path, "wb") as f:
        f.write(pdf_bytes)

    return HTMLResponse(
        f"""
        <h2>PDF Generated</h2>
        <p><a href="/static/rms_report.pdf" target="_blank">Download RMS PDF</a></p>
        <p><a href="/">Create another report</a></p>
        """
    )
