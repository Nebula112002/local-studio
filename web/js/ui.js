/** Toast notification system */

const Toast = {
  container: null,

  init() {
    if (this.container) return;
    this.container = document.createElement("div");
    this.container.id = "toastContainer";
    this.container.className = "toast-container";
    document.body.appendChild(this.container);
  },

  show(message, type = "info", duration = 4000) {
    this.init();
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    this.container.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add("show"));
    setTimeout(() => {
      toast.classList.remove("show");
      setTimeout(() => toast.remove(), 300);
    }, duration);
  },

  success(msg) { this.show(msg, "success"); },
  error(msg) { this.show(msg, "error", 6000); },
  info(msg) { this.show(msg, "info"); },
  warn(msg) { this.show(msg, "warn", 5000); },
};

/** ComfyUI connectivity banner — polls /api/image-lab, never auto-starts ComfyUI */

const ComfyUIStatus = {
  data: null,
  polling: null,

  MESSAGES: {
    offline:
      "Launch from Stability Matrix → Packages → ComfyUI → Launch",
    ready:
      "Ready — open Image Lab for chat editing, or generate below",
    port_busy:
      "Port in use but not responding yet. Wait, then Reload.",
  },

  init() {
    const reloadBtn = document.getElementById("comfyuiReloadBtn");
    const smBtn = document.getElementById("comfyuiOpenSmBtn");
    reloadBtn?.addEventListener("click", () => this.refresh());
    smBtn?.addEventListener("click", () => this.openStabilityMatrix());
    this.refresh();
    this.polling = setInterval(() => this.refresh(), 8000);
  },

  async refresh() {
    const reloadBtn = document.getElementById("comfyuiReloadBtn");
    if (reloadBtn) reloadBtn.disabled = true;
    try {
      this.data = await API.get("/api/image-lab");
      this.render();
    } catch {
      this.renderError();
    } finally {
      if (reloadBtn) reloadBtn.disabled = false;
    }
  },

  async openStabilityMatrix() {
    const smBtn = document.getElementById("comfyuiOpenSmBtn");
    if (smBtn) smBtn.disabled = true;
    try {
      const result = await API.post("/api/image-lab/launch", {});
      Toast.info(result.note || "Opened Stability Matrix");
      setTimeout(() => this.refresh(), 2000);
    } catch (err) {
      Toast.error(err.message || "Could not open Stability Matrix");
    } finally {
      if (smBtn) smBtn.disabled = false;
    }
  },

  renderError() {
    const banner = document.getElementById("comfyuiBanner");
    if (!banner) return;
    banner.className = "comfyui-banner comfyui-offline";
    document.getElementById("comfyuiTitle").textContent = "Studio unreachable";
    document.getElementById("comfyuiMessage").textContent =
      "Could not reach Local Studio API.";
    const hint = document.getElementById("comfyuiHint");
    hint.hidden = true;
    document.getElementById("comfyuiOpenBtn")?.classList.add("hidden");
  },

  render() {
    const banner = document.getElementById("comfyuiBanner");
    if (!banner || !this.data) return;

    const status = this.data.comfyui_status || "offline";
    const title = document.getElementById("comfyuiTitle");
    const message = document.getElementById("comfyuiMessage");
    const hint = document.getElementById("comfyuiHint");
    const openBtn = document.getElementById("comfyuiOpenBtn");

    const compact = status === "ready";
    banner.className = `comfyui-banner comfyui-${status}${compact ? " comfyui-compact" : ""}`;

    if (status === "ready") {
      title.textContent = "ComfyUI ready";
      message.textContent = this.MESSAGES.ready;
      hint.hidden = true;
      if (openBtn) {
        openBtn.classList.remove("hidden");
        openBtn.href = this.data.embed_url || "/proxy/comfyui/";
        openBtn.title = this.data.comfyui_direct_url || this.MESSAGES.ready;
      }
    } else if (status === "port_busy") {
      title.textContent = "ComfyUI starting…";
      message.textContent = this.data.comfyui_message || this.MESSAGES.port_busy;
      hint.hidden = false;
      hint.textContent =
        this.data.comfyui_hint || "Check Settings → ComfyUI URL if this persists.";
      openBtn?.classList.add("hidden");
    } else {
      title.textContent = "ComfyUI offline";
      message.textContent = this.MESSAGES.offline;
      hint.hidden = false;
      hint.textContent =
        this.data.comfyui_hint ||
        "Local Studio does not auto-start ComfyUI — launch it when you need to generate.";
      openBtn?.classList.add("hidden");
    }
  },
};

/** Access links (empty state + health metadata) */

const AccessLinks = {
  localUrl: "http://127.0.0.1:8787",

  async init() {
    try {
      const health = await API.get("/api/health");
      this.localUrl = health.local || health.links?.local || this.localUrl;
      this.render(health);
    } catch {
      this.render({ local: this.localUrl, tailnet: null });
    }
  },

  render(health) {
    const local = health.local || health.links?.local || this.localUrl;
    const tailnet = health.tailnet || health.links?.tailnet;

    const mobile = document.getElementById("mobileLinks");
    if (mobile) {
      mobile.innerHTML = `Studio: <a href="${local}">${local}</a>${tailnet ? ` · <a href="${tailnet}">Tailnet</a>` : ""}`;
    }
  },
};

