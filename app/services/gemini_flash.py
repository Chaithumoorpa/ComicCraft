from app.config import get_settings
from app.schemas import PromptRequest
from app.services.gemini_client import generate_json

REQUIRED_KEYS = ("panel_number", "title", "scene_description", "image_prompt")

def generate_outline(request: PromptRequest) -> dict:
    settings = get_settings()
    prompt = f"""
Create a coherent 5-panel comic outline.

User story idea: {request.story_prompt}
Main character: {request.character_name}
Setting: {request.setting}
Tone: {request.tone}
Art style: {request.art_style}

Return ONLY JSON in this exact shape:
{{
  "title": "short comic title",
  "panels": [
    {{
      "panel_number": 1,
      "title": "panel title",
      "scene_description": "2-3 sentence visual scene description",
      "image_prompt": "detailed image-generation prompt"
    }}
  ]
}}

Rules:
- Exactly 5 panels.
- Keep the same main character visually consistent across panels.
- Give each image prompt concrete subjects, action, environment, lighting, camera framing,
  and the requested art style.
- No markdown and no extra keys.
"""
    data = generate_json(settings.gemini_outline_model, prompt, temperature=0.8)
    panels = data.get("panels")
    if not isinstance(panels, list) or not data.get("title"):
        raise ValueError("Unexpected outline format from Gemini.")
    if len(panels) != 5:
        raise ValueError("Gemini returned an outline that is not 5 panels.")
    for i, panel in enumerate(panels, start=1):
        missing = [k for k in REQUIRED_KEYS if not isinstance(panel, dict) or k not in panel]
        if missing:
            raise ValueError(f"Outline panel {i} is missing: {', '.join(missing)}.")
    return data
