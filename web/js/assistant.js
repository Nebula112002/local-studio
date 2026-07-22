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

      const model = this.status.effective_model || this.status.configured_model;

      const modelOk = this.status.model_installed !== false;

      label.textContent = modelOk

        ? `LLM: ${model}`

        : `LLM: ${model} (auto)`;

      dot.style.background = modelOk ? "var(--accent)" : "var(--warning)";

      if (typeof populateAssistantModels === "function") {

        populateAssistantModels(this.status, model);

      }

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



  flashField(el) {

    if (!el) return;

    el.classList.remove("field-applied");

    void el.offsetWidth;

    el.classList.add("field-applied");

    el.addEventListener("animationend", () => el.classList.remove("field-applied"), { once: true });

  },



  parseResultOptions(text, mode) {

    const trimmed = (text || "").trim();

    if (!trimmed) return [];



    const stripLabel = (s) => s.replace(/^(?:positive|enhanced|prompt|option\s*\d*)[:\s-]*/i, "").trim();

    const defaultTarget = mode === "negative" ? "negative" : "prompt";



    // Positive + negative in one response (e.g. "Enhanced: …\nNegative: …")

    const negMatch = trimmed.match(

      /^([\s\S]*?)\n\s*(?:negative(?:\s*prompt)?|neg):\s*([\s\S]+)$/i

    );

    if (negMatch && mode === "enhance") {

      const options = [];

      const positive = stripLabel(negMatch[1].replace(/^(?:positive|enhanced)(?:\s*prompt)?:\s*/i, "").trim());

      const negative = negMatch[2].trim();

      if (positive) options.push({ label: "Enhanced prompt", text: positive, target: "prompt" });

      if (negative) options.push({ label: "Enhanced negative", text: negative, target: "negative" });

      if (options.length) return options;

    }



    // Numbered or bulleted variations

    const lines = trimmed.split("\n").map((l) => l.trim()).filter(Boolean);

    const listPattern = /^(?:\d+[\.\)]\s*|[-*•]\s*|Option\s+[A-Z\d]+:\s*)/i;

    const listItems = lines.filter((l) => listPattern.test(l));

    if (listItems.length >= 2) {

      return listItems.map((line, i) => ({

        label: `Variation ${i + 1}`,

        text: line.replace(listPattern, "").trim(),

        target: defaultTarget,

      }));

    }



    // Blank-line separated blocks

    const blocks = trimmed.split(/\n\s*\n/).map((b) => stripLabel(b.trim())).filter(Boolean);

    if (blocks.length >= 2 && blocks.every((b) => b.length > 15)) {

      return blocks.map((block, i) => ({

        label: `Option ${i + 1}`,

        text: block,

        target: defaultTarget,

      }));

    }



    // Single result

    const label = mode === "negative"

      ? "Negative prompt"

      : mode === "enhance"

        ? "Enhanced prompt"

        : "Result";

    return [{ label, text: stripLabel(trimmed), target: defaultTarget }];

  },



  applyToPrompt(text) {

    const scene = document.getElementById("sceneInput")?.value?.trim();

    const promptEl = document.getElementById("prompt");

    if (ProfileManager.activeId && scene) {

      const prefix = ProfileManager.getActive()?.prompt_prefix || "";

      ProfileManager.applyPrompt(prefix ? `${prefix}, ${text}` : text, scene);

    } else {

      promptEl.value = text;

    }

    this.flashField(promptEl);

  },



  applyToNegative(text) {

    const el = document.getElementById("negativePrompt");

    el.value = text;

    this.flashField(el);

  },



  applyToScene(text) {

    const sceneEl = document.getElementById("sceneInput");

    sceneEl.value = text;

    if (ProfileManager.activeId) {

      ProfileManager.applyPrompt(ProfileManager.getActive()?.prompt_prefix || "", text);

      this.flashField(document.getElementById("prompt"));

    } else {

      this.flashField(sceneEl);

    }

  },



  applyOption(option) {

    if (!option?.text) return;

    if (option.target === "negative") {

      this.applyToNegative(option.text);

    } else if (option.target === "scene") {

      this.applyToScene(option.text);

    } else {

      this.applyToPrompt(option.text);

    }

  },



  createApplyButton(label, option) {

    const btn = document.createElement("button");

    btn.type = "button";

    btn.className = "btn ghost small assistant-btn";

    btn.textContent = label;

    btn.addEventListener("click", () => this.applyOption(option));

    return btn;

  },



  renderOptions(options, mode) {

    const output = document.getElementById("assistantOutput");

    output.hidden = false;

    output.classList.remove("assistant-output--plain");

    output.innerHTML = "";



    const container = document.createElement("div");

    container.className = "assistant-options";



    for (const option of options) {

      const card = document.createElement("div");

      card.className = "assistant-option";



      const label = document.createElement("div");

      label.className = "assistant-option-label";

      label.textContent = option.label;



      const text = document.createElement("div");

      text.className = "assistant-option-text";

      text.textContent = option.text;



      const actions = document.createElement("div");

      actions.className = "assistant-option-actions";



      if (mode === "scenes") {

        actions.appendChild(this.createApplyButton("Use as scene", { ...option, target: "scene" }));

        actions.appendChild(this.createApplyButton("Use in prompt", { ...option, target: "prompt" }));

      } else if (option.target === "negative") {

        actions.appendChild(this.createApplyButton("Use in negative", option));

      } else {

        actions.appendChild(this.createApplyButton("Use in prompt", option));

      }



      card.append(label, text, actions);

      container.appendChild(card);

    }



    output.appendChild(container);

  },



  renderPlain(text) {

    const output = document.getElementById("assistantOutput");

    output.hidden = false;

    output.classList.add("assistant-output--plain");

    output.textContent = text;

  },



  async run(mode, extra = {}) {

    if (this.busy) return;

    this.setBusy(true);

    this.renderPlain("Thinking…");



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

        const options = result.scenes.map((s, i) => ({

          label: `Scene ${i + 1}`,

          text: s,

          target: "scene",

        }));

        this.renderOptions(options, "scenes");



        if (ProfileManager.activeId) {

          const profile = ProfileManager.getActive();

          const merged = [...new Set([...(profile.scene_ideas || []), ...result.scenes])];

          API.put(`/api/profiles/${profile.id}`, { ...profile, scene_ideas: merged }).then(() => {

            ProfileManager.load();

          }).catch(() => {});

        }

      } else if (result.result) {

        const options = this.parseResultOptions(result.result, mode);

        this.renderOptions(options, mode);

      } else {

        this.renderPlain("No result returned.");

      }

    } catch (err) {

      this.renderPlain(`Error: ${err.message}`);

    } finally {

      this.setBusy(false);

    }

  },



  bindEvents() {

    document.getElementById("enhancePromptBtn")?.addEventListener("click", () => this.run("enhance"));

    document.getElementById("generateScenesBtn")?.addEventListener("click", () => this.run("scenes"));

    document.getElementById("generateNegativeBtn")?.addEventListener("click", () => this.run("negative"));

    document.getElementById("clearAssistantBtn")?.addEventListener("click", () => {

      const output = document.getElementById("assistantOutput");

      output.hidden = true;

      output.textContent = "";

      output.classList.remove("assistant-output--plain");

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


