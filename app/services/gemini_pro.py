import json

from app.config import get_settings
from app.services.gemini_client import generate_json

def generate_story(outline: dict, story_context: dict) -> dict:
    settings = get_settings()
    prompt = f"""
Expand this 5-panel comic outline into polished comic narration and dialogue.

Context:
{json.dumps(story_context, ensure_ascii=False)}

Outline:
{json.dumps(outline, ensure_ascii=False)}

Return ONLY JSON:
{{
  "panels": [
    {{
      "panel_number": 1,
      "caption": "short comic caption",
      "narration": "2-4 sentences of narration",
      "dialogue": "optional dialogue; use speaker labels if needed"
    }}
  ]
}}

Rules:
- Exactly one object for every outline panel, in the same order.
- Preserve the plot and character identity from the outline.
- Keep dialogue natural and concise.
- Do not introduce unrelated characters or locations.
- No markdown and no extra keys.
"""
    data = generate_json(settings.gemini_story_model, prompt, temperature=0.85)
    panels = data.get("panels")
    if not isinstance(panels, list) or len(panels) != 5:
        raise ValueError("Gemini returned an invalid story panel count.")
    if not all(isinstance(p, dict) and "panel_number" in p for p in panels):
        raise ValueError("Gemini story panels are missing panel_number.")
    return data
