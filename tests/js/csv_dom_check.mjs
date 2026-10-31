/* Execute the real composer frontend against a scripted CSV-mode transcript.
 *
 *   node tests/js/csv_dom_check.mjs <fixture.json>
 *
 * The fixture comes from a real in-process Site: captures, confirmations, edit responses and
 * job records. The harness loads src/composer_web/app.js unmodified, fires DOMContentLoaded,
 * switches to the "Your CSV" route, uploads, confirms the interpretation, edits sections and
 * generates. Every request the page sends is matched against the transcript. A pass proves the
 * CSV journey renders and drives real elements; it is not a visual, layout or accessibility
 * check (the real-browser review stays required).
 */
import fs from "node:fs";
import { Document } from "./minidom.mjs";

const fixturePath = process.argv[2];
if (!fixturePath) {
  console.error("usage: node tests/js/csv_dom_check.mjs <fixture.json>");
  process.exit(2);
}
const fixture = JSON.parse(fs.readFileSync(fixturePath, "utf8"));
const appPath = fixture.app_js;
const indexPath = fixture.index_html;

const results = [];
const problems = [];
let failures = 0;
function check(name, ok, detail) {
  results.push({ name, ok: Boolean(ok), detail: ok ? undefined : String(detail ?? "") });
  if (!ok) failures += 1;
  console.log((ok ? "PASS " : "FAIL ") + name + (ok ? "" : " — " + String(detail ?? "")));
}

const document = new Document();
document.registerIds(fs.readFileSync(indexPath, "utf8"));
const window = { matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} }) };

const csvEditQueue = [...(fixture.csv_edit_steps || [])];
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
function takeCsvEdit(step, request) {
  const mismatches = [];
  for (const key of Object.keys(step.request)) {
    if (!same(request[key], step.request[key])) {
      mismatches.push(`${key}: sent ${JSON.stringify(request[key])}, expected ${JSON.stringify(step.request[key])}`);
    }
  }
  if (mismatches.length) {
    problems.push(`csv edit mismatch: ${mismatches.join("; ")}`);
    return { status: 598, body: { error: { code: "request_mismatch", message: "" } } };
  }
  return { status: 200, body: step.response };
}
function respond(payload, status) {
  return { ok: status >= 200 && status < 300, status,
           async json() { return payload; }, async text() { return JSON.stringify(payload); } };
}

const csvDoc = fixture.csv_document;
const csvStateDoc = { ...csvDoc, composer: [...csvDoc.composer] };
let job = null;
let restoreBody = null;

