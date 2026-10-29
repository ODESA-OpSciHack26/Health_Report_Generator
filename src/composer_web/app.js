/* Local composer frontend: no framework, no CDN, no build step.
   All scientific work happens on the server through the shared loader and renderer.
   Display labels live here; the server keeps sending stable internal ids. */
"use strict";

const PRESET_EMOJI = { researcher: "🧑‍🔬", health_institution: "🏥", public: "👪",
                       custom: "🛠️" };

/* Plain-language names for the supported block types. Unknown ids fall back to the id. */
const BLOCK_LABELS = {
  intro: { label: "Introduction", description: "Short context for this report." },
  "series-trend": { label: "Annual trend for one disease",
                    description: "One saved annual series with its exact recorded values." },
  "series-collection": { label: "Annual trends by disease",
                         description: "One expandable chart per checked disease, with the "
                           + "same saved values in a table." },
  "coverage-selection": { label: "Data coverage and included observations",
                          description: "What the saved selection covers, and what it leaves out." },
  "sensitivity-comparison": { label: "Comparison across analysis choices",
                              description: "Saved main versus sensitivity group results." },
  "monitoring-overview": { label: "Latest observations by disease",
                           description: "The latest saved value and comparison per disease." },
  "reference-comparison": { label: "Change from the reference period",
                            description: "One saved change against the reference year." },
  limitations: { label: "Limitations and cautions", description: "What this report cannot support." },
  reproduction: { label: "Reproduction and evidence",
                  description: "How to check the published files and rerun the render." },
};
const STYLE_LABELS = { standard: "Standard", compact: "Compact" };

const state = {
  presets: [],
  preset: null,
  doc: null,
  rendered: null,        // { digest, preset, label, classification, job_id }
  job: null,
  seq: 0,                // intent counter: a late response never overwrites newer state
  busy: false,
  polling: null,
};

const el = (id) => document.getElementById(id);

function setStatus(node, message, kind) {
  node.textContent = message || "";
  node.className = "status" + (kind ? " " + kind : "");
}

function announce(message) {
  el("live").textContent = "";
  if (message) el("live").textContent = message;
}

function shortDigest(value) {
  return value ? value.slice(0, 12) : "—";
}

function blockInfo(block) {
  return BLOCK_LABELS[block.block] || { label: block.block, description: "" };
}

async function request(path, options) {
  const response = await fetch(path, Object.assign({ credentials: "same-origin" }, options));
  let payload = null;
  try { payload = await response.json(); } catch (error) { payload = null; }
  if (!response.ok) {
    const message = payload && payload.error ? payload.error.message
      : "Request failed (" + response.status + ").";
    const failure = new Error(message);
    failure.status = response.status;
    failure.code = payload && payload.error ? payload.error.code : "http_" + response.status;
    throw failure;
  }
  return payload;
}

function mutate(action, path, body) {
  return request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Composer-Action": action },
    body: JSON.stringify(body || {}),
  });
}

/* ------------------------------------------------------------------ presets */

function presetEntry(id) {
  return state.presets.find((item) => item.id === id) || null;
}

function renderPresets() {
  const container = el("presets");
  container.replaceChildren();
  for (const preset of state.presets) {
    const isCustom = preset.id === "custom";
    const selected = preset.id === state.preset;
    const card = document.createElement("button");
    card.type = "button";
    card.className = "preset" + (preset.customized ? " preset--customized" : "");
    card.dataset.preset = preset.id;
    card.setAttribute("role", "radio");
    card.setAttribute("aria-checked", String(selected));
    card.setAttribute("aria-disabled", String(!preset.available));
    card.tabIndex = selected ? 0 : -1;
    card.disabled = !preset.available;

    const icon = document.createElement("span");
    icon.className = "preset-icon";
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = PRESET_EMOJI[preset.id] || "";

    const name = document.createElement("span");
    name.className = "preset-label";
    name.textContent = preset.label;

    const mark = document.createElement("span");
    mark.className = "preset-mark";
    if (selected) mark.textContent = "✓ Selected";
    else if (!isCustom && preset.customized) mark.textContent = "• Customized";

    const detail = document.createElement("span");
    detail.className = "preset-detail";
    if (!preset.available) {
      detail.textContent = preset.reason || "Not available in this deployment.";
    } else if (preset.draft_error) {
      detail.textContent = "Saved copy needs attention: " + preset.draft_error;
    } else if (preset.source) {
      detail.textContent = preset.source.included_topics + " diseases · "
        + (preset.source.years || []).join("–") + " · ref. " + preset.source.reference_year;
    }

    card.append(icon, name, mark, detail);
    if (preset.available) {
      card.addEventListener("click", () => choosePreset(preset.id));
      card.addEventListener("keydown", (event) => onPresetKey(event, preset.id));
    }
    container.append(card);
  }
}

