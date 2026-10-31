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
  route: "health",
  sourcesOpener: null,
  csvDigest: null,
  csvDocument: null,
  csvJob: null,
  busyCsv: false,
  presets: [],
  preset: null,
  context: null,         // the saved data context the custom composition is bound to
  audience: null,        // the last audience preset the reader looked at
  mode: "preset",        // "preset" (audience) or "custom" (block library)
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
    } else if (isCustom) {
      detail.textContent = preset.detail || "Compose from the block library.";
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
  const usable = state.presets.filter((item) => item.available);
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
  if (!entry || !entry.available) return;
  if (id === "custom") return chooseCustom();
  const seq = ++state.seq;
  state.mode = "preset";
  state.preset = id;
  state.audience = id;
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
  state.mode = "preset";
  state.preset = doc.preset;
  state.audience = doc.preset;
  el("custom-card").hidden = true;
  el("audience-card").hidden = false;
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
  if ((diff.layout || []).length) parts.push("chart layout changed");
  if ((diff.selection || []).length) parts.push("disease selection changed");
  if (!doc.customized) parts.push("matches the default");
  return parts.join(" · ");
}

function renderSourceCard(source) {
  if (!source) return;
  const years = (source.years || []).join("–");
  el("source-geography").textContent = source.geography
    || "Switzerland and Liechtenstein where the saved bundle supports it";
  el("source-geo").textContent = source.geography || "Not recorded";
  el("source-years").textContent = years || "Not recorded";
  el("source-topics").textContent = source.included_topics
    ? source.included_topics + " diseases" : "Not recorded";
  el("source-snapshot").textContent = source.snapshot_id || "Not recorded";
  el("source-captured").textContent = "Not recorded for this bundle";
  el("source-release").textContent = "Not recorded for this bundle";
}

function renderSummary(source) {
  const node = el("source-summary");
  renderSourceCard(source);
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

/* ------------------------------------------------------------ shared section editor
   One implementation of the ordered section list. The audience editor and the Custom
   editor render the same controls from the same document fields; the adapter is the only
   mode-specific part and only maps a control onto that mode's server action. Disease
   selection, ordering, exclusion and option rules live here once, not once per mode. */

function sectionText(block) {
  const fallback = BLOCK_LABELS[block.block] || {};
  return { label: block.label || fallback.label || block.block,
           description: block.description || fallback.description || "" };
}

function optionValue(block, key) {
  const options = block.options || {};
  if (Object.prototype.hasOwnProperty.call(options, key)) return options[key];
  if (key === "topics") return block.selected_topics;
  if (key === "style") return block.style;
  if (key === "default_topic") return block.default_topic;
  return undefined;
}

function presetAdapter(doc) {
  return {
    mode: "preset",
    setIncluded: (id, include) => edit(include ? "include" : "exclude", id, null),
    move: (id, direction) => edit(direction === "up" ? "move-up" : "move-down", id, null),
    setTopics: (id, topics) => edit("set-topics", id, topics),
    setDefaultOpen: (id, topic) => edit("set-default-open", id, topic),
    setTitle: (id, value) => edit("set-title", id, value),
    option: (id, name, value) => edit(name === "layout" ? "set-layout" : "set-style",
                                      id, value),
    canDuplicate: false,
    duplicate: null,
  };
}

function customAdapter(doc) {
  return {
    mode: "custom",
    setIncluded: (id, include) => customAction(include ? "restore" : "remove", id),
    move: (id, direction) => customAction(direction === "up" ? "move-up" : "move-down", id),
    setTopics: (id, topics) => customAction("set-topics", id, topics),
    setDefaultOpen: (id, topic) => customAction("set-default-open", id, topic),
    setTitle: (id, value) => customAction("set-title", id, value),
    // The website speaks "style"/"layout"; the block contract calls them "presentation.*".
    option: (id, name, value) => setOption(
      id, (name === "style" || name === "layout") ? "presentation." + name : name, value),
    canDuplicate: true,
    duplicate: (id) => customAction("duplicate", id),
  };
}

function renderBlocks(doc) {
  renderSections(doc, presetAdapter(doc), el("blocks"));
}

function renderSections(doc, adapter, list) {
  const included = doc.blocks.filter((block) => block.included);
  const activeId = document.activeElement && document.activeElement.id;
  if (!(list._openBlocks instanceof Set)) list._openBlocks = new Set();
  list.replaceChildren();
  doc.blocks.forEach((block) => {
    const info = sectionText(block);
    const item = document.createElement("li");
    item.className = "block block--card" + (block.included ? "" : " block--off");
    item.setAttribute("data-instance", block.instance_id);

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
      adapter.setIncluded(block.instance_id, box.checked));
    const text = document.createElement("span");
    text.className = "block-label";
    text.textContent = info.label;
    wrap.append(box, text);
    head.append(wrap);

    if (block.required) {
      const state = document.createElement("span");
      state.className = "badge badge--req";
      state.textContent = "Required";
      head.append(state);
    } else if (!block.included) {
      const state = document.createElement("span");
      state.className = "badge badge--soft";
      state.textContent = "Excluded";
      head.append(state);
    }
    if (block.copy_label) {
      const copy = document.createElement("span");
      copy.className = "badge badge--soft block-copy";
      copy.textContent = block.copy_label;
      copy.title = "Editor-only disambiguation; not part of the report title.";
      head.append(copy);
    }
    item.append(head);

    // Collapsed line: the user's title (if any) and the factual effective summary.
    const compactBits = [];
    if (block.title) compactBits.push(block.title);
    if (block.display_summary) compactBits.push(block.display_summary);
    else if (block.summary) compactBits.push(block.summary);
    else if (info.description) compactBits.push(info.description);
    if (compactBits.length) {
      const compact = document.createElement("p");
      compact.className = "block-compact-line";
      compact.textContent = compactBits.join(" · ");
      item.append(compact);
    }
    if (block.summary) {
      const problem = document.createElement("p");
      problem.className = "blocking-text";
      problem.setAttribute("role", "alert");
      problem.textContent = block.summary;
      item.append(problem);
    }

    const details = document.createElement("details");
    details.className = "block-details";
    details.open = list._openBlocks.has(block.instance_id);
    details.addEventListener("toggle", () => {
      if (details.open) list._openBlocks.add(block.instance_id);
      else list._openBlocks.delete(block.instance_id);
    });
    const summary = document.createElement("summary");
    summary.textContent = "Settings and details";
    details.append(summary);
    const body = document.createElement("div");
    body.className = "block-details-body";
    details.append(body);

    if (info.description) {
      const description = document.createElement("p");
      description.className = "block-desc";
      description.textContent = info.description;
      body.append(description);
    }
    if (block.required) {
      const note = document.createElement("p");
      note.className = "block-required";
      note.textContent = "Always included. " + (block.required_reason || "");
      body.append(note);
    }

    const controls = document.createElement("div");
    controls.className = "block-controls";
    if (block.included) {
      const position = included.findIndex((entry) => entry.instance_id === block.instance_id);
      const move = document.createElement("div");
      move.className = "move";
      move.append(
        controlButton("↑", "up-" + block.instance_id, "Move " + info.label + " up",
                      position <= 0, () => adapter.move(block.instance_id, "up")),
        controlButton("↓", "down-" + block.instance_id, "Move " + info.label + " down",
                      position === included.length - 1,
                      () => adapter.move(block.instance_id, "down")));
      controls.append(move);
      if (adapter.canDuplicate && block.repeatable) {
        controls.append(controlButton("Duplicate", "dup-" + block.instance_id,
                                      "Duplicate " + info.label, false,
                                      () => adapter.duplicate(block.instance_id)));
      }
      if (adapter.canDelete) {
        const sameType = doc.blocks.filter((entry) => entry.block === block.block).length;
        if (sameType > 1) {
          controls.append(controlButton(
            "Delete duplicate", "delete-" + block.instance_id,
            "Delete this duplicate of " + info.label, false,
            () => inlineConfirm(body,
              "Delete this duplicate section? Only this instance and its own settings are "
              + "removed; the other copies stay in the report.",
              "Delete duplicate", () => adapter.deleteInstance(block.instance_id))));
        }
      }
    }
    body.append(controls);

    if (block.included) {
      body.append(titleField(adapter, block));
      if (block.block === "reference-comparison" || block.block === "monitoring-overview") {
        const scope = document.createElement("p");
        scope.className = "field-help";
        scope.textContent = block.block === "reference-comparison"
          ? "The reporting year and the reference year come from this report's saved analysis "
            + "settings. To change them, generate an analysis with different settings."
          : "The reporting window comes from this report's saved analysis settings; the value "
            + "shown is the latest saved observation inside that window, not a fixed reporting "
            + "year. To change the window, generate an analysis with different settings.";
        body.append(scope);
      }
      if (block.block === "series-collection") {
        const note = document.createElement("p");
        note.className = "field-help";
        note.textContent = "Display years only choose saved rows from the same series; they do "
          + "not change the reporting window used by the analysis.";
        body.append(note);
      }
      const editable = block.editable || [];
      if (editable.includes("topic")) body.append(topicControl(adapter, block));
      if (editable.includes("measure")) body.append(measureControl(adapter, block));
      if (editable.includes("layout")) body.append(layoutControl(adapter, block));
      if (editable.includes("topics")) body.append(diseasePicker(adapter, block));
      if (editable.includes("style") || editable.includes("years")) {
        body.append(advancedControls(adapter, block));
      }
    }
    const technical = document.createElement("p");
    technical.className = "block-id";
    technical.textContent = "Section id " + block.instance_id;
    body.append(technical);
    const confirm = document.createElement("div");
    confirm.className = "inline-confirm";
    body.append(confirm);
    item.append(details);
    list.append(item);
  });

  if (activeId) {
    const again = document.getElementById(activeId);
    if (again && again.focus) again.focus();
  }

  // Every registered type that this draft does not contain yet stays visible as an unchecked
  // row after the saved sections. Checking one asks the service to create a real instance.
  const absent = adapter.absentTypes ? adapter.absentTypes() : [];
  for (const type of absent) {
    const item = document.createElement("li");
    item.className = "block block--absent";

    const head = document.createElement("div");
    head.className = "block-head";
    const wrap = document.createElement("label");
    wrap.className = "check";
    const box = document.createElement("input");
    box.type = "checkbox";
    box.id = "add-" + type.block;
    box.checked = false;
    box.disabled = !type.available;
    box.addEventListener("change", () => {
      if (box.checked) adapter.addType(type.block, box, item);
    });
    const text = document.createElement("span");
    text.className = "block-label";
    text.textContent = type.label;
    wrap.append(box, text);
    head.append(wrap);
    const badge = document.createElement("span");
    badge.className = "badge badge--soft";
    badge.textContent = "Not in this report";
    head.append(badge);
    item.append(head);

    const description = document.createElement("p");
    description.className = "block-desc";
    description.textContent = type.description;
    item.append(description);

    if (!type.available) {
      const reason = document.createElement("p");
      reason.className = "library-reason";
      reason.textContent = "Not available for this data context: "
        + (type.reason || "the saved records do not support this section.");
      item.append(reason);
    } else if (!type.repeatable && type.repeat_reason) {
      const note = document.createElement("p");
      note.className = "field-help";
      note.textContent = type.repeat_reason;
      item.append(note);
    }

    const confirm = document.createElement("div");
    confirm.className = "inline-confirm";
    item.append(confirm);
    list.append(item);
  }
}

function fieldShell(text, control, helpText, wide) {
  const field = document.createElement("div");
  field.className = "field" + (wide ? " field--wide" : "");
  const label = document.createElement("label");
  label.textContent = text;
  label.htmlFor = control.id;
  field.append(label, control);
  if (helpText) {
    const help = document.createElement("p");
    help.className = "field-help";
    help.textContent = helpText;
    field.append(help);
  }
  return field;
}

function selectField(id, choices, current, onChange) {
  const select = document.createElement("select");
  select.id = id;
  for (const choice of choices) {
    const option = document.createElement("option");
    option.value = choice.value;
    option.textContent = choice.label;
    if (choice.value === current) option.selected = true;
    select.append(option);
  }
  select.addEventListener("change", () => onChange(select.value));
  return select;
}

