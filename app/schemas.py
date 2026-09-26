from pydantic import BaseModel, ConfigDict, Field, field_validator

class PromptRequest(BaseModel):
    # Strip before length checks so whitespace-only input is rejected.
    model_config = ConfigDict(str_strip_whitespace=True)

    story_prompt: str = Field(..., min_length=5, max_length=2000)
    character_name: str = Field(..., min_length=1, max_length=80)
    setting: str = Field(..., min_length=1, max_length=120)
    tone: str = Field(..., min_length=1, max_length=60)
    art_style: str = Field(..., min_length=1, max_length=80)

class Panel(BaseModel):
    panel_number: int
    title: str
    scene_description: str
    image_prompt: str = ""
    caption: str = ""
    narration: str = ""
    dialogue: str = ""
    image_path: str = ""

    @field_validator("image_path")
    @classmethod
    def panel_images_only(cls, value: str) -> str:
        if value and (not value.startswith("/static/panels/") or ".." in value or "\\" in value):
            raise ValueError("image_path must point to a generated panel in /static/panels/.")
        return value

class ExportRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    layout: list[Panel] = Field(..., min_length=1, max_length=20)

class ComicResponse(BaseModel):
    title: str
    panels: list[Panel]
    pdf_path: str | None = None