function onPresetKey(event, id) {
  const keys = ["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp", "Home", "End"];
  if (!keys.includes(event.key)) return;
  event.preventDefault();
  const usable = state.presets.filter((item) => item.available && item.id !== "custom");
  const index = usable.findIndex((item) => item.id === id);
  let next = index;
  if (event.key === "Home") next = 0;
  else if (event.key === "End") next = usable.length - 1;
  else if (event.key === "ArrowRight" || event.key === "ArrowDown") next = (index + 1) % usable.length;
  else next = (index - 1 + usable.length) % usable.length;
  const target = usable[next];
  if (!target) return;
  const node = document.querySelector('[data-preset="' + target.id + '"]');
  if (node) node.focus();
  choosePreset(target.id);
}

async function choosePreset(id) {
  const entry = presetEntry(id);
  if (!entry || !entry.available || id === "custom") return;
  const seq = ++state.seq;
  state.preset = id;
  renderPresets();
  setStatus(el("edit-status"), "Loading this audience…", "");
  try {
    const doc = await request("/api/editor?preset=" + encodeURIComponent(id));
    if (seq !== state.seq) return;
    applyDocument(doc, { openEditor: false });
    setStatus(el("edit-status"), "", "");
  } catch (error) {
    if (seq !== state.seq) return;
    setStatus(el("edit-status"), error.message, "error");
  }
}

/* ------------------------------------------------------------------ document */

function applyDocument(doc, options) {
  const active = document.activeElement && document.activeElement.id;
  state.doc = doc;
  state.preset = doc.preset;
  const entry = presetEntry(doc.preset);
  if (entry) entry.customized = doc.customized;
  el("custom-badge").hidden = !doc.customized;
  el("differences").textContent = describeDifferences(doc);
  el("reset-open").hidden = !doc.draft;
  el("reset-confirm").hidden = true;
  el("renderable-digest").textContent = shortDigest(doc.renderable_sha256);
  el("renderable-digest").title = doc.renderable_sha256;
  el("pending-note").textContent = doc.pending_sha256 === doc.renderable_sha256
    ? "" : (doc.ready
      ? "Pending changes are not part of the saved copy until you generate."
      : "Pending changes cannot be rendered yet.");
  renderSummary(doc.source);
  renderPresets();
  renderBlocks(doc);
  renderReadiness(doc);
  renderReuse(doc.reuse);
  if (options && options.openEditor !== undefined) el("editor").open = options.openEditor;
  updateGenerateEnabled();
  markStale();
  if (active) {
    const restored = document.getElementById(active);
    if (restored && typeof restored.focus === "function") restored.focus();
  }
}

function describeDifferences(doc) {
  if (!doc.draft) return "No saved copy yet; the editor shows this audience's default.";
  const diff = doc.differences || {};
  const parts = [];
  if ((diff.excluded || []).length) {
    parts.push(diff.excluded.length + (diff.excluded.length === 1 ? " section removed"
      : " sections removed"));
  }
  if (diff.reordered) parts.push("section order changed");
  if ((diff.style || []).length) parts.push("chart height changed");
  if ((diff.selection || []).length) parts.push("disease selection changed");
  if (!doc.customized) parts.push("matches the default");
  return parts.join(" · ");
}

function renderSummary(source) {
  const node = el("source-summary");
  if (!source) { node.textContent = ""; return; }
  const years = (source.years || []).join("–");
  const parts = [
    years ? "Reporting period " + years : null,
    source.reference_year ? "reference " + source.reference_year : null,
    source.geography || null,
    source.included_topics ? source.included_topics + " diseases in the saved bundle" : null,
    source.snapshot_short ? "saved data " + source.snapshot_short : null,
  ].filter(Boolean);
  node.textContent = parts.join(" · ");
  if (source.title) node.title = source.title;
}

