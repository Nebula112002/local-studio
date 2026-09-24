const $ = (id) => document.getElementById(id);

const MODE_LABELS = {
  txt2img: "Generate image",
  img2img: "Transform image",
  txt2video: "Generate video",
  img2video: "Animate image",
};

const APPLIED_STORAGE_KEY = "localStudio.appliedSettings";

const state = {
  backend: null,
  polling: null,
  progressPolling: null,
  lockedSeed: null,
  galleryItems: [],
  mode: "txt2img",
  sourceImageB64: null,
  maskDirty: false,
  applied: null,
};

const els = {
  backendStatus: $("backendStatus"),
  modeTabs: $("modeTabs"),
  modelSelect: $("modelSelect"),
  videoModelSelect: $("videoModelSelect"),
  videoModelField: $("videoModelField"),
  checkpointField: $("checkpointField"),
  sourceImageSection: $("sourceImageSection"),
  sourceImageInput: $("sourceImageInput"),
  dropzone: $("dropzone"),
  dropzoneEmpty: $("dropzoneEmpty"),
  sourcePreview: $("sourcePreview"),
  sourceFrame: $("sourceFrame"),
  maskCanvas: $("maskCanvas"),
  maskTools: $("maskTools"),
  maskBrush: $("maskBrush"),
  clearMaskBtn: $("clearMaskBtn"),
  clearSourceBtn: $("clearSourceBtn"),
  similaritySection: $("similaritySection"),
  similarity: $("similarity"),
  similarityLabel: $("similarityLabel"),
  videoSection: $("videoSection"),
  frames: $("frames"),
  fps: $("fps"),
  videoDuration: $("videoDuration"),
  videoHint: $("videoHint"),
  motionBucket: $("motionBucket"),
  motionLabel: $("motionLabel"),
  batchSection: $("batchSection"),
  samplerSelect: $("samplerSelect"),
  schedulerSelect: $("schedulerSelect"),
  width: $("width"),
  height: $("height"),
  steps: $("steps"),
  cfgScale: $("cfgScale"),
  clipSkip: $("clipSkip"),
  seed: $("seed"),
  lockSeed: $("lockSeed"),
  batchSize: $("batchSize"),
  batchCount: $("batchCount"),
  seedMode: $("seedMode"),
  promptVariations: $("promptVariations"),
  variationSuffix: $("variationSuffix"),
  prompt: $("prompt"),
  negativePrompt: $("negativePrompt"),
  generateBtn: $("generateBtn"),
  batchBtn: $("batchBtn"),
  cancelBtn: $("cancelBtn"),
  gallery: $("gallery"),
  queueBar: $("queueBar"),
  queueStats: $("queueStats"),
  progressFill: $("progressFill"),
  genStatus: $("genStatus"),
  genStatusMessage: $("genStatusMessage"),
  genStatusPercent: $("genStatusPercent"),
  genProgressFill: $("genProgressFill"),
  genLog: $("genLog"),
  settingsBtn: $("settingsBtn"),
  settingsDialog: $("settingsDialog"),
  backendType: $("backendType"),
  comfyuiUrl: $("comfyuiUrl"),
  automatic1111Url: $("automatic1111Url"),
  saveToDisk: $("saveToDisk"),
  saveSettingsBtn: $("saveSettingsBtn"),
  lightbox: $("lightbox"),
  lightboxImg: $("lightboxImg"),
  lightboxVideo: $("lightboxVideo"),
  lightboxMeta: $("lightboxMeta"),
  lightboxClose: $("lightboxClose"),
  randomSeedBtn: $("randomSeedBtn"),
  applyBar: $("applyBar"),
  applySummary: $("applySummary"),
  applySettingsBtn: $("applySettingsBtn"),
};

function setStatus(connected, label) {
  els.backendStatus.classList.toggle("connected", connected);
  els.backendStatus.classList.toggle("disconnected", !connected);
  els.backendStatus.querySelector(".label").textContent = label;
}

function fillSelect(select, items, fallback = ["euler"]) {
  const current = select.value;
  const list = [...(items?.length ? items : fallback)];
  if (current && !list.includes(current)) list.unshift(current);
  select.innerHTML = "";
  for (const item of list) {
    const opt = document.createElement("option");
    opt.value = item;
    opt.textContent = item;
    select.appendChild(opt);
  }
  if (current && [...select.options].some((o) => o.value === current)) {
    select.value = current;
  }
}

function setSelectValue(select, value) {
  if (!select) return;
  const str = value == null ? "" : String(value);
  if (str && ![...select.options].some((o) => o.value === str)) {
    const opt = document.createElement("option");
    opt.value = str;
    opt.textContent = str;
    select.appendChild(opt);
  }
  select.value = str;
}

function readSidebarSettings() {
  return {
    model: els.modelSelect?.value || "",
    video_model: els.videoModelSelect?.value || "",
    sampler: els.samplerSelect?.value || "euler",
    scheduler: els.schedulerSelect?.value || "normal",
    width: Number(els.width.value) || 1024,
    height: Number(els.height.value) || 1024,
    steps: Number(els.steps.value) || 28,
    cfg_scale: Number(els.cfgScale.value) || 7,
    clip_skip: Number(els.clipSkip.value) || 1,
    seed: Number(els.seed.value),
    lock_seed: !!els.lockSeed.checked,
    batch_size: Number(els.batchSize.value) || 1,
    batch_count: Number(els.batchCount.value) || 1,
    seed_mode: els.seedMode.value || "increment",
    frames: Number(els.frames.value) || 25,
    fps: Number(els.fps.value) || 8,
    motion_bucket_id: Number(els.motionBucket.value) || 127,
    similarity: Number(els.similarity.value) || 45,
  };
}

