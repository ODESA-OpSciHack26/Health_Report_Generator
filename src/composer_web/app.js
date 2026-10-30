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
  list.replaceChildren();
  doc.blocks.forEach((block) => {
    const info = sectionText(block);
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
      adapter.setIncluded(block.instance_id, box.checked));
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

    if (block.title) {
      const title = document.createElement("p");
      title.className = "block-title";
      title.textContent = block.title;
      item.append(title);
    }
    if (block.copy_label) {
      const copy = document.createElement("span");
      copy.className = "badge badge--soft block-copy";
      copy.textContent = block.copy_label;
      copy.title = "Editor-only disambiguation; not part of the report title.";
      item.append(copy);
    }
    if (info.description) {
      const description = document.createElement("p");
      description.className = "block-desc";
      description.textContent = info.description;
      item.append(description);
    }
    if (block.summary) {
      const summary = document.createElement("p");
      summary.className = "block-summary";
      summary.textContent = block.summary;
      item.append(summary);
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
            () => inlineConfirm(item,
              "Delete this duplicate section? Only this instance and its own settings are "
              + "removed; the other copies stay in the report.",
              "Delete duplicate", () => adapter.deleteInstance(block.instance_id))));
        }
      }
    }
    item.append(controls);

    if (block.included) {
      item.append(titleField(adapter, block));
      if (block.block === "reference-comparison" || block.block === "monitoring-overview") {
        const scope = document.createElement("p");
        scope.className = "field-help";
        scope.textContent = block.block === "reference-comparison"
          ? "The reporting year and the reference year come from this report's saved analysis "
            + "settings. To change them, generate an analysis with different settings."
          : "The reporting window comes from this report's saved analysis settings; the value "
            + "shown is the latest saved observation inside that window, not a fixed reporting "
            + "year. To change the window, generate an analysis with different settings.";
        item.append(scope);
      }
      if (block.block === "series-collection") {
        const note = document.createElement("p");
        note.className = "field-help";
        note.textContent = "Display years only choose saved rows from the same series; they do "
          + "not change the reporting window used by the analysis.";
        item.append(note);
      }
      const editable = block.editable || [];
      if (editable.includes("topic")) item.append(topicControl(adapter, block));
      if (editable.includes("measure")) item.append(measureControl(adapter, block));
      if (editable.includes("layout")) item.append(layoutControl(adapter, block));
      if (editable.includes("topics")) item.append(diseasePicker(adapter, block));
      if (editable.includes("style") || editable.includes("years")) {
        item.append(advancedControls(adapter, block));
      }
    }
    const confirm = document.createElement("div");
    confirm.className = "inline-confirm";
    item.append(confirm);
    list.append(item);
  });

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

/* ------------------------------------------------------------------ saved data */

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
    for (const job of data.jobs) {
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
  load();
}

document.addEventListener("DOMContentLoaded", wire);