function renderReadiness(doc) {
  const chip = el("ready-state");
  const blocking = el("blocking");
  if (doc.ready) {
    chip.textContent = "Ready to generate";
    chip.className = "chip chip--ok";
    blocking.hidden = true;
    blocking.textContent = "";
  } else {
    chip.textContent = "Not ready to generate";
    chip.className = "chip chip--warn";
    blocking.hidden = false;
    blocking.textContent = doc.blocking_reason || "This draft cannot be generated yet.";
  }
}

function renderBlocks(doc) {
  const list = el("blocks");
  list.replaceChildren();
  const included = doc.blocks.filter((block) => block.included);
  doc.blocks.forEach((block) => {
    const info = blockInfo(block);
    const item = document.createElement("li");
    item.className = "block" + (block.included ? "" : " block--off");

    const head = document.createElement("div");
    head.className = "block-head";
    const wrap = document.createElement("label");
    wrap.className = "check";
    const box = document.createElement("input");
    box.type = "checkbox";
    box.id = "include-" + block.instance_id;
    box.checked = block.included;
    box.disabled = block.required || (block.included && included.length <= 1);
    box.addEventListener("change", () =>
      edit(box.checked ? "include" : "exclude", block.instance_id, null));
    const text = document.createElement("span");
    text.className = "block-label";
    text.textContent = info.label;
    wrap.append(box, text);
    head.append(wrap);

    const id = document.createElement("span");
    id.className = "block-id";
    id.textContent = block.instance_id;
    head.append(id);
    item.append(head);

    if (info.description) {
      const description = document.createElement("p");
      description.className = "block-desc";
      description.textContent = info.description;
      item.append(description);
    }
    if (block.required) {
      const note = document.createElement("p");
      note.className = "block-required";
      note.textContent = "Always included. " + (block.required_reason || "");
      item.append(note);
    }

    const controls = document.createElement("div");
    controls.className = "block-controls";
    if (block.included) {
      const position = included.findIndex((entry) => entry.instance_id === block.instance_id);
      const move = document.createElement("div");
      move.className = "move";
      const up = document.createElement("button");
      up.type = "button";
      up.id = "up-" + block.instance_id;
      up.textContent = "↑";
      up.setAttribute("aria-label", "Move " + info.label + " up");
      up.disabled = position <= 0;
      up.addEventListener("click", () => edit("move-up", block.instance_id, null));
      const down = document.createElement("button");
      down.type = "button";
      down.id = "down-" + block.instance_id;
      down.textContent = "↓";
      down.setAttribute("aria-label", "Move " + info.label + " down");
      down.disabled = position === included.length - 1;
      down.addEventListener("click", () => edit("move-down", block.instance_id, null));
      move.append(up, down);
      controls.append(move);
    }
    item.append(controls);

    if ((block.editable || []).includes("topics")) {
      item.append(diseasePicker(block, info));
    }
    if ((block.editable || []).includes("style")) {
      item.append(advancedStyle(block));
    }

    list.append(item);
  });
}