function writeSidebarSettings(settings) {
  if (!settings) return;
  if ("model" in settings) setSelectValue(els.modelSelect, settings.model || "");
  if ("video_model" in settings) setSelectValue(els.videoModelSelect, settings.video_model || "");
  if (settings.sampler) setSelectValue(els.samplerSelect, settings.sampler);
  if (settings.scheduler) setSelectValue(els.schedulerSelect, settings.scheduler);
  if (settings.width) els.width.value = settings.width;
  if (settings.height) els.height.value = settings.height;
  if (settings.steps) els.steps.value = settings.steps;
  if (settings.cfg_scale != null) els.cfgScale.value = settings.cfg_scale;
  if (settings.clip_skip) els.clipSkip.value = settings.clip_skip;
  if (settings.seed != null) els.seed.value = settings.seed;
  if ("lock_seed" in settings) {
    els.lockSeed.checked = !!settings.lock_seed;
    state.lockedSeed = settings.lock_seed && Number(settings.seed) >= 0 ? Number(settings.seed) : null;
  }
  if (settings.batch_size) els.batchSize.value = settings.batch_size;
  if (settings.batch_count) els.batchCount.value = settings.batch_count;
  if (settings.seed_mode) els.seedMode.value = settings.seed_mode;
  if (settings.frames) els.frames.value = settings.frames;
  if (settings.fps) els.fps.value = settings.fps;
  if (settings.motion_bucket_id) {
    els.motionBucket.value = settings.motion_bucket_id;
    updateMotionLabel();
  }
  updateVideoHint();
  if (settings.similarity != null) {
    els.similarity.value = settings.similarity;
    updateSimilarityLabel();
  }
  syncSizeChips();
}

function syncSizeChips() {
  const w = String(els.width.value);
  const h = String(els.height.value);
  document.querySelectorAll("#sizePresets .chip").forEach((chip) => {
    chip.classList.toggle("active", chip.dataset.w === w && chip.dataset.h === h);
  });
}

function settingsEqual(a, b) {
  return !!a && !!b && JSON.stringify(a) === JSON.stringify(b);
}

function isSidebarDirty() {
  return !state.applied || !settingsEqual(readSidebarSettings(), state.applied);
}

function formatAppliedSummary(settings) {
  if (!settings) return "Click Apply to lock sampler, size, and steps";
  const seed = settings.lock_seed && Number(settings.seed) >= 0 ? `seed ${settings.seed}` : "random seed";
  return `${settings.sampler} · ${settings.scheduler} · ${settings.steps} steps · CFG ${settings.cfg_scale} · ${settings.width}×${settings.height} · ${seed}`;
}

function updateApplyDirty() {
  const dirty = isSidebarDirty();
  els.applyBar?.classList.toggle("dirty", dirty);
  if (els.applySummary) {
    els.applySummary.textContent = dirty
      ? "Unapplied changes — click Apply to lock them in"
      : formatAppliedSummary(state.applied);
  }
  if (els.applySettingsBtn) {
    els.applySettingsBtn.textContent = dirty ? "Apply changes" : "Applied";
  }
}

function persistAppliedLocal(settings) {
  try {
    localStorage.setItem(APPLIED_STORAGE_KEY, JSON.stringify(settings));
  } catch {}
}

