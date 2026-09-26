def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return value

def build_comic_layout(outline: dict, story: dict, image_paths: list[str]) -> list[dict]:
    story_by_number = {_as_int(p.get("panel_number")): p for p in story["panels"]}
    layout = []
    for i, panel in enumerate(outline["panels"]):
        number = _as_int(panel["panel_number"])
        text = story_by_number.get(number, {})
        layout.append({
            "panel_number": number,
            "title": panel["title"],
            "scene_description": panel["scene_description"],
            "image_prompt": panel["image_prompt"],
            "caption": text.get("caption", ""),
            "narration": text.get("narration", ""),
            "dialogue": text.get("dialogue", ""),
            "image_path": image_paths[i],
        })
    return layout
