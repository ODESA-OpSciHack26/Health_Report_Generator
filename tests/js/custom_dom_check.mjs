/* Execute the real composer frontend against a scripted, real-server transcript.
 *
 *   node tests/js/custom_dom_check.mjs <fixture.json>
 *
 * The fixture comes from a real in-process Site: the resolved custom document plus an ordered
 * transcript of the requests the page is expected to send, each with the document that server
 * call actually returned (or the error it raised). The harness loads src/composer_web/app.js
 * unmodified, fires DOMContentLoaded, and drives the ordered section editor in both modes by
 * clicking and changing real elements. Every request the page sends is matched against the
 * transcript, so a wrong action name, instance id or payload fails here.
 *
 * Limits: no layout, CSS, event bubbling or browser engine. A pass proves the rendering and the
 * event handlers run and produce the expected elements and requests; it is not a visual,
 * focus-order or accessibility check. The real-browser retest stays required.
 */
import fs from "node:fs";
import { Document } from "./minidom.mjs";

const fixturePath = process.argv[2];
if (!fixturePath) {
  console.error("usage: node tests/js/custom_dom_check.mjs <fixture.json>");
  process.exit(2);
}
const fixture = JSON.parse(fs.readFileSync(fixturePath, "utf8"));
const appPath = fixture.app_js;
const indexPath = fixture.index_html;

const results = [];
const problems = [];
let failures = 0;
function check(name, ok, detail) {
  results.push({ name, ok: Boolean(ok),
                 detail: ok ? undefined : (detail === undefined ? null : String(detail)) });
  if (!ok) failures += 1;
  console.log((ok ? "PASS " : "FAIL ") + name
              + (ok ? "" : " — " + (detail === undefined ? "" : detail)));
}

const document = new Document();
document.registerIds(fs.readFileSync(indexPath, "utf8"));
const window = {
  matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} }),
};

const queues = { custom: [...(fixture.custom_steps || [])],
                 preset: [...(fixture.preset_steps || [])] };
const customState = Object.assign({}, fixture.custom_state || {});
const editorState = Object.assign({}, fixture.editor || {});
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

function takeStep(kind, request) {
  const queue = queues[kind];
  const step = queue.shift();
  if (!step) {
    problems.push(`unexpected ${kind} request: ${JSON.stringify(request)}`);
    return { status: 599, error: { code: "unexpected_request",
                                   message: `unexpected ${kind} request` } };
  }
  const mismatches = [];
  for (const key of Object.keys(request)) {
    if (!same(request[key], step.request[key])) {
      mismatches.push(`${key}: sent ${JSON.stringify(request[key])}, `
                      + `expected ${JSON.stringify(step.request[key])}`);
    }
  }
  if (mismatches.length) {
    problems.push(`request mismatch: ${mismatches.join("; ")}`);
    return { status: 598, error: { code: "request_mismatch",
                                   message: `request mismatch: ${mismatches.join("; ")}` } };
  }
  if (step.error) return { status: step.status || 400, error: step.error };
  if (kind === "custom") customState[step.request.context] = step.doc;
  if (kind === "preset") editorState[step.request.preset] = step.doc;
  return { status: 200, body: step.doc };
}

function respond(payload, status) {
  return {
    ok: status >= 200 && status < 300,
    status,
    async json() { return payload; },
    async text() { return JSON.stringify(payload); },
  };
}
function respondFrom(result) {
  if (result.error) return respond({ error: result.error }, result.status);
  return respond(result.body, 200);
}

async function fetchShim(url, options) {
  const parsed = new URL(url, "http://localhost");
  const method = (options && options.method) || "GET";
  if (parsed.pathname === "/api/presets") return respond(fixture.presets, 200);
  if (parsed.pathname === "/api/saved") {
    return respond(fixture.saved || { jobs: [], drafts: [], custom_drafts: [] }, 200);
  }
  if (parsed.pathname === "/api/editor") {
    return respond(editorState[parsed.searchParams.get("preset")]
                   || { error: { code: "missing_fixture", message: "no editor fixture" } }, 200);
  }
  if (parsed.pathname === "/api/custom") {
    const context = parsed.searchParams.get("context") || fixture.context;
    if (!parsed.searchParams.get("context")) {
      if (parsed.searchParams.get("audience") !== fixture.audience) {
        problems.push("open requested an unexpected audience");
      }
    }
    return respond(customState[context]
                   || { error: { code: "missing_fixture", message: "no custom fixture" } }, 200);
  }
  if (parsed.pathname === "/api/edit" && method === "POST") {
    return respondFrom(takeStep("preset", JSON.parse(options.body)));
  }
  if (parsed.pathname === "/api/custom/edit" && method === "POST") {
    return respondFrom(takeStep("custom", JSON.parse(options.body)));
  }
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
  throw new Error("timed out waiting for " + label
                  + (problems.length ? " | " + problems.join(" | ") : ""));
}

