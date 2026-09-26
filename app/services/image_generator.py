from pathlib import Path
import re
import threading
from PIL import Image, ImageDraw

from app.config import get_settings

PIPELINE = None
# One lock guards both loading and running the pipeline: it is not thread-safe
# and routes run in FastAPI's threadpool.
_PIPELINE_LOCK = threading.Lock()

def _safe_name(text: str, index: int, run_id: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", text).strip("_").lower()
    return f"{run_id}_panel_{index}_{cleaned[:50] or 'scene'}.png"

def _placeholder(prompt: str, output: Path, index: int):
    settings = get_settings()
    img = Image.new("RGB", (settings.image_width, settings.image_height), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle((20, 20, settings.image_width-20, settings.image_height-20), outline="black", width=4)
    draw.text((40, 50), f"ComicCraft Panel {index}", fill="black")
    wrapped = "\n".join(prompt[i:i+55] for i in range(0, min(len(prompt), 500), 55))
    draw.text((40, 110), wrapped, fill="black")
    img.save(output)
    return output

def _get_pipeline():
    global PIPELINE
    if PIPELINE is not None:
        return PIPELINE

    import torch
    from diffusers import StableDiffusionPipeline

    settings = get_settings()
    device = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
    kwargs = {"use_safetensors": True}
    if settings.hf_token:
        kwargs["token"] = settings.hf_token
    if device == "cuda":
        kwargs["torch_dtype"] = torch.float16

    pipe = StableDiffusionPipeline.from_pretrained(settings.image_model_id, **kwargs)
    pipe = pipe.to(device)
    if device == "cuda":
        pipe.enable_attention_slicing()
    PIPELINE = pipe
    return PIPELINE

def generate_image(prompt: str, index: int, title: str, run_id: str) -> str:
    settings = get_settings()
    output_dir = Path(__file__).resolve().parents[2] / "static" / "panels"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / _safe_name(title, index, run_id)

    if settings.image_provider.lower() == "placeholder":
        _placeholder(prompt, output, index)
        return f"/static/panels/{output.name}"

    import torch
    with _PIPELINE_LOCK:
        pipe = _get_pipeline()
        generator = torch.Generator(device=pipe.device).manual_seed(settings.seed + index)
        result = pipe(
            prompt=prompt,
            negative_prompt="blurry, distorted, extra limbs, text, watermark, low quality",
            num_inference_steps=settings.image_steps,
            width=settings.image_width,
            height=settings.image_height,
            generator=generator,
        )
    result.images[0].save(output)
    return f"/static/panels/{output.name}"