function loadAppliedLocal() {
  try {
    const raw = localStorage.getItem(APPLIED_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function toApiDefaults(settings) {
  return {
    ...settings,
    model: settings.model || null,
    video_model: settings.video_model || null,
  };
}

function applySidebarSettings({ persist = true, toast = false } = {}) {
  const settings = readSidebarSettings();
  state.applied = settings;
  persistAppliedLocal(settings);
  if (persist) {
    API.post("/api/generation-defaults", toApiDefaults(settings)).catch(() => {});
  }
  updateApplyDirty();
  if (toast) {
    Toast.success(`Applied ${settings.sampler} · ${settings.steps} steps · CFG ${settings.cfg_scale}`);
  }
  return settings;
}

function commitSidebarForGenerate() {
  if (isSidebarDirty()) applySidebarSettings({ persist: true, toast: false });
  return state.applied || readSidebarSettings();
}

async function restoreAppliedSettings() {
  let saved = null;
  try {
    const remote = await API.get("/api/generation-defaults");
    if (remote?.saved) saved = remote;
  } catch {}
  if (!saved) saved = loadAppliedLocal();
  if (saved) {
    const videoModels = state.backend?.video_models || [];
    if (saved.video_model && videoModels.length && !videoModels.includes(saved.video_model)) {
      saved.video_model = "";
    }
    writeSidebarSettings(saved);
    state.applied = readSidebarSettings();
    persistAppliedLocal(state.applied);
  } else {
    state.applied = readSidebarSettings();
  }
  updateApplyDirty();
}

function similarityToDenoise(similarity) {
  return Math.max(0.02, 1 - similarity / 100);
}

function updateSimilarityLabel() {
  const value = Number(els.similarity.value);
  let text = "moderate change";
  if (value >= 75) text = "keep most of the original";
  else if (value >= 50) text = "balanced change";
  else if (value >= 25) text = "significant change";
  else text = "heavy rework";
  els.similarityLabel.textContent = `${value}% — ${text}`;
}

function updateMotionLabel() {
  const value = Number(els.motionBucket.value);
  let text = "balanced motion";
  if (value < 64) text = "subtle motion";
  else if (value >= 160) text = "high motion";
  els.motionLabel.textContent = `${value} — ${text}`;
}

function wanLength(frames) {
  const maxLen = 81;
  const n = Math.max(9, Math.min(Number(frames) || 25, maxLen));
  const count = Math.round((n - 1) / 4);
  return Math.max(9, Math.min(maxLen, count * 4 + 1));
}

function updateVideoHint() {
  const frames = Number(els.frames.value) || 25;
  const fps = Math.max(4, Math.min(Number(els.fps.value) || 16, 30));
  const length = wanLength(frames);
  const secs = (length / fps).toFixed(1);
  const w = Number(els.width.value) || 640;
  const h = Number(els.height.value) || 384;
  if (els.videoDuration) {
    els.videoDuration.textContent = `${length} frames at ${fps} fps ≈ ${secs}s`;
  }
  if (els.videoHint) {
    els.videoHint.textContent =
      `Wan 2.2 uses these controls: ${length} frames at ${fps} fps ≈ ${secs}s, ${w}×${h} (capped at 640×480 on 12GB). Motion drives how much it moves. Lightning stays 4 steps.`;
  }
}

function setMode(mode) {
  state.mode = mode;
  document.querySelectorAll(".mode-tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.mode === mode);
  });

  const needsImage = mode === "img2img" || mode === "img2video";
  const isVideo = mode === "txt2video" || mode === "img2video";

  els.sourceImageSection.hidden = !needsImage;
  els.similaritySection.hidden = mode !== "img2img";
  syncMaskTools();
  els.videoSection.hidden = !isVideo;
  els.videoModelField.classList.toggle("hidden", !isVideo);
  els.checkpointField.classList.toggle("hidden", isVideo && mode === "img2video");
  els.batchSection.hidden = isVideo;
  els.batchBtn.hidden = isVideo;

  els.generateBtn.querySelector(".btn-label").textContent = MODE_LABELS[mode] || "Generate";

  if (isVideo) {
    updateVideoHint();
    updateMotionLabel();
  }

  applyCapabilityHints();
  updateApplyDirty();
}

function applyCapabilityHints() {
  const caps = state.backend?.capabilities || ["txt2img", "img2img"];
  document.querySelectorAll(".mode-tab").forEach((tab) => {
    const supported = caps.includes(tab.dataset.mode);
    tab.classList.toggle("disabled", !supported);
    tab.title = supported ? "" : "Requires ComfyUI with a Wan 2.2 or SVD video model";
  });
}

function getPayload() {
  const profile = ProfileManager.getActive();
  let prompt = els.prompt.value.trim();
  const scene = document.getElementById("sceneInput")?.value?.trim() || "";
  const gen = commitSidebarForGenerate();

  // If character is active and prompt doesn't already include appearance, merge
  if (profile && scene && !prompt.includes(profile.hair || "___")) {
    const appearance = profile.prompt_prefix || [
      profile.age_range,
      profile.ethnicity,
      profile.hair && `${profile.hair} hair`,
      profile.eyes && `${profile.eyes} eyes`,
      profile.art_style,
    ].filter(Boolean).join(", ");
    if (appearance && !prompt.startsWith(appearance.slice(0, 20))) {
      prompt = [appearance, scene, prompt].filter(Boolean).join(", ");
    }
  }

  return {
    prompt,
    negative_prompt: els.negativePrompt.value.trim(),
    profile_id: ProfileManager.activeId || null,
    profile_name: ProfileManager.getActive()?.name || null,
    mode: state.mode,
    width: Number(gen.width),
    height: Number(gen.height),
    steps: Number(gen.steps),
    cfg_scale: Number(gen.cfg_scale),
    sampler: gen.sampler || "euler",
    scheduler: gen.scheduler || "normal",
    seed: Number(gen.seed),
    batch_size: Number(gen.batch_size),
    model: gen.model || null,
    clip_skip: Number(gen.clip_skip) || 1,
    denoise: similarityToDenoise(Number(gen.similarity)),
    init_image: state.sourceImageB64,
    mask: state.mode === "img2img" ? exportMask() : null,
    frames: Number(gen.frames),
    fps: Number(gen.fps),
    video_model: gen.video_model || null,
    motion_bucket_id: Number(gen.motion_bucket_id),
  };
}

function validateRequest() {
  const payload = getPayload();
  if (!payload.prompt && state.mode !== "img2video") {
    Toast.warn("Enter a prompt first.");
    return false;
  }
  if ((state.mode === "img2img" || state.mode === "img2video") && !payload.init_image) {
    Toast.warn("Add a source image for this mode.");
    return false;
  }
  if ((state.mode === "txt2video" || state.mode === "img2video") && state.backend) {
    if (!state.backend.capabilities?.includes(state.mode)) {
      Toast.error("Video modes need ComfyUI with a Wan 2.2 or SVD video model.");
      return false;
    }
  }
  return true;
}

function outputUrl(file) {
  return `/api/output/${String(file).split(/[\\/]/).map(encodeURIComponent).join("/")}`;
}

function imageSrc(b64, mime = "image/png") {
  return `data:${mime};base64,${b64}`;
}

function videoSrc(b64) {
  return imageSrc(b64, "video/mp4");
}

function addMediaCard({ images = [], videos = [], seeds, prompt, label, status = "completed", error, mode, filename, filenames }) {
  if (status !== "completed") {
    const card = document.createElement("article");
    card.className = `card placeholder status-${status || "running"}`;
    card.dataset.jobCard = "1";
    const title = label || (status === "queued" ? "Queued" : "Generating…");
    const sub = error || prompt || "Working…";
    card.innerHTML = `<div class="placeholder-title">${title}</div><div class="placeholder-sub">${sub}</div>`;
    els.gallery.prepend(card);
    return card;
  }

  videos.forEach((vid, index) => {
    const seed = seeds?.[index];
    const file = filenames?.[index] || filename;
    const card = document.createElement("article");
    card.className = "card";
    if (file) card.dataset.filename = file;
    card.innerHTML = `
      <video src="${typeof vid === "string" && !vid.startsWith("http") && vid.length < 400 ? `/api/output/${encodeURIComponent(vid)}` : videoSrc(vid)}" muted loop playsinline></video>
      <div class="card-body">
        <div><strong>Video</strong> · Seed ${seed ?? "?"}</div>
        <div class="truncate">${prompt || file || ""}</div>
      </div>
      <div class="card-actions">
        <button class="btn ghost" type="button" data-action="download">Download</button>
        <button class="btn ghost" type="button" data-action="reuse">Reuse seed</button>
        ${file ? '<button class="btn ghost danger" type="button" data-action="delete">Delete</button>' : ""}
      </div>
    `;
    const video = card.querySelector("video");
    const srcIsFile = file && (!vid || String(vid).endsWith(".mp4") || String(vid) === file);
    if (srcIsFile) {
      video.src = outputUrl(file);
    }
    video.addEventListener("click", () => {
      if (srcIsFile) window.open(outputUrl(file), "_blank");
      else openLightbox(null, vid, seed, prompt, true);
    });
    video.addEventListener("mouseenter", () => video.play().catch(() => {}));
    video.addEventListener("mouseleave", () => { video.pause(); video.currentTime = 0; });
    card.querySelector('[data-action="download"]').addEventListener("click", () => {
      if (file) window.open(outputUrl(file), "_blank");
      else downloadVideo(vid, seed);
    });
    card.querySelector('[data-action="reuse"]').addEventListener("click", () => reuseSeed(seed));
    card.querySelector('[data-action="delete"]')?.addEventListener("click", () => deleteOutputFile(file, card));
    els.gallery.prepend(card);
  });

  images.forEach((img, index) => {
    const seed = seeds?.[index];
    const file = filenames?.[index] || filename;
    const isFileRef = file && (!img || String(img).endsWith(".png") || String(img).endsWith(".jpg") || String(img) === file);
    const card = document.createElement("article");
    card.className = "card";
    if (file) card.dataset.filename = file;
    const imgSrc = isFileRef
      ? outputUrl(file)
      : imageSrc(img);
    card.innerHTML = `
      <img src="${imgSrc}" alt="Generated image" />
      <div class="card-body">
        <div><strong>${mode === "img2img" ? "Img2Img" : "Image"}</strong> · Seed ${seed ?? "?"}</div>
        <div class="truncate">${prompt || file || ""}</div>
      </div>
      <div class="card-actions">
        <button class="btn ghost" type="button" data-action="download">Download</button>
        <button class="btn ghost" type="button" data-action="reuse">Reuse seed</button>
        <button class="btn ghost" type="button" data-action="animate">→ Video</button>
        <button class="btn ghost" type="button" data-action="set-ref" title="Save as character reference">Ref</button>
        <button class="btn ghost" type="button" data-action="set-thumb" title="Set character thumbnail">Thumb</button>
        ${file ? '<button class="btn ghost danger" type="button" data-action="delete">Delete</button>' : ""}
      </div>
    `;
    card.querySelector("img").addEventListener("click", () => {
      if (isFileRef) window.open(imgSrc, "_blank");
      else openLightbox(img, null, seed, prompt, false);
    });
    card.querySelector('[data-action="download"]').addEventListener("click", () => {
      if (file) {
        const a = document.createElement("a");
        a.href = outputUrl(file);
        a.download = file;
        a.click();
      } else downloadImage(img, seed);
    });
    card.querySelector('[data-action="reuse"]').addEventListener("click", () => reuseSeed(seed));
    card.querySelector('[data-action="animate"]').addEventListener("click", async () => {
      if (isFileRef) {
        // fetch as blob -> b64 for img2video source
        try {
          const res = await fetch(outputUrl(file));
          const blob = await res.blob();
          const b64 = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(String(reader.result).split(",")[1]);
            reader.onerror = reject;
            reader.readAsDataURL(blob);
          });
          useAsVideoSource(b64);
        } catch (err) {
          Toast.error(err.message || "Could not load image");
        }
      } else useAsVideoSource(img);
    });
    card.querySelector('[data-action="set-ref"]')?.addEventListener("click", async () => {
      if (isFileRef) {
        try {
          const res = await fetch(outputUrl(file));
          const blob = await res.blob();
          const b64 = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(String(reader.result).split(",")[1]);
            reader.onerror = reject;
            reader.readAsDataURL(blob);
          });
          ProfileManager.setReferenceFromImage(b64);
        } catch (err) {
          Toast.error(err.message || "Could not load image");
        }
      } else ProfileManager.setReferenceFromImage(img);
    });
    card.querySelector('[data-action="set-thumb"]')?.addEventListener("click", async () => {
      if (isFileRef) {
        try {
          const res = await fetch(outputUrl(file));
          const blob = await res.blob();
          const b64 = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(String(reader.result).split(",")[1]);
            reader.onerror = reject;
            reader.readAsDataURL(blob);
          });
          ProfileManager.setThumbnailFromImage(b64);
        } catch (err) {
          Toast.error(err.message || "Could not load image");
        }
      } else ProfileManager.setThumbnailFromImage(img);
    });
    card.querySelector('[data-action="delete"]')?.addEventListener("click", () => deleteOutputFile(file, card));
    els.gallery.prepend(card);
  });
}