const byId = (id) => document.getElementById(id);
const deep = (id) => document.querySelector("#" + id) || byId(id);
const text = (id) => (byId(id) ? byId(id).textContent : "");
const click = (node) => node.fire("click");
const toggle = (node, checked) => { node.checked = checked; node.fire("change"); };
const change = (node, value) => { node.value = value; node.fire("change"); };
const section = (block) => app.state.doc.blocks.find((b) => b.block === block);
const buttonsWithText = (root, label) =>
  root.querySelectorAll("button").filter((node) => node.textContent === label);

function pickers(list, instance) {
  return list.querySelectorAll("input").filter((node) =>
    (node.id || "").startsWith("pick-" + instance + "-"));
}
function rowFor(list, instance) {
  return list.children.find((row) => Boolean(row.querySelector("#include-" + instance)));
}

async function assertPresetEditor() {
  const list = byId("blocks");
  check("preset editor renders the shared include checkbox",
        list.children.length > 0 && Boolean(deep("include-intro-0001")), list.children.length);
  check("preset editor renders the shared order controls",
        Boolean(deep("up-intro-0001")) && Boolean(deep("down-intro-0001")));
  check("preset editor renders the shared disease picker",
        Boolean(deep("all-researcher-series-collection"))
        && Boolean(deep("clear-researcher-series-collection"))
        && Boolean(deep("open-researcher-series-collection")));
  check("preset editor renders the shared advanced display options",
        list.textContent.includes("Advanced display options")
        && list.textContent.includes("Chart height"));
  check("preset editor has no absent-type rows", !deep("add-series-collection"),
        list.children.length);

  click(deep("clear-researcher-series-collection"));
  await settle(() => text("blocking").length > 0, "preset empty-selection guard");
  check("preset Clear produces the shared empty-selection guard",
        text("blocking").includes("Select at least one disease"), text("blocking"));
  check("preset Generate is disabled while no disease is checked",
        byId("generate").disabled === true);
  click(deep("all-researcher-series-collection"));
  await settle(() => text("blocking") === "", "preset ready again");
  check("preset Select all restores readiness", byId("generate").disabled === false);
}