function diseasePicker(block, info) {
  const wrap = document.createElement("fieldset");
  wrap.className = "diseases";
  wrap.id = "topics-" + block.instance_id;
  const legend = document.createElement("legend");
  legend.textContent = "Diseases shown in this section";
  wrap.append(legend);

  const chosen = block.selected_topics || [];
  const choices = block.topic_choices || [];
  const disabled = !block.included;

  const buttons = document.createElement("div");
  buttons.className = "buttons buttons--inline";
  const all = document.createElement("button");
  all.type = "button";
  all.id = "all-" + block.instance_id;
  all.textContent = "Select all";
  all.disabled = disabled;
  all.addEventListener("click", () => edit("set-topics", block.instance_id, choices.slice()));
  const none = document.createElement("button");
  none.type = "button";
  none.id = "clear-" + block.instance_id;
  none.textContent = "Clear";
  none.disabled = disabled;
  none.addEventListener("click", () => edit("set-topics", block.instance_id, []));
  buttons.append(all, none);
  wrap.append(buttons);

  const grid = document.createElement("div");
  grid.className = "disease-grid";
  for (const topic of choices) {
    const label = document.createElement("label");
    label.className = "disease";
    const box = document.createElement("input");
    box.type = "checkbox";
    box.id = "pick-" + block.instance_id + "-" + topic;
    box.value = topic;
    box.checked = chosen.includes(topic);
    box.disabled = disabled;
    box.addEventListener("change", () => {
      const current = (state.doc && state.doc.blocks.find(
        (entry) => entry.instance_id === block.instance_id) || {}).selected_topics || [];
      const next = box.checked
        ? current.concat([topic])
        : current.filter((entry) => entry !== topic);
      edit("set-topics", block.instance_id, next);
    });
    const name = document.createElement("span");
    name.textContent = topic;
    label.append(box, name);
    grid.append(label);
  }
  wrap.append(grid);

  if (!choices.length) {
    const note = document.createElement("p");
    note.className = "field-help";
    note.textContent = "This saved bundle lists no diseases for the section.";
    wrap.append(note);
  }
  if (disabled) {
    const note = document.createElement("p");
    note.className = "field-help";
    note.textContent = "This section is turned off; your disease selection is kept.";
    wrap.append(note);
  }

  const field = document.createElement("div");
  field.className = "field field--wide";
  const label = document.createElement("label");
  label.textContent = "Disease expanded when the report opens";
  label.htmlFor = "open-" + block.instance_id;
  const select = document.createElement("select");
  select.id = "open-" + block.instance_id;
  if (!chosen.length) {
    const placeholder = document.createElement("option");
    placeholder.textContent = "No diseases selected";
    placeholder.value = "";
    select.append(placeholder);
    select.disabled = true;
  }
  for (const topic of chosen) {
    const option = document.createElement("option");
    option.value = topic;
    option.textContent = topic;
    if (block.default_topic === topic) option.selected = true;
    select.append(option);
  }
  select.addEventListener("change", () =>
    edit("set-default-open", block.instance_id, select.value));
  const help = document.createElement("p");
  help.className = "field-help";
  help.textContent = "Other checked diseases remain available in the report.";
  field.append(label, select, help);
  wrap.append(field);
  return wrap;
}

function advancedStyle(block) {
  const wrap = document.createElement("details");
  wrap.className = "advanced";
  const summary = document.createElement("summary");
  summary.textContent = "Advanced display options";
  wrap.append(summary);

  const field = document.createElement("div");
  field.className = "field";
  const label = document.createElement("label");
  label.textContent = "Chart height";
  label.htmlFor = "style-" + block.instance_id;
  const select = document.createElement("select");
  select.id = "style-" + block.instance_id;
  for (const value of ["standard", "compact"]) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = STYLE_LABELS[value] || value;
    if (block.style === value) option.selected = true;
    select.append(option);
  }
  select.addEventListener("change", () => {
    if (select.value === block.style) return;   // no-op must not change the recipe
    edit("set-style", block.instance_id, select.value);
  });
  const help = document.createElement("p");
  help.className = "field-help";
  help.textContent = "Changes the figure height only. Values, axes, wording and analytical "
    + "meaning are unchanged.";
  field.append(label, select, help);
  wrap.append(field);
  return wrap;
}

async function edit(action, instance, value) {
  if (!state.preset) return;
  const seq = ++state.seq;
  setStatus(el("edit-status"), "Saving…", "");
  try {
    const doc = await mutate("edit", "/api/edit",
      { preset: state.preset, action: action, instance: instance, value: value });
    if (seq !== state.seq) return;
    applyDocument(doc, { openEditor: true });
    for (const note of doc.notes || []) {
      if (note.kind === "default-open-moved") {
        announce("The expanded disease moved to " + note.to + " because " + note.from
          + " is no longer checked.");
      } else if (note.kind === "default-open-cleared") {
        announce("No disease is checked, so the expanded disease was cleared.");
      }
    }
    setStatus(el("edit-status"), doc.customized
      ? "Saved. This audience now differs from its default."
      : "Saved. This audience matches its default again.", "ok");
  } catch (error) {
    if (seq !== state.seq) return;
    setStatus(el("edit-status"), error.message, "error");
    if (state.doc) renderBlocks(state.doc);
  }
}