async function deleteOutputFile(filename, cardEl) {
  if (!filename) return;
  try {
    const result = await API.del(outputUrl(filename));
    cardEl?.remove();
    const n = result.files_removed ?? 1;
    Toast.success(n ? `Deleted ${filename}` : "Deleted");
    HistoryPanel.load();
  } catch (err) {
    Toast.error(err.message || "Delete failed");
  }
}

async function loadGalleryFromDisk() {
  try {
    const files = await API.get("/api/output");
    if (!Array.isArray(files) || !files.length) return;
    // Render oldest→newest so prepend leaves newest on top
    for (const f of [...files].reverse().slice(-24)) {
      const isVideo = f.media_type === "video";
      addMediaCard({
        images: isVideo ? [] : [f.filename],
        videos: isVideo ? [f.filename] : [],
        filenames: [f.filename],
        filename: f.filename,
        prompt: f.filename,
        mode: isVideo ? "img2video" : "txt2img",
      });
    }
  } catch {}
}

function reuseSeed(seed) {
  els.seed.value = seed;
  els.lockSeed.checked = true;
  state.lockedSeed = seed;
}

function useAsVideoSource(imgB64) {
  setSourceImage(imgB64);
  const tab = document.querySelector('.mode-tab[data-mode="img2video"]');
  if (tab) tab.click();
}

