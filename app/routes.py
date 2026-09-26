import logging
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse

from app.schemas import ExportRequest, PromptRequest
from app.services.gemini_flash import generate_outline
from app.services.gemini_pro import generate_story
from app.services.image_generator import generate_image
from app.services.layout_builder import build_comic_layout
from app.services.exporters import EXPORT_DIR, save_pdf
from app.templating import templates as template_engine

logger = logging.getLogger("comiccraft")
router = APIRouter()

def _generate(request_data: PromptRequest):
    run_id = uuid4().hex[:8]
    outline = generate_outline(request_data)
    story = generate_story(outline, request_data.model_dump())
    image_paths = [
        generate_image(panel["image_prompt"], panel["panel_number"], panel["title"], run_id)
        for panel in outline["panels"]
    ]
    layout = build_comic_layout(outline, story, image_paths)
    pdf_path = save_pdf(outline["title"], layout)
    return outline["title"], layout, pdf_path

def templates(request: Request, name: str, **context):
    return template_engine.TemplateResponse(
        request=request, name=name, context=context
    )

# Generation routes are plain `def` so FastAPI runs them in a threadpool:
# the Gemini and Stable Diffusion calls block for a long time.

@router.get("/")
def home(request: Request):
    return templates(request, "index.html")

@router.get("/generate")
def generate_redirect():
    # Refreshing or going back to a result page issues GET /generate.
    return RedirectResponse("/", status_code=303)

@router.post("/generate")
def generate(
    request: Request,
    story_prompt: str = Form(...),
    character_name: str = Form(...),
    setting: str = Form(...),
    tone: str = Form(...),
    art_style: str = Form(...),
):
    try:
        data = PromptRequest(
            story_prompt=story_prompt,
            character_name=character_name,
            setting=setting,
            tone=tone,
            art_style=art_style,
        )
        title, layout, pdf_path = _generate(data)
        return templates(
            request, "comic_preview.html",
            title=title, layout=layout, pdf_path=pdf_path
        )
    except Exception as exc:
        logger.exception("Comic generation failed")
        return templates(request, "error.html", error=str(exc))

@router.post("/generate-comic/json")
def generate_json(payload: PromptRequest):
    try:
        title, layout, pdf_path = _generate(payload)
        return {"title": title, "panels": layout, "pdf_path": pdf_path}
    except Exception as exc:
        logger.exception("Comic generation failed")
        raise HTTPException(status_code=500, detail=str(exc))

@router.post("/export-json")
def export_json(payload: ExportRequest):
    try:
        layout = [panel.model_dump() for panel in payload.layout]
        return {"pdf_path": save_pdf(payload.title, layout)}
    except Exception as exc:
        logger.exception("PDF export failed")
        raise HTTPException(status_code=500, detail=str(exc))

@router.get("/export-success")
def export_success(request: Request, pdf_path: str | None = None):
    if pdf_path and not pdf_path.startswith("/static/exports/"):
        pdf_path = None
    return templates(request, "export_success.html", pdf_path=pdf_path)

@router.get("/download/{filename}")
def download(filename: str):
    file = (EXPORT_DIR / filename).resolve()
    if file.parent != EXPORT_DIR.resolve() or file.suffix.lower() != ".pdf" or not file.exists():
        raise HTTPException(status_code=404, detail="PDF not found.")
    return FileResponse(file, media_type="application/pdf", filename=file.name)

@router.post("/test-image")
def test_image(prompt: str = Form(...)):
    try:
        path = generate_image(prompt, 999, "test", uuid4().hex[:8])
        return {"image_path": path}
    except Exception as exc:
        logger.exception("Test image failed")
        raise HTTPException(status_code=500, detail=str(exc))