function diseasePicker(adapter, block) {
  const wrap = document.createElement("fieldset");
  wrap.className = "diseases";
  wrap.id = "topics-" + block.instance_id;
  const legend = document.createElement("legend");
  legend.textContent = "Diseases shown in this section";
  wrap.append(legend);

  const chosen = optionValue(block, "topics") || [];
  const choices = block.topic_choices || [];
  const disabled = !block.included;

  const buttons = document.createElement("div");
  buttons.className = "buttons buttons--inline";
  const all = document.createElement("button");
  all.type = "button";
  all.id = "all-" + block.instance_id;
  all.textContent = "Select all";
  all.disabled = disabled;
  all.addEventListener("click", () => adapter.setTopics(block.instance_id, choices.slice()));
  const none = document.createElement("button");
  none.type = "button";
  none.id = "clear-" + block.instance_id;
  none.textContent = "Clear";
  none.disabled = disabled;
  none.addEventListener("click", () => adapter.setTopics(block.instance_id, []));
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
      const current = optionValue(
        (state.doc && state.doc.blocks.find(
          (entry) => entry.instance_id === block.instance_id)) || { options: {} },
        "topics") || [];
      const next = box.checked ? current.concat([topic])
        : current.filter((entry) => entry !== topic);
      adapter.setTopics(block.instance_id, next);
    });
    const name = document.createElement("span");
    name.textContent = topicLabel(topic);
    label.append(box, name);
    grid.append(label);
  }
  wrap.append(grid);

  if (!choices.length) {
    const note = document.createElement("p");
    note.className = "field-help";
    note.textContent = "This saved data context lists no diseases for this section.";
    wrap.append(note);
  }
  if (disabled) {
    const note = document.createElement("p");
    note.className = "field-help";
    note.textContent = "This section is turned off; your disease selection is kept.";
    wrap.append(note);
  }

  const select = selectField("open-" + block.instance_id,
                             chosen.map((topic) => ({ value: topic, label: topicLabel(topic) })),
                             optionValue(block, "default_topic"),
                             (value) => adapter.setDefaultOpen(block.instance_id, value));
  if (!chosen.length) {
    const placeholder = document.createElement("option");
    placeholder.textContent = "No diseases selected";
    placeholder.value = "";
    select.prepend(placeholder);
    select.disabled = true;
  }
  select.disabled = select.disabled || disabled;
  const combined = (optionValue(block, "layout") || "panels") === "combined";
  wrap.append(fieldShell(
    combined ? "Disease details expanded when the report opens"
             : "Disease expanded when the report opens",
    select,
    combined
      ? "All selected diseases are plotted in the chart; this only chooses which detail panel is "
        + "open first."
      : "Other checked diseases remain available in the report.", true));
  return wrap;
}

function titleField(adapter, block) {
  const wrap = document.createElement("div");
  wrap.className = "field field--wide block-title-field";
  const label = document.createElement("label");
  label.textContent = "Report section title (optional)";
  label.htmlFor = "title-" + block.instance_id;
  const input = document.createElement("input");
  input.type = "text";
  input.id = "title-" + block.instance_id;
  input.maxLength = 80;
  input.value = block.title || "";
  input.placeholder = "Uses the block name when blank";
  input.addEventListener("change", () => {
    const value = input.value.trim();
    if (value === (block.title || "")) return;
    adapter.setTitle(block.instance_id, value);
  });
  const help = document.createElement("p");
  help.className = "field-help";
  help.textContent = "Plain text, up to 80 characters. It becomes the section heading; the block "
    + "name and a summary of the saved content stay beside it.";
  wrap.append(label, input, help);
  return wrap;
}

function layoutControl(adapter, block) {
  const current = optionValue(block, "layout") || "panels";
  const select = selectField("layout-" + block.instance_id,
                             [{ value: "panels", label: "Separate chart per disease" },
                              { value: "combined", label: "One combined chart" }],
                             current,
                             (value) => {
                               if (value === optionValue(block, "layout")) return;
                               adapter.option(block.instance_id, "layout", value);
                             });
  const combined = current === "combined";
  return fieldShell("Chart layout", select,
                    combined
                      ? "Every selected disease is plotted in one chart on a shared axis; each "
                        + "disease keeps its own expandable detail table. Changing the layout "
                        + "changes the presentation only, not the saved values."
                      : "Each disease keeps its own chart and detail panel.", true);
}

function topicControl(adapter, block) {
  const reference = block.block === "reference-comparison";
  const choices = reference ? (block.reference_choices || []) : (block.topic_choices || []);
  const select = selectField("topic-" + block.instance_id,
                             choices.map((topic) => ({ value: topic, label: topic })),
                             optionValue(block, "topic"),
                             (value) => adapter.option(block.instance_id, "topic", value));
  return fieldShell(reference ? "Saved comparison shown" : "Disease shown", select,
                    reference
                      ? "Chooses a different saved result. The displayed disease, its counts "
                        + "and this section's checked instance identity change; no analysis is run."
                      : "This section shows one disease. Choosing another saved series changes "
                        + "what is displayed; the report scope does not change and no analysis "
                        + "is run.", true);
}

function measureControl(adapter, block) {
  const choices = block.measures && block.measures.length
    ? block.measures : [optionValue(block, "measure")].filter(Boolean);
  const select = selectField("measure-" + block.instance_id,
                             choices.map((measure) => ({ value: measure, label: measure })),
                             optionValue(block, "measure"),
                             (value) => adapter.option(block.instance_id, "measure", value));
  return fieldShell("Measure shown", select,
                    "Chooses which saved measure is displayed. It does not change what was "
                    + "analysed.", false);
}

function advancedControls(adapter, block) {
  const wrap = document.createElement("details");
  wrap.className = "advanced";
  const summary = document.createElement("summary");
  summary.textContent = "Advanced display options";
  wrap.append(summary);
  const editable = block.editable || [];
  if (editable.includes("style")) wrap.append(styleControl(adapter, block));
  if (editable.includes("years")) wrap.append(yearsControl(adapter, block));
  return wrap;
}

function styleControl(adapter, block) {
  const current = optionValue(block, "style") || "standard";
  const select = selectField("style-" + block.instance_id,
                             [{ value: "standard", label: STYLE_LABELS.standard },
                              { value: "compact", label: STYLE_LABELS.compact }],
                             current,
                             (value) => {
                               // no-op must not change the recipe
                               if (value === optionValue(block, "style")) return;
                               adapter.option(block.instance_id, "style", value);
                             });
  return fieldShell("Chart height", select,
                    "Changes the figure height only. Values, axes, wording and analytical "
                    + "meaning are unchanged.", false);
}