function openLightbox(img, vid, seed, prompt, isVideo) {
  els.lightboxImg.hidden = isVideo;
  els.lightboxVideo.hidden = !isVideo;
  if (isVideo) {
    els.lightboxVideo.src = videoSrc(vid);
    els.lightboxVideo.load();
  } else {
    els.lightboxImg.src = imageSrc(img);
  }
  els.lightboxMeta.textContent = `Seed ${seed ?? "?"} — ${prompt || ""}`;
  els.lightbox.showModal();
}

function downloadImage(b64, seed) {
  const a = document.createElement("a");
  a.href = imageSrc(b64);
  a.download = `local_studio_${seed ?? Date.now()}.png`;
  a.click();
}

function downloadVideo(b64, seed) {
  const a = document.createElement("a");
  a.href = videoSrc(b64);
  a.download = `local_studio_${seed ?? Date.now()}.mp4`;
  a.click();
}

function setBusy(busy) {
  els.generateBtn.disabled = busy;
  els.batchBtn.disabled = busy;
  const label = MODE_LABELS[state.mode] || "Generate";
  els.generateBtn.querySelector(".btn-label").textContent = busy ? "Working…" : label;
}

async function refreshBackend() {
  try {
    const info = await API.get("/api/backend");
    if (!info.connected) {
      setStatus(false, info.error || "No backend");
      state.backend = null;
      return;
    }
    setStatus(true, info.name || "Connected");
    const draft = readSidebarSettings();
    fillSelect(els.modelSelect, ["", ...info.models]);
    els.modelSelect.querySelector("option").textContent = "(auto / default)";
    fillSelect(els.videoModelSelect, ["", ...(info.video_models || [])]);
    if (els.videoModelSelect.querySelector("option")) {
      els.videoModelSelect.querySelector("option").textContent = "(auto)";
    }
    fillSelect(els.samplerSelect, info.samplers, ["euler", "dpmpp_2m", "ddim"]);
    fillSelect(els.schedulerSelect, info.schedulers, ["normal", "karras"]);
    if (draft.video_model && !(info.video_models || []).includes(draft.video_model)) {
      draft.video_model = "";
    }
    writeSidebarSettings(draft);
    state.backend = info;
    applyCapabilityHints();
  } catch {
    setStatus(false, "Studio offline");
  }
}

function readFileAsB64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      resolve(result.split(",")[1]);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function setSourceImage(b64) {
  state.sourceImageB64 = b64;
  state.maskDirty = false;
  els.sourcePreview.src = imageSrc(b64);
  els.sourcePreview.hidden = false;
  els.sourceFrame.hidden = false;
  els.dropzoneEmpty.hidden = true;
  els.clearSourceBtn.hidden = false;
  els.sourcePreview.onload = () => {
    fitMaskCanvas(true);
    syncMaskTools();
  };
  syncMaskTools();
}

function clearSourceImage() {
  state.sourceImageB64 = null;
  state.maskDirty = false;
  els.sourcePreview.hidden = true;
  els.sourcePreview.src = "";
  els.sourceFrame.hidden = true;
  els.dropzoneEmpty.hidden = false;
  els.clearSourceBtn.hidden = true;
  els.sourceImageInput.value = "";
  clearMask();
  syncMaskTools();
}

function syncMaskTools() {
  const show = state.mode === "img2img" && !!state.sourceImageB64;
  if (els.maskTools) els.maskTools.hidden = !show;
  if (els.maskCanvas) els.maskCanvas.hidden = !show;
}

function fitMaskCanvas(reset) {
  const img = els.sourcePreview;
  const canvas = els.maskCanvas;
  if (!img || !canvas || !img.naturalWidth) return;
  if (reset || canvas.width !== img.naturalWidth || canvas.height !== img.naturalHeight) {
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    state.maskDirty = false;
  }
}

