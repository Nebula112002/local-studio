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

/** Access links bar */

const AccessLinks = {
  async init() {
    try {
      const health = await API.get("/api/health");
      this.render(health);
    } catch {
      this.render({ local: "http://127.0.0.1:8787", tailnet: null });
    }
  },

  render(health) {
    const bar = document.getElementById("accessBar");
    if (!bar) return;

    const local = health.local || health.links?.local || "http://127.0.0.1:8787";
    const tailnet = health.tailnet || health.links?.tailnet;

    bar.innerHTML = `
      <div class="access-links">
        <span class="access-label">Open Local Studio:</span>
        <a href="${local}" target="_blank" class="access-link local">${local}</a>
        <button class="btn ghost tiny copy-btn" data-copy="${local}" type="button">Copy</button>
        ${tailnet ? `
          <span class="access-sep">·</span>
          <a href="${tailnet}" target="_blank" class="access-link tailnet" title="Remote access via Tailscale">${tailnet}</a>
          <button class="btn ghost tiny copy-btn" data-copy="${tailnet}" type="button">Copy</button>
        ` : ""}
      </div>
      <div class="access-meta">
        <span class="version-badge">v${health.version || "2.0"}</span>
      </div>
    `;

    bar.querySelectorAll(".copy-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        navigator.clipboard.writeText(btn.dataset.copy).then(() => {
          Toast.success("Link copied!");
        }).catch(() => Toast.error("Could not copy"));
      });
    });

    const mobile = document.getElementById("mobileLinks");
    if (mobile) {
      mobile.innerHTML = `Open: <a href="${local}">${local}</a>${tailnet ? ` · <a href="${tailnet}">Tailnet</a>` : ""}`;
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