function yearsControl(adapter, block) {
  const window = block.years_window && block.years_window.length
    ? block.years_window : [];
  const current = optionValue(block, "years") || window;
  const row = document.createElement("div");
  row.className = "field field--wide";
  const start = document.createElement("input");
  start.type = "number";
  start.id = "years-start-" + block.instance_id;
  start.value = current[0] || "";
  start.min = window[0] || "";
  start.max = window[window.length - 1] || "";
  const end = document.createElement("input");
  end.type = "number";
  end.id = "years-end-" + block.instance_id;
  end.value = current[1] || "";
  end.min = window[0] || "";
  end.max = window[window.length - 1] || "";
  const label = document.createElement("label");
  label.textContent = "Years shown (saved reporting window " + window.join("–") + ")";
  label.htmlFor = start.id;
  const buttons = document.createElement("div");
  buttons.className = "buttons buttons--inline";
  buttons.append(
    controlButton("Apply years", "years-apply-" + block.instance_id, null, false,
                  () => adapter.option(block.instance_id, "years",
                                       [Number(start.value), Number(end.value)])),
    controlButton("Use the whole window", "years-reset-" + block.instance_id, null, false,
                  () => adapter.option(block.instance_id, "years", null)));
  const help = document.createElement("p");
  help.className = "field-help";
  help.textContent = "Display window only: it selects saved rows from the same series. It does "
    + "not analyse a new period or change the report scope.";
  row.append(label, start, end, buttons, help);
  return row;
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

async function resetCustom() {
  if (state.mode !== "custom" || !state.context) return;
  const seq = ++state.seq;
  try {
    const doc = await mutate("custom-reset", "/api/custom/reset", { context: state.context });
    if (seq !== state.seq) return;
    el("custom-reset-confirm").hidden = true;
    applyCustom(doc, {});
    setStatus(el("custom-status"), "Reset this context's custom composition. Generated reports, "
      + "other data contexts and audience drafts are kept.", "ok");
    announce("Custom composition reset.");
    loadSaved(true);
  } catch (error) {
    if (seq !== state.seq) return;
    setStatus(el("custom-status"), error.message, "error");
  }
}

/* ------------------------------------------------------------------ custom mode */
function contextLabel(id) {
  const entry = state.presets.find((item) => item.id === id);
  return entry ? entry.label : (id || "this");
}

function topicLabel(topic) {
  const labels = (state.doc && state.doc.topic_labels) || {};
  return labels[topic] || topic;
}

function summarizeSource(source) {
  if (!source) return "";
  const parts = [
    (source.years || []).length ? "Reporting period " + (source.years || []).join("–") : null,
    source.reference_year ? "reference " + source.reference_year : null,
    source.geography || null,
    source.included_topics ? source.included_topics + " diseases in the saved bundle" : null,
    source.snapshot_short ? "saved data " + source.snapshot_short : null,
  ].filter(Boolean);
  const text = parts.join(" · ");
  return source.title ? text + " — " + source.title : text;
}

function controlButton(text, id, label, disabled, handler, className) {
  const node = document.createElement("button");
  node.type = "button";
  if (id) node.id = id;
  node.textContent = text;
  if (label) node.setAttribute("aria-label", label);
  node.disabled = Boolean(disabled);
  if (className) node.className = className;
  node.addEventListener("click", handler);
  return node;
}

async function chooseCustom(context) {
  const query = context
    ? "?context=" + encodeURIComponent(context)
    : (state.audience ? "?audience=" + encodeURIComponent(state.audience) : "");
  const seq = ++state.seq;
  state.mode = "custom";
  state.preset = "custom";
  renderPresets();
  setStatus(el("custom-status"), "Reading the saved context…", "");
  try {
    const doc = await request("/api/custom" + query);
    if (seq !== state.seq) return;
    applyCustom(doc, {});
    setStatus(el("custom-status"), "", "");
  } catch (error) {
    if (seq !== state.seq) return;
    setStatus(el("custom-status"), error.message, "error");
  }
}

function applyCustom(doc, options) {
  const active = document.activeElement && document.activeElement.id;
  state.doc = doc;
  state.mode = "custom";
  state.preset = "custom";
  state.context = doc.context;
  const card = presetEntry("custom");
  if (card) card.customized = doc.different_from_preset;
  el("audience-card").hidden = true;
  el("custom-card").hidden = false;
  el("custom-badge").hidden = true;
  renderCustomBlocks(doc);
  renderPending(doc);
  const repair = el("custom-repair");
  const needs = doc.needs_repair || [];
  repair.hidden = needs.length === 0;
  if (needs.length) {
    el("custom-repair-text").textContent = "This saved draft still refers to sections it no "
      + "longer contains (" + needs.join(", ") + "). Repairing removes only those references; the "
      + "composition, its ids and its settings stay as they are.";
  }
  renderCustomReadiness(doc);
  el("custom-digest").textContent = shortDigest(doc.recipe_sha256);
  el("custom-digest").title = doc.recipe_sha256 || "";
  el("custom-pending-note").textContent = doc.ready ? ""
    : "The saved composition is unchanged; your pending choice blocks generation.";
  renderPresets();
  renderReuse(doc.reuse);
  updateGenerateEnabled();
  markStale();
  if (options && options.openReset === false) el("custom-reset-confirm").hidden = true;
  if (active) {
    const restored = document.getElementById(active);
    if (restored && typeof restored.focus === "function") restored.focus();
  }
}

function defaultsFor(doc, block) {
  const options = {};
  if (block === "reference-comparison") {
    if ((doc.reference_topics || []).length) options.topic = doc.reference_topics[0];
  } else if (block === "series-trend" || block === "series-collection") {
    const measure = (doc.measures || [])[0];
    if (measure) options.measure = measure;
    if (block === "series-trend") {
      const topics = ((doc.topics_by_measure || {})[measure] || []);
      if (topics.length) options.topic = topics[0];
    }
  }
  return options;
}

function conflictingInstance(doc, block) {
  const same = doc.blocks.filter((item) => item.block === block);
  if (same.length) return same[0];
  if (block === "series-trend") {
    return doc.blocks.find((item) => item.block === "series-collection") || null;
  }
  if (block === "series-collection") {
    return doc.blocks.find((item) => item.block === "series-trend") || null;
  }
  return null;
}

/* Block types of the registered library that this draft does not contain yet (and that are not
   already waiting for a choice). They are shown as unchecked rows after the saved sections, so
   every supported type stays discoverable without a separate Add list. */
function absentTypes(doc) {
  const present = new Set(doc.blocks.map((block) => block.block));
  for (const item of doc.pending || []) present.add(item.block);
  return (doc.library || []).filter((item) => !present.has(item.block));
}

function customAdapter(doc) {
  return {
    mode: "custom",
    setIncluded: (id, include) => customAction(include ? "restore" : "remove", id),
    move: (id, direction) => customAction(direction === "up" ? "move-up" : "move-down", id),
    setTopics: (id, topics) => customAction("set-topics", id, topics),
    setDefaultOpen: (id, topic) => customAction("set-default-open", id, topic),
    setTitle: (id, value) => customAction("set-title", id, value),
    // The website speaks "style"/"layout"; the block contract calls them "presentation.*".
    option: (id, name, value) => setOption(
      id, (name === "style" || name === "layout") ? "presentation." + name : name, value),
    canDuplicate: true,
    duplicate: (id) => customAction("duplicate", id),
    canDelete: true,
    deleteInstance: (id) => customAction("delete-instance", id),
    absentTypes: () => absentTypes(doc),
    addType: (block, box, row) => addTypeRow(doc, block, box, row),
  };
}

function renderCustomBlocks(doc) {
  renderSections(doc, customAdapter(doc), el("custom-blocks"));
}

async function addTypeRow(doc, block, box, row) {
  const options = defaultsFor(doc, block);
  box.disabled = true;
  await runCustomAction("add-block", null, { block: block, options: options }, (error) => {
    const conflict = conflictingInstance(doc, block);
    if (error.code === "combination_conflict" && conflict) {
      inlineConfirm(row,
        (error.message || "This section cannot join the report as it stands.")
          + " Replace " + conflict.label + "?",
        "Replace " + conflict.label,
        () => runCustomAction("add-block", null,
          { block: block, options: options, replace: [conflict.instance_id] }));
      return true;
    }
    return false;
  });
  box.disabled = false;
  box.checked = false;                 // the list re-renders on success; on failure, stay off
}

function inlineConfirm(container, message, confirmLabel, onConfirm) {
  let box = container.querySelector(".inline-confirm");
  if (!box) {
    box = document.createElement("div");
    box.className = "inline-confirm";
    container.append(box);
  }
  box.replaceChildren();
  const text = document.createElement("p");
  text.className = "inline-confirm-text";
  text.textContent = message;
  const row = document.createElement("div");
  row.className = "buttons buttons--inline";
  const yes = controlButton(confirmLabel, null, null, false, onConfirm, "danger");
  const no = controlButton("Cancel", null, null, false, () => box.replaceChildren());
  row.append(yes, no);
  box.append(text, row);
  yes.focus();
}

function renderPending(doc) {
  const wrap = el("custom-pending-wrap");
  const list = el("custom-pending");
  list.replaceChildren();
  const pending = doc.pending || [];
  wrap.hidden = pending.length === 0;
  for (const item of pending) {
    const li = document.createElement("li");
    li.className = "block block--pending";
    const head = document.createElement("div");
    head.className = "block-head";
    const title = document.createElement("span");
    title.className = "block-label";
    title.textContent = item.label;
    head.append(title);
    const id = document.createElement("span");
    id.className = "block-id";
    id.textContent = item.instance_id;
    head.append(id);
    li.append(head);
    const problem = document.createElement("p");
    problem.className = "blocking-text";
    problem.textContent = item.problem;
    li.append(problem);
    const controls = document.createElement("div");
    controls.className = "block-controls";
    for (const existing of item.replace || []) {
      const label = (doc.blocks.find((block) => block.instance_id === existing) || {}).label
        || existing;
      controls.append(controlButton("Replace " + label,
                                    "replace-" + item.instance_id + "-" + existing, null, false,
                                    () => customAction("replace-pending", item.instance_id,
                                                       { pending: item.instance_id,
                                                         existing: existing })));
    }
    controls.append(controlButton("Discard", "discard-" + item.instance_id, null, false,
                                  () => customAction("discard-pending", item.instance_id)));
    li.append(controls);
    list.append(li);
  }
}

function renderCustomReadiness(doc) {
  const chip = el("custom-ready");
  const blocking = el("custom-blocking");
  if (doc.ready) {
    chip.textContent = "Ready to generate";
    chip.className = "chip chip--ok";
    blocking.hidden = true;
    blocking.textContent = "";
  } else {
    chip.textContent = "Not ready to generate";
    chip.className = "chip chip--warn";
    blocking.hidden = false;
    blocking.textContent = doc.blocking_reason || "This composition cannot be generated yet.";
  }
}

async function customAction(action, instance, value) {
  return runCustomAction(action, instance, value);
}

async function runCustomAction(action, instance, value, onError) {
  if (state.mode !== "custom" || !state.context) return;
  const seq = ++state.seq;
  setStatus(el("custom-status"), "Saving…", "");
  try {
    const doc = await mutate("custom-edit", "/api/custom/edit",
      { context: state.context, action: action, instance: instance, value: value });
    if (seq !== state.seq) return;
    applyCustom(doc, {});
    setStatus(el("custom-status"), "Saved. The composition is this context's own draft.", "ok");
    for (const note of doc.notes || []) {
      if (note.kind === "default-open-moved") {
        announce("The expanded disease moved to " + note.to + " because " + note.from
          + " is no longer checked.");
      } else if (note.kind === "default-open-cleared") {
        announce("No disease is checked, so the expanded disease was cleared.");
      }
    }
  } catch (error) {
    if (seq !== state.seq) return;
    if (onError && onError(error)) {
      setStatus(el("custom-status"), error.message, "error");
      announce(error.message);
      return;
    }
    setStatus(el("custom-status"), error.message, "error");
    announce(error.message);
    if (state.doc) applyCustom(state.doc, {});
  }
}

function setOption(instance, option, value) {
  return customAction("set-option", instance, { option: option, value: value });
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
  meta.textContent = "Generated " + when + " · " + compositionWord(reuse.classification)
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

function compositionWord(classification) {
  if (classification === "custom") return "custom-library";
  if (classification === "customized") return "customized";
  return "default";
}

function reportLabel(job) {
  if (job.origin === "custom" || job.preset === "custom") {
    return "Custom report · " + contextLabel(job.context) + " data context";
  }
  const entry = presetEntry(job.preset) || { label: job.preset };
  return entry.label + " " + compositionWord(job.classification) + " composition";
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
  state.rendered = { digest: job.recipe_sha256, preset: job.preset,
                     context: job.context || null, label: reportLabel(job),
                     classification: job.classification, job_id: job.job_id };
}

async function showHere() {
  const reuse = state.doc && state.doc.reuse;
  if (!reuse || !reuse.available) return;
  const seq = ++state.seq;
  const mode = state.mode;
  const context = state.context;
  setStatus(el("generate-status"), "Checking that report…", "");
  try {
    const body = mode === "custom"
      ? { preset: "custom", context: context, job_id: reuse.job_id }
      : { preset: state.preset, job_id: reuse.job_id };
    const job = await mutate("reuse", "/api/reuse", body);
    if (seq !== state.seq) return;
    const already = state.rendered && state.rendered.job_id === job.job_id;
    displayReport(Object.assign({ preset: state.preset, context: context }, job));
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
  const changed = rendered.digest !== current || rendered.preset !== state.preset
    || (rendered.context || null) !== (state.context || null);
  node.hidden = !changed;
  node.textContent = changed
    ? "The report on screen was generated from the " + rendered.label + " (recipe "
      + shortDigest(rendered.digest) + "). The choices now differ; generate again to refresh it."
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
    const body = state.mode === "custom"
      ? { preset: "custom", context: state.context }
      : { preset: state.preset };
    const job = await mutate("generate", "/api/generate", body);
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
      state.rendered = { digest: job.recipe_sha256, preset: job.preset,
                         context: job.context, label: reportLabel(job),
                         classification: job.classification, job_id: job.job_id };
      const frame = el("report-frame");
      frame.hidden = false;
      frame.src = job.report_url + "?job=" + encodeURIComponent(job.job_id);
      el("open-report").hidden = false;
      el("open-report").href = job.report_url;
      el("report-empty").textContent = "";
      el("job-digest").textContent = shortDigest(job.recipe_sha256);
      el("job-digest").title = job.recipe_sha256;
      setStatus(el("generate-status"), "Generated the " + reportLabel(job) + " (recipe "
        + shortDigest(job.recipe_sha256) + ") at " + job.finished_utc + ".", "ok");
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
  const mode = state.mode;
  const context = state.context;
  const preset = state.preset;
  const seq = ++state.seq;
  try {
    const doc = mode === "custom"
      ? await request("/api/custom?context=" + encodeURIComponent(context))
      : await request("/api/editor?preset=" + encodeURIComponent(preset));
    if (seq !== state.seq) return;
    if (mode === "custom") applyCustom(doc, {});
    else applyDocument(doc, {});
  } catch (error) {
    setStatus(el("edit-status"), error.message, "error");
  }
}

/* ------------------------------------------------------------------ CSV (Your CSV) mode */

// The neutral vocabulary the CSV composer offers, derived from the library on the server.
const CSV_TYPE_ORDER = ["intro", "data-overview", "values-by-group", "values-over-time",
                        "coverage-over-time", "data-quality", "limitations", "reproduction"];
const CSV_TYPE_LABELS = {
  intro: "Report context", "data-overview": "Dataset overview",
  "values-by-group": "Values by group", "values-over-time": "Values over time",
  "coverage-over-time": "Observation coverage over time",
  "data-quality": "Data quality and completeness", limitations: "Limitations and cautions",
  reproduction: "Reproduction and evidence",
};
const CSV_REQUIRED = { limitations: "Required: every report states its limitations and cautions." };

function csvStatus(node, message, kind) {
  node.textContent = message;
  node.className = "status" + (kind ? " " + kind : "");
  node.hidden = !message && kind !== "ok";
}

function switchRoute(route) {
  state.route = route;
  el("route-health").setAttribute("aria-selected", String(route === "health"));
  el("route-csv").setAttribute("aria-selected", String(route === "csv"));
  el("health-panel").hidden = route !== "health";
  el("csv-panel").hidden = route !== "csv";
  if (route === "csv" && !state.csvDocument) loadCsv();
}

async function loadCsv() {
  try {
    const doc = await request("/api/csv");
    state.csvDocument = doc;
    renderDatasetList(doc);
  } catch (error) {
    csvStatus(el("csv-generate-status"), error.message, "error");
  }
}

function renderDatasetList(doc) {
  const node = el("csv-datasets");
  node.replaceChildren();
  const datasets = doc.datasets || [];
  state.csvDatasets = datasets;
  if (!datasets.length) {
    const hint = document.createElement("p");
    hint.className = "hint";
    hint.textContent = "No captured tables yet. Upload one below.";
    node.append(hint);
    return;
  }
  const list = document.createElement("div");
  list.className = "dataset-list" + (state.csvDatasetsOpen ? " dataset-list--open" : "");
  list.id = "csv-dataset-scroll";
  for (const item of datasets) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "dataset-row" + (item.digest === state.csvDigest ? " is-selected" : "");
    card.setAttribute("role", "tab");
    card.setAttribute("aria-selected", String(item.digest === state.csvDigest));
    const count = item.record_count === null || item.record_count === undefined
      ? "?" : item.record_count;
    const name = document.createElement("span");
    name.className = "dataset-name-text";
    name.textContent = item.source_filename;
    name.title = item.source_filename;
    const meta = document.createElement("span");
    meta.className = "dataset-meta";
    meta.textContent = count + " records"
      + (item.confirmed ? " · confirmed" : " · awaiting confirmation");
    card.append(name, meta);
    card.addEventListener("click", () => selectDataset(item.digest));
    list.append(card);
  }
  node.append(list);
  const toggle = el("csv-datasets-toggle");
  toggle.hidden = datasets.length <= 1;
  toggle.setAttribute("aria-expanded", String(Boolean(state.csvDatasetsOpen)));
  toggle.textContent = state.csvDatasetsOpen
    ? "Collapse list" : "Show all " + datasets.length + " datasets";
  if (state.csvDatasetsOpen) list.classList.add("dataset-list--open");
  else list.classList.remove("dataset-list--open");
}

async function selectDataset(digest) {
  state.csvDigest = digest;
  state.csvDisplayDraft = {};
  state.csvJob = null;
  el("csv-sources").disabled = true;
  state.csvSelectionToken = (state.csvSelectionToken || 0) + 1;
  const token = state.csvSelectionToken;
  try {
    const doc = await request("/api/csv?digest=" + encodeURIComponent(digest));
    if (token !== state.csvSelectionToken || digest !== state.csvDigest) return;
    state.csvDocument = doc;
    renderDatasetList(doc);
    renderCsvPipeline(doc);
  } catch (error) {
    csvStatus(el("csv-generate-status"), error.message, "error");
  }
}

function renderCsvDatasetHeader(doc) {
  const node = el("csv-dataset-header");
  const confirmation = doc.confirmation || {};
  const dataset = confirmation.dataset || {};
  if (!dataset.source_filename) { node.hidden = true; node.replaceChildren(); return; }
  node.hidden = false;
  node.replaceChildren();
  const name = document.createElement("p");
  name.className = "dataset-name";
  name.textContent = dataset.source_filename;
  const facts = [];
  const count = dataset.record_count;
  facts.push(count === null || count === undefined ? "record count not established"
                                                   : count + " records");
  if (doc.analysis) {
    facts.push(doc.analysis.group_count + " groups");
    const time = doc.analysis.time || {};
    if (time.has_time && time.period_count) {
      const periods = time.periods || [];
      const from = periods.length ? periods[0].slice(0, 4) : null;
      const to = periods.length ? periods[periods.length - 1].slice(0, 4) : null;
      facts.push(from && to ? from + "–" + to : time.period_count + " periods");
    }
    facts.push("Interpretation confirmed");
  } else if (confirmation.confirmation) {
    facts.push("Interpretation confirmed");
  } else {
    facts.push("Interpretation not confirmed");
  }
  const line = document.createElement("p");
  line.className = "dataset-facts";
  line.textContent = facts.join(" · ");
  const actions = document.createElement("p");
  actions.className = "dataset-actions";
  const change = document.createElement("button");
  change.type = "button";
  change.className = "ghost";
  change.textContent = "Change dataset";
  change.addEventListener("click", () => {
    el("csv-setup-details").open = true;
    const first = el("csv-datasets").querySelector?.("button");
    if (first && first.focus) first.focus();
  });
  const review = document.createElement("button");
  review.type = "button";
  review.className = "ghost";
  review.textContent = "Review interpretation";
  review.addEventListener("click", () => {
    el("csv-interpretation-details").open = true;
    const select = el("csv-confirm-category");
    if (select && select.focus) select.focus();
  });
  actions.append(change, review);
  node.append(name, line, actions);
}

function renderCsvDisclosureSummary(doc) {
  const summary = el("csv-disclosure-summary");
  const warning = el("csv-disclosure-warning");
  const current = doc.disclosure || null;
  if (!current) {
    summary.textContent = "No disclosure policy chosen yet — generation stays blocked until "
      + "you choose one.";
    summary.className = "disclosure-summary disclosure-summary--warn";
    warning.hidden = true;
  } else {
    const label = current.policy === "local-audit" ? "Local audit" : "Restricted share";
    summary.textContent = label
      + " · " + (current.permit_values ? "Numerical values included" : "Numerical values excluded")
      + " · " + (current.permit_records ? "Contributing records included"
                                        : "Contributing records excluded");
    summary.className = "disclosure-summary";
    warning.hidden = false;
    warning.textContent = current.policy === "local-audit"
      ? "Local audit output is not private once shared."
      : "Withheld values do not make this output anonymous or universally safe.";
  }
  const conflicts = doc.disclosure_conflicts || [];
  if (conflicts.length) {
    el("csv-disclosure-more").hidden = false;
    el("csv-disclosure-toggle").setAttribute("aria-expanded", "true");
  }
}

function renderCsvPipeline(doc) {
  renderDatasetList(doc);
  renderCsvDatasetHeader(doc);
  renderCsvDisclosureSummary(doc);
  const confirmation = doc.confirmation || {};
  if (confirmation.preview) {
    renderCsvPreview(confirmation.preview);
    el("csv-preview-block").hidden = false;
    el("csv-preview-wrap").hidden = false;
    if (state.csvPreviewDigest !== doc.selected_digest) {
      state.csvPreviewDigest = doc.selected_digest;
      const wrap = el("csv-preview-wrap");
      if (wrap) { wrap.scrollTop = 0; wrap.scrollLeft = 0; }
    }
  } else {
    el("csv-preview-block").hidden = true;
  }
  el("csv-setup-details").open = !doc.analysis;
  el("csv-interpretation-details").open = !doc.analysis;
  if (doc.analysis) {
    el("csv-compose-card").hidden = false;
    el("csv-disclosure-card").hidden = false;
    renderCsvPassport(confirmation, doc.analysis);
    renderCsvConfirm(doc);
    renderCsvDisclosure(doc);
    renderCsvComposer(doc);
    renderCsvHistory(doc);
  } else {
    el("csv-confirm-card").hidden = false;
    renderCsvPassport(confirmation, null);
    renderCsvConfirm(doc);
    el("csv-compose-card").hidden = true;
  }
}

function renderCsvPreview(preview) {
  const node = el("csv-preview");
  node.replaceChildren();
  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  for (const column of preview.preview_columns) {
    const th = document.createElement("th");
    th.scope = "col";
    th.textContent = column;
    th.title = column;
    headRow.append(th);
  }
  thead.append(headRow);
  table.append(thead);
  const tbody = document.createElement("tbody");
  for (const row of preview.preview_rows) {
    const tr = document.createElement("tr");
    for (const cell of row) {
      const td = document.createElement("td");
      td.textContent = cell;
      if (String(cell || "").length > 40) td.title = cell;
      tr.append(td);
    }
    tbody.append(tr);
  }
  table.append(tbody);
  node.append(table);

  const shown = preview.preview_rows.length;
  const total = preview.logical_records;
  const complete = !preview.preview_truncated_rows && !preview.preview_truncated_columns;
  el("csv-preview-summary").textContent = (preview.source_filename || "captured table")
    + " · " + total + " logical records · "
    + (complete ? "showing all " + shown + " records"
                : "showing " + shown + " of " + total + " records (bounded preview)")
    + (preview.preview_truncated_columns
      ? " · " + preview.preview_truncated_columns + " further columns not shown" : "")
    + " · digest " + shortDigest(preview.input_sha256);
  const note = el("csv-preview-note");
  note.textContent = complete
    ? "The whole captured table is shown in this structural preview; scroll within the table to "
      + "inspect records."
    : "Only a bounded portion is available in this structural preview; vertical scrolling does "
      + "not reveal further records.";
}

function renderCsvPassport(confirmation, analysis) {
  const node = el("csv-passport");
  node.replaceChildren();
  const dataset = confirmation.dataset || {};
  const preview = confirmation.preview || {};
  const count = dataset.record_count === null || dataset.record_count === undefined
    ? (preview.logical_records === null || preview.logical_records === undefined
      ? "?" : preview.logical_records)
    : dataset.record_count;
  const title = document.createElement("p");
  title.className = "hint";
  title.textContent = "Dataset passport — captured file " + dataset.source_filename
    + " · " + count + " records · content digest "
    + shortDigest(dataset.input_sha256) + " · captured " + (dataset.captured_at_utc || "?")
    + " (UTC). The file name is not its identity and the capture time is not an observation "
    + "date. Attribution and version statements are user-supplied.";
  node.append(title);
  if (analysis) {
    const confirmed = confirmation && confirmation.confirmation;
    const summary = document.createElement("p");
    summary.className = "hint";
    summary.textContent = "Confirmed reading: group column "
      + String((confirmed && confirmed.category) || "none")
      + ", measure " + (analysis.measure ? analysis.measure.label : "—")
      + (analysis.time && analysis.time.column ? ", time column " + analysis.time.column : "")
      + ". " + analysis.row_count + " records, " + analysis.group_count + " groups.";
    node.append(summary);
  }
}

function csvColumns(doc) {
  const preview = doc.confirmation && doc.confirmation.preview;
  return preview ? preview.columns : [];
}

function columnSelect(id, columns, current, onChange) {
  const select = document.createElement("select");
  select.id = id;
  const none = document.createElement("option");
  none.value = "";
  none.textContent = "(none)";
  select.append(none);
  for (const column of columns) {
    const option = document.createElement("option");
    option.value = column;
    option.textContent = column;
    if (column === current) option.selected = true;
    select.append(option);
  }
  select.addEventListener("change", () => onChange(select.value));
  return select;
}

function textField(id, value, placeholder) {
  const input = document.createElement("input");
  input.id = id;
  input.type = "text";
  input.value = value || "";
  input.placeholder = placeholder || "";
  return input;
}

function renderCsvConfirm(doc) {
  const node = el("csv-confirm");
  node.replaceChildren();
  const confirmed = doc.confirmation && doc.confirmation.confirmation;
  const suggestion = doc.confirmation ? doc.confirmation.suggestion : {};
  const columns = csvColumns(doc);
  const current = {
    category: confirmed ? confirmed.category : (suggestion.category || ""),
    measure: confirmed ? confirmed.measure : (suggestion.measure || ""),
    time: confirmed ? confirmed.time : (suggestion.time || ""),
    label: confirmed ? confirmed.measure_label || "" : "",
    unit: confirmed ? confirmed.unit || "" : "",
    meaning: confirmed ? confirmed.meaning || "" : "",
    tokens: confirmed ? (confirmed.missing_tokens || []).join(", ") : "",
  };
  const card = document.createElement("fieldset");
  const legend = document.createElement("legend");
  legend.textContent = confirmed
    ? "Confirmed interpretation (edit to change; a change re-validates the analysis)"
    : "Confirm how the table is read";
  card.append(legend);
  const groupField = fieldShell("Group column (what one row is grouped by)",
                                columnSelect("csv-confirm-category", columns, current.category,
                                  () => {}), "");
  const measureField = fieldShell("Measure column (numeric)",
                                  columnSelect("csv-confirm-measure", columns, current.measure,
                                    () => {}), "");
  const timeField = fieldShell("Time column (optional)",
                               columnSelect("csv-confirm-time", columns, current.time,
                                 () => {}), "Optional. Whole years (2021) or ISO dates.");
  card.append(groupField, measureField, timeField,
              fieldShell("Measure label", textField("csv-confirm-label", current.label,
                "Observed value"), "Readable name shown in the report."),
              fieldShell("Unit", textField("csv-confirm-unit", current.unit,
                "not specified"), "Keep 'not specified' when the unit is unknown."),
              fieldShell("One row represents", textField("csv-confirm-meaning", current.meaning,
                "a single supplied observation (or not specified)"),
                "State what one record means. Unknown may stay 'not specified'."),
              fieldShell("Declared missing tokens (comma separated)",
                         textField("csv-confirm-tokens", current.tokens),
                         "Blank cells are always missing. Literal NA/null are data unless listed."));
  const buttons = document.createElement("div");
  buttons.className = "buttons";
  const confirm = document.createElement("button");
  confirm.type = "button";
  confirm.className = "primary";
  confirm.textContent = confirmed ? "Update interpretation" : "Accept interpretation";
  confirm.addEventListener("click", () => submitInterpretation(doc));
  buttons.append(confirm);
  card.append(buttons);
  node.append(card);
}

async function submitInterpretation(doc) {
  const digest = state.csvDigest;
  const tokens = (el("csv-confirm-tokens").value || "")
    .split(",").map((token) => token.trim()).filter(Boolean);
  const interpretation = {
    category: el("csv-confirm-category").value,
    measure: el("csv-confirm-measure").value,
    time: el("csv-confirm-time").value || null,
    measure_label: el("csv-confirm-label").value || null,
    unit: el("csv-confirm-unit").value || null,
    meaning: el("csv-confirm-meaning").value || null,
    missing_tokens: tokens,
  };
  try {
    const result = await mutate("csv-confirm", "/api/csv/confirm",
                                { digest, interpretation });
    setStatus(el("csv-confirm-status"),
              "Interpretation confirmed; the analysis was prepared and saved.",
              "ok");
    const fresh = await request("/api/csv?digest=" + encodeURIComponent(digest));
    state.csvDocument = fresh;
    renderCsvPipeline(fresh);
  } catch (error) {
    csvStatus(el("csv-confirm-status"), error.message, "error");
    announce(error.message);
  }
}

function renderCsvDisclosure(doc) {
  // Built once per page, then updated in place: rebuilding on every edit would drop keyboard
  // focus from the policy radio or the records checkbox.
  const node = el("csv-disclosure");
  const options = doc.disclosure_options || [];
  const signature = options.map((entry) => entry.policy).join("|");
  if (node.dataset.signature !== signature) {
    node.replaceChildren();
    node._inputs = {};
    const legend = document.createElement("legend");
    legend.className = "visually-hidden";
    legend.textContent = "Disclosure policy";
    node.append(legend);
    for (const option of options) {
      const id = "csv-policy-" + option.policy;
      const wrap = document.createElement("label");
      wrap.className = "disclosure-option";
      wrap.htmlFor = id;
      const input = document.createElement("input");
      input.type = "radio";
      input.name = "csv-disclosure-policy";
      input.id = id;
      input.value = option.policy;
      input.addEventListener("change", () => {
        if (input.checked) csvEdit("set-disclosure", null, { policy: option.policy });
      });
      const text = document.createElement("span");
      const title = document.createElement("strong");
      title.textContent = option.label;
      const summary = document.createElement("span");
      summary.className = "disclosure-summary";
      summary.textContent = option.summary;
      text.append(title, summary);
      wrap.append(input, text);
      node.append(wrap);
      node._inputs[option.policy] = input;
    }
    node.dataset.signature = signature;
  }
  const current = doc.disclosure || null;
  for (const option of options) {
    const input = node._inputs && node._inputs[option.policy];
    if (input) input.checked = Boolean(current && current.policy === option.policy);
  }
  const detail = el("csv-disclosure-detail");
  detail.replaceChildren();
  const option = options.find((entry) => current && entry.policy === current.policy);
  if (!current) {
    const note = document.createElement("p");
    note.className = "hint";
    note.textContent = "No choice recorded yet. Choose one of the policies above before "
      + "generating; the server refuses a report whose sections do not fit the chosen policy.";
    detail.append(note);
  } else if (option) {
    const note = document.createElement("p");
    note.className = "disclosure-consequence";
    note.textContent = option.detail;
    detail.append(note);
    if (option.permits_records) {
      const label = document.createElement("label");
      label.className = "check";
      const box = document.createElement("input");
      box.type = "checkbox";
      box.id = "csv-permit-records";
      box.checked = Boolean(current.permit_records);
      box.addEventListener("change", () => {
        csvEdit("set-disclosure", null,
                { policy: current.policy, permit_records: box.checked });
      });
      const text = document.createElement("span");
      text.textContent = "Also download the contributing records "
        + "(data/selected-records.csv in the evidence package)";
      label.append(box, text);
      detail.append(label);
    }
  }
  const conflicts = doc.disclosure_conflicts || [];
  const banner = el("csv-disclosure-conflicts");
  banner.textContent = conflicts.map((item) => item.message).join(" ");
  banner.hidden = conflicts.length === 0;
}


// ---- per-instance display settings (presentation only) ------------------------------------
const CSV_LAYOUT_LABELS = {
  table: "Table",
  chart: "Chart",
  "chart-and-table": "Chart and table",
  panels: "Panels by group",
  combined: "Combined chart",
};



// ---- Previously generated reports for this dataset -------------------------------------------
const CSV_REUSE_LABELS = {
  match: "Matches current settings",
  different: "Different settings",
  unknown: "Reuse identity not recorded",
  unavailable: "Not reusable now",
};

function csvHistoryRow(item) {
  const row = document.createElement("li");
  const head = document.createElement("div");
  head.className = "saved-head";
  const title = document.createElement("strong");
  const when = humanTime(item.created_utc);
  title.textContent = (item.titles && item.titles.length ? item.titles[0] : "Generated report");
  const meta = document.createElement("span");
  meta.className = "hint";
  meta.textContent = when + " · CSV · " + (item.preview ? "preview" : "review render")
    + (item.policy && item.policy.policy ? " · " + (item.policy.label || item.policy.policy) : "");
  head.append(title, meta);
  row.append(head);

  const details = document.createElement("details");
  details.className = "saved-details";
  const toggle = document.createElement("summary");
  toggle.textContent = "Show details";
  details.append(toggle);
  const body = document.createElement("div");
  body.className = "saved-details-body";
  details.append(body);
  const datasetLine = document.createElement("p");
  datasetLine.className = "hint";
  datasetLine.textContent = (item.dataset && item.dataset.filename ? item.dataset.filename : "")
    + " · " + String((item.dataset && item.dataset.digest) || "").slice(0, 12)
    + " · " + when;
  body.append(datasetLine);

  const chips = document.createElement("p");
  chips.className = "saved-reuse";
  const state = (item.reuse && item.reuse.state) || "unknown";
  const chip = document.createElement("span");
  chip.className = "chip " + (state === "match" ? "chip--ok" : "chip--warn");
  chip.textContent = CSV_REUSE_LABELS[state] || state;
  const why = document.createElement("span");
  why.className = "hint";
  why.textContent = (item.reuse && item.reuse.reason) || "";
  chips.append(chip, why);
  body.append(chips);

  if (item.policy && item.policy.policy) {
    const permissions = document.createElement("p");
    permissions.className = "hint";
    permissions.textContent = "Values " + (item.policy.permit_values ? "included" : "excluded")
      + " · contributing records " + (item.policy.permit_records ? "included" : "excluded");
    body.append(permissions);
  }

  if (item.links && item.links.report) {
    const actions = document.createElement("div");
    actions.className = "saved-actions";
    const show = document.createElement("button");
    show.type = "button";
    show.className = "ghost";
    show.textContent = "Show here";
    show.addEventListener("click", () => {
      state.csvJob = { job_id: item.job_id, report_url: item.links.report };
      displayCsvReport(state.csvJob);
      el("csv-sources").disabled = false;
      csvStatus(el("csv-generate-status"),
        "Showing a saved report. Your current settings may differ; generate to update the preview.",
        "");
    });
    const open = document.createElement("a");
    open.href = item.links.report;
    open.target = "_blank";
    open.rel = "noopener";
    open.textContent = "Open report";
    const sources = document.createElement("button");
    sources.type = "button";
    sources.className = "ghost";
    sources.textContent = "Data & sources";
    sources.addEventListener("click", () => openSources(item.job_id, sources));
    const copy = document.createElement("button");
    copy.type = "button";
    copy.className = "ghost";
    copy.textContent = "Edit a copy";
    copy.addEventListener("click", () => csvCopyComposition(item, copy));
    actions.append(show, open, sources, copy);
    body.append(actions);
  }
  row.append(details);
  return row;
}

function renderCsvHistory(doc) {
  const card = el("csv-history-card");
  if (!doc || !doc.analysis) { card.hidden = true; return; }
  card.hidden = false;
  const list = el("csv-history");
  list.replaceChildren();
  const history = doc.history || { items: [] };
  el("csv-history-empty").hidden = (history.items || []).length > 0;
  for (const item of history.items || []) list.append(csvHistoryRow(item));
  const displayed = state.csvJob && state.csvJob.job_id;
  if (!displayed) {
    el("csv-report-empty").textContent = (history.items || []).length
      ? "No report is currently displayed. Previously generated reports are available below."
      : "No reports generated yet for this dataset.";
  }
  if (history.truncated) {
    const note = document.createElement("p");
    note.className = "hint";
    note.textContent = "Showing the " + (history.limit || 20) + " most recent of "
      + history.total + " reports for this dataset.";
    list.append(note);
  }
}

async function csvCopyComposition(item, opener, confirm) {
  const digest = state.csvDigest;
  if (!digest) return;
  try {
    const result = await mutate("csv-edit", "/api/csv/edit",
      { digest, action: "restore-composition", instance: null,
        value: { job_id: item.job_id, confirm: Boolean(confirm) } });
    el("csv-copy-confirm").hidden = true;
    state.csvDocument = result.document;
    renderCsvPipeline(result.document);
    csvStatus(el("csv-history-status"),
      "Copied this report's section settings into the current draft. The report itself is unchanged.",
      "ok");
  } catch (error) {
    if ((error.code === "draft_has_edits" || error.code === "context_changed") && !confirm) {
      state.csvCopyPending = { item, opener };
      el("csv-copy-confirm-text").textContent =
        "This replaces the current editable draft with this report's saved configuration. "
        + "The historical report itself is not changed. " + error.message;
      el("csv-copy-confirm").hidden = false;
      el("csv-copy-confirm-yes").focus();
      return;
    }
    csvStatus(el("csv-history-status"), error.message, "error");
  }
}

function csvCopyCancel() {
  el("csv-copy-confirm").hidden = true;
  const opener = state.csvCopyPending && state.csvCopyPending.opener;
  state.csvCopyPending = null;
  if (opener && opener.focus) opener.focus();
}

// ---- Data & sources: report-bound, read-only ------------------------------------------------
const SOURCE_LINK_PREFIX = "/";

function sourcesSection(title, open) {
  const section = document.createElement("details");
  section.className = "sources-group";
  section.open = Boolean(open);
  const heading = document.createElement("summary");
  heading.textContent = title;
  section.append(heading);
  return section;
}

function sourcesRows(pairs) {
  const list = document.createElement("dl");
  list.className = "sources-rows";
  for (const [label, value] of pairs) {
    if (value === null || value === undefined || value === "") continue;
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    // Duck-typed on purpose: keeps this file usable in the DOM harness sandbox.
    if (value && typeof value === "object" && value.tagName) dd.append(value);
    else dd.textContent = String(value);
    list.append(dt, dd);
  }
  return list;
}

function sourcesDigest(value) {
  if (!value) return null;
  const code = document.createElement("code");
  code.className = "digest-full";
  code.textContent = value;
  code.title = value;
  return code;
}

function sourcesLink(href, label, download) {
  if (typeof href !== "string" || href.indexOf(SOURCE_LINK_PREFIX) !== 0) return null;
  const link = document.createElement("a");
  link.href = href;
  link.textContent = label;
  if (download) link.setAttribute("download", "");
  else { link.target = "_blank"; link.rel = "noopener"; }
  return link;
}

function sourcesStatusText(status, detail) {
  const map = {
    recorded: "Recorded",
    verified_now: "Checked now",
    unavailable: "Not available",
    missing: "Missing",
    withheld: "Withheld",
    integrity_failed: "Integrity check failed",
    unreadable: "Unreadable",
    unsupported: "Unsupported metadata version",
  };
  return map[status] || status;
}

function renderSources(doc) {
  const body = el("sources-body");
  body.replaceChildren();
  const report = doc.report || {};
  el("sources-note").textContent = report.note || "";

  const head = document.createElement("div");
  head.className = "sources-head-block";
  const title = document.createElement("h3");
  title.textContent = (doc.data && doc.data.filename) || "Saved report";
  head.append(title);
  const facts = [];
  facts.push(["Generated", report.created_utc || "Not recorded"]);
  facts.push(["Report", report.job_id]);
  facts.push(["Profile / mode", report.profile || report.mode || "Not recorded"]);
  if (report.preview) facts.push(["Status", report.preview_notice || "Preview render — not an accepted publication."]);
  if (doc.disclosure && doc.disclosure.recorded) {
    facts.push(["Disclosure policy", doc.disclosure.label || doc.disclosure.policy]);
  } else if (doc.data && doc.data.kind === "neutral") {
    facts.push(["Disclosure policy", "Not recorded for this report"]);
  }
  if (report.package_sha256) {
    const code = document.createElement("code");
    code.className = "digest-full";
    code.textContent = report.package_sha256;
    facts.push(["Package digest", code]);
  }
  head.append(sourcesRows(facts));
  body.append(head);

  if ((doc.notices || []).length) {
    const notices = document.createElement("ul");
    notices.className = "sources-notices";
    for (const note of doc.notices) {
      const item = document.createElement("li");
      item.textContent = note;
      notices.append(item);
    }
    body.append(notices);
  }

  // A. Data
  const dataSection = sourcesSection("Data", true);
  const data = doc.data || {};
  const dataRows = [];
  if (data.kind === "neutral") {
    dataRows.push(["Captured file", data.filename]);
    if (data.digest) dataRows.push(["Full source digest", sourcesDigest(data.digest)]);
    dataRows.push(["Captured", data.captured_at_utc]);
    dataRows.push(["Observation time", data.measured_at || "Not recorded (capture time is not an observation date)"]);
    dataRows.push(["Dataset version", data.user_version || "Not recorded"]);
    if (data.roles) {
      dataRows.push(["Confirmed group column", data.roles.category || "none"]);
      dataRows.push(["Confirmed measure column", data.roles.measure || "none"]);
      dataRows.push(["Confirmed time column", data.roles.time || "none (snapshot)"]);
      if ((data.roles.missing_tokens || []).length) {
        dataRows.push(["Declared missing tokens", data.roles.missing_tokens.join(", ")]);
      }
    }
    if (data.measure) {
      dataRows.push(["Measure", data.measure.label || "Not recorded"]);
      dataRows.push(["Unit", data.measure.unit || "Not recorded"]);
      dataRows.push(["Row meaning", data.measure.meaning || "Not recorded"]);
    }
    dataRows.push(["Analytical filters", data.filters]);
    if (data.counts) {
      dataRows.push(["Analysed records", data.counts.analysed_records]);
      dataRows.push(["Analysed groups", data.counts.analysed_groups]);
      dataRows.push(["Analysed periods", data.counts.analysed_periods]);
    }
    if (data.coverage) {
      dataRows.push(["Observation coverage", (data.coverage.from || "—") + " to " + (data.coverage.to || "—")]);
    }
  } else {
    dataRows.push(["Dataset", data.filename || "Read from the saved analysis bundle"]);
    if (data.digest) dataRows.push(["Snapshot id", sourcesDigest(data.digest)]);
    dataRows.push(["Retrieved", data.captured_at_utc]);
    if (data.measured_at && data.measured_at.publishing_date_range) {
      dataRows.push(["Publishing dates", data.measured_at.publishing_date_range.join(" to ")]);
    }
    if (data.counts) {
      dataRows.push(["Datasets used", data.counts.datasets_used]);
      dataRows.push(["Datasets in snapshot", data.counts.datasets_in_snapshot]);
    }
    if (data.filters) {
      const pre = document.createElement("code");
      pre.className = "sources-json";
      pre.textContent = JSON.stringify(data.filters, null, 1);
      dataRows.push(["Analytical filters", pre]);
    }
  }
  dataSection.append(sourcesRows(dataRows));

  if ((doc.sections || []).length) {
    const scope = document.createElement("div");
    scope.className = "sources-scope";
    const scopeTitle = document.createElement("h4");
    scopeTitle.textContent = "Displayed scope in this report";
    scope.append(scopeTitle);
    const list = document.createElement("ul");
    for (const entry of doc.sections) {
      const item = document.createElement("li");
      if (entry.block === "display_scope") {
        item.textContent = "Displayed topics: " + entry.displayed_topics
          + " · group summaries: " + entry.group_summaries
          + " · monitoring topics: " + entry.monitoring_topics;
      } else {
        const parts = [];
        if (entry.groups) parts.push(entry.groups.shown + " of " + entry.groups.analysed + " analysed groups");
        if (entry.periods) parts.push(entry.periods.shown + " of " + entry.periods.analysed + " analysed periods");
        item.textContent = (entry.title || entry.instance_id || entry.block)
          + " — " + (parts.join(" · ") || "all analysed content")
          + (entry.layout ? " · " + entry.layout : "");
      }
      list.append(item);
    }
    scope.append(list);
    dataSection.append(scope);
  }
  body.append(dataSection);

  // artifacts included in this package
  const artifacts = doc.artifacts || [];
  if (artifacts.length) {
    const wrap = document.createElement("div");
    wrap.className = "sources-artifacts";
    const heading = document.createElement("h4");
    heading.textContent = "Files in this report package";
    wrap.append(heading);
    const list = document.createElement("ul");
    for (const entry of artifacts) {
      const item = document.createElement("li");
      const link = sourcesLink(entry.href, entry.label, true);
      if (link) item.append(link);
      else item.textContent = entry.label + " (unavailable)";
      if (entry.bytes !== undefined) {
        const size = document.createElement("span");
        size.className = "hint";
        size.textContent = " · " + Math.round(entry.bytes / 1024) + " KB";
        item.append(size);
      }
      list.append(item);
    }
    wrap.append(list);
    body.append(wrap);
  }

  // retained steward-only material
  const retained = doc.retained || { available: false, reason: "not_applicable" };
  const retainedOpen = !retained.available
    || (retained.items || []).some((item) => item.status === "integrity_failed")
    || (retained.withheld || []).some((item) => item.status === "integrity_failed");
  const retainedSection = document.createElement("details");
  retainedSection.className = "sources-group";
  retainedSection.open = retainedOpen;
  const retainedTitle = document.createElement("summary");
  retainedTitle.textContent = "Retained locally (steward only)";
  retainedSection.append(retainedTitle);
  const retainedNote = document.createElement("p");
  retainedNote.className = "hint";
  retainedNote.textContent = retained.detail || "";
  retainedSection.append(retainedNote);
  if (retained.available && (retained.items || []).length) {
    const list = document.createElement("ul");
    for (const entry of retained.items) {
      const item = document.createElement("li");
      if (entry.href) {
        const link = sourcesLink(entry.href, entry.label, true);
        if (link) item.append(link);
      } else {
        item.textContent = entry.label;
      }
      const state = document.createElement("span");
      state.className = "hint";
      state.textContent = " · " + sourcesStatusText(entry.status, entry.detail)
        + (entry.detail ? " — " + entry.detail : "");
      item.append(state);
      list.append(item);
    }
    retainedSection.append(list);
  }
  if (retained.available && (retained.current || []).length) {
    const heading = document.createElement("h5");
    heading.textContent = "Current workspace material — differs from this report";
    retainedSection.append(heading);
    const list = document.createElement("ul");
    for (const entry of retained.current) {
      const item = document.createElement("li");
      item.textContent = entry.label + " — " + (entry.detail || "differs from this report");
      list.append(item);
    }
    retainedSection.append(list);
  }
  if (retained.available && (retained.withheld || []).length) {
    const heading = document.createElement("h5");
    heading.textContent = "Not offered";
    retainedSection.append(heading);
    const list = document.createElement("ul");
    for (const entry of retained.withheld) {
      const item = document.createElement("li");
      item.textContent = entry.label + " — " + (entry.detail || sourcesStatusText(entry.status));
      list.append(item);
    }
    retainedSection.append(list);
  }
  body.append(retainedSection);

  // B. Source & attribution
  const attribution = doc.attribution || {};
  const sourceSection = sourcesSection("Source & attribution", false);
  if (attribution.recorded) {
    sourceSection.append(sourcesRows([
      ["Publisher / provider", attribution.publisher],
      ["Source URL", (() => {
        if (!attribution.url || attribution.url.indexOf("https://") !== 0) return attribution.url;
        const link = document.createElement("a");
        link.href = attribution.url;
        link.textContent = attribution.url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        return link;
      })()],
      ["Dataset version / date", attribution.version && (attribution.version.snapshot_id || attribution.version.publishing_date_range)],
      ["Licence or terms", attribution.licence],
      ["Note", attribution.detail],
    ]));
  } else {
    const note = document.createElement("p");
    note.className = "hint";
    note.textContent = attribution.detail || "Not recorded for this report.";
    sourceSection.append(note);
  }
  body.append(sourceSection);

  // C. Methods & reproduction
  const methods = doc.methods || {};
  const methodsSection = sourcesSection("Methods & reproduction", false);
  const linkRow = [];
  if (methods.methods_href) linkRow.push(["Companion methods", sourcesLink(methods.methods_href, "Methods and sources")]);
  if (methods.provenance_href) linkRow.push(["Machine-readable provenance", sourcesLink(methods.provenance_href, "provenance.json")]);
  if (methods.composition_href) linkRow.push(["Frozen effective request", sourcesLink(methods.composition_href, "composition.json")]);
  if (methods.method && methods.method.calc_version) {
    linkRow.push(["Analysis method", "calculation version " + methods.method.calc_version]);
  }
  if (methods.code) {
    if (methods.code.files) {
      const code = document.createElement("code");
      code.className = "sources-json";
      code.textContent = Object.keys(methods.code.files).join("\n");
      linkRow.push(["Retained implementation at render time", code]);
    } else if (methods.code.git_commit) {
      linkRow.push(["Recorded revision", methods.code.git_commit + (methods.code.source_state ? " (" + methods.code.source_state + ")" : "")]);
    } else {
      linkRow.push(["Code reference", "Not recorded for this report"]);
    }
  }
  if (methods.environment && methods.environment.files) {
    const code = document.createElement("code");
    code.className = "sources-json";
    code.textContent = Object.keys(methods.environment.files).join("\n");
    linkRow.push(["Render helpers recorded", code]);
  }
  methodsSection.append(sourcesRows(linkRow));
  const replay = methods.replay || {};
  const replayState = document.createElement("p");
  replayState.className = "hint";
  const stateLabels = {
    complete_local: "Complete local replay possible",
    requires_private_inputs: "Replay requires retained private inputs",
    partial: "Partial replay only",
    unavailable: "Replay unavailable",
  };
  replayState.textContent = (stateLabels[replay.state] || "Replay status not recorded")
    + (replay.detail ? " — " + replay.detail : "");
  methodsSection.append(replayState);
  if (replay.command) {
    const command = document.createElement("code");
    command.className = "replay-command";
    command.textContent = replay.command;
    methodsSection.append(command);
  }
  body.append(methodsSection);
}

async function openSources(jobId, opener) {
  const panel = el("sources-panel");
  state.sourcesOpener = opener || null;
  el("sources-body").replaceChildren();
  el("sources-note").textContent = "";
  el("sources-status").className = "status";
  el("sources-status").textContent = "Reading the saved report…";
  panel.hidden = false;
  // Focus (not an explicit scroll) brings the panel into view; discovery never moves the page.
  el("sources-close").focus();
  try {
    const doc = await request("/api/jobs/" + encodeURIComponent(jobId) + "/sources");
    renderSources(doc);
    el("sources-status").textContent = "";
  } catch (error) {
    el("sources-status").className = "status error";
    el("sources-status").textContent = error.message;
  }
}

function closeSources() {
  const panel = el("sources-panel");
  if (panel.hidden) return;
  panel.hidden = true;
  el("sources-body").replaceChildren();
  el("sources-status").textContent = "";
  const opener = state.sourcesOpener;
  state.sourcesOpener = null;
  if (opener && opener.focus) opener.focus();
}

function csvDisplayPanel(row) {
  const ui = row.display_ui;
  if (!ui) return null;
  if (!state.csvOpenDisplays) state.csvOpenDisplays = new Set();
  const current = () => JSON.parse(JSON.stringify(state.csvDisplayDraft[row.instance_id]
    || row.display || {}));
  const send = (patch) => {
    const next = Object.assign(current(), patch);
    state.csvDisplayDraft[row.instance_id] = next;
    csvEdit("set-display", row.instance_id, next);
  };
  const details = document.createElement("details");
  details.className = "block-display";
  details.open = state.csvOpenDisplays.has(row.instance_id);
  details.addEventListener("toggle", () => {
    if (details.open) state.csvOpenDisplays.add(row.instance_id);
    else state.csvOpenDisplays.delete(row.instance_id);
  });
  const summary = document.createElement("summary");
  summary.textContent = "Display settings";
  details.append(summary);
  const body = document.createElement("div");
  body.className = "display-body";
  details.append(body);

  const field = (labelText, control, hint) => {
    const wrap = document.createElement("div");
    wrap.className = "display-field";
    const label = document.createElement("span");
    label.className = "display-label";
    label.textContent = labelText;
    wrap.append(label, control);
    if (hint) {
      const note = document.createElement("p");
      note.className = "hint";
      note.textContent = hint;
      wrap.append(note);
    }
    return wrap;
  };

  // Statistics columns
  if (ui.capabilities.includes("statistics")) {
    const list = document.createElement("div");
    list.className = "display-checks";
    const chosen = new Set(current().statistics || []);
    for (const column of ui.statistics) {
      const label = document.createElement("label");
      label.className = "check";
      const box = document.createElement("input");
      box.type = "checkbox";
      box.value = column.key;
      box.checked = chosen.has(column.key);
      box.addEventListener("change", () => {
        const next = new Set(current().statistics || []);
        if (box.checked) next.add(column.key);
        else next.delete(column.key);
        if (!next.size) {
          box.checked = true;
          announce("Keep at least one statistics column, or switch the section to a chart.");
          return;
        }
        send({ statistics: Array.from(next) });
      });
      const text = document.createElement("span");
      text.textContent = column.label;
      label.append(box, text);
      list.append(label);
    }
    body.append(field("Statistics shown", list,
      "Only statistics already saved in the analysis are shown; choosing a column never recalculates it."));
  }

  // Groups (display-only)
  if (ui.capabilities.includes("groups")) {
    const chosen = current().groups ? new Set(current().groups) : new Set(ui.groups);
    const wrap = document.createElement("div");
    const search = document.createElement("input");
    search.type = "search";
    search.placeholder = "Search groups";
    search.className = "display-search";
    const list = document.createElement("div");
    list.className = "display-checks scroll";
    const count = document.createElement("p");
    count.className = "display-scope";
    const boxes = [];
    const updateCount = () => {
      const n = boxes.filter((box) => box.checked).length;
      count.textContent = "Showing " + n + " of " + ui.groups.length + " analysed groups.";
    };
    for (const name of ui.groups) {
      const label = document.createElement("label");
      label.className = "check";
      const box = document.createElement("input");
      box.type = "checkbox";
      box.value = name;
      box.checked = chosen.has(name);
      box.addEventListener("change", () => {
        const picked = boxes.filter((item) => item.checked).map((item) => item.value);
        if (!picked.length) {
          box.checked = true;
          announce("Keep at least one group, or remove the section.");
          return;
        }
        if (picked.length === ui.groups.length) send({ groups: null });
        else send({ groups: picked });
      });
      const text = document.createElement("span");
      text.textContent = name;
      label.append(box, text);
      boxes.push(box);
      list.append(label);
    }
    search.addEventListener("input", () => {
      const needle = search.value.trim().toLowerCase();
      for (const box of boxes) box.parentElement.hidden = needle
        && box.value.toLowerCase().indexOf(needle) === -1;
    });
    const actions = document.createElement("p");
    const all = document.createElement("button");
    all.type = "button";
    all.className = "link-button";
    all.textContent = "Select all";
    all.addEventListener("click", () => send({ groups: null }));
    const none = document.createElement("button");
    none.type = "button";
    none.className = "link-button";
    none.textContent = "Clear selection";
    none.addEventListener("click", () => {
      boxes[0].checked = true;
      for (const box of boxes.slice(1)) box.checked = false;
      send({ groups: [boxes[0].value] });
    });
    actions.append(all, none);
    wrap.append(search, actions, list, count);
    updateCount();
    body.append(field("Groups shown", wrap,
      "Display only: hiding a group never changes the saved analysis or another section."));
  }

  // Periods (display-only)
  if (ui.capabilities.includes("periods") && ui.has_time) {
    const periods = current().periods || { mode: "all" };
    const wrap = document.createElement("div");
    const modes = document.createElement("div");
    modes.className = "display-checks";
    const allLabel = document.createElement("label");
    allLabel.className = "check";
    const allRadio = document.createElement("input");
    allRadio.type = "radio";
    allRadio.name = "period-mode-" + row.instance_id;
    allRadio.checked = periods.mode === "all";
    allRadio.addEventListener("change", () => {
      if (allRadio.checked) send({ periods: { mode: "all" } });
    });
    const allText = document.createElement("span");
    allText.textContent = "All " + ui.periods.length + " analysed periods";
    allLabel.append(allRadio, allText);
    const listLabel = document.createElement("label");
    listLabel.className = "check";
    const listRadio = document.createElement("input");
    listRadio.type = "radio";
    listRadio.name = "period-mode-" + row.instance_id;
    listRadio.checked = periods.mode === "list";
    listRadio.addEventListener("change", () => {
      if (listRadio.checked) send({ periods: { mode: "list",
        values: periods.mode === "list" ? periods.values : ui.periods.slice(0, 1) } });
    });
    const listText = document.createElement("span");
    listText.textContent = "Choose individual periods";
    listLabel.append(listRadio, listText);
    modes.append(allLabel, listLabel);
    const list = document.createElement("div");
    list.className = "display-checks scroll";
    const chosen = new Set(periods.mode === "list" ? periods.values : ui.periods);
    const boxes = [];
    for (const period of ui.periods) {
      const label = document.createElement("label");
      label.className = "check";
      const box = document.createElement("input");
      box.type = "checkbox";
      box.value = period;
      box.checked = chosen.has(period);
      box.disabled = periods.mode !== "list";
      box.addEventListener("change", () => {
        const picked = boxes.filter((item) => item.checked).map((item) => item.value);
        if (!picked.length) {
          box.checked = true;
          announce("Keep at least one period, or show all periods.");
          return;
        }
        send({ periods: { mode: "list", values: picked } });
      });
      const text = document.createElement("span");
      text.textContent = period.slice(0, 10);
      label.append(box, text);
      boxes.push(box);
      list.append(label);
    }
    wrap.append(modes, list);
    body.append(field("Periods shown", wrap,
      "Display only: hidden periods stay in the saved analysis and in the group statistics."));
    if (ui.capabilities.includes("axis_labels")) {
      const axis = current().axis_labels || { mode: "auto" };
      const select = document.createElement("select");
      const options = [["auto", "Automatic"], ["every", "Label every period"],
                       ["every_n", "Label every N periods"]];
      for (const [value, text] of options) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = text;
        option.selected = axis.mode === value;
        select.append(option);
      }
      const every = document.createElement("input");
      every.type = "number";
      every.min = "2";
      every.max = "20";
      every.value = String(axis.n || 2);
      every.className = "display-number";
      every.disabled = axis.mode !== "every_n";
      select.addEventListener("change", () => {
        if (select.value === "every_n") send({ axis_labels: { mode: "every_n", n: Number(every.value) || 2 } });
        else send({ axis_labels: { mode: select.value } });
      });
      every.addEventListener("change", () => {
        if (select.value === "every_n") send({ axis_labels: { mode: "every_n", n: Number(every.value) || 2 } });
      });
      const row2 = document.createElement("div");
      row2.className = "display-inline";
      row2.append(select, every);
      body.append(field("Axis labels", row2,
        "Labels only: thinning labels never drops observations or changes their spacing."));
    }
  }

  // Layout
  if (ui.capabilities.includes("layout") && ui.layouts.length > 1) {
    const select = document.createElement("select");
    for (const value of ui.layouts) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = CSV_LAYOUT_LABELS[value] || value;
      option.selected = (current().layout || "table") === value;
      select.append(option);
    }
    select.addEventListener("change", () => send({ layout: select.value }));
    body.append(field("Layout", select));
  }

  // Precision
  if (ui.capabilities.includes("precision")) {
    const precision = current().precision || { mode: "decimal", places: 1 };
    const select = document.createElement("select");
    const options = [["0", "Whole numbers"], ["1", "1 decimal place"],
                     ["2", "2 decimal places"], ["3", "3 decimal places"],
                     ["full", "Full precision"]];
    for (const [value, text] of options) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = text;
      option.selected = precision.mode === "full" ? value === "full"
        : String(precision.places) === value;
      select.append(option);
    }
    select.addEventListener("change", () => {
      if (select.value === "full") send({ precision: { mode: "full" } });
      else send({ precision: { mode: "decimal", places: Number(select.value) } });
    });
    body.append(field("Numbers shown", select,
      "Display rounding only. The saved results keep full precision, and a nonzero value is never shown as an exact zero."));
  }

  return details;
}

