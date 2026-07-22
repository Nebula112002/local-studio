# Local Studio

Self-contained **100% local** image and video generation studio. No cloud APIs, no prompt filtering, no account required. Talks to **ComfyUI** or **Forge / Automatic1111** (usually via Stability Matrix).

## Paths (this PC)

| What | Where |
|------|-------|
| **App (fast disk)** | `D:\AI\caleb-pc\sites\local-studio` |
| **Outputs** | `G:\Generation\Local-Studio\output` |
| **Local URL** | http://127.0.0.1:8787 |
| **Tailnet** | https://calebscomputer.tailfdadcb.ts.net:8787 |

Do **not** run the app from `G:\Generation` — G: is for generated media only.

## Quick start

1. **Start your SD backend** in Stability Matrix:
   - ComfyUI → usually `http://127.0.0.1:8188`
   - Forge / A1111 → usually `http://127.0.0.1:7860`

2. **Launch Local Studio** (from this folder):

   **Windows:**
   ```powershell
   .\start.ps1
   ```

   **Linux / macOS:**
   ```bash
   ./start.sh
   ```

   Or double-click `start.bat` on Windows.

3. Open **http://127.0.0.1:8787** in your browser (opens automatically on Linux/macOS).

The UI auto-detects which backend is running. Use **Settings** to force a specific backend or change URLs.

## Modes

| Mode | Backend | What it does |
|------|---------|--------------|
| **Text → Image** | ComfyUI or Forge | Standard prompt-to-image |
| **Image → Image** | ComfyUI or Forge | Upload a source image; use **Similarity** to control how much stays the same |
| **Text → Video** | ComfyUI + SVD | Generates a still frame from your prompt, then animates it |
| **Image → Video** | ComfyUI + SVD | Animates your uploaded image into a short clip |

### Similarity slider (image modes)

Higher similarity = output stays closer to your source image. Lower = more creative change. This maps to denoising strength under the hood.

### Video setup (Stability Matrix)

1. Launch **ComfyUI** (not Forge) for video modes
2. Download an **SVD** model (e.g. `svd_xt` or `svd_xt_1_1`) in Stability Matrix
3. In Local Studio Settings, set backend to **ComfyUI** (or auto-detect)

## Features

- **Single generate** — one click with full control over steps, CFG, sampler, scheduler, size, seed, model
- **Batch queue** — run many generations with:
  - Batch count (1–100)
  - Images per pass (batch size)
  - Seed modes: increment, fixed, or random per batch
  - Prompt variations (one per line, appended or standalone)
- **Character profiles** — save reusable character definitions (hair, eyes, style, outfit, seed) for consistent generations across sessions
- **Local AI prompt assistant** — enhance prompts, generate scene ideas, and write negative prompts via **Ollama** or any OpenAI-compatible local API (no cloud, no filtering)
- **Quality presets** — one-click photorealistic, cinematic, portrait, fashion, anime, and artistic settings
- **Generation history** — every run is logged with prompt, seed, and settings; reuse any past generation in one click
- **Video presets** — subtle, balanced, dynamic, and cinematic clip presets for SVD video
- **Toast notifications** — clean feedback instead of popup alerts
- **Keyboard shortcut** — `Ctrl+Enter` to generate
- **Auto-save** — PNGs written to `G:\Generation\Local-Studio\output` on this PC (toggle in Settings; override with `LOCAL_STUDIO_OUTPUT_DIR`)
- **Uncensored** — prompts pass through unchanged to your local model

## Requirements

- Python 3.10+
- A local Stable Diffusion install (ComfyUI or A1111/Forge)
- A checkpoint model in your backend's `models` folder

## Folder layout

```
Local-Studio/
  start.ps1 / start.bat / start.sh   # launch scripts
  requirements.txt
  server/                 # FastAPI backend + queue
  web/                    # frontend UI
  output/                 # saved images (created on first run)
  profiles.json           # character profiles (created on first use)
```

## Stability Matrix tips

1. Open Stability Matrix and launch **ComfyUI** or **SD WebUI Forge**.
2. Wait until the backend shows as running (green).
3. Then start Local Studio.
4. Pick your checkpoint in the left panel once connected.

For uncensored results, use an uncensored checkpoint in Stability Matrix (e.g. realistic or anime models without safety filters). Local Studio does not add any safety layer.

## Character profiles

Create characters in the left sidebar (**+ New**) or use **Quick start** templates. Each profile stores appearance, scenes, reference image, and generation defaults.

### Power features
- **Reference image** — upload a face/body reference for img2img consistency across scenes
- **Batch scenes** — one click queues every saved scene for the active character
- **Scene chips** — click saved scenes to instantly fill the prompt
- **Social sizes** — X, Instagram, TikTok, portrait HD presets in one click
- **Gallery actions** — save any output as character reference or thumbnail
- **Templates** — Fitness, Glamour Editorial, Girl Next Door starters

Select a character → **Apply** → **Batch scenes** to generate a full content set.

## Local AI prompt assistant

Local Studio can call a **local LLM** to enhance your prompts — entirely on your machine, no cloud APIs.

### Setup (Ollama — recommended)

1. Install [Ollama](https://ollama.com)
2. Pull a model: `ollama pull llama3.2` (or `mistral`, `dolphin-mixtral`, etc.)
3. Open **Settings → Local AI Assistant** and confirm URL `http://127.0.0.1:11434`

### What it does

| Button | Action |
|--------|--------|
| **Enhance prompt** | Expands your prompt with lighting, composition, quality tags |
| **Scene ideas** | Generates clickable scene/setting suggestions for the active character |
| **Better negative** | Writes a tailored negative prompt |
| **Apply** | Copies the assistant output into your prompt fields |

The assistant uses whatever local model you choose — including uncensored models — with no content filtering from Local Studio.

## Quality presets

Click a preset chip above the prompt (Photorealistic, Cinematic, Portrait, Fashion, Anime, Artistic) to apply optimized steps, CFG, sampler, and prompt suffixes in one click.

## Transferring this project

Clone or copy this repository to another machine. Run `start.ps1` or `start.bat` after Python is installed.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "No backend found" | Start ComfyUI or Forge in Stability Matrix first |
| Wrong port | Settings → set ComfyUI / A1111 URL |
| Slow first image | Model loading; normal on first run |
| ComfyUI timeout | Check ComfyUI console for workflow errors; ensure a checkpoint exists |

## API (optional)

- `GET /api/backend` — connection status, models, samplers
- `POST /api/generate` — single image
- `POST /api/batch` — queue batch jobs
- `GET /api/queue` — queue status and results
- `GET /api/profiles` — list character profiles
- `POST /api/profiles` — create profile
- `PUT /api/profiles/{id}` — update profile
- `DELETE /api/profiles/{id}` — delete profile
- `GET /api/presets` — quality preset list
- `POST /api/assistant/enhance` — run local LLM prompt assistant
- `GET /api/assistant/status` — check Ollama/API connectivity