function clearMask() {
  const canvas = els.maskCanvas;
  if (!canvas) return;
  canvas.getContext("2d").clearRect(0, 0, canvas.width, canvas.height);
  state.maskDirty = false;
}

function maskPoint(event) {
  const canvas = els.maskCanvas;
  const rect = canvas.getBoundingClientRect();
  return {
    x: (event.clientX - rect.left) * (canvas.width / rect.width),
    y: (event.clientY - rect.top) * (canvas.height / rect.height),
  };
}

const maskPaint = { drawing: false, last: null };

function paintMaskStroke(point) {
  const canvas = els.maskCanvas;
  const ctx = canvas.getContext("2d");
  const rect = canvas.getBoundingClientRect();
  const scale = canvas.width / Math.max(rect.width, 1);
  const size = Math.max(4, Number(els.maskBrush.value) || 36) * scale;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.strokeStyle = "rgba(255, 90, 130, 0.55)";
  ctx.fillStyle = "rgba(255, 90, 130, 0.55)";
  ctx.lineWidth = size;
  if (!maskPaint.last) {
    ctx.beginPath();
    ctx.arc(point.x, point.y, size / 2, 0, Math.PI * 2);
    ctx.fill();
  } else {
    ctx.beginPath();
    ctx.moveTo(maskPaint.last.x, maskPaint.last.y);
    ctx.lineTo(point.x, point.y);
    ctx.stroke();
  }
  maskPaint.last = point;
  state.maskDirty = true;
}

function exportMask() {
  const canvas = els.maskCanvas;
  if (!canvas || canvas.hidden || !state.maskDirty || !canvas.width) return null;
  const ctx = canvas.getContext("2d");
  const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const out = document.createElement("canvas");
  out.width = canvas.width;
  out.height = canvas.height;
  const outCtx = out.getContext("2d");
  const copy = outCtx.createImageData(out.width, out.height);
  let painted = false;
  for (let i = 0; i < pixels.data.length; i += 4) {
    const on = pixels.data[i + 3] > 12;
    const value = on ? 255 : 0;
    if (on) painted = true;
    copy.data[i] = value;
    copy.data[i + 1] = value;
    copy.data[i + 2] = value;
    copy.data[i + 3] = 255;
  }
  if (!painted) return null;
  outCtx.putImageData(copy, 0, 0);
  return out.toDataURL("image/png").split(",")[1];
}

function bindMaskPaint() {
  const canvas = els.maskCanvas;
  if (!canvas) return;
  canvas.addEventListener("pointerdown", (event) => {
    if (canvas.hidden) return;
    event.preventDefault();
    event.stopPropagation();
    canvas.setPointerCapture(event.pointerId);
    maskPaint.drawing = true;
    maskPaint.last = null;
    paintMaskStroke(maskPoint(event));
  });
  canvas.addEventListener("pointermove", (event) => {
    if (!maskPaint.drawing) return;
    event.preventDefault();
    paintMaskStroke(maskPoint(event));
  });
  const endStroke = () => {
    maskPaint.drawing = false;
    maskPaint.last = null;
  };
  canvas.addEventListener("pointerup", endStroke);
  canvas.addEventListener("pointercancel", endStroke);
  els.clearMaskBtn?.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    clearMask();
  });
}

function populateAssistantModels(status, configuredModel) {
  const select = $("assistantModel");
  if (!select) return;
  const models = status?.models || [];
  const current = configuredModel || select.value || "qwen2.5:3b";
  if (!models.length) {
    select.innerHTML = `<option value="${current}">${current}</option>`;
    select.value = current;
    return;
  }
  select.innerHTML = "";
  for (const name of models) {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    select.appendChild(opt);
  }
  const pick = status?.effective_model || current;
  select.value = [...select.options].some((o) => o.value === pick) ? pick : current;
}

async function loadSettings() {
  const settings = await API.get("/api/settings");
  els.backendType.value = settings.backend_type;
  els.comfyuiUrl.value = settings.comfyui_url;
  els.automatic1111Url.value = settings.automatic1111_url;
  els.saveToDisk.checked = settings.save_to_disk;
  if ($("assistantEnabled")) $("assistantEnabled").checked = settings.assistant_enabled !== false;
  if ($("assistantProvider")) $("assistantProvider").value = settings.assistant_provider || "ollama";
  if ($("assistantUrl")) $("assistantUrl").value = settings.assistant_url || "http://127.0.0.1:11434";
  if ($("assistantApiKey")) $("assistantApiKey").value = settings.assistant_api_key || "";
  if ($("assistantTemperature")) $("assistantTemperature").value = settings.assistant_temperature ?? 0.8;
  const status = await PromptAssistant.checkStatus();
  populateAssistantModels(status, settings.assistant_model || "qwen2.5:3b");
}

async function saveSettings(e) {
  e.preventDefault();
  await API.post("/api/settings", {
    backend_type: els.backendType.value,
    comfyui_url: els.comfyuiUrl.value,
    automatic1111_url: els.automatic1111Url.value,
    save_to_disk: els.saveToDisk.checked,
    assistant_enabled: $("assistantEnabled")?.checked ?? true,
    assistant_provider: $("assistantProvider")?.value || "ollama",
    assistant_url: $("assistantUrl")?.value || "http://127.0.0.1:11434",
    assistant_model: $("assistantModel")?.value || "qwen2.5:3b",
    assistant_api_key: $("assistantApiKey")?.value || "",
    assistant_temperature: Number($("assistantTemperature")?.value) || 0.8,
  });
  els.settingsDialog.close();
  await refreshBackend();
  await ComfyUIStatus.refresh();
  await PromptAssistant.checkStatus();
}