function csvAdapter(doc) {
  return {
    mode: "csv",
    setIncluded: (id, include) => csvEdit(include ? "include" : "exclude", id, null),
    move: (id, direction) => csvEdit(direction === "up" ? "move-up" : "move-down", id, null),
    setTitle: (id, value) => csvEdit("set-title", id, value),
    canDuplicate: true,
    duplicate: (id) => csvEdit("duplicate", id, null),
    absentTypes: () => csvAbsentTypes(doc),
    addType: (block, box) => {
      csvEdit("include", block, null).then(() => { box.checked = false; });
    },
  };
}

function csvAbsentTypes(doc) {
  const present = new Set((doc.composer || []).map((entry) => entry.block));
  const analysis = doc.analysis || {};
  const available = !analysis || !analysis.row_count ? false : true;
  return CSV_TYPE_ORDER.filter((block) => !present.has(block)).map((block) => ({
    block,
    label: CSV_TYPE_LABELS[block],
    available,
    reason: "This section is not available for this dataset yet.",
  }));
}

async function csvEdit(action, instance, value) {
  const digest = state.csvDigest;
  if (!digest) return;
  try {
    const result = await mutate("csv-edit", "/api/csv/edit",
                                { digest, action, instance, value });
    state.csvDocument = result.document;
    renderCsvComposer(result.document);
    renderCsvDisclosure(result.document);
    renderCsvHistory(result.document);
    renderDatasetList(result.document);
  } catch (error) {
    csvStatus(el("csv-generate-status"), error.message, "error");
    announce(error.message);
  }
}

