const $ = (id) => document.getElementById(id);

const MODE_LABELS = {
  txt2img: "Generate image",
  img2img: "Transform image",
  txt2video: "Generate video",
  img2video: "Animate image",
};

const state = {
  backend: null,
  polling: null,
  progressPolling: null,
  lockedSeed: null,
  galleryItems: [],
  mode: "txt2img",
  sourceImageB64: null,
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
  clearSourceBtn: $("clearSourceBtn"),
  similaritySection: $("similaritySection"),
  similarity: $("similarity"),
  similarityLabel: $("similarityLabel"),
  videoSection: $("videoSection"),
  frames: $("frames"),
  fps: $("fps"),
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
  emptyState: $("emptyState"),
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
};

function setStatus(connected, label) {
  els.backendStatus.classList.toggle("connected", connected);
  els.backendStatus.classList.toggle("disconnected", !connected);
  els.backendStatus.querySelector(".label").textContent = label;
}

function fillSelect(select, items, fallback = ["euler"]) {
  select.innerHTML = "";
  const list = items?.length ? items : fallback;
  for (const item of list) {
    const opt = document.createElement("option");
    opt.value = item;
    opt.textContent = item;
    select.appendChild(opt);
  }
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
  else if (value > 180) text = "high motion";
  els.motionLabel.textContent = `${value} — ${text}`;
}

function setMode(mode) {
  state.mode = mode;
  document.querySelectorAll(".mode-tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.mode === mode);
  });

  const needsImage = mode === "img2img" || mode === "img2video";
  const needsSimilarity = needsImage;
  const isVideo = mode === "txt2video" || mode === "img2video";

  els.sourceImageSection.hidden = !needsImage;
  els.similaritySection.hidden = !needsSimilarity;
  els.videoSection.hidden = !isVideo;
  els.videoModelField.classList.toggle("hidden", !isVideo);
  els.checkpointField.classList.toggle("hidden", isVideo && mode === "img2video");
  els.batchSection.hidden = isVideo;
  els.batchBtn.hidden = isVideo;

  els.generateBtn.querySelector(".btn-label").textContent = MODE_LABELS[mode] || "Generate";

  if (isVideo) {
    if (Number(els.width.value) === 1024 && Number(els.height.value) === 1024) {
      els.width.value = 1024;
      els.height.value = 576;
    }
    els.cfgScale.value = Math.min(Number(els.cfgScale.value), 4);
  }

  applyCapabilityHints();
}

function applyCapabilityHints() {
  const caps = state.backend?.capabilities || ["txt2img", "img2img"];
  document.querySelectorAll(".mode-tab").forEach((tab) => {
    const supported = caps.includes(tab.dataset.mode);
    tab.classList.toggle("disabled", !supported);
    tab.title = supported ? "" : "Requires ComfyUI with SVD for video modes";
  });
}

function getPayload() {
  const profile = ProfileManager.getActive();
  let prompt = els.prompt.value.trim();
  const scene = document.getElementById("sceneInput")?.value?.trim() || "";

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
    width: Number(els.width.value),
    height: Number(els.height.value),
    steps: Number(els.steps.value),
    cfg_scale: Number(els.cfgScale.value),
    sampler: els.samplerSelect.value,
    scheduler: els.schedulerSelect.value,
    seed: Number(els.seed.value),
    batch_size: Number(els.batchSize.value),
    model: els.modelSelect.value || null,
    clip_skip: Number(els.clipSkip.value),
    denoise: similarityToDenoise(Number(els.similarity.value)),
    init_image: state.sourceImageB64,
    frames: Number(els.frames.value),
    fps: Number(els.fps.value),
    video_model: els.videoModelSelect.value || null,
    motion_bucket_id: Number(els.motionBucket.value),
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
      Toast.error("Video modes need ComfyUI with an SVD model (e.g. svd_xt).");
      return false;
    }
  }
  return true;
}

function imageSrc(b64, mime = "image/png") {
  return `data:${mime};base64,${b64}`;
}

function videoSrc(b64) {
  return imageSrc(b64, "video/mp4");
}

function hideEmpty() {
  if (els.emptyState) els.emptyState.style.display = "none";
}