function showGenStatus(show) {
  els.genStatus.hidden = !show;
}

function updateGenStatusUI(data) {
  const percent = Math.round(data.percent ?? 0);
  els.genStatusMessage.textContent = data.message || "Working…";
  els.genStatusPercent.textContent = `${percent}%`;
  els.genProgressFill.style.width = `${percent}%`;
  if (data.log?.length) {
    els.genLog.textContent = data.log.join("\n");
    els.genLog.scrollTop = els.genLog.scrollHeight;
  }
}

async function pollProgress() {
  try {
    updateGenStatusUI(await API.get("/api/progress"));
  } catch {}
}

function startProgressPolling() {
  showGenStatus(true);
  els.genLog.textContent = "";
  els.genProgressFill.style.width = "0%";
  els.genStatusPercent.textContent = "0%";
  if (state.progressPolling) return;
  state.progressPolling = setInterval(pollProgress, 600);
  pollProgress();
}

function stopProgressPolling(finalMessage) {
  if (state.progressPolling) {
    clearInterval(state.progressPolling);
    state.progressPolling = null;
  }
  pollProgress().finally(() => {
    if (finalMessage) {
      els.genStatusMessage.textContent = finalMessage;
      els.genStatusPercent.textContent = "100%";
      els.genProgressFill.style.width = "100%";
    }
    setTimeout(() => showGenStatus(false), finalMessage ? 2000 : 0);
  });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function showCompletedResult(result, payload) {
  const files = result.metadata?.files || result.files || [];
  addMediaCard({
    images: result.images || [],
    videos: result.videos || [],
    seeds: result.seeds,
    prompt: payload.prompt,
    mode: payload.mode,
    filenames: files,
  });
  const isVideo = (result.videos && result.videos.length) || files.some((f) => String(f).endsWith(".mp4"));
  Toast.success(`${isVideo ? "Video" : "Image"} generated`);
  HistoryPanel.load();
}

async function recoverLatestOutput(payload, startedAt) {
  const deadline = Date.now() + 8 * 60 * 1000;
  while (Date.now() < deadline) {
    try {
      const progress = await API.get("/api/progress");
      updateGenStatusUI(progress);
      if (!progress.active) {
        const hist = await API.get("/api/history?limit=8");
        const item = (hist.items || []).find((entry) => {
          const files = entry.files || [];
          if (!files.length) return false;
          if (entry.mode && payload.mode && entry.mode !== payload.mode) return false;
          const ts = Date.parse(entry.timestamp || entry.created_at || "") || 0;
          return !ts || ts >= startedAt - 5000;
        });
        if (item) {
          return {
            images: (item.files || []).filter((f) => !String(f).endsWith(".mp4")),
            videos: (item.files || []).filter((f) => String(f).endsWith(".mp4")),
            seeds: item.seeds || [],
            metadata: { files: item.files || [] },
          };
        }
        const files = await API.get("/api/output");
        const latest = (files || []).find((f) => {
          const name = f.filename || f.name || "";
          const modified = Date.parse(f.modified || "") || 0;
          const isVideo = payload.mode?.includes("video") ? name.endsWith(".mp4") : true;
          return isVideo && (!modified || modified >= startedAt - 5000);
        });
        if (latest?.filename) {
          const name = latest.filename;
          return {
            images: name.endsWith(".mp4") ? [] : [name],
            videos: name.endsWith(".mp4") ? [name] : [],
            seeds: [],
            metadata: { files: [name] },
          };
        }
        return null;
      }
    } catch {}
    await sleep(1500);
  }
  return null;
}

async function generateOnce() {
  if (!validateRequest()) return;
  setBusy(true);
  startProgressPolling();
  const payload = getPayload();
  const startedAt = Date.now();
  try {
    const result = await API.post("/api/generate", payload);
    stopProgressPolling("Generation complete");
    showCompletedResult(result, payload);
    if (!els.lockSeed.checked) {
      els.seed.value = -1;
    } else if (result.seeds?.length) {
      els.seed.value = result.seeds[0];
      state.lockedSeed = result.seeds[0];
    }
    if (state.applied) {
      state.applied.seed = Number(els.seed.value);
      state.applied.lock_seed = els.lockSeed.checked;
      persistAppliedLocal(state.applied);
    }
    updateApplyDirty();
  } catch (err) {
    const recovered = await recoverLatestOutput(payload, startedAt);
    if (recovered) {
      stopProgressPolling("Generation complete");
      showCompletedResult(recovered, payload);
    } else {
      stopProgressPolling();
      showGenStatus(false);
      Toast.error(err.message || String(err));
    }
  } finally {
    setBusy(false);
  }
}

async function queueBatch() {
  if (!validateRequest()) return;
  setBusy(true);
  try {
    const payload = {
      ...getPayload(),
      batch_count: Number(els.batchCount.value),
      seed_mode: els.seedMode.value,
      prompt_variations: els.promptVariations.value
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean),
      use_variation_suffix: els.variationSuffix.checked,
    };
    await API.post("/api/batch", payload);
    els.queueBar.hidden = false;
    els.cancelBtn.hidden = false;
    startQueuePolling();
    Toast.info(`Queued ${payload.batch_count} batch job(s)`);
  } catch (err) {
    Toast.error(err.message || String(err));
  } finally {
    setBusy(false);
  }
}

