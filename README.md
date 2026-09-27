# ComicCraft — AI Comic Story Creator

ComicCraft turns a story idea into a five-panel comic. Gemini writes the story; Stable Diffusion (via Hugging Face Diffusers) draws the panels; the result is shown in the browser and exported as a PDF.

## How it works

1. **Outline** — Gemini (`GEMINI_OUTLINE_MODEL`, default `gemini-3.8-flash`) writes a 5-panel outline with an image prompt per panel.
2. **Story** — Gemini (`GEMINI_STORY_MODEL`, default `gemini-3.1-pro-preview`) adds captions, narration and dialogue.
3. **Images** — Stable Diffusion renders each panel into `static/panels/` (or a placeholder image, see below).
4. **Layout + PDF** — panels are combined and exported with FPDF2 into `static/exports/`.

Stack: FastAPI + Jinja2, `google-genai`, `diffusers` / `transformers` / `torch`, FPDF2, Pillow.

## Requirements

- Python **3.11 or newer** (tested on 3.14)
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)
- For real images: several GB of disk for the model; an NVIDIA GPU is strongly recommended

## Quick start — Windows (PowerShell)

```powershell
cd ComicCraft
py -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
```

Open `.env` and set `GEMINI_API_KEY`. Keep `.env` private — it is listed in `.gitignore`.

### Fast smoke test (no Stable Diffusion download)

In `.env` set:

```env
IMAGE_PROVIDER=placeholder
```

Then start the server:

```powershell
python -m app.main
```

Open http://127.0.0.1:8000. (`uvicorn app.main:app --reload` also works.) `python -m app.main` uses `APP_HOST`, `APP_PORT` and `DEBUG` (auto-reload) from `.env`.

## Real image generation

Set `IMAGE_PROVIDER=diffusers`. The first generation downloads the checkpoint in `IMAGE_MODEL_ID` (about 4 GB for Stable Diffusion 1.5).

**GPU note:** `pip install -r requirements.txt` installs the **CPU-only** PyTorch build on Windows. CPU generation works but takes minutes per panel. For an NVIDIA GPU, reinstall PyTorch with the CUDA build from the selector at https://pytorch.org/get-started/locally/, for example:

```powershell
pip install --force-reinstall torch torchvision --index-url https://download.pytorch.org/whl/cu128
```

Check with `python -c "import torch; print(torch.cuda.is_available())"`. On CUDA the pipeline runs in float16 to save memory.

If the model needs Hugging Face authentication, set `HF_TOKEN` in `.env`.

## Configuration (`.env`)

| Variable | Default | Purpose |
|-|-|-|
| `GEMINI_API_KEY` | — | Required. Gemini API key. |
| `GEMINI_OUTLINE_MODEL` | `gemini-3.8-flash` | Model for the 5-panel outline. |
| `GEMINI_STORY_MODEL` | `gemini-3.1-pro-preview` | Model for narration and dialogue. |
| `GEMINI_FALLBACK_MODEL` | empty | Optional model to switch to when the models above run out of quota (HTTP 429). |
| `IMAGE_PROVIDER` | `diffusers` | `diffusers` for real images, `placeholder` for quick tests. |
| `IMAGE_MODEL_ID` | `stable-diffusion-v1-5/stable-diffusion-v1-5` | Hugging Face model ID. |
| `IMAGE_STEPS` / `IMAGE_WIDTH` / `IMAGE_HEIGHT` | `20` / `512` / `512` | Diffusion settings. |
| `SEED` | `42` | Base seed; panel *n* uses `SEED + n`. |
| `HF_TOKEN` | empty | Hugging Face token for gated models. |
| `APP_HOST` / `APP_PORT` / `DEBUG` | `127.0.0.1` / `8000` / `true` | Used by `python -m app.main`. |

Model IDs change over time; if a call fails with "model not found", pick a current ID from https://ai.google.dev/gemini-api/docs/models and update `.env`.

## API

| Method & path | Description |
|-|-|
| `GET /` | Web UI |
| `POST /generate` | Form submission; returns the comic preview page |
| `POST /generate-comic/json` | JSON API; returns title, panels and `pdf_path` |
| `POST /export-json` | Re-export a layout (from the JSON API) to a new PDF |
| `GET /download/{filename}` | Download an exported PDF |
| `POST /test-image` | Generate one image from a `prompt` form field |
| `GET /docs` | Swagger UI |

Example body for `POST /generate-comic/json`:

```json
{
  "story_prompt": "A brave fox explores an enchanted forest.",
  "character_name": "Luna",
  "setting": "Enchanted forest",
  "tone": "Funny",
  "art_style": "Comic book"
}
```

`/export-json` only accepts panel images under `/static/panels/`, and `/download` only serves PDFs from `static/exports/`.

## Testing

1. Set `IMAGE_PROVIDER=placeholder` and a valid `GEMINI_API_KEY`.
2. Run `python -m app.main` and submit the form at http://127.0.0.1:8000 — you should see five panels and a working **Download PDF** button.
3. Or open `/docs`, choose `POST /generate-comic/json`, click **Try it out**, paste the example body and execute.

## Troubleshooting

- **`pip install` fails with `ResolutionImpossible`** — use the current `requirements.txt` (diffusers 0.40 needs transformers 5.x).
- **`GEMINI_API_KEY is not configured`** — copy `.env.example` to `.env` and add the key, then restart the server.
- **Gemini 404 / model not found / "no longer available to new users"** — the model ID isn't available to your key; change `GEMINI_OUTLINE_MODEL` / `GEMINI_STORY_MODEL` (e.g. `gemini-2.5-pro` is closed to new users).
- **Gemini 429 / quota exceeded** — your plan has no (or no remaining) quota for that model. Each comic makes 2 Gemini calls (outline + story).
  - *Per-minute limit*: the app waits the delay Gemini asks for and retries once automatically.
  - *Daily limit* (`...PerDay...` in the details, e.g. 20 requests/day on the free tier): waiting a minute won't help; the quota resets at midnight Pacific time. Free-tier quotas are per model, so set `GEMINI_FALLBACK_MODEL` (or change `GEMINI_OUTLINE_MODEL` / `GEMINI_STORY_MODEL`) to another model your key can use, or enable billing.
  - Free-tier keys often have no Pro quota at all: set `GEMINI_STORY_MODEL` to a Flash model.
- **Gemini 503 / high demand** — temporary overload; the app retries 3 times automatically, then asks you to try again later.
- **`GET /generate 405`** — no longer happens; refreshing a result page now redirects to the home page.
- **Gemini returned an empty response** — the prompt was likely blocked by safety filters; rephrase the story.
- **Generation is very slow** — you are on CPU; use `IMAGE_PROVIDER=placeholder` or install CUDA PyTorch (see above).
- **CUDA out of memory** — lower `IMAGE_WIDTH`/`IMAGE_HEIGHT` or `IMAGE_STEPS`.
- **Model access error** — accept the model's license on Hugging Face and set `HF_TOKEN`.
- **Special characters in the PDF** — the PDF uses a built-in Latin font; curly quotes and dashes are converted, and unsupported characters (e.g. emoji) appear as `?`.