async function resetCopy() {
  if (!state.preset) return;
  const seq = ++state.seq;
  try {
    const doc = await mutate("reset", "/api/reset", { preset: state.preset });
    if (seq !== state.seq) return;
    applyDocument(doc, { openEditor: true });
    setStatus(el("edit-status"), "Reset to this audience's default. Earlier reports are kept.",
      "ok");
    announce("Reset to default.");
    loadSaved(true);
  } catch (error) {
    if (seq !== state.seq) return;
    setStatus(el("edit-status"), error.message, "error");
  }
}

/* ------------------------------------------------------------------ generation */

function updateGenerateEnabled() {
  const reuse = state.doc && state.doc.reuse;
  const matched = Boolean(reuse && reuse.available);
  el("generate").disabled = state.busy || !state.preset || !state.doc || !state.doc.ready
    || matched;
  el("generate").title = matched ? "A matching report already exists; use Show here."
    : "";
}

function renderReuse(reuse) {
  const panel = el("reuse");
  const text = el("reuse-text");
  const meta = el("reuse-meta");
  const open = el("reuse-open");
  if (!reuse || !reuse.available) {
    panel.hidden = true;
    open.hidden = true;
    open.removeAttribute("href");
    text.textContent = "";
    meta.textContent = "";
    return;
  }
  const shown = state.rendered && state.rendered.job_id === reuse.job_id;
  panel.hidden = false;
  text.textContent = shown
    ? "This matching report is already on screen. Show here returns you to it."
    : "A report matching these settings is already available.";
  open.hidden = false;
  open.href = reuse.report_url;
  const when = reuse.finished_utc || reuse.created_utc || "unknown time";
  meta.textContent = "Generated " + when + " · "
    + (reuse.classification === "customized" ? "customized" : "default")
    + " composition · recipe " + shortDigest(reuse.recipe_sha256)
    + " · " + (reuse.package_files || 0) + " published files";
  el("replay-command").textContent = reuse.replay_command
    || "No replay command was recorded for this report.";
}

function focusReport() {
  const region = el("report");
  const reduce = window.matchMedia
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  region.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  region.focus({ preventScroll: true });
}

function displayReport(job) {
  const frame = el("report-frame");
  frame.hidden = false;
  frame.src = job.report_url + "?job=" + encodeURIComponent(job.job_id);
  el("open-report").hidden = false;
  el("open-report").href = job.report_url;
  el("report-empty").textContent = "";
  el("job-digest").textContent = shortDigest(job.recipe_sha256);
  el("job-digest").title = job.recipe_sha256 || "";
  el("replay-command").textContent = job.replay_command || "—";
  const entry = presetEntry(job.preset) || { label: job.preset };
  state.rendered = { digest: job.recipe_sha256, preset: job.preset, label: entry.label,
                     classification: job.classification, job_id: job.job_id };
}

async function showHere() {
  const reuse = state.doc && state.doc.reuse;
  if (!reuse || !reuse.available) return;
  const seq = ++state.seq;
  setStatus(el("generate-status"), "Checking that report…", "");
  try {
    const job = await mutate("reuse", "/api/reuse",
      { preset: state.preset, job_id: reuse.job_id });
    if (seq !== state.seq) return;
    const already = state.rendered && state.rendered.job_id === job.job_id;
    displayReport(Object.assign({ preset: state.preset }, job));
    renderReuse(state.doc && state.doc.reuse);
    markStale();
    setStatus(el("generate-status"), already
      ? "That report is already on screen; moved back to it."
      : "Showing the retained report " + job.job_id + " generated at "
        + (job.finished_utc || job.created_utc) + ". The package was not rendered again.",
      "ok");
    focusReport();
    await refreshDocument();
  } catch (error) {
    if (seq !== state.seq) return;
    setStatus(el("generate-status"), error.message
      + " Generate is available again; the report on screen is unchanged.", "error");
    announce(error.message);
    await refreshDocument();
  }
}

function markStale() {
  const node = el("stale");
  const rendered = state.rendered;
  if (!rendered) { node.hidden = true; node.textContent = ""; return; }
  const current = state.doc ? state.doc.pending_sha256 : null;
  const changed = rendered.digest !== current || rendered.preset !== state.preset;
  node.hidden = !changed;
  node.textContent = changed
    ? "The report on screen was generated from the " + rendered.label + " ("
      + (rendered.classification === "customized" ? "customized" : "default")
      + " composition, recipe " + shortDigest(rendered.digest)
      + "). The choices now differ; generate again to refresh it."
    : "";
}