async function main() {
  // Negative control: the DOM contract behind the earlier reported failure still holds.
  let chained = null;
  try {
    byId("custom-blocks").append(document.createElement("div")).className = "x";
  } catch (error) { chained = error; }
  check("control: chaining Element.append() throws like a browser",
        chained instanceof TypeError && /className/.test(chained.message),
        chained && chained.message);

  document.fire("DOMContentLoaded");
  await settle(() => app.state.doc && app.state.mode === "preset", "initial audience load");
  await sleep(50);
  check("audience view rendered without an error status", text("edit-status") === "",
        text("edit-status"));
  await assertPresetEditor();

  click(document.querySelector('[data-preset="custom"]'));
  await settle(() => app.state.mode === "custom" && byId("custom-card").hidden === false,
               "custom panel");
  await sleep(50);
  check("Custom opens without an error status", text("custom-status") === "",
        text("custom-status"));

  // The simplified layout: no preamble, context selector or separate block library.
  const page = fs.readFileSync(indexPath, "utf8");
  for (const removed of ['id="context-select"', 'id="context-summary"', 'id="context-note"',
                         'id="library"', "Block library"]) {
    check("custom markup no longer contains " + removed, !page.includes(removed), removed);
  }
  check("Custom keeps the ordered section heading",
        page.includes("Report sections, in order") && page.includes('id="custom-title"'));

  const list = byId("custom-blocks");
  check("opening Custom created no draft and no instance",
        app.state.doc.draft === false && app.state.doc.blocks.length === 3,
        app.state.doc.blocks.length);
  check("every offered type is visible as an ordered row",
        list.children.length === 8 && Boolean(deep("add-series-collection")),
        list.children.length);
  check("the single-disease trend is no longer offered as a new section",
        !deep("add-series-trend"), list.children.length);
  check("absent types are unchecked and clearly labelled",
        deep("add-series-collection").checked === false
        && list.textContent.includes("Not in this report"));
  check("saved sections keep their place before the absent types",
        list.children.slice(0, 3).every((row) => !row.querySelector('[id^="add-"]')),
        list.children.slice(0, 3).map((row) => row.textContent.slice(0, 20)));

  const collection = fixture.collection_instance;
  const reference = fixture.reference_instance;
  const monitoring = fixture.monitoring_instance;
  const duplicate = fixture.duplicate_instance;

  // 1. Checking an absent type asks the service for exactly one new instance.
  toggle(deep("add-series-collection"), true);
  await settle(() => list.children.length === 8 && Boolean(deep("include-" + collection)),
               "collection added");
  check("checking a type creates one valid instance",
        app.state.doc.blocks.filter((b) => b.block === "series-collection").length === 1
        && app.state.doc.draft === true);
  check("the new section renders the shared disease picker",
        pickers(list, collection).length === fixture.eligible_count, pickers(list, collection).length);
  check("collection offers every eligible disease",
        Boolean(deep("pick-" + collection + "-influenza")));

  check("a new collection starts in the combined layout",
        deep("layout-" + collection) && deep("layout-" + collection).value === "combined",
        deep("layout-" + collection) && deep("layout-" + collection).value);
  check("the expanded-disease control says it chooses details, not the plotted series",
        list.textContent.includes("Disease details expanded when the report opens")
        && list.textContent.includes("All selected diseases are plotted in the chart"));

  // 1b. The layout is switchable, and the default-open wording follows it.
  change(deep("layout-" + collection), "panels");
  await settle(() => section("series-collection").options.layout === "panels", "panels layout");
  check("switching to the panels layout keeps the section and its settings",
        section("series-collection").options.layout === "panels"
        && section("series-collection").instance_id === collection);
  check("the panels wording is back",
        list.textContent.includes("Disease expanded when the report opens"));
  change(deep("layout-" + collection), "combined");
  await settle(() => section("series-collection").options.layout === "combined",
               "combined layout again");
  check("switching back restores the combined layout",
        section("series-collection").options.layout === "combined");

  check("the row carries a summary of the effective content",
        list.textContent.includes("combined chart") && list.textContent.includes("cases"));
  check("each included section offers an optional report title",
        Boolean(deep("title-" + collection)), deep("title-" + collection));

  // 1c. A report section title is stored and shown on the row.
  change(deep("title-" + collection), "Hepatitis focus");
  await settle(() => section("series-collection").title === "Hepatitis focus", "title saved");
  check("a section title is persisted and displayed",
        section("series-collection").title === "Hepatitis focus"
        && list.textContent.includes("Hepatitis focus"));
  check("the summary stays factual next to the title",
        list.textContent.includes("Campylobacteriosis"));

  // 2. Clear, then a two-disease subset through the shared checkboxes.
  click(deep("clear-" + collection));
  await settle(() => text("custom-blocking").includes("Select at least one disease"),
               "empty selection guard");
  check("Custom Clear shows the shared empty-selection guard",
        text("custom-blocking").includes("Select at least one disease"), text("custom-blocking"));
  check("Custom Generate is disabled while no disease is checked",
        byId("generate").disabled === true);
  toggle(deep("pick-" + collection + "-campylobacteriosis"), true);
  await settle(() => text("custom-blocking") === "", "ready after one disease");
  toggle(deep("pick-" + collection + "-influenza"), true);
  await settle(() => text("custom-blocking") === "", "second disease saved");
  check("two diseases are checked in the shared picker",
        deep("pick-" + collection + "-campylobacteriosis").checked
        && deep("pick-" + collection + "-influenza").checked);
  check("expanded disease is restricted to the checked diseases",
        deep("open-" + collection).children.every((option) =>
          ["campylobacteriosis", "influenza"].includes(option.value)));

  // 3. Expanded disease, chart height, display window, order.
  change(deep("open-" + collection), "influenza");
  await settle(() => section("series-collection").options.default_topic === "influenza",
               "expanded disease saved");
  change(deep("style-" + collection), "compact");
  await settle(() => section("series-collection").options.style === "compact",
               "chart height saved");
  check("chart height applies under Advanced display options",
        section("series-collection").options.style === "compact");
  rowFor(list, collection).querySelector("#years-start-" + collection).value = "2022";
  rowFor(list, collection).querySelector("#years-end-" + collection).value = "2024";
  click(deep("years-apply-" + collection));
  await settle(() => same(section("series-collection").options.years, [2022, 2024]),
               "display window saved");
  check("display window is kept as a display option",
        same(section("series-collection").options.years, [2022, 2024]));
  click(deep("up-" + collection));
  await settle(() => app.state.doc.blocks.findIndex((b) => b.instance_id === collection) === 2,
               "reordered");
  check("ordering moves the section without changing its instance id",
        app.state.doc.blocks[2].instance_id === collection);

  // 4. Exclude and restore keeps the settings and the id.
  toggle(deep("include-" + collection), false);
  await settle(() => section("series-collection").included === false, "excluded");
  check("include checkbox excludes without deleting",
        section("series-collection").included === false
        && app.state.doc.blocks.some((b) => b.instance_id === collection));
  check("an excluded section keeps its disease subset and display options",
        same(section("series-collection").options.topics,
             ["campylobacteriosis", "influenza"])
        && section("series-collection").options.style === "compact");
  toggle(deep("include-" + collection), true);
  await settle(() => section("series-collection").included === true, "restored");
  check("restoring keeps the same instance id and settings",
        deep("pick-" + collection + "-influenza").checked
        && section("series-collection").instance_id === collection);

  // 5. Reference comparison through its absent-type row.
  toggle(deep("add-reference-comparison"), true);
  await settle(() => Boolean(deep("topic-" + reference)), "reference added");
  check("reference row explains that the saved result changes identity",
        list.textContent.includes("checked instance identity change"));
  change(deep("topic-" + reference), fixture.reference_target);
  await settle(() => section("reference-comparison").options.topic === fixture.reference_target,
               "reference topic saved");
  check("choosing another saved result keeps the instance id",
        section("reference-comparison").instance_id === reference);

  // 6. Duplicate and Delete duplicate, then the delete control disappears.
  toggle(deep("add-monitoring-overview"), true);
  await settle(() => Boolean(deep("dup-" + monitoring)), "monitoring added");
  check("a repeatable type offers Duplicate", Boolean(deep("dup-" + monitoring)));
  check("Delete duplicate is hidden while a type has one instance",
        !deep("delete-" + monitoring));
  click(deep("dup-" + monitoring));
  await settle(() => Boolean(deep("delete-" + duplicate)), "duplicate created");
  check("both instances show Delete duplicate once the type repeats",
        Boolean(deep("delete-" + monitoring)) && Boolean(deep("delete-" + duplicate)));
  const copyRow = rowFor(list, duplicate);
  click(deep("delete-" + duplicate));
  await settle(() => Boolean(copyRow.querySelector(".inline-confirm"))
               && copyRow.querySelector(".inline-confirm").children.length > 0,
               "delete confirmation");
  click(copyRow.querySelector(".inline-confirm").querySelectorAll("button")[0]);
  await settle(() => !app.state.doc.blocks.some((b) => b.instance_id === duplicate),
               "duplicate deleted");
  check("Delete duplicate removes exactly the selected instance",
        app.state.doc.blocks.filter((b) => b.block === "monitoring-overview").length === 1
        && app.state.doc.blocks.some((b) => b.instance_id === monitoring)
        && !app.state.doc.blocks.some((b) => b.instance_id === duplicate));
  check("the delete control disappears when one instance remains",
        !deep("delete-" + monitoring));
  check("the deleted id is retired, not reissued",
        app.state.doc.excluded.includes(duplicate) === false);

  check("no request was unexpected or mismatched", problems.length === 0,
        problems.join(" | "));

  console.log("SUMMARY " + JSON.stringify({ checks: results.length, failures }));
  if (failures) {
    console.log("FAILED " + JSON.stringify(results.filter((item) => !item.ok), null, 2));
    process.exit(1);
  }
}

main().catch((error) => {
  console.error("HARNESS ERROR " + (error && error.stack ? error.stack : error));
  process.exit(1);
});