async function fetchShim(url, options) {
  const parsed = new URL(url, "http://localhost");
  const method = (options && options.method) || "GET";
  if (parsed.pathname === "/api/presets") return respond(fixture.presets, 200);
  if (parsed.pathname === "/api/saved") return respond({ jobs: [], drafts: [], custom_drafts: [] }, 200);
  if (parsed.pathname === "/api/editor") {
    const preset = parsed.searchParams.get("preset");
    return respond(fixture.editor_state && fixture.editor_state[preset]
                   || { error: { code: "missing_fixture", message: "no editor fixture" } }, 200);
  }
  if (parsed.pathname === "/api/csv" && method === "GET") {
    return respond(csvStateDoc, 200);
  }
  if (parsed.pathname === "/api/csv/upload" && method === "POST") {
    return respond({ capture: fixture.capture }, 200);
  }
  if (parsed.pathname === "/api/csv/confirm" && method === "POST") {
    const body = JSON.parse(options.body);
    if (!same(body.digest, fixture.csv_digest)) {
      problems.push(`confirm digest mismatch: ${body.digest}`);
      return respond({ error: { code: "digest_mismatch", message: "digest mismatch" } }, 400);
    }
    csvStateDoc.analysis = fixture.analysis_after_confirm;
    csvStateDoc.confirmation = fixture.confirmation_after_confirm;
    csvStateDoc.recipe = fixture.recipe_after_confirm;
    return respond({ digest: fixture.csv_digest, confirmed: fixture.confirmed_interpretation,
                     analysis: fixture.analysis_after_confirm }, 200);
  }
  if (parsed.pathname === "/api/csv/edit" && method === "POST") {
    const body = JSON.parse(options.body);
    if (body.action === "restore-composition") {
      restoreBody = body;
      return respond({ recipe: csvStateDoc.recipe, document: csvStateDoc }, 200);
    }
  }
  if (parsed.pathname === "/api/csv/edit" && method === "POST") {
    const step = csvEditQueue.shift();
    if (!step) {
      problems.push(`unexpected csv edit: ${options.body}`);
      return respond({ error: { code: "unexpected_request", message: "" } }, 599);
    }
    const result = takeCsvEdit(step, JSON.parse(options.body));
    if (result.status !== 200) return respond(result.body, result.status);
    csvStateDoc.recipe = result.body.recipe;
    csvStateDoc.composer = result.body.composer;
    return respond({ recipe: result.body.recipe, document: csvStateDoc }, 200);
  }
  if (/^\/api\/jobs\/[^/]+\/sources$/.test(parsed.pathname) && method === "GET") {
    return respond(fixture.sources_document, 200);
  }
  if (parsed.pathname === "/api/csv/generate" && method === "POST") {
    job = fixture.job_response;
    return respond(job, 202);
  }
  if (parsed.pathname.startsWith("/api/jobs/") && method === "GET") {
    if (job && parsed.pathname.endsWith(job.job_id)) {
      const current = job.status === "running" ? job : job;
      return respond({ ...current, status: "succeeded",
                       report_url: "/reports/" + job.job_id + "/report.html",
                       replay_command: "python scripts/health_pipeline/publish.py html --bundle <captured-dataset> --composition <recipe>" }, 200);
    }
    return respond({ error: { code: "unknown_job", message: "unknown job" } }, 404);
  }
  if (parsed.pathname === "/reports/") return respond("<html></html>", 200);
  problems.push(`unexpected request ${method} ${url}`);
  return respond({ error: { code: "unexpected_request", message: url } }, 599);
}

const source = fs.readFileSync(appPath, "utf8");
const factory = new Function(
  "window", "document", "fetch", "console", "setTimeout", "clearTimeout",
  "setInterval", "clearInterval", "URLSearchParams",
  source + "\n;return { state };",
);
const app = factory(window, document, fetchShim, console, setTimeout, clearTimeout,
                    setInterval, clearInterval, URLSearchParams);

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function settle(predicate, label, timeoutMs = 5000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if (predicate()) return true;
    await sleep(5);
  }
  const status = document.getElementById("csv-generate-status");
  throw new Error("timed out waiting for " + label
    + (status && status.textContent ? " | ui: " + status.textContent : "")
    + (problems.length ? " | " + problems.join(" | ") : ""));
}
const byId = (id) => document.getElementById(id);
const text = (id) => (byId(id) ? byId(id).textContent : "");
const click = (node) => node.fire("click");
const change = (node, value) => { node.value = value; node.fire("change"); };