function renderCsvComposer(doc) {
  const node = el("csv-blocks");
  const activeId = document.activeElement && document.activeElement.id;
  if (!(node._openBlocks instanceof Set)) node._openBlocks = new Set();
  node.replaceChildren();
  const blocks = doc.composer || [];
  const hasProblem = blocks.some((entry) => Boolean(entry.summary));
  const conflicts = doc.disclosure_conflicts || [];
  el("csv-generate").disabled = !(doc.recipe && doc.recipe.blocks && blocks.length)
    || hasProblem || conflicts.length > 0;
  el("csv-ready").textContent = conflicts.length
    ? "Resolve the disclosure choice before generating"
    : hasProblem
      ? "Some sections cannot render with this dataset yet"
      : "Composition ready";
  el("csv-digest").textContent = shortDigest(hashRecipe(doc.recipe));
  el("csv-digest").title = hashRecipe(doc.recipe) || "";
  for (const block of blocks) {
    const item = document.createElement("li");
    item.className = "block block--card";
    item.setAttribute("data-instance", block.instance_id);

    // One compact row: [↑][↓] Name · title/scope [Required] [Settings]
    const row = document.createElement("div");
    row.className = "block-row";
    const position = blocks.findIndex((entry) => entry.instance_id === block.instance_id);
    const move = document.createElement("div");
    move.className = "block-move";
    move.append(
      controlButton("↑", "csv-up-" + block.instance_id, "Move section up",
                    position <= 0, () => csvEdit("move-up", block.instance_id, null)),
      controlButton("↓", "csv-down-" + block.instance_id, "Move section down",
                    position === blocks.length - 1,
                    () => csvEdit("move-down", block.instance_id, null)));
    const main = document.createElement("div");
    main.className = "block-main";
    const label = document.createElement("span");
    label.className = "block-label";
    label.textContent = CSV_TYPE_LABELS[block.block] || block.block;
    const compactBits = [];
    if (block.title) compactBits.push(block.title);
    if (block.display_summary) compactBits.push(block.display_summary);
    else if (block.description) compactBits.push(block.description);
    main.append(label);
    if (compactBits.length) {
      const compact = document.createElement("span");
      compact.className = "block-compact-line";
      compact.textContent = compactBits.join(" · ");
      main.append(compact);
    }
    row.append(move, main);
    const required = Boolean(block.required || CSV_REQUIRED[block.block]);
    if (required) {
      const state = document.createElement("span");
      state.className = "badge badge--req";
      state.textContent = "Required";
      row.append(state);
    }
    const settings = document.createElement("button");
    settings.type = "button";
    settings.className = "ghost block-settings";
    settings.id = "csv-settings-" + block.instance_id;
    settings.setAttribute("aria-controls", "csv-details-" + block.instance_id);
    row.append(settings);
    item.append(row);

    if (block.summary) {
      const problem = document.createElement("p");
      problem.className = "blocking-text";
      problem.setAttribute("role", "alert");
      problem.textContent = block.summary;
      item.append(problem);
    }

    const details = document.createElement("details");
    details.className = "block-details";
    details.id = "csv-details-" + block.instance_id;
    const summary = document.createElement("summary");
    summary.className = "visually-hidden";
    summary.textContent = "Settings for " + (CSV_TYPE_LABELS[block.block] || block.block);
    details.append(summary);
    const body = document.createElement("div");
    body.className = "block-details-body";
    details.append(body);
    const setOpen = (open) => {
      details.open = open;
      if (open) node._openBlocks.add(block.instance_id);
      else node._openBlocks.delete(block.instance_id);
      settings.textContent = open ? "Hide settings" : "Settings";
      settings.setAttribute("aria-expanded", String(open));
    };
    setOpen(node._openBlocks.has(block.instance_id));
    settings.addEventListener("click", () => setOpen(!details.open));
    details.addEventListener("toggle", () => setOpen(details.open));

    const description = document.createElement("p");
    description.className = "block-desc";
    description.textContent = block.description || "";
    body.append(description);
    const titleField = document.createElement("p");
    const input = document.createElement("input");
    input.type = "text";
    input.id = "csv-title-" + block.instance_id;
    input.className = "block-title-field";
    input.placeholder = "Optional report section title";
    input.value = block.title || "";
    input.addEventListener("change", () => csvEdit("set-title", block.instance_id, input.value));
    titleField.append(input);
    body.append(titleField);
    const displayPanel = csvDisplayPanel(block);
    if (displayPanel) body.append(displayPanel);
    if (required) {
      const note = document.createElement("p");
      note.className = "block-required";
      note.textContent = "Always included. " + (CSV_REQUIRED[block.block] || "");
      body.append(note);
    }
    const actions = document.createElement("p");
    actions.className = "block-actions";
    actions.append(controlButton(
      "Remove", "csv-remove-" + block.instance_id, "Remove this section from the report",
      required, () => csvEdit("exclude", block.instance_id, null)));
    if (block.repeatable) {
      actions.append(controlButton("Duplicate", "csv-dup-" + block.instance_id,
                                   "Duplicate this section", false,
                                   () => csvEdit("duplicate", block.instance_id, null)));
    }
    body.append(actions);
    const technical = document.createElement("p");
    technical.className = "block-id";
    technical.textContent = "Section id " + block.instance_id;
    body.append(technical);
    item.append(details);
    node.append(item);
  }
  if (activeId) {
    const again = document.getElementById(activeId);
    if (again && again.focus) again.focus();
  }
  for (const type of csvAbsentTypes(doc)) {
    const item = document.createElement("li");
    item.className = "block block--absent";
    const head = document.createElement("div");
    head.className = "block-head";
    const wrap = document.createElement("label");
    wrap.className = "check";
    const box = document.createElement("input");
    box.type = "checkbox";
    box.id = "csv-add-" + type.block;
    box.addEventListener("change", () => { if (box.checked) csvEdit("include", type.block, null); });
    const text = document.createElement("span");
    text.className = "block-label";
    text.textContent = type.label;
    wrap.append(box, text);
    head.append(wrap);
    const badge = document.createElement("span");
    badge.className = "badge badge--soft";
    badge.textContent = "Not in this report";
    head.append(badge);
    item.append(head);
    node.append(item);
  }
}