/** Generation history panel */

const HistoryPanel = {
  items: [],

  async load() {
    try {
      const data = await API.get("/api/history?limit=30");
      this.items = data.items || [];
      const countEl = document.getElementById("historyCount");
      if (countEl) countEl.textContent = data.total ? `(${data.total})` : "";
      this.render();
    } catch {}
  },

  render() {
    const panel = document.getElementById("historyPanel");
    if (!panel) return;

    if (!this.items.length) {
      panel.innerHTML = '<p class="hint">No generation history yet. Your prompts and seeds are saved here automatically.</p>';
      return;
    }

    panel.innerHTML = this.items.map((item) => `
      <div class="history-item" data-id="${item.id}">
        <div class="history-meta">
          <span class="history-mode">${item.mode}</span>
          <span class="history-seed">Seed ${item.seeds?.[0] ?? "?"}</span>
          ${item.profile_name ? `<span class="history-profile">${item.profile_name}</span>` : ""}
        </div>
        <div class="history-prompt">${item.prompt}</div>
        <div class="history-actions">
          <button class="btn ghost tiny" type="button" data-action="reuse" data-id="${item.id}">Reuse</button>
          <button class="btn ghost tiny" type="button" data-action="delete" data-id="${item.id}">Delete</button>
        </div>
      </div>
    `).join("");

    panel.querySelectorAll('[data-action="reuse"]').forEach((btn) => {
      btn.addEventListener("click", () => this.reuse(btn.dataset.id));
    });
    panel.querySelectorAll('[data-action="delete"]').forEach((btn) => {
      btn.addEventListener("click", () => this.remove(btn.dataset.id));
    });
  },

  reuse(id) {
    const item = this.items.find((i) => i.id === id);
    if (!item) return;
    document.getElementById("prompt").value = item.prompt;
    document.getElementById("negativePrompt").value = item.negative_prompt || "";
    if (item.seeds?.[0]) document.getElementById("seed").value = item.seeds[0];
    if (item.width) document.getElementById("width").value = item.width;
    if (item.height) document.getElementById("height").value = item.height;
    if (item.steps) document.getElementById("steps").value = item.steps;
    if (item.cfg_scale) document.getElementById("cfgScale").value = item.cfg_scale;
    Toast.success("Loaded from history");
  },

  async remove(id) {
    await API.del(`/api/history/${id}`);
    Toast.info("Removed from history");
    await this.load();
  },
};

/** Video presets */

const VideoPresets = {
  presets: [],

  async load() {
    try {
      const data = await API.get("/api/presets");
      this.presets = data.video || [];
      this.render();
    } catch {}
  },

  render() {
    const row = document.getElementById("videoPresets");
    if (!row) return;
    row.innerHTML = "";
    for (const p of this.presets) {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "chip";
      chip.textContent = p.label;
      chip.title = `Frames: ${p.frames}, FPS: ${p.fps}, Motion: ${p.motion_bucket_id}`;
      chip.addEventListener("click", () => this.apply(p));
      row.appendChild(chip);
    }
  },

  apply(preset) {
    if (preset.frames) document.getElementById("frames").value = preset.frames;
    if (preset.fps) document.getElementById("fps").value = preset.fps;
    if (preset.motion_bucket_id) {
      document.getElementById("motionBucket").value = preset.motion_bucket_id;
      document.getElementById("motionBucket").dispatchEvent(new Event("input"));
    }
    if (preset.steps) document.getElementById("steps").value = preset.steps;
    if (preset.cfg_scale) document.getElementById("cfgScale").value = preset.cfg_scale;
    if (preset.width) document.getElementById("width").value = preset.width;
    if (preset.height) document.getElementById("height").value = preset.height;
    Toast.success(`Applied: ${preset.label}`);
  },
};

/** Social / platform size presets */

const SocialPresets = {
  presets: [],

  async load() {
    try {
      const data = await API.get("/api/presets");
      this.presets = data.social || [];
      this.render();
    } catch {}
  },

  render() {
    const row = document.getElementById("socialPresets");
    if (!row) return;
    row.innerHTML = "";
    for (const p of this.presets) {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "chip social-chip";
      chip.textContent = p.label;
      chip.title = p.description || `${p.width}×${p.height}`;
      chip.addEventListener("click", () => this.apply(p));
      row.appendChild(chip);
    }
  },

  apply(preset) {
    if (preset.width) document.getElementById("width").value = preset.width;
    if (preset.height) document.getElementById("height").value = preset.height;
    if (preset.steps) document.getElementById("steps").value = preset.steps;
    if (preset.cfg_scale) document.getElementById("cfgScale").value = preset.cfg_scale;
    document.querySelectorAll("#sizePresets .chip").forEach((c) => c.classList.remove("active"));
    Toast.success(`${preset.label}: ${preset.width}×${preset.height}`);
  },
};
