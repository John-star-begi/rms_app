from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from weasyprint import HTML
import os
from datetime import datetime

app = FastAPI()
templates = Jinja2Templates(directory="templates")

UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

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
async def generate_rms(
    request: Request,
    agency: str = Form(...),
    property_manager: str = Form(...),
    property_address: str = Form(...),
    **form_data,
):
    categories_data = {}

    for cat in CATEGORIES:
        key = cat.lower().replace(" ", "_")
        status = form_data.get(f"{key}_status")
        comment = form_data.get(f"{key}_comment", "")

        photos = request.files.getlist(f"{key}_photos")

        saved_photos = []
        for photo in photos:
            filename = f"{key}_{photo.filename}"
            path = os.path.join(UPLOAD_DIR, filename)
            with open(path, "wb") as f:
                f.write(await photo.read())
            saved_photos.append(path)

        categories_data[key] = {
            "name": cat,
            "status": status,
            "comment": comment,
            "photos": saved_photos,
        }

    html = templates.get_template("rms.html").render(
        agency=agency,
        property_manager=property_manager,
        property_address=property_address,
        categories=CATEGORIES,
        data=categories_data,
        generated_date=datetime.now().strftime("%d %b %Y"),
        request=request,
    )

    pdf = HTML(string=html, base_url=".").write_pdf()

    output_path = "rms_report.pdf"
    with open(output_path, "wb") as f:
        f.write(pdf)

    return HTMLResponse(
        f"<h2>PDF Generated</h2><a href='/{output_path}'>Download RMS PDF</a>"
    )