function updateQueueUI(data) {
  const { status, jobs } = data;
  const done = status.completed + status.failed;
  const total = status.total || 1;
  els.queueStats.textContent = `Queue: ${status.running ? "running" : "idle"} — ${done}/${total} done — ${status.queued} waiting`;
  els.progressFill.style.width = `${Math.round((done / total) * 100)}%`;

  document.querySelectorAll("[data-job-card]").forEach((el) => el.remove());

  for (const job of jobs.filter((j) => j.status === "running" || j.status === "queued").slice(0, 3)) {
    addMediaCard({ label: job.label, status: job.status, error: job.error, prompt: job.prompt });
  }

  for (const job of jobs.filter((j) => j.status === "completed" && j.images?.length)) {
    const key = `done-${job.id}`;
    if (document.querySelector(`[data-done="${key}"]`)) continue;
    addMediaCard({
      images: job.images,
      seeds: job.seeds,
      prompt: job.prompt,
      mode: job.mode,
    });
  }

  if (status.queued === 0 && status.running === 0 && status.total > 0) {
    els.cancelBtn.hidden = true;
  }
}

async function pollQueue() {
  try {
    updateQueueUI(await API.get("/api/queue"));
  } catch {}
}

function startQueuePolling() {
  if (state.polling) return;
  state.polling = setInterval(pollQueue, 1200);
  pollQueue();
}

async function cancelQueue() {
  await API.post("/api/queue/cancel", {});
  await API.post("/api/queue/clear", {});
  els.cancelBtn.hidden = true;
}

function bindPresets() {
  document.querySelectorAll("#sizePresets .chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      document.querySelectorAll("#sizePresets .chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      els.width.value = chip.dataset.w;
      els.height.value = chip.dataset.h;
      updateVideoHint();
      updateApplyDirty();
    });
  });
}

function bindSourceImage() {
  els.dropzone.addEventListener("click", (event) => {
    if (event.target.closest("#sourceFrame")) return;
    els.sourceImageInput.click();
  });
  els.clearSourceBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    clearSourceImage();
  });
  els.sourceImageInput.addEventListener("change", async () => {
    const file = els.sourceImageInput.files?.[0];
    if (file) setSourceImage(await readFileAsB64(file));
  });
  els.dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    els.dropzone.classList.add("dragover");
  });
  els.dropzone.addEventListener("dragleave", () => els.dropzone.classList.remove("dragover"));
  els.dropzone.addEventListener("drop", async (e) => {
    e.preventDefault();
    els.dropzone.classList.remove("dragover");
    const file = e.dataTransfer.files?.[0];
    if (file?.type.startsWith("image/")) {
      setSourceImage(await readFileAsB64(file));
    }
  });
}

function bindEvents() {
  document.querySelectorAll(".mode-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      if (tab.classList.contains("disabled")) {
        Toast.warn("This mode needs ComfyUI with a Wan 2.2 or SVD video model.");
        return;
      }
      setMode(tab.dataset.mode);
    });
  });

  els.similarity.addEventListener("input", () => {
    updateSimilarityLabel();
    updateApplyDirty();
  });
  els.motionBucket.addEventListener("input", () => {
    updateMotionLabel();
    updateApplyDirty();
  });
  els.frames.addEventListener("input", () => {
    updateVideoHint();
    updateApplyDirty();
  });
  els.fps.addEventListener("input", () => {
    updateVideoHint();
    updateApplyDirty();
  });
  els.width.addEventListener("input", () => {
    updateVideoHint();
    updateApplyDirty();
  });
  els.height.addEventListener("input", () => {
    updateVideoHint();
    updateApplyDirty();
  });
  els.generateBtn.addEventListener("click", generateOnce);
  els.batchBtn.addEventListener("click", queueBatch);
  els.cancelBtn.addEventListener("click", cancelQueue);
  els.settingsBtn.addEventListener("click", () => els.settingsDialog.showModal());
  els.saveSettingsBtn.addEventListener("click", saveSettings);
  els.applySettingsBtn?.addEventListener("click", () => {
    applySidebarSettings({ persist: true, toast: true });
  });
  document.querySelector(".settings-scroll")?.addEventListener("input", updateApplyDirty);
  document.querySelector(".settings-scroll")?.addEventListener("change", updateApplyDirty);
  els.randomSeedBtn.addEventListener("click", () => {
    els.seed.value = Math.floor(Math.random() * 2 ** 32);
    updateApplyDirty();
  });
  els.lightboxClose.addEventListener("click", () => els.lightbox.close());
  els.lightbox.addEventListener("click", (e) => {
    if (e.target === els.lightbox) els.lightbox.close();
  });

  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      if (!els.generateBtn.disabled) generateOnce();
    }
  });
}

async function init() {
  Toast.init();
  bindPresets();
  bindSourceImage();
  bindMaskPaint();
  bindEvents();
  ProfileManager.bindEvents();
  HistoryPanel.bindEvents();
  PromptAssistant.bindEvents();
  QualityPresets.bindEvents();
  updateSimilarityLabel();
  updateMotionLabel();
  updateVideoHint();
  setMode("txt2img");
  await loadSettings();
  ComfyUIStatus.init();
  await AccessLinks.init();
  await refreshBackend();
  await restoreAppliedSettings();
  await ProfileManager.load();
  await QualityPresets.load();
  await VideoPresets.load();
  await SocialPresets.load();
  await PromptAssistant.checkStatus();
  await HistoryPanel.load();
  await loadGalleryFromDisk();
  setInterval(refreshBackend, 15000);
  setInterval(() => PromptAssistant.checkStatus(), 30000);
}

init();
