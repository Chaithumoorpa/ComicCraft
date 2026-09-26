from pathlib import Path
from datetime import datetime
from uuid import uuid4
from fpdf import FPDF
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
PANELS_DIR = ROOT / "static" / "panels"
EXPORT_DIR = ROOT / "static" / "exports"

# FPDF's core fonts (Helvetica) only cover Latin-1. Map the punctuation Gemini
# commonly emits and replace anything else so export never crashes.
_REPLACEMENTS = {
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "…": "...", " ": " ",
}

def _pdf_text(text) -> str:
    text = str(text or "")
    for src, dst in _REPLACEMENTS.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", "replace").decode("latin-1")

def _asset_path(web_path: str) -> Path | None:
    """Resolve a /static/panels/... URL to a file, refusing anything outside that folder."""
    if not web_path.startswith("/static/panels/"):
        return None
    candidate = (PANELS_DIR / web_path.removeprefix("/static/panels/")).resolve()
    if candidate.parent != PANELS_DIR.resolve():
        return None
    return candidate

def save_pdf(title: str, layout: list[dict]) -> str:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"comic_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}.pdf"
    output = EXPORT_DIR / filename

    pdf = FPDF("P", "mm", "A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_title(_pdf_text(title))

    for i, panel in enumerate(layout):
        pdf.add_page()
        if i == 0:
            pdf.set_font("Helvetica", "B", 24)
            pdf.multi_cell(0, 12, _pdf_text(title), align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(4)
        pdf.set_font("Helvetica", "B", 18)
        pdf.multi_cell(0, 10, _pdf_text(f"Panel {panel['panel_number']}: {panel['title']}"),
                       new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        image_file = _asset_path(panel.get("image_path", ""))
        if image_file and image_file.exists():
            with Image.open(image_file) as img:
                w, h = img.size
            max_w, max_h = 180, 105
            ratio = min(max_w / w, max_h / h)
            pdf.image(str(image_file), x=(210 - w*ratio)/2, w=w*ratio, h=h*ratio)
        pdf.ln(6)

        pdf.set_font("Helvetica", "I", 11)
        pdf.multi_cell(0, 7, _pdf_text(panel["scene_description"]), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        if panel.get("caption"):
            pdf.set_font("Helvetica", "B", 11)
            pdf.multi_cell(0, 7, _pdf_text(f"Caption: {panel['caption']}"), new_x="LMARGIN", new_y="NEXT")
        if panel.get("narration"):
            pdf.set_font("Helvetica", "", 11)
            pdf.multi_cell(0, 7, _pdf_text(f"Narration: {panel['narration']}"), new_x="LMARGIN", new_y="NEXT")
        if panel.get("dialogue"):
            pdf.set_font("Helvetica", "", 11)
            pdf.multi_cell(0, 7, _pdf_text(f"Dialogue: {panel['dialogue']}"), new_x="LMARGIN", new_y="NEXT")

    pdf.output(str(output))
    return f"/static/exports/{filename}"