function hashRecipe(recipe) {
  if (!recipe || !Array.isArray(recipe.blocks)) return "";
  return "csv" + recipe.blocks.map((entry) => entry.instance_id + ":" + entry.block).join("|")
    .slice(0, 24);
}

async function uploadCsvFile(file) {
  if (!file) return;
  state.busyCsv = true;
  el("csv-upload-button").disabled = true;
  csvStatus(el("csv-upload-error"), "", "error");
  try {
    const form = new FormData();
    form.append("file", file);
    const result = await request("/api/csv/upload", {
      method: "POST",
      body: form,
      headers: { "X-Composer-Action": "csv-upload" },
    });
    el("csv-upload-error").hidden = true;
    await selectDataset(result.capture.input_sha256);
  } catch (error) {
    csvStatus(el("csv-upload-error"), error.message, "error");
    el("csv-upload-error").hidden = false;
    announce(error.message);
  } finally {
    state.busyCsv = false;
    el("csv-upload-button").disabled = false;
  }
}

async function generateCsv() {
  const digest = state.csvDigest;
  const doc = state.csvDocument;
  if (!digest || !doc || !doc.recipe || el("csv-generate").disabled) return;
  csvStatus(el("csv-generate-status"), "Submitting…", "");
  try {
    const job = await mutate("csv-generate", "/api/csv/generate",
                             { digest, recipe: doc.recipe });
    state.csvJob = job;
    el("csv-sources").disabled = false;
    el("csv-replay-command").textContent = job.replay_command || "—";
    if (job.reused) {
      csvStatus(el("csv-generate-status"),
        job.reuse_message || "Opened an existing report matching these settings.", "ok");
      displayCsvReport(job);
      refreshCsvHistory();
      return;
    }
    csvStatus(el("csv-generate-status"), "Queued as " + job.job_id + ".", "");
    pollCsv(job.job_id);
  } catch (error) {
    csvStatus(el("csv-generate-status"), error.message, "error");
    announce(error.message);
  }
}