function addMediaCard({ images = [], videos = [], seeds, prompt, label, status = "completed", error, mode }) {
  hideEmpty();

  if (status !== "completed") {
    const card = document.createElement("article");
    card.className = `card placeholder status-${status}`;
    card.dataset.jobCard = "1";
    card.innerHTML = `<div>${label || status}</div><div>${error || "Working…"}</div>`;
    els.gallery.prepend(card);
    return card;
  }

  videos.forEach((vid, index) => {
    const seed = seeds?.[index];
    const card = document.createElement("article");
    card.className = "card";
    card.innerHTML = `
      <video src="${videoSrc(vid)}" muted loop playsinline></video>
      <div class="card-body">
        <div><strong>Video</strong> · Seed ${seed ?? "?"}</div>
        <div class="truncate">${prompt || ""}</div>
      </div>
      <div class="card-actions">
        <button class="btn ghost" type="button" data-action="download">Download MP4</button>
        <button class="btn ghost" type="button" data-action="reuse">Reuse seed</button>
      </div>
    `;
    const video = card.querySelector("video");
    video.addEventListener("click", () => openLightbox(null, vid, seed, prompt, true));
    video.addEventListener("mouseenter", () => video.play());
    video.addEventListener("mouseleave", () => { video.pause(); video.currentTime = 0; });
    card.querySelector('[data-action="download"]').addEventListener("click", () => downloadVideo(vid, seed));
    card.querySelector('[data-action="reuse"]').addEventListener("click", () => reuseSeed(seed));
    els.gallery.prepend(card);
  });

  images.forEach((img, index) => {
    const seed = seeds?.[index];
    const card = document.createElement("article");
    card.className = "card";
    card.innerHTML = `
      <img src="${imageSrc(img)}" alt="Generated image" />
      <div class="card-body">
        <div><strong>${mode === "img2img" ? "Img2Img" : "Image"}</strong> · Seed ${seed ?? "?"}</div>
        <div class="truncate">${prompt || ""}</div>
      </div>
      <div class="card-actions">
        <button class="btn ghost" type="button" data-action="download">Download</button>
        <button class="btn ghost" type="button" data-action="reuse">Reuse seed</button>
        <button class="btn ghost" type="button" data-action="animate">→ Video</button>
      </div>
    `;
    card.querySelector("img").addEventListener("click", () => openLightbox(img, null, seed, prompt, false));
    card.querySelector('[data-action="download"]').addEventListener("click", () => downloadImage(img, seed));
    card.querySelector('[data-action="reuse"]').addEventListener("click", () => reuseSeed(seed));
    card.querySelector('[data-action="animate"]').addEventListener("click", () => useAsVideoSource(img));
    els.gallery.prepend(card);
  });
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
    const caps = info.capabilities || ["txt2img"];
    setStatus(true, `${info.name} — ${caps.join(", ")}`);
    fillSelect(els.modelSelect, ["", ...info.models]);
    els.modelSelect.querySelector("option").textContent = "(auto / default)";
    fillSelect(els.videoModelSelect, ["", ...(info.video_models || [])]);
    if (els.videoModelSelect.querySelector("option")) {
      els.videoModelSelect.querySelector("option").textContent = "(auto)";
    }
    fillSelect(els.samplerSelect, info.samplers, ["euler", "dpmpp_2m", "ddim"]);
    fillSelect(els.schedulerSelect, info.schedulers, ["normal", "karras"]);
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
  els.sourcePreview.src = imageSrc(b64);
  els.sourcePreview.hidden = false;
  els.dropzoneEmpty.hidden = true;
  els.clearSourceBtn.hidden = false;
}

function clearSourceImage() {
  state.sourceImageB64 = null;
  els.sourcePreview.hidden = true;
  els.sourcePreview.src = "";
  els.dropzoneEmpty.hidden = false;
  els.clearSourceBtn.hidden = true;
  els.sourceImageInput.value = "";
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
  if ($("assistantModel")) $("assistantModel").value = settings.assistant_model || "llama3.2";
  if ($("assistantApiKey")) $("assistantApiKey").value = settings.assistant_api_key || "";
  if ($("assistantTemperature")) $("assistantTemperature").value = settings.assistant_temperature ?? 0.8;
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
    assistant_model: $("assistantModel")?.value || "llama3.2",
    assistant_api_key: $("assistantApiKey")?.value || "",
    assistant_temperature: Number($("assistantTemperature")?.value) || 0.8,
  });
  els.settingsDialog.close();
  await refreshBackend();
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

async function generateOnce() {
  if (!validateRequest()) return;
  setBusy(true);
  startProgressPolling();
  try {
    const payload = getPayload();
    const result = await API.post("/api/generate", payload);
    stopProgressPolling("Generation complete");
    addMediaCard({
      images: result.images,
      videos: result.videos,
      seeds: result.seeds,
      prompt: payload.prompt,
      mode: payload.mode,
    });
    Toast.success(`${result.videos?.length ? "Video" : "Image"} generated`);
    HistoryPanel.load();
    if (!els.lockSeed.checked) {
      els.seed.value = -1;
    } else if (result.seeds?.length) {
      els.seed.value = result.seeds[0];
      state.lockedSeed = result.seeds[0];
    }
  } catch (err) {
    stopProgressPolling();
    showGenStatus(false);
    Toast.error(err.message || String(err));
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
    });
  });
}

function bindSourceImage() {
  els.dropzone.addEventListener("click", () => els.sourceImageInput.click());
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
        Toast.warn("This mode needs ComfyUI with an SVD video model.");
        return;
      }
      setMode(tab.dataset.mode);
    });
  });

  els.similarity.addEventListener("input", updateSimilarityLabel);
  els.motionBucket.addEventListener("input", updateMotionLabel);
  els.generateBtn.addEventListener("click", generateOnce);
  els.batchBtn.addEventListener("click", queueBatch);
  els.cancelBtn.addEventListener("click", cancelQueue);
  els.settingsBtn.addEventListener("click", () => els.settingsDialog.showModal());
  els.saveSettingsBtn.addEventListener("click", saveSettings);
  els.randomSeedBtn.addEventListener("click", () => {
    els.seed.value = Math.floor(Math.random() * 2 ** 32);
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
  bindEvents();
  ProfileManager.bindEvents();
  PromptAssistant.bindEvents();
  QualityPresets.bindEvents();
  updateSimilarityLabel();
  updateMotionLabel();
  setMode("txt2img");
  await loadSettings();
  await AccessLinks.init();
  await refreshBackend();
  await ProfileManager.load();
  await QualityPresets.load();
  await VideoPresets.load();
  await PromptAssistant.checkStatus();
  await HistoryPanel.load();
  setInterval(refreshBackend, 15000);
  setInterval(() => PromptAssistant.checkStatus(), 30000);
}

init();