async function main() {
  document.fire("DOMContentLoaded");
  await settle(() => app.state.preset, "initial health load");
  // default route is health; switch to the CSV journey
  check("default route is Health reports", app.state.route === "health", app.state.route);
  click(byId("route-csv"));
  await settle(() => app.state.route === "csv" && !byId("csv-panel").hidden, "csv route");
  await settle(() => byId("csv-datasets").children.length > 0, "csv dataset list");
  check("captured dataset card shown", text("csv-datasets").includes(fixture.file_name),
        text("csv-datasets"));
  // Finding C: the list must show the captured count, never null/?.
  const listedCount = (csvDoc.datasets || [])[0] && csvDoc.datasets[0].record_count;
  check("dataset card shows the captured record count",
        listedCount !== null && listedCount !== undefined
        && text("csv-datasets").includes(String(listedCount) + " records")
        && !text("csv-datasets").includes("null") && !text("csv-datasets").includes("?"),
        text("csv-datasets"));

  // upload: set the file input and submit the form
  const fileInput = byId("csv-file");
  fileInput.files = [ { name: fixture.file_name || "sample.csv", size: 100 } ];
  byId("csv-upload-form").fire("submit");
  await settle(() => app.state.csvDigest === fixture.csv_digest, "capture selected");
  check("upload selects the captured dataset", app.state.csvDigest === fixture.csv_digest);
  await settle(() => text("csv-preview-summary").includes("logical records"), "preview summary");
  check("structural preview rendered",
        text("csv-preview-summary").includes("logical records")
        && (text("csv-preview-note").includes("whole captured table")
            || text("csv-preview-note").includes("bounded portion")),
        text("csv-preview-summary"));

  // The fixture dataset is already confirmed (analysis present), so the passthrough shows the
  // composer directly; the confirmation card is re-shown for a not-yet-confirmed dataset.
  check("composer visible for confirmed dataset", !byId("csv-compose-card").hidden);
  check("dashboard passport rendered", text("csv-passport").includes("Dataset passport")
        || text("csv-passport").includes("captured file"), text("csv-passport").slice(0, 80));
  check("empty preview points at the retained history",
        text("csv-report-empty").includes("Previously generated reports are available"),
        text("csv-report-empty"));
  check("passport shows the captured record count",
        text("csv-passport").includes(String(listedCount) + " records")
        && !text("csv-passport").includes("? records"), text("csv-passport").slice(0, 160));

  // composition: sections ordered and editable; generate becomes enabled
  const blocks = byId("csv-blocks");
  await settle(() => blocks.children.length >= 4, "csv blocks rendered");
  check("composer renders the saved sections", blocks.children.length >= 4,
        String(blocks.children.length));

  // The disclosure choice is a first-class control, not a hidden default.
  const policyChoices = byId("csv-disclosure").children.filter((node) => node.tagName === "LABEL");
  check("disclosure policies are offered as explicit choices", policyChoices.length === 2,
        String(policyChoices.length));
  // Keyboard operability is a property of the control: a native radio input, associated with
  // its label, with the change handler on the input itself. Real Tab/arrow use is browser work.
  const nativeRadios = policyChoices.every((label) => label.children[0]
    && label.children[0].tagName === "INPUT"
    && label.children[0].type === "radio"
    && label.children[0].name === "csv-disclosure-policy"
    && label.htmlFor === label.children[0].id);
  const radioFacts = policyChoices.map((label) => ({
    tag: label.children[0] && label.children[0].tagName,
    type: label.children[0] && label.children[0].type,
    name: label.children[0] && label.children[0].name,
    matchesLabel: Boolean(label.children[0]) && label.htmlFor === label.children[0].id,
  }));
  check("policy controls are native labelled radio inputs", nativeRadios,
        JSON.stringify(radioFacts));
  const savedPolicy = (csvStateDoc.recipe && csvStateDoc.recipe.disclosure) || {};
  const selected = policyChoices.find((label) => label.children[0].checked);
  check("the saved policy is the selected choice",
        Boolean(selected) && selected.children[0].value === savedPolicy.policy,
        savedPolicy.policy);
  check("the consequence of the choice is stated",
        text("csv-disclosure-detail").length > 40, text("csv-disclosure-detail"));
  check("the disclosure choice is recorded in the saved recipe",
        Boolean(savedPolicy.policy)
        && savedPolicy.permit_values === (savedPolicy.policy === "local-audit"),
        JSON.stringify(savedPolicy));

  if (fixture.expect_conflict) {
    // An unresolved combination is explained before generation and keeps it blocked.
    check("the incompatibility is explained before generation",
          byId("csv-disclosure-conflicts").hidden === false
          && text("csv-disclosure-conflicts").includes("restricted shareable export excludes"),
          text("csv-disclosure-conflicts"));
    check("generate stays disabled for an unresolved combination",
          byId("csv-generate").disabled === true);
    check("the reason is announced in the composer",
          text("csv-ready").includes("Resolve the disclosure choice"), text("csv-ready"));
    const failedConflict = results.filter((item) => !item.ok);
    console.log("SUMMARY " + JSON.stringify({ checks: results.length,
                                              failures: failedConflict.length }));
    process.exit(failedConflict.length ? 1 : 0);
  }

  // Display settings panel: presentation controls for the value sections.
  const allNodes = [];
  (function walk(node) {
    for (const child of node.children || []) { allNodes.push(child); walk(child); }
  })(byId("csv-blocks"));
  const panels = allNodes.filter((node) => node.tagName === "DETAILS"
    && (node.className || "").indexOf("block-display") !== -1);
  check("display settings are offered per value section", panels.length >= 1,
        String(panels.length));
  const panelText = panels.map((panel) => panel.textContent).join(" ");
  check("display panel states the effective scope",
        /Showing \d+ of \d+ analysed groups/.test(panelText), panelText.slice(0, 160));
  const panelInputs = allNodes.filter((node) => node.tagName === "INPUT"
    && node.parentElement && (node.parentElement.className || "").indexOf("check") !== -1);
  check("display controls are native checkbox inputs", panelInputs.length >= 1,
        String(panelInputs.length));
  check("no false incompatibility for a compatible composition",
        byId("csv-disclosure-conflicts").hidden === true, text("csv-disclosure-conflicts"));
  check("composer has a generate button enabled", byId("csv-generate").disabled === false);
  click(byId("csv-generate"));
  await settle(() => app.state.csvJob && app.state.csvJob.job_id, "job submitted");
  check("generate submits the saved recipe", app.state.csvJob.job_id === fixture.job_response.job_id);
  await settle(() => text("csv-generate-status").includes("Generated"), "job succeeded");
  check("success status shown", text("csv-generate-status").includes("Generated"),
        text("csv-generate-status"));
  check("replay command disclosed", text("csv-replay-command").includes("publish.py"),
        text("csv-replay-command"));

  // ---- Visual pass: compact sections, dataset header, disclosure summary -----------------
  const firstBlock = byId("csv-blocks").children[0];
  check("dataset expansion control is compact and secondary",
        byId("csv-datasets-toggle").className.indexOf("link-button") !== -1
        && byId("csv-datasets-toggle").getAttribute("aria-expanded") === "false",
        byId("csv-datasets-toggle").className);
  check("structural preview sits outside the upload panel",
        !byId("csv-preview-block").hidden
        && byId("csv-preview-block").parentElement === byId("csv-upload-title").parentElement,
        "preview block not in the dataset card");
  check("preview states how much of the table is shown",
        text("csv-preview-summary").includes("logical records")
        && (text("csv-preview-summary").includes("showing all")
            || text("csv-preview-summary").includes("bounded preview")),
        text("csv-preview-summary"));
  const previewTable = byId("csv-preview").children[0];
  check("preview table headers are scoped",
        previewTable && previewTable.children[0].children[0].children[0].scope === "col",
        "no scoped header");
  check("preview is a bounded scroll region",
        byId("csv-preview-wrap").className.indexOf("csv-preview-scroll") !== -1,
        byId("csv-preview-wrap").className);
  check("dataset list is a bounded scroll container",
        Boolean(byId("csv-datasets").children.find(
          (node) => (node.className || "").indexOf("dataset-list") !== -1)),
        byId("csv-datasets").children.map((n) => n.className).join(","));
  const firstName = byId("csv-datasets").children
    .find((node) => (node.className || "").indexOf("dataset-list") !== -1)
    .children[0].children[0];
  check("dataset name is truncated visually but keeps the full value",
        firstName.title === firstName.textContent, firstName.title);
  check("selected dataset is marked",
        byId("csv-datasets").children[0].children[0].classList.contains("is-selected"),
        byId("csv-datasets").children[0].children[0].className);
  const blockRow = firstBlock.children.find((node) => (node.className || "").indexOf("block-row") !== -1);
  check("collapsed section is a single compact row",
        Boolean(blockRow) && Boolean(blockRow.querySelector("#csv-up-" + fixture.csv_document.recipe.blocks[0].instance_id)),
        blockRow && blockRow.className);
  const settingsButton = blockRow.querySelector("#csv-settings-" + fixture.csv_document.recipe.blocks[0].instance_id);
  check("settings control is labelled and exposes its state",
        settingsButton && settingsButton.textContent === "Settings"
        && settingsButton.getAttribute("aria-expanded") === "false",
        settingsButton && settingsButton.textContent);
  click(settingsButton);
  await settle(() => settingsButton.getAttribute("aria-expanded") === "true", "settings opened");
  check("settings control opens the details without a request", problems.length === 0,
        problems.join(" | "));
  click(settingsButton);
  await settle(() => settingsButton.getAttribute("aria-expanded") === "false", "settings closed");
  check("collapsed section shows no internal instance id",
        !firstBlock.children[0].textContent.includes(fixture.csv_document.recipe.blocks[0]
          .instance_id), firstBlock.children[0].textContent);
  check("section exposes a settings details element",
        Boolean(firstBlock.children.find((node) => node.tagName === "DETAILS")),
        firstBlock.children.map((node) => node.tagName).join(","));
  const beforeToggle = app.state.csvDocument;
  const blockDetails = firstBlock.children.find((node) => node.tagName === "DETAILS");
  blockDetails.fire("toggle");
  check("expanding a section changes no document state",
        app.state.csvDocument === beforeToggle && problems.length === 0,
        problems.join(" | "));
  check("dataset header carries the compact passport",
        !byId("csv-dataset-header").hidden
        && text("csv-dataset-header").includes("records"), text("csv-dataset-header"));
  check("disclosure summary states policy and permissions",
        text("csv-disclosure-summary").includes("Local audit")
        && text("csv-disclosure-summary").includes("records"), text("csv-disclosure-summary"));
  check("disclosure consequence stays visible",
        byId("csv-disclosure-warning").hidden === false
        && text("csv-disclosure-warning").includes("not private once shared"),
        text("csv-disclosure-warning"));
  // Expanding a section and editing inside it must keep the card open and the focus in place.
  const focusTarget = fixture.focus_instance;
  const rowFor = (id) => byId("csv-blocks").children.find(
    (row) => (row.getAttribute ? row.getAttribute("data-instance") : row.dataset.instance) === id);
  const firstDetails = rowFor(focusTarget).children.find((node) => node.tagName === "DETAILS");
  firstDetails.open = true;
  firstDetails.fire("toggle");
  const titleInput = document.getElementById("csv-title-" + focusTarget);
  check("expanded section exposes its title field", Boolean(titleInput));
  titleInput.focus();
  titleInput.value = "Focused title";
  titleInput.fire("change");
  await settle(() => (app.state.csvDocument.recipe.titles || {})[focusTarget] === "Focused title",
               "title saved");
  const reopened = rowFor(focusTarget).children.find((node) => node.tagName === "DETAILS");
  check("expanded section stays open after an edit", reopened.open === true,
        String(reopened && reopened.open));
  check("focus returns to the edited field",
        document.activeElement === document.getElementById("csv-title-" + focusTarget),
        document.activeElement && document.activeElement.id);
  check("editing inside a section made no stray request", problems.length === 0,
        problems.join(" | "));

  // ---- Previously generated reports -------------------------------------------------------
  check("history card is visible for a selected dataset", byId("csv-history-card").hidden === false);
  const historyRows = byId("csv-history").children.filter((node) => node.tagName === "LI");
  check("history lists the retained report", historyRows.length === 1, String(historyRows.length));
  check("history row states the reuse match",
        historyRows[0].textContent.includes("Matches current settings"),
        historyRows[0].textContent.slice(0, 160));
  const historyActions = [];
  (function walk(node) {
    for (const child of node.children || []) {
      if (child.tagName === "A" || child.tagName === "BUTTON") historyActions.push(child);
      walk(child);
    }
  })(historyRows[0]);
  check("history row offers open, sources and edit-copy",
        historyActions.some((a) => a.textContent === "Open report")
        && historyActions.some((a) => a.textContent === "Data & sources")
        && historyActions.some((a) => a.textContent === "Edit a copy"),
        JSON.stringify(historyActions.map((a) => a.textContent)));
  const copyButton = historyActions.find((a) => a.textContent === "Edit a copy");
  click(copyButton);
  await settle(() => restoreBody !== null, "copy request sent");
  check("edit a copy posts the report id and no forced confirm",
        restoreBody.value.job_id === "20261030T120000Z-1111111111"
        && restoreBody.value.confirm === false, JSON.stringify(restoreBody.value));
  await settle(() => text("csv-history-status").includes("Copied"), "copy status shown");
  check("copy status explains the report is unchanged",
        text("csv-history-status").includes("report itself is unchanged"),
        text("csv-history-status"));

  // ---- Data & sources panel -------------------------------------------------------------
  await settle(() => byId("csv-sources").disabled === false, "sources action enabled");
  click(byId("csv-sources"));
  await settle(() => byId("sources-body").children.length > 0, "sources panel populated");
  check("sources panel opens", byId("sources-panel").hidden === false);
  const sourcesText = byId("sources-body").textContent;
  const groups = byId("sources-body").children.filter((node) => node.tagName === "DETAILS");
  const groupByTitle = (title) => groups.find((group) =>
    group.children[0] && group.children[0].textContent === title);
  check("sources: the data group is open by default",
        Boolean(groupByTitle("Data")) && groupByTitle("Data").open === true,
        groups.map((g) => (g.children[0] || {}).textContent).join(","));
  check("sources: secondary groups start collapsed",
        groupByTitle("Methods & reproduction") && groupByTitle("Methods & reproduction").open === false
        && groupByTitle("Source & attribution").open === false,
        groups.map((g) => (g.children[0] || {}).textContent + ":" + g.open).join(","));
  check("sources: retained-state group stays open when it carries a state",
        Boolean(groupByTitle("Retained locally (steward only)")),
        groups.map((g) => (g.children[0] || {}).textContent).join(","));
  check("sources panel has the three sections",
        sourcesText.includes("Data") && sourcesText.includes("Source & attribution")
        && sourcesText.includes("Methods & reproduction"), sourcesText.slice(0, 200));
  check("sources panel states the report binding note",
        text("sources-note").includes("describes this saved report"), text("sources-note"));
  const anchors = [];
  (function collect(node) {
    for (const child of node.children || []) {
      if (child.tagName === "A") anchors.push(child);
      collect(child);
    }
  })(byId("sources-body"));
  check("package links stay report-relative", anchors.some((a) => String(a.href).indexOf("/reports/") === 0),
        JSON.stringify(anchors.map((a) => a.href)));
  check("unsafe link schemes are never rendered as links",
        !anchors.some((a) => String(a.href).toLowerCase().indexOf("javascript:") === 0),
        JSON.stringify(anchors.map((a) => a.href)));
  check("hostile labels are text, not markup",
        sourcesText.includes("<script>alert(1)</script>"), sourcesText.slice(0, 120));
  check("retained material is separated from report-bound material",
        sourcesText.includes("Current workspace material — differs from this report")
        && sourcesText.includes("Not offered")
        && sourcesText.includes("Original captured file"), sourcesText.slice(-400));
  check("display scope names the section subset",
        sourcesText.includes("1 of 2 analysed groups"), sourcesText);
  click(byId("sources-close"));
  await settle(() => byId("sources-panel").hidden === true, "sources panel closed");
  check("sources panel closes and clears", byId("sources-body").children.length === 0);

  const failed = results.filter((item) => !item.ok);
  console.log("SUMMARY " + JSON.stringify({ checks: results.length, failures: failed.length }));
  process.exit(failed.length ? 1 : 0);
}
main().catch((error) => {
  console.error(error && error.stack ? error.stack : error);
  process.exit(1);
});