async function refreshCsvHistory() {
  const digest = state.csvDigest;
  if (!digest) return;
  try {
    const doc = await request("/api/csv?digest=" + encodeURIComponent(digest));
    state.csvDocument = doc;
    renderCsvHistory(doc);
  } catch (error) {
    // keep the previous list; the status line already reports the main error
  }
}

function displayCsvReport(job) {
  const frame = el("csv-report-frame");
  frame.hidden = false;
  frame.src = job.report_url;
  el("csv-open-report").hidden = false;
  el("csv-open-report").href = job.report_url;
  el("csv-report-empty").textContent = "";
  el("csv-replay-command").textContent = job.replay_command || "—";
}

function pollCsv(jobId) {
  if (state.polling) clearInterval(state.polling);
  state.polling = setInterval(async () => {
    let job = null;
    try {
      job = await request("/api/jobs/" + encodeURIComponent(jobId));
    } catch (error) {
      clearInterval(state.polling);
      state.polling = null;
      return;
    }
    if (!state.csvJob || state.csvJob.job_id !== job.job_id) return;
    state.csvJob = job;
    if (job.status === "queued" || job.status === "running") {
      csvStatus(el("csv-generate-status"), "Rendering… started " + (job.started_utc || "shortly")
        + ".", "");
      return;
    }
    clearInterval(state.polling);
    state.polling = null;
    if (job.status === "succeeded") {
      displayCsvReport(job);
      csvStatus(el("csv-generate-status"), "Generated the report (recipe "
        + shortDigest(job.recipe_sha256) + ") at " + job.finished_utc + ".", "ok");
      refreshCsvHistory();
    } else {
      csvStatus(el("csv-generate-status"), "Generation " + job.status + ". " + (job.error || "")
        + " The report already on screen is unchanged.", "error");
    }
  }, 900);
}

