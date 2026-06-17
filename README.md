# Local Studio

A self-contained, **100% local** image generation UI. No cloud APIs, no prompt filtering, no account required. It talks directly to whatever Stable Diffusion backend you run on your machine ??? typically **ComfyUI** or **Forge / Automatic1111** launched through **Stability Matrix**.

## Quick start

1. **Start your SD backend** in Stability Matrix:
   - ComfyUI ??? usually `http://127.0.0.1:8188`
   - Forge / A1111 ??? usually `http://127.0.0.1:7860`

2. **Launch Local Studio** (from this folder):

   ```powershell
   .\start.ps1
   ```

   Or double-click `start.bat`.

3. Open **http://127.0.0.1:8787** in your browser.

The UI auto-detects which backend is running. Use **Settings** to force a specific backend or change URLs.

## Modes

| Mode | Backend | What it does |
|------|---------|--------------|
| **Text ??? Image** | ComfyUI or Forge | Standard prompt-to-image |
| **Image ??? Image** | ComfyUI or Forge | Upload a source image; use **Similarity** to control how much stays the same |
| **Text ??? Video** | ComfyUI + SVD | Generates a still frame from your prompt, then animates it |
| **Image ??? Video** | ComfyUI + SVD | Animates your uploaded image into a short clip |

### Similarity slider (image modes)

Higher similarity = output stays closer to your source image. Lower = more creative change. This maps to denoising strength under the hood.

### Video setup (Stability Matrix)

1. Launch **ComfyUI** (not Forge) for video modes
2. Download an **SVD** model (e.g. `svd_xt` or `svd_xt_1_1`) in Stability Matrix
3. In Local Studio Settings, set backend to **ComfyUI** (or auto-detect)

## Features

- **Single generate** ??? one click with full control over steps, CFG, sampler, scheduler, size, seed, model
- **Batch queue** ??? run many generations with:
  - Batch count (1???100)
  - Images per pass (batch size)
  - Seed modes: increment, fixed, or random per batch
  - Prompt variations (one per line, appended or standalone)
- **Gallery** ??? preview, lightbox, download, reuse seed
- **Auto-save** ??? PNGs written to `output/` (toggle in Settings)
- **Uncensored** ??? prompts pass through unchanged to your local model

## Requirements

- Python 3.10+
- A local Stable Diffusion install (ComfyUI or A1111/Forge)
- A checkpoint model in your backend's `models` folder

## Folder layout

```
Local-Studio/
  start.ps1 / start.bat   # launch scripts
  requirements.txt
  server/                 # FastAPI backend + queue
  web/                    # frontend UI
  output/                 # saved images (created on first run)
```

## Stability Matrix tips

1. Open Stability Matrix and launch **ComfyUI** or **SD WebUI Forge**.
2. Wait until the backend shows as running (green).
3. Then start Local Studio.
4. Pick your checkpoint in the left panel once connected.

For uncensored results, use an uncensored checkpoint in Stability Matrix (e.g. realistic or anime models without safety filters). Local Studio does not add any safety layer.

## Transferring this project

Clone or copy this repository to another machine. Run `start.ps1` or `start.bat` after Python is installed.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "No backend found" | Start ComfyUI or Forge in Stability Matrix first |
| Wrong port | Settings ??? set ComfyUI / A1111 URL |
| Slow first image | Model loading; normal on first run |
| ComfyUI timeout | Check ComfyUI console for workflow errors; ensure a checkpoint exists |

## API (optional)

- `GET /api/backend` ??? connection status, models, samplers
- `POST /api/generate` ??? single image
- `POST /api/batch` ??? queue batch jobs
- `GET /api/queue` ??? queue status and results
