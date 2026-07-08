/** Local LLM prompt assistant (Ollama / OpenAI-compatible) */

const PromptAssistant = {
  status: null,
  busy: false,

  async checkStatus() {
    try {
      this.status = await API.get("/api/assistant/status");
    } catch {
      this.status = { available: false, reason: "Could not reach assistant API" };
    }
    this.renderStatus();
    return this.status;
  },

  renderStatus() {
    const pill = document.getElementById("assistantStatus");
    if (!pill) return;
    const dot = pill.querySelector(".dot");
    const label = pill.querySelector(".label");

    if (this.status?.available) {
      pill.classList.add("connected");
      pill.classList.remove("disconnected");
      const modelOk = this.status.model_installed !== false;
      label.textContent = modelOk
        ? `LLM: ${this.status.configured_model}`
        : `LLM online — pull ${this.status.configured_model}`;
      dot.style.background = modelOk ? "var(--accent)" : "var(--warning)";
    } else {
      pill.classList.add("disconnected");
      pill.classList.remove("connected");
      label.textContent = this.status?.reason || "LLM offline";
    }
  },

  setBusy(busy) {
    this.busy = busy;
    document.querySelectorAll(".assistant-btn").forEach((btn) => {
      btn.disabled = busy;
    });
  },

  async run(mode, extra = {}) {
    if (this.busy) return;
    this.setBusy(true);
    const output = document.getElementById("assistantOutput");
    output.hidden = false;
    output.textContent = "Thinking…";

    const prompt = document.getElementById("prompt").value.trim();
    const scene = document.getElementById("sceneInput")?.value?.trim() || "";
    const characterContext = ProfileManager.getCharacterContext();

    try {
      const result = await API.post("/api/assistant/enhance", {
        prompt,
        mode,
        character_context: characterContext,
        scene_hint: scene || extra.scene_hint || "",
        style: document.getElementById("qualityPreset")?.dataset?.active || "",
        ...extra,
      });

      if (mode === "scenes" && result.scenes?.length) {
        output.innerHTML = result.scenes
          .map((s) => `<button type="button" class="scene-chip" data-scene="${s.replace(/"/g, "&quot;")}">${s}</button>`)
          .join("");
        output.querySelectorAll(".scene-chip").forEach((chip) => {
          chip.addEventListener("click", () => {
            const sceneText = chip.dataset.scene;
            document.getElementById("sceneInput").value = sceneText;
            if (ProfileManager.activeId) {
              ProfileManager.applyPrompt(
                ProfileManager.getActive()?.prompt_prefix || "",
                sceneText
              );
            } else {
              document.getElementById("prompt").value = sceneText;
            }
          });
        });

        // Save scenes to active profile scene ideas
        if (ProfileManager.activeId) {
          const profile = ProfileManager.getActive();
          const merged = [...new Set([...(profile.scene_ideas || []), ...result.scenes])];
          API.put(`/api/profiles/${profile.id}`, { ...profile, scene_ideas: merged }).then(() => {
            ProfileManager.load();
          }).catch(() => {});
        }
      } else {
        output.textContent = result.result;
      }
    } catch (err) {
      output.textContent = `Error: ${err.message}`;
    } finally {
      this.setBusy(false);
    }
  },

  applyResult() {
    const output = document.getElementById("assistantOutput");
    const text = output.textContent?.trim();
    if (!text || text.startsWith("Error:") || text === "Thinking…") return;

    const mode = output.dataset.lastMode;
    if (mode === "negative") {
      document.getElementById("negativePrompt").value = text;
    } else {
      const scene = document.getElementById("sceneInput")?.value?.trim();
      if (ProfileManager.activeId && scene) {
        const prefix = ProfileManager.getActive()?.prompt_prefix || "";
        ProfileManager.applyPrompt(prefix ? `${prefix}, ${text}` : text, scene);
      } else {
        document.getElementById("prompt").value = text;
      }
    }
  },

  bindEvents() {
    document.getElementById("enhancePromptBtn")?.addEventListener("click", () => {
      document.getElementById("assistantOutput").dataset.lastMode = "enhance";
      this.run("enhance");
    });
    document.getElementById("generateScenesBtn")?.addEventListener("click", () => {
      document.getElementById("assistantOutput").dataset.lastMode = "scenes";
      this.run("scenes");
    });
    document.getElementById("generateNegativeBtn")?.addEventListener("click", () => {
      document.getElementById("assistantOutput").dataset.lastMode = "negative";
      this.run("negative");
    });
    document.getElementById("applyAssistantBtn")?.addEventListener("click", () => this.applyResult());
    document.getElementById("clearAssistantBtn")?.addEventListener("click", () => {
      const output = document.getElementById("assistantOutput");
      output.hidden = true;
      output.textContent = "";
    });
  },
};

/** Quality presets */

const QualityPresets = {
  presets: [],
  activeId: null,

  async load() {
    const data = await API.get("/api/presets");
    this.presets = data.image || data;
    this.render();
  },

  render() {
    const row = document.getElementById("qualityPresets");
    if (!row) return;
    row.innerHTML = "";
    for (const p of this.presets) {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = `chip${p.id === this.activeId ? " active" : ""}`;
      chip.textContent = p.label;
      chip.title = p.description;
      chip.dataset.id = p.id;
      chip.addEventListener("click", () => this.apply(p.id));
      row.appendChild(chip);
    }
  },

  async apply(id) {
    const preset = this.presets.find((p) => p.id === id) || await API.get(`/api/presets/${id}`);
    this.activeId = id;
    document.getElementById("qualityPreset").dataset.active = id;
    this.render();

    if (preset.steps) document.getElementById("steps").value = preset.steps;
    if (preset.cfg_scale) document.getElementById("cfgScale").value = preset.cfg_scale;
    if (preset.clip_skip) document.getElementById("clipSkip").value = preset.clip_skip;
    if (preset.width) document.getElementById("width").value = preset.width;
    if (preset.height) document.getElementById("height").value = preset.height;

    if (preset.sampler) {
      const s = document.getElementById("samplerSelect");
      if (s && [...s.options].some((o) => o.value === preset.sampler)) s.value = preset.sampler;
    }
    if (preset.scheduler) {
      const s = document.getElementById("schedulerSelect");
      if (s && [...s.options].some((o) => o.value === preset.scheduler)) s.value = preset.scheduler;
    }

    // Append suffix to prompt if not already present
    if (preset.prompt_suffix) {
      const promptEl = document.getElementById("prompt");
      const current = promptEl.value.trim();
      if (!current.includes(preset.prompt_suffix.split(",")[0])) {
        promptEl.value = current ? `${current}, ${preset.prompt_suffix}` : preset.prompt_suffix;
      }
    }

    if (preset.negative_prompt) {
      document.getElementById("negativePrompt").value = preset.negative_prompt;
    }
  },

  bindEvents() {},
};