/* ------------------------------------------------------------------ saved data */

function humanTime(iso) {
  if (!iso) return "time not recorded";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov",
                  "Dec"];
  const pad = (value) => String(value).padStart(2, "0");
  return date.getUTCDate() + " " + months[date.getUTCMonth()] + " " + date.getUTCFullYear()
    + ", " + pad(date.getUTCHours()) + ":" + pad(date.getUTCMinutes()) + " UTC";
}

function classificationLabel(job) {
  if (job.classification === "custom") return "Custom composition";
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
    renderCustomDrafts(data.custom_drafts || []);
    el("data-paths").textContent = "Work root " + data.work_root
      + " · inputs " + data.inputs_root
      + (data.drafts.length ? " · managed copies: " + data.drafts.join(", ") : "")
      + (data.custom_drafts && data.custom_drafts.length
        ? " · custom drafts: " + data.custom_drafts.join(", ") : "");
    const list = el("saved-list");
    list.replaceChildren();
    const scope = state.savedScope || "mode";
    const jobs = (data.jobs || []).filter((job) => scope === "all" || job.mode !== "csv");
    el("saved-total").textContent = jobs.length + (jobs.length === 1 ? " report" : " reports")
      + (scope === "mode" ? " in this mode" : " (all modes)");
    for (const job of jobs) {
      const row = document.createElement("li");
      const head = document.createElement("div");
      head.className = "saved-head";
      const entry = presetEntry(job.preset) || { label: job.preset || "unknown audience" };
      const title = document.createElement("strong");
      title.textContent = (job.origin === "custom" || job.preset === "custom")
        ? "Custom report · " + contextLabel(job.context) + " data context"
        : entry.label + " · " + classificationLabel(job);
      const when = document.createElement("span");
      when.className = "hint";
      when.textContent = job.created_utc + " · " + job.status
        + " · recipe " + shortDigest(job.recipe_sha256)
        + (job.error ? " — " + job.error : "");
      when.textContent = humanTime(job.created_utc) + " · " + (job.mode === "csv" ? "CSV"
        : (entry.label || job.preset || "health")) + " · " + job.status
        + (job.error ? " — " + job.error : "");
      head.append(title, when);
      row.append(head);
      const details = document.createElement("details");
      details.className = "saved-details";
      const toggle = document.createElement("summary");
      toggle.textContent = "Show details";
      details.append(toggle);
      const body = document.createElement("div");
      body.className = "saved-details-body";
      details.append(body);
      const summary = document.createElement("p");
      summary.className = "hint";
      summary.textContent = snapshotText(job.snapshot_summary);
      body.append(summary);

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
      body.append(line);

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
        const sources = document.createElement("button");
        sources.type = "button";
        sources.className = "ghost";
        sources.textContent = "Data & sources";
        sources.addEventListener("click", () => openSources(job.job_id, sources));
        actions.append(show, open, sources);
        body.append(actions);
      }
      const technical = document.createElement("p");
      technical.className = "hint";
      technical.textContent = "Recipe " + (job.recipe_sha256 || "not recorded");
      body.append(technical);
      row.append(details);
      list.append(row);
    }
    el("saved-empty").hidden = jobs.length > 0;
    if (el("report-frame").hidden) {
      el("report-empty").textContent = jobs.length
        ? "No report is currently displayed. Previously generated reports are available below."
        : "No reports generated yet.";
    }
  } catch (error) {
    if (!quiet) setStatus(el("edit-status"), error.message, "error");
  }
}

function renderCustomDrafts(contexts) {
  const node = el("custom-drafts");
  node.replaceChildren();
  const line = document.createElement("p");
  line.className = "hint";
  if (state.mode === "custom" && state.doc) {
    line.textContent = "This custom report is bound to the " + contextLabel(state.context)
      + " data context. " + summarizeSource(state.doc.source);
  } else {
    line.textContent = "Custom reports keep one draft per data context.";
  }
  node.append(line);
  if (!contexts.length) return;
  const row = document.createElement("div");
  row.className = "buttons buttons--inline";
  for (const context of contexts) {
    const current = state.mode === "custom" && state.context === context;
    row.append(controlButton((current ? "Editing: " : "Open ") + contextLabel(context),
                             "open-custom-" + context,
                             "Open the " + contextLabel(context) + " custom draft",
                             current, () => chooseCustom(context)));
  }
  node.append(row);
}

function displaySaved(job) {
  const already = state.rendered && state.rendered.job_id === job.job_id;
  displayReport(job);
  renderReuse(state.doc && state.doc.reuse);
  markStale();
  setStatus(el("generate-status"), (already ? "That report is already on screen; moved back to it."
    : "Showing the saved " + reportLabel(job) + " report " + job.job_id + " generated at "
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
  el("custom-reset-open").addEventListener("click", () => {
    el("custom-reset-confirm").hidden = false;
    el("custom-reset-yes").focus();
  });
  el("custom-reset-cancel").addEventListener("click", () => {
    el("custom-reset-confirm").hidden = true;
    el("custom-reset-open").focus();
  });
  el("custom-reset-yes").addEventListener("click", resetCustom);
  el("custom-repair-yes").addEventListener("click", () =>
    customAction("repair-draft", null, null));
  el("data").addEventListener("toggle", () => { if (el("data").open) loadSaved(true); });
  el("route-health").addEventListener("click", () => switchRoute("health"));
  el("route-csv").addEventListener("click", () => switchRoute("csv"));
  el("csv-upload-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const file = el("csv-file").files && el("csv-file").files[0];
    uploadCsvFile(file);
  });
  el("csv-generate").addEventListener("click", generateCsv);
  el("sources-close").addEventListener("click", closeSources);
  el("csv-copy-confirm-yes").addEventListener("click", () => {
    const pending = state.csvCopyPending;
    if (pending) csvCopyComposition(pending.item, pending.opener, true);
  });
  el("csv-copy-confirm-no").addEventListener("click", csvCopyCancel);
  el("csv-disclosure-toggle").addEventListener("click", () => {
    const more = el("csv-disclosure-more");
    more.hidden = !more.hidden;
    el("csv-disclosure-toggle").setAttribute("aria-expanded", String(!more.hidden));
    if (!more.hidden) {
      const first = el("csv-disclosure").querySelector?.("input");
      if (first && first.focus) first.focus();
    }
  });
  el("csv-datasets-toggle").addEventListener("click", () => {
    state.csvDatasetsOpen = !state.csvDatasetsOpen;
    const list = el("csv-dataset-scroll");
    const toggle = el("csv-datasets-toggle");
    if (list) {
      if (state.csvDatasetsOpen) list.classList.add("dataset-list--open");
      else list.classList.remove("dataset-list--open");
    }
    toggle.setAttribute("aria-expanded", String(state.csvDatasetsOpen));
    toggle.textContent = state.csvDatasetsOpen
      ? "Collapse list" : "Show all " + ((state.csvDatasets || []).length) + " datasets";
  });
  el("saved-scope").addEventListener("change", () => {
    state.savedScope = el("saved-scope").value;
    loadSaved(true);
  });
  el("sources-panel").addEventListener("keydown", (event) => {
    if (event.key === "Escape") { event.preventDefault(); closeSources(); }
  });
  el("csv-sources").addEventListener("click", () => {
    const job = state.csvJob;
    if (job && job.job_id) openSources(job.job_id, el("csv-sources"));
  });
  load();
}

document.addEventListener("DOMContentLoaded", wire);
