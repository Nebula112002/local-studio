/** Character profile management */

const ProfileManager = {
  profiles: [],
  activeId: null,

  async load() {
    this.profiles = await API.get("/api/profiles");
    this.renderList();
    this.renderSelector();
    return this.profiles;
  },

  getActive() {
    return this.profiles.find((p) => p.id === this.activeId) || null;
  },

  renderSelector() {
    const sel = document.getElementById("profileSelect");
    if (!sel) return;
    const prev = sel.value;
    sel.innerHTML = '<option value="">No character selected</option>';
    for (const p of this.profiles) {
      const opt = document.createElement("option");
      opt.value = p.id;
      opt.textContent = p.name || `Character ${p.id}`;
      sel.appendChild(opt);
    }
    if (prev && this.profiles.some((p) => p.id === prev)) {
      sel.value = prev;
      this.activeId = prev;
    }
  },

  renderList() {
    const list = document.getElementById("profileList");
    if (!list) return;
    list.innerHTML = "";

    if (!this.profiles.length) {
      list.innerHTML = '<p class="hint">No characters yet. Create one to keep consistent looks across generations.</p>';
      return;
    }

    for (const p of this.profiles) {
      const item = document.createElement("div");
      item.className = `profile-item${p.id === this.activeId ? " active" : ""}`;
      const thumb = p.thumbnail
        ? `<img class="profile-thumb" src="data:image/png;base64,${p.thumbnail}" alt="" />`
        : `<div class="profile-thumb placeholder">${(p.name || "?")[0].toUpperCase()}</div>`;
      item.innerHTML = `
        ${thumb}
        <div class="profile-info">
          <strong>${p.name || "Unnamed"}</strong>
          <span>${p.art_style || "—"} · ${p.hair || "no hair set"}</span>
        </div>
        <div class="profile-item-actions">
          <button class="btn ghost small" type="button" data-action="use">Use</button>
          <button class="btn ghost small" type="button" data-action="edit">Edit</button>
        </div>
      `;
      item.querySelector('[data-action="use"]').addEventListener("click", () => this.select(p.id));
      item.querySelector('[data-action="edit"]').addEventListener("click", () => this.openEditor(p.id));
      list.appendChild(item);
    }
  },

  async select(id) {
    this.activeId = id || null;
    const sel = document.getElementById("profileSelect");
    if (sel) sel.value = id || "";
    this.renderList();

    if (!id) return;
    const defaults = await API.get(`/api/profiles/${id}/defaults`);
    if (defaults.negative_prompt) {
      document.getElementById("negativePrompt").value = defaults.negative_prompt;
    }
    if (defaults.model) {
      const modelSel = document.getElementById("modelSelect");
      if (modelSel && [...modelSel.options].some((o) => o.value === defaults.model)) {
        modelSel.value = defaults.model;
      }
    }
    if (defaults.seed >= 0) document.getElementById("seed").value = defaults.seed;
    if (defaults.width) document.getElementById("width").value = defaults.width;
    if (defaults.height) document.getElementById("height").value = defaults.height;
    if (defaults.steps) document.getElementById("steps").value = defaults.steps;
    if (defaults.cfg_scale) document.getElementById("cfgScale").value = defaults.cfg_scale;
    if (defaults.clip_skip) document.getElementById("clipSkip").value = defaults.clip_skip;
    if (defaults.sampler) {
      const s = document.getElementById("samplerSelect");
      if (s && [...s.options].some((o) => o.value === defaults.sampler)) s.value = defaults.sampler;
    }
    if (defaults.scheduler) {
      const s = document.getElementById("schedulerSelect");
      if (s && [...s.options].some((o) => o.value === defaults.scheduler)) s.value = defaults.scheduler;
    }

    const scene = document.getElementById("sceneInput")?.value?.trim();
    const prefix = defaults.prompt_prefix || "";
    if (prefix) {
      this.applyPrompt(prefix, scene);
    }
  },

  applyPrompt(prefix, scene = "") {
    const promptEl = document.getElementById("prompt");
    const parts = [prefix, scene].filter(Boolean);
    promptEl.value = parts.join(", ");
  },

  buildAppearancePreview(data) {
    const traits = [];
    if (data.age_range) traits.push(data.age_range);
    if (data.ethnicity) traits.push(data.ethnicity);
    if (data.hair) traits.push(`${data.hair} hair`);
    if (data.eyes) traits.push(`${data.eyes} eyes`);
    if (data.skin_tone) traits.push(`${data.skin_tone} skin`);
    if (data.body_type) traits.push(data.body_type);
    if (data.distinctive_features) traits.push(data.distinctive_features);
    if (data.default_outfit) traits.push(`wearing ${data.default_outfit}`);
    const parts = [data.prompt_prefix, traits.join(", "), data.art_style].filter(Boolean);
    return parts.join(", ");
  },

  buildProfileFromForm() {
    const sceneIdeas = document.getElementById("profileSceneIdeas").value
      .split("\n").map((l) => l.trim()).filter(Boolean);
    const tags = document.getElementById("profileTags").value
      .split(",").map((t) => t.trim()).filter(Boolean);
    return {
      id: document.getElementById("profileId").value || undefined,
      name: document.getElementById("profileName").value.trim(),
      hair: document.getElementById("profileHair").value.trim(),
      eyes: document.getElementById("profileEyes").value.trim(),
      skin_tone: document.getElementById("profileSkin").value.trim(),
      body_type: document.getElementById("profileBody").value.trim(),
      age_range: document.getElementById("profileAge").value.trim() || "young adult",
      ethnicity: document.getElementById("profileEthnicity").value.trim(),
      distinctive_features: document.getElementById("profileFeatures").value.trim(),
      art_style: document.getElementById("profileStyle").value.trim() || "photorealistic",
      default_outfit: document.getElementById("profileOutfit").value.trim(),
      personality_vibe: document.getElementById("profileVibe").value.trim(),
      prompt_prefix: document.getElementById("profilePrefix").value.trim(),
      negative_prompt: document.getElementById("profileNegative").value.trim(),
      preferred_seed: Number(document.getElementById("profileSeed").value),
      preferred_width: Number(document.getElementById("profileWidth").value) || 1024,
      preferred_height: Number(document.getElementById("profileHeight").value) || 1024,
      preferred_steps: Number(document.getElementById("profileSteps").value) || 30,
      preferred_cfg: Number(document.getElementById("profileCfg").value) || 7,
      scene_ideas: sceneIdeas,
      tags,
      notes: document.getElementById("profileNotes").value.trim(),
    };
  },

  fillEditor(profile) {
    document.getElementById("profileId").value = profile?.id || "";
    document.getElementById("profileName").value = profile?.name || "";
    document.getElementById("profileHair").value = profile?.hair || "";
    document.getElementById("profileEyes").value = profile?.eyes || "";
    document.getElementById("profileSkin").value = profile?.skin_tone || "";
    document.getElementById("profileBody").value = profile?.body_type || "";
    document.getElementById("profileAge").value = profile?.age_range || "young adult";
    document.getElementById("profileEthnicity").value = profile?.ethnicity || "";
    document.getElementById("profileFeatures").value = profile?.distinctive_features || "";
    document.getElementById("profileStyle").value = profile?.art_style || "photorealistic";
    document.getElementById("profileOutfit").value = profile?.default_outfit || "";
    document.getElementById("profileVibe").value = profile?.personality_vibe || "";
    document.getElementById("profilePrefix").value = profile?.prompt_prefix || "";
    document.getElementById("profileNegative").value = profile?.negative_prompt || "";
    document.getElementById("profileSeed").value = profile?.preferred_seed ?? -1;
    document.getElementById("profileWidth").value = profile?.preferred_width || 1024;
    document.getElementById("profileHeight").value = profile?.preferred_height || 1024;
    document.getElementById("profileSteps").value = profile?.preferred_steps || 30;
    document.getElementById("profileCfg").value = profile?.preferred_cfg || 7;
    document.getElementById("profileSceneIdeas").value = (profile?.scene_ideas || []).join("\n");
    document.getElementById("profileTags").value = (profile?.tags || []).join(", ");
    document.getElementById("profileNotes").value = profile?.notes || "";
    document.getElementById("profileEditorTitle").textContent = profile ? `Edit: ${profile.name}` : "New Character";
    document.getElementById("deleteProfileBtn").hidden = !profile;
    this.updatePreviewPrompt(profile);
  },

  updatePreviewPrompt(profile) {
    const preview = document.getElementById("profilePromptPreview");
    if (!preview) return;
    const data = profile || this.buildProfileFromForm();
    preview.textContent = this.buildAppearancePreview(data) || "(fill in traits above)";
  },

  openEditor(id = null) {
    const profile = id ? this.profiles.find((p) => p.id === id) : null;
    this.fillEditor(profile);
    document.getElementById("profileEditorDialog").showModal();
  },

  async save() {
    const data = this.buildProfileFromForm();
    const id = data.id;
    delete data.id;

    if (id) {
      await API.put(`/api/profiles/${id}`, { ...data, id });
    } else {
      await API.post("/api/profiles", data);
    }
    document.getElementById("profileEditorDialog").close();
    await this.load();
  },

  async remove() {
    const id = document.getElementById("profileId").value;
    if (!id || !confirm("Delete this character profile?")) return;
    await API.del(`/api/profiles/${id}`);
    if (this.activeId === id) this.activeId = null;
    document.getElementById("profileEditorDialog").close();
    await this.load();
  },

  getCharacterContext() {
    const p = this.getActive();
    if (!p) return "";
    const lines = [
      `Name: ${p.name}`,
      p.hair && `Hair: ${p.hair}`,
      p.eyes && `Eyes: ${p.eyes}`,
      p.skin_tone && `Skin: ${p.skin_tone}`,
      p.body_type && `Body: ${p.body_type}`,
      p.age_range && `Age: ${p.age_range}`,
      p.ethnicity && `Ethnicity: ${p.ethnicity}`,
      p.distinctive_features && `Features: ${p.distinctive_features}`,
      p.default_outfit && `Default outfit: ${p.default_outfit}`,
      p.personality_vibe && `Vibe: ${p.personality_vibe}`,
      p.art_style && `Style: ${p.art_style}`,
      p.prompt_prefix && `Extra tags: ${p.prompt_prefix}`,
    ].filter(Boolean);
    return lines.join("\n");
  },

  bindEvents() {
    document.getElementById("newProfileBtn")?.addEventListener("click", () => this.openEditor());
    document.getElementById("saveProfileBtn")?.addEventListener("click", (e) => {
      e.preventDefault();
      this.save().catch((err) => alert(err.message));
    });
    document.getElementById("deleteProfileBtn")?.addEventListener("click", (e) => {
      e.preventDefault();
      this.remove().catch((err) => alert(err.message));
    });
    document.getElementById("profileSelect")?.addEventListener("change", (e) => {
      this.select(e.target.value || null);
    });
    document.getElementById("applyProfileBtn")?.addEventListener("click", () => {
      if (this.activeId) this.select(this.activeId);
    });

    // Live preview in editor
    const editorFields = document.querySelectorAll("#profileEditorDialog input, #profileEditorDialog textarea, #profileEditorDialog select");
    editorFields.forEach((el) => {
      el.addEventListener("input", () => this.updatePreviewPrompt(null));
    });
  },
};