function setJobState(status) {
  el("job-state").textContent = status;
  el("job-state").dataset.state = status;
}

async function generate() {
  if (state.busy || !state.preset || !state.doc || !state.doc.ready) return;
  state.busy = true;
  updateGenerateEnabled();
  setStatus(el("generate-status"), "Submitting…", "");
  try {
    const job = await mutate("generate", "/api/generate", { preset: state.preset });
    state.job = job;
    setJobState(job.status);
    el("replay-command").textContent = job.replay_command || "—";
    setStatus(el("generate-status"), "Queued as " + job.job_id + ".", "");
    poll(job.job_id);
  } catch (error) {
    state.busy = false;
    updateGenerateEnabled();
    setStatus(el("generate-status"), error.message, "error");
    announce(error.message);
  }
}

function poll(jobId) {
  if (state.polling) clearInterval(state.polling);
  state.polling = setInterval(async () => {
    let job = null;
    try {
      job = await request("/api/jobs/" + encodeURIComponent(jobId));
    } catch (error) {
      clearInterval(state.polling);
      state.polling = null;
      state.busy = false;
      updateGenerateEnabled();
      setStatus(el("generate-status"), error.message, "error");
      return;
    }
    if (!state.job || state.job.job_id !== job.job_id) return;
    state.job = job;
    setJobState(job.status);
    if (job.status === "queued" || job.status === "running") {
      setStatus(el("generate-status"),
        "Rendering… started " + (job.started_utc || "shortly") + ".", "");
      return;
    }
    clearInterval(state.polling);
    state.polling = null;
    state.busy = false;
    if (job.status === "succeeded") {
      const entry = presetEntry(job.preset) || { label: job.preset };
      state.rendered = { digest: job.recipe_sha256, preset: job.preset,
                         label: entry.label, classification: job.classification,
                         job_id: job.job_id };
      const frame = el("report-frame");
      frame.hidden = false;
      frame.src = job.report_url + "?job=" + encodeURIComponent(job.job_id);
      el("open-report").hidden = false;
      el("open-report").href = job.report_url;
      el("report-empty").textContent = "";
      el("job-digest").textContent = shortDigest(job.recipe_sha256);
      el("job-digest").title = job.recipe_sha256;
      setStatus(el("generate-status"), "Generated the " + entry.label + " "
        + (job.classification === "customized" ? "customized" : "default")
        + " composition (recipe " + shortDigest(job.recipe_sha256) + ") at "
        + job.finished_utc + ".", "ok");
    } else {
      el("job-digest").textContent = shortDigest(job.recipe_sha256);
      el("job-digest").title = job.recipe_sha256;
      setStatus(el("generate-status"), "Generation " + job.status + ". " + (job.error || "")
        + " The report on screen is unchanged.", "error");
    }
    updateGenerateEnabled();
    markStale();
    await refreshDocument();
    loadSaved(true);
  }, 900);
}

async function refreshDocument() {
  if (!state.preset) return;
  const seq = ++state.seq;
  try {
    const doc = await request("/api/editor?preset=" + encodeURIComponent(state.preset));
    if (seq !== state.seq) return;
    applyDocument(doc, {});
  } catch (error) {
    setStatus(el("edit-status"), error.message, "error");
  }
}

/* ------------------------------------------------------------------ saved data */

function classificationLabel(job) {
  if (job.classification === "default") return "Default";
  if (job.classification === "customized") return "Customized";
  if (job.mode === "standard") return "Default (standard composition)";
  return "Customization status not recorded";
}

function snapshotText(summary) {
  if (!summary || !summary.available) {
    return summary && summary.detail ? summary.detail : "Snapshot summary unavailable.";
  }
  const blocks = (summary.blocks || []).map((entry) => {
    const info = BLOCK_LABELS[entry.block] || { label: entry.block };
    return info.label;
  });
  return summary.block_count + " section" + (summary.block_count === 1 ? "" : "s")
    + ": " + blocks.join(", ");
}

async function loadSaved(quiet) {
  try {
    const data = await request("/api/saved");
    el("data-paths").textContent = "Work root " + data.work_root
      + " · inputs " + data.inputs_root
      + (data.drafts.length ? " · managed copies: " + data.drafts.join(", ") : "");
    const list = el("saved-list");
    list.replaceChildren();
    for (const job of data.jobs) {
      const row = document.createElement("li");
      const head = document.createElement("div");
      head.className = "saved-head";
      const entry = presetEntry(job.preset) || { label: job.preset || "unknown audience" };
      const title = document.createElement("strong");
      title.textContent = entry.label + " · " + classificationLabel(job);
      const when = document.createElement("span");
      when.className = "hint";
      when.textContent = job.created_utc + " · " + job.status
        + " · recipe " + shortDigest(job.recipe_sha256)
        + (job.error ? " — " + job.error : "");
      head.append(title, when);
      const summary = document.createElement("p");
      summary.className = "hint";
      summary.textContent = snapshotText(job.snapshot_summary);
      row.append(head, summary);

      const reuse = job.reuse || { eligible: false, reason: "" };
      const line = document.createElement("p");
      line.className = "saved-reuse";
      const chip = document.createElement("span");
      chip.className = "chip " + (reuse.eligible ? "chip--ok" : "chip--warn");
      chip.textContent = reuse.eligible ? "Reusable now" : "Not reusable now";
      const why = document.createElement("span");
      why.className = "hint";
      why.textContent = reuse.reason || "";
      line.append(chip, why);
      if (job.composition_match === "different") {
        const differ = document.createElement("span");
        differ.className = "hint";
        differ.textContent = "Sections or diseases differ from the editor.";
        line.append(differ);
      } else if (job.composition_match === "same") {
        const same = document.createElement("span");
        same.className = "hint";
        same.textContent = "Sections and diseases match the editor.";
        line.append(same);
      }
      row.append(line);

      if (job.status === "succeeded" && job.report_url) {
        const actions = document.createElement("div");
        actions.className = "saved-actions";
        const show = document.createElement("button");
        show.type = "button";
        show.textContent = "Show here";
        show.addEventListener("click", () => displaySaved(job));
        const open = document.createElement("a");
        open.href = job.report_url;
        open.target = "_blank";
        open.rel = "noopener";
        open.textContent = "Open";
        actions.append(show, open);
        row.append(actions);
      }
      list.append(row);
    }
    el("saved-empty").hidden = data.jobs.length > 0;
  } catch (error) {
    if (!quiet) setStatus(el("edit-status"), error.message, "error");
  }
}

function displaySaved(job) {
  const already = state.rendered && state.rendered.job_id === job.job_id;
  displayReport(job);
  renderReuse(state.doc && state.doc.reuse);
  markStale();
  const entry = presetEntry(job.preset) || { label: job.preset || "this audience" };
  setStatus(el("generate-status"), (already ? "That report is already on screen; moved back to it."
    : "Showing the saved " + entry.label + " report " + job.job_id + " generated at "
      + job.created_utc + ".") + " Your editor settings are unchanged.",
    "ok");
  focusReport();
}

/* ------------------------------------------------------------------ wiring */

async function load() {
  try {
    const data = await request("/api/presets");
    state.presets = data.presets;
    renderPresets();
    const first = state.presets.find((item) => item.id !== "custom" && item.available);
    if (!first) {
      setStatus(el("generate-status"),
        "No audience is available in this deployment: no maintained recipe and saved bundle "
        + "pair was found.", "error");
      return;
    }
    await choosePreset(first.id);
    await loadSaved(true);
  } catch (error) {
    setStatus(el("generate-status"), "Could not load the choices: " + error.message, "error");
  }
}

function wire() {
  el("generate").addEventListener("click", generate);
  el("reuse-show").addEventListener("click", showHere);
  el("reset-open").addEventListener("click", () => {
    el("reset-confirm").hidden = false;
    el("reset-confirm-yes").focus();
  });
  el("reset-cancel").addEventListener("click", () => {
    el("reset-confirm").hidden = true;
    el("reset-open").focus();
  });
  el("reset-confirm-yes").addEventListener("click", resetCopy);
  el("data").addEventListener("toggle", () => { if (el("data").open) loadSaved(true); });
  load();
}

document.addEventListener("DOMContentLoaded", wire);
